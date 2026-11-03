"""用途：半实证班组路线MILP、ALNS、预算鲁棒缓冲和情景评价。
生成逻辑：网格服务需求为研究设定；读取config及真实区域派生输入。单班组一车辆，同点起降，回收后转场。
MILP最优性限于候选路线池，ALNS仅给可行解；保留全部算法日志及验证字段。
"""
from pathlib import Path
from dataclasses import dataclass
import json,time,math,copy,itertools,platform,sys
import numpy as np,pandas as pd
from collections import OrderedDict
from scipy.optimize import milp,Bounds,LinearConstraint,linprog
from scipy.sparse import lil_matrix,csr_matrix,vstack
BASE=Path('D:/Desktop/code');D=BASE/'02_处理数据';R=BASE/'04_求解结果';R.mkdir(exist_ok=True)
C=json.loads((BASE/'config.json').read_text(encoding='utf-8'));U=pd.read_csv(D/'研究服务单元.csv');TM=np.load(D/'转场时间矩阵.npy');ROAD=np.load(D/'已知道路时间矩阵.npy');W=pd.read_csv(D/'建平_逐小时窗口.csv');rng=np.random.default_rng(C['seed']);N=len(U);A=U.area_mu.to_numpy()
WX={date:np.repeat(group.sort_values('hour').eligible.to_numpy(dtype=bool),60)[360:1080] for date,group in W.groupby('date')}
# 每天数据24小时，06:00为分钟0，18:00为720。历史天气用于离线设计，不称当时可得预报。
test_dates=sorted(k for k in WX if k.startswith('2025-08'))
nominal_date=min(test_dates,key=lambda k:(abs(WX[k].sum()-np.median([WX[d].sum() for d in test_dates])),k))
training_dates=[f'{y}-08-{day:02d}' for y,day in zip(C['weather_training_years'],[3,6,9,12,15,18,21,24,27])]
teams=[{'id':f'OWN{i+1}','external':False,'arrival':0} for i in range(C['num_owned_teams'])]+[{'id':f'EXT{i+1}','external':True,'arrival':C['external_arrival_min']} for i in range(C['num_external_teams'])]
def write(name,obj): (R/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda o:o.item() if isinstance(o,np.generic) else str(o)),encoding='utf-8')
def outcsv(name,rows,purpose,logic):
    df=pd.DataFrame(rows)
    if 'group_rates' in df:
        for g in U.group.unique():df['timely_rate_'+str(g)]=[x.get(g,np.nan) if isinstance(x,dict) else np.nan for x in df.group_rates]
        df=df.drop(columns=['group_rates'])
    df['purpose']=purpose;df['generation_logic']=logic;df.to_csv(R/name,index=False,encoding='utf-8-sig');return df
def protection(legs,gamma,fraction):
    vals=sorted((v*fraction for v in legs),reverse=True); k=min(int(gamma),len(vals));return sum(vals[:k])+(gamma-k)*vals[k] if k<len(vals) else sum(vals)
def schedule(route,team,date=nominal_date,gamma=0,cfg=None,tm=None,strict=True):
    c=C if cfg is None else cfg;tm=TM if tm is None else tm;weather=WX[date]
    t=float(team['arrival']);loc=0;water=c['vehicle_liquid_capacity_L'];battery=np.zeros(c['batteries_per_team']);chargers=np.zeros(c['charger_count_per_team']);legs=[];buf=0;events=[];completed={};travel=0.;energy=0.;flights=0;charge_wait=0.;weather_wait=0.;refills=0
    def move(dest):
        nonlocal t,loc,travel,buf
        leg=float(tm[loc,dest]);legs.append(leg);p=protection(legs,gamma,c['travel_deviation_fraction']);dur=leg+p-buf;start=t;t+=dur;travel+=leg;buf=p;events.append({'type':'travel','start':start,'end':t,'from':loc,'to':dest,'nominal_minutes':leg,'buffer_increment':dur-leg});loc=dest
    def window(at,duration):
        at=max(at,0.);start=int(math.ceil(at-1e-9));size=int(math.ceil(duration+1e-9))
        while start+size<=720:
            bad=np.flatnonzero(~weather[start:start+size])
            if len(bad)==0:return float(start)
            start+=int(bad[0])+1
        return None
    for i in route:
        i=int(i);move(i+1);prep=t;t+=c['preparation_min_per_unit'];events.append({'type':'prepare','unit':i,'start':prep,'end':t});remain=float(A[i]);local_ready=np.full(c['drones_per_team'],t);task_failed=False
        while remain>1e-8:
            flight_rate=c['flight_speed_ms']*c['spray_width_m']*3600/(2000/3)*c['field_efficiency_factor']
            max_energy_air=(c['battery_nominal_kwh']*c['battery_usable_fraction']-c['energy_reserve_kwh'])/c['air_power_kw_assumed']*60
            mu=min(remain,c['drone_tank_L']/c['liquid_L_per_mu'],flight_rate*min(c['max_sortie_air_min'],max_energy_air)/60)
            liquid=mu*c['liquid_L_per_mu'];air=mu/flight_rate*60
            if water+1e-8<liquid:
                t=max(t,float(local_ready.max()));move(0);start=t;t+=c['refill_depot_min'];water=c['vehicle_liquid_capacity_L'];refills+=1;events.append({'type':'refill','start':start,'end':t,'location':0});move(i+1);local_ready[:]=t
            dr=int(np.argmin(local_ready));bi=int(np.argmin(battery));earliest=max(float(local_ready[dr]),float(battery[bi]),t);start=window(earliest,air)
            if start is None or start+air+c['turnaround_min_per_sortie']+float(tm[i+1,0])>720:
                task_failed=True;break
            charge_wait+=max(0.,float(battery[bi])-max(t,float(local_ready[dr])));weather_wait+=start-earliest
            end=start+air;local_ready[dr]=end+c['turnaround_min_per_sortie'];water-=liquid;en=air/60*c['air_power_kw_assumed'];energy+=en;flights+=1
            events.append({'type':'flight','unit':i,'drone':dr,'battery':bi,'start':start,'end':end,'mu':mu,'water_after_L':water,'liquid_L':liquid,'energy_kwh':en,'battery_ready_before':float(battery[bi]),'vehicle_location':i+1})
            ch=int(np.argmin(chargers));charge_start=max(end+c['cooling_min'],float(chargers[ch]));charge_end=charge_start+c['charge_min'];chargers[ch]=charge_end;battery[bi]=charge_end
            events.append({'type':'charge','battery':bi,'charger':ch,'start':charge_start,'end':charge_end,'return_at':end,'location_at_return':i+1})
            remain-=mu
        t=max(t,float(local_ready.max()))
        if task_failed:
            # 未完成单元的喷施面积另行记录，不能计为覆盖。允许情景评价有中止，严格建列则拒绝。
            if strict:return None
            break
        completed[i]=t
    move(0)
    if t>720+1e-6 and strict:return None
    area=sum(A[i] for i in completed);on=sum(A[i] for i,v in completed.items() if v<=c['recommended_deadline_min']);loss=sum(A[i]*(1+max(0.,v-c['recommended_deadline_min'])/120) for i,v in completed.items())
    # benefit = 完成面积减去逾期代理惩罚；未服务以area进入主模型。不能将其称为货币农业损失。
    benefit=sum(A[i]*(1-min(.9,max(0.,v-c['recommended_deadline_min'])/120)) for i,v in completed.items())
    actual_flown=sum(ev.get('mu',0) for ev in events if ev['type']=='flight');resource_cost=(c['owned_fixed_cost_yuan']+c['operating_cost_yuan_per_mu']*actual_flown+c['vehicle_cost_yuan_per_travel_min']*travel+c['labor_cost_yuan_per_min']*(t-team['arrival'])) if route else 0
    offer=c['external_mobilization_yuan']+c['external_reference_price_yuan_per_mu']*sum(A[i] for i in route)
    cost=max(offer,resource_cost+c['external_opportunity_yuan']) if team['external'] and route else resource_cost
    return {'team':team['id'],'route':list(map(int,route)),'completed':completed,'area':float(area),'on_time_area':float(on),'benefit':float(benefit),'cost':float(cost),'resource_cost':float(resource_cost),'offer':float(offer) if route else 0,'external_profit':float(cost-resource_cost) if team['external'] and route else None,'finish':float(t),'travel':travel,'energy':energy,'flights':flights,'charge_wait':charge_wait,'weather_wait':weather_wait,'refills':refills,'events':events,'gamma':gamma,'date':date}

def total(plans):
    ids=[i for p in plans for i in p['completed']];assert len(ids)==len(set(ids));cost=sum(p['cost'] for p in plans);benefit=sum(p['benefit'] for p in plans);timely=sum(p['on_time_area'] for p in plans);groups={g:sum(A[i] for p in plans for i,v in p['completed'].items() if U.group.iloc[i]==g and v<=C['recommended_deadline_min'])/sum(A[U.group==g]) for g in U.group.unique()}
    return {'cost':cost,'risk_proxy_loss_mu':float(A.sum()-benefit),'served_area_mu':sum(p['area'] for p in plans),'timely_area_mu':timely,'timely_rate':float(timely/A.sum()),'worst_group_rate':float(min(groups.values())),'group_rates':groups,'travel_min':sum(p['travel'] for p in plans),'energy_kwh':sum(p['energy'] for p in plans),'refills':sum(p['refills'] for p in plans),'flights':sum(p['flights'] for p in plans)}

CACHE=OrderedDict()
def ev(route,j,gamma=0):
    key=(tuple(route),j,gamma)
    if key not in CACHE:
        CACHE[key]=schedule(route,teams[j],gamma=gamma)
        if len(CACHE)>20000:CACHE.popitem(last=False)
    return CACHE[key]
def greedy(order,gamma=0):
    routes=[[] for _ in teams];plans=[ev([],j,gamma) for j in range(len(teams))]
    for i in order:
        opts=[]
        for j in range(len(teams)):
            p=ev(routes[j]+[int(i)],j,gamma)
            if p:
                inc=p['cost']-plans[j]['cost'];val=(p['benefit']-plans[j]['benefit'])/(max(inc,1));opts.append((val,-p['finish'],j,p))
        if opts:
            _,_,j,p=max(opts,key=lambda z:z[:3]);routes[j]=p['route'];plans[j]=p
    return plans

POOL={}
def add(plans,origin):
    for p in plans:
        if p and p['route']:
            k=(p['team'],tuple(p['route']),p['gamma']);p['origin']=origin;POOL[k]=p

def alns(seed,gamma=0,iterations=None):
    rr=np.random.default_rng(seed);initial=greedy(np.argsort(TM[0,1:]+60/A),gamma);current=initial;best=current;trace=[];weights=np.ones(3);scores=np.zeros(3);counts=np.zeros(3)
    def score(ps):
        z=total(ps);return z['risk_proxy_loss_mu']*100+z['cost']+max(0,z['cost']-C['budget_yuan'])*100+max(0,C['minimum_group_timely_rate']-z['worst_group_rate'])*A.sum()*200
    bestval=score(best);curval=bestval;temp=max(10.,bestval*.03);iterations=C['alns_iterations'] if iterations is None else iterations
    add(current,'greedy_seed')
    for it in range(iterations):
        op=int(rr.choice(3,p=weights/weights.sum()));routes=[p['route'].copy() for p in current];served=[i for r in routes for i in r];k=max(2,min(7,len(served)//6));
        if op==0:removed=set(rr.choice(served,min(k,len(served)),replace=False).tolist()) if served else set()
        elif op==1:removed=set(sorted(served,key=lambda i:TM[0,i+1]/A[i],reverse=True)[:k])
        else:
            anchor=int(rr.integers(N));removed=set(sorted(served,key=lambda i:TM[anchor+1,i+1])[:k])
        routes=[[i for i in r if i not in removed] for r in routes];plans=[ev(r,j,gamma) for j,r in enumerate(routes)];unserved=set(range(N))-set(i for r in routes for i in r)
        # 修复按信息可得的面积/转场评分；插入所有位置，每次用资源可行模拟器。
        order=sorted(unserved,key=lambda i:(-A[i]/(10+TM[0,i+1]) if op!=2 else rr.random()))
        for i in order:
            options=[]
            for j,r in enumerate(routes):
                for pos in range(len(r)+1):
                    cand=r[:pos]+[i]+r[pos:];p=ev(cand,j,gamma)
                    if p:
                        gain=100*(p['benefit']-plans[j]['benefit'])-(p['cost']-plans[j]['cost']);options.append((gain,-p['finish'],j,p))
            if options:
                gain,_,j,p=max(options,key=lambda z:z[:3])
                if gain>0:routes[j]=p['route'];plans[j]=p
        val=score(plans);reward=0
        if val<bestval-1e-6:best=plans;bestval=val;reward=8
        if val<curval or rr.random()<math.exp(min(0.,(curval-val)/temp)):
            current=plans;curval=val;reward=max(reward,2)
        add(plans,'ALNS');scores[op]+=reward;counts[op]+=1;temp*=.985
        if (it+1)%20==0:
            weights=.8*weights+.2*np.divide(scores,np.maximum(counts,1));weights=np.maximum(weights,.15);scores[:]=0;counts[:]=0
        trace.append({'seed':seed,'iteration':it+1,'operator':['random_removal','worst_removal','related_removal'][op],'best_score':bestval,'current_score':curval,'temperature':temp,'cached_schedules':len(CACHE)})
    return best,trace

def master(pool,budget=12000,minrate=0.3,loss_bound=None,mode='loss',scenarios=None,cvar_weight=0.,timelimit=None):
    start=time.perf_counter();P=list(pool);nr=len(P);ns=0 if scenarios is None else len(scenarios);nv=nr+N+(1+ns if ns else 0)
    cover=np.zeros((N,nr));benefit=np.array([p['benefit'] for p in P]);cost=np.array([p['cost'] for p in P]);groups=list(U.group.unique());rows=[];lower=[];upper=[]
    for i in range(N):
        row={nr+i:1.}
        for j,p in enumerate(P):
            if i in p['completed']:row[j]=1.;cover[i,j]=1.
        rows.append(row);lower.append(1.);upper.append(1.)
    for t in teams:
        rows.append({j:1. for j,p in enumerate(P) if p['team']==t['id']});lower.append(0.);upper.append(1.)
    rows.append({j:cost[j] for j in range(nr)});lower.append(0.);upper.append(budget)
    for g in groups:
        coef={j:sum(A[i] for i,v in p['completed'].items() if U.group.iloc[i]==g and v<=C['recommended_deadline_min']) for j,p in enumerate(P)};rows.append(coef);lower.append(minrate*sum(A[U.group==g]));upper.append(np.inf)
    if loss_bound is not None:rows.append({j:-benefit[j] for j in range(nr)});lower.append(-np.inf);upper.append(loss_bound-A.sum())
    obj=np.zeros(nv);obj[:nr]=-benefit if mode=='loss' else cost
    sc_benefit=None
    if ns:
        sc_benefit=np.array([[schedule(p['route'],next(t for t in teams if t['id']==p['team']),date=d,gamma=p['gamma'],strict=False)['benefit'] for p in P] for d in scenarios])
        obj[:nr]=-sc_benefit.mean(axis=0)
        obj[nr+N]=cvar_weight
        obj[nr+N+1:]=cvar_weight/(.1*ns)
        for s in range(ns):
            row={j:-sc_benefit[s,j] for j in range(nr)};row[nr+N]=-1.;row[nr+N+1+s]=-1.;rows.append(row);lower.append(-np.inf);upper.append(-A.sum())
    mat=lil_matrix((len(rows),nv))
    for r,row in enumerate(rows):
        for j,v in row.items():mat[r,j]=v
    mat=mat.tocsr();lo=np.zeros(nv);hi=np.ones(nv);integ=np.ones(nv)
    if ns:hi[nr+N:]=np.inf;integ[nr+N:]=0
    opts={'time_limit':C['milp_time_limit_seconds'] if timelimit is None else timelimit,'mip_rel_gap':.001}
    res=milp(obj,integrality=integ,bounds=Bounds(lo,hi),constraints=LinearConstraint(mat,np.array(lower),np.array(upper)),options=opts)
    log={'variables':nv,'binary_variables':nr+N,'constraints':len(rows),'nonzeros':mat.nnz,'seconds':time.perf_counter()-start,'status':int(res.status),'message':res.message,'mip_gap':res.mip_gap if res.x is not None else None,'objective_bound':res.mip_dual_bound if res.x is not None else None,'objective':res.fun if res.x is not None else None,'pool_routes':nr,'budget':budget,'minimum_group_rate':minrate,'mode':mode,'scenarios':ns,'cvar_weight':cvar_weight,'optimality_scope':'当前候选路线池及代理输入','loss_offset_mu':float(A.sum())}
    if res.x is None:return None,log
    plans=[p for j,p in enumerate(P) if res.x[j]>.5];maxv=max(float(np.max(np.maximum(np.array(lower)-mat@res.x,0))),float(np.max(np.maximum(mat@res.x-np.array(upper),0))));log['maximum_constraint_violation']=maxv
    # 同池LP界，仅是受限主问题的界，不是完整道路/航线问题的全局界。
    lp=milp(obj,integrality=np.zeros(nv),bounds=Bounds(lo,hi),constraints=LinearConstraint(mat,np.array(lower),np.array(upper)),options={'time_limit':10});log['restricted_lp_objective']=lp.fun if lp.x is not None else None
    if scenarios is None:
        # 精确第二阶段：固定最佳损失阈值，再最小化支出，避免人为epsilon系数扭曲主目标。
        if mode=='loss' and res.status==0:
            cut=lil_matrix((1,nv));cut[0,:nr]=-benefit;mat2=vstack([mat,cut.tocsr()]);sec=np.zeros(nv);sec[:nr]=cost
            res2=milp(sec,integrality=integ,bounds=Bounds(lo,hi),constraints=LinearConstraint(mat2,np.r_[lower,-np.inf],np.r_[upper,res.fun+1e-5]),options=opts)
            log['secondary_status']=int(res2.status);log['seconds']=time.perf_counter()-start
            if res2.x is not None:plans=[p for j,p in enumerate(P) if res2.x[j]>.5];log['secondary_cost']=float(res2.fun)
    return plans,log

def validate(plans):
    issues=[];ids=[];batteries=[];chargers=[]
    for p in plans:
        if p['finish']>720+1e-6:issues.append('shift_end '+p['team'])
        ids+=list(p['completed'])
        team=next(t for t in teams if t['id']==p['team']);re=schedule(p['route'],team,p['date'],p['gamma']);
        if re is None:issues.append('route_replay '+p['team']);continue
        if abs(re['cost']-p['cost'])>1e-4:issues.append('cost_replay '+p['team'])
        flights=[x for x in p['events'] if x['type']=='flight'];charges=[x for x in p['events'] if x['type']=='charge'];weather=WX[p['date']]
        for f in flights:
            if not weather[int(math.floor(f['start'])):int(math.ceil(f['end']))].all():issues.append('weather '+p['team'])
            if f['start']+1e-8<f['battery_ready_before']:issues.append('battery '+p['team'])
            if f['water_after_L']< -1e-6 or f['liquid_L']>C['drone_tank_L']+1e-6:issues.append('liquid '+p['team'])
            if f['energy_kwh']+C['energy_reserve_kwh']>C['battery_nominal_kwh']*C['battery_usable_fraction']+1e-6:issues.append('energy '+p['team'])
        for ch in range(C['charger_count_per_team']):
            q=sorted([v for v in charges if v['charger']==ch],key=lambda v:v['start'])
            if any(b['start']<a['end']-1e-6 for a,b in zip(q,q[1:])):issues.append('charger_overlap '+p['team'])
        for dr in range(C['drones_per_team']):
            q=sorted([v for v in flights if v['drone']==dr],key=lambda v:v['start'])
            if any(b['start']<a['end']-1e-6 for a,b in zip(q,q[1:])):issues.append('drone_overlap '+p['team'])
        travel=[v for v in p['events'] if v['type']=='travel'];
        if any(v['start']<f['end']-1e-6 and v['end']>f['start']+1e-6 for v in travel for f in flights):issues.append('vehicle_flight_sync '+p['team'])
        if team['external'] and p['external_profit']+1e-5<C['external_opportunity_yuan']:issues.append('participation '+p['team'])
    if len(ids)!=len(set(ids)):issues.append('duplicate_coverage')
    z=total(plans)
    if z['cost']>C['budget_yuan']+1e-5:issues.append('budget')
    if z['worst_group_rate']<C['minimum_group_timely_rate']-1e-5:issues.append('fairness')
    return {'purpose':'独立事件检查和资源可行重放','generation_logic':'检查天气、库存下界、能量、飞行/车动不重叠、充电并发、唯一覆盖、预算和合同参与','passed':not issues,'issues':issues,'metrics':z}

def held_karp(indices):
    # 固定小集合的有向转场TSP；只优化距离/时间顺序，完整资源可行性随后重新模拟。
    ids=list(indices);dp={};parent={};n=len(ids)
    for j in range(n):dp[(1<<j,j)]=TM[0,ids[j]+1]
    for mask in range(1,1<<n):
        for j in range(n):
            if (mask,j) not in dp:continue
            for k in range(n):
                if mask>>k&1:continue
                nm=mask|(1<<k);v=dp[(mask,j)]+TM[ids[j]+1,ids[k]+1]
                if v<dp.get((nm,k),np.inf):dp[(nm,k)]=v;parent[(nm,k)]=j
    mask=(1<<n)-1;last=min(range(n),key=lambda j:dp[(mask,j)]+TM[ids[j]+1,0]);value=dp[(mask,last)]+TM[ids[last]+1,0];route=[]
    while mask:
        route.append(ids[last]);p=parent.get((mask,last));mask^=1<<last;last=p
    return route[::-1],value,len(dp)

def run():
    print('nominal date',nominal_date,'eligible minutes',WX[nominal_date].sum(),flush=True)
    alogs=[];baseline=[]
    for name,order in [('nearest',np.argsort(TM[0,1:])),('largest_first',np.argsort(-A)),('benefit_density',np.argsort(TM[0,1:]+60/A))]:
        ps=greedy(order);add(ps,name);baseline.append({'algorithm':name,**total(ps)})
    # 单任务种子保证难单元具备列；再生成随机重排的贪心路线。
    for j in range(len(teams)):
        for i in range(N):add([ev([i],j)],'singleton')
    for k in range(45):add(greedy(rng.permutation(N)),'randomized_greedy')
    for seed in [C['seed'],C['seed']+1,C['seed']+2]:
        start=time.perf_counter();ps,trace=alns(seed);alogs+=trace;baseline.append({'algorithm':'ALNS','seed':seed,'seconds':time.perf_counter()-start,**total(ps)});print('ALNS',seed,len(POOL),total(ps)['risk_proxy_loss_mu'],flush=True)
    nominal_pool=list(POOL.values());ps,log=master(nominal_pool,budget=C['budget_yuan'],minrate=C['minimum_group_timely_rate']);
    if ps is None:raise RuntimeError('main master infeasible '+str(log))
    baseps=ps;write('主方案.json',{'purpose':'班组任务包选择与完整执行事件','generation_logic':'ALNS/贪心生成路线池，MILP按损失优先并次级成本最小化','evidence_boundary':'网格需求、设备数量、道路接入和报价为场景条件；无真实经营验证','plans':ps,'metrics':total(ps),'solver':log});write('独立可行性验证.json',validate(ps));baseline.append({'algorithm':'ALNS_pool_MILP',**total(ps),**log})
    write('主模型求解日志.json',log)
    write('候选路线池.json',{'purpose':'精确复现MILP及补充实验的全部可执行候选列','generation_logic':'保留1040条贪心/ALNS路线，内部事件已生成','plans':nominal_pool})
    # 实际使用动态规划改进固定小路线集合，并重新验证资源可行性。
    dp_rows=[]
    for p in baseps:
        if len(p['route'])<=10:
            start=time.perf_counter();rr,value,states=held_karp(p['route']);team=next(t for t in teams if t['id']==p['team']);new=schedule(rr,team);dp_rows.append({'team':p['team'],'n':len(rr),'states':states,'seconds':time.perf_counter()-start,'tsp_minutes':value,'original_travel_minutes':p['travel'],'resource_feasible':new is not None});add([new],'DP_reordered')
    outcsv('动态规划子路线实验.csv',dp_rows,'DP顺序改进与约束复核','固定集合Held-Karp有向TSP，随后完整资源模拟')
    # 多目标支出-未及时面积，以budget作为epsilon；服务公平标准为合同场景。
    sens=[];solverlogs=[];frontplans={}
    for budget in [3000,4500,6000,7500,9000,12000,15000,20000]:
        for fair in [0.,.3,.5]:
            p,l=master(nominal_pool,budget=budget,minrate=fair,timelimit=15);row={'budget':budget,'fairness_floor':fair,'status':l['status'],'seconds':l['seconds']}
            if p:row.update(total(p));frontplans[f'{budget}_{fair}']={'metrics':total(p),'routes':[(z['team'],z['route']) for z in p]}
            sens.append(row);solverlogs.append(l)
    outcsv('预算与公平灵敏度.csv',sens,'预算epsilon约束及公平代价','同一候选池、同一研究需求，不可行档位显式status=2');write('灵敏度求解日志.json',solverlogs);write('多目标代表方案.json',frontplans)
    # 鲁棒路线池：原路线经预算偏差缓冲重建，追加独立robust ALNS。
    for gamma in [1,2,4]:
        pool=[]
        for p in nominal_pool:
            j=next(j for j,t in enumerate(teams) if t['id']==p['team']);q=ev(p['route'],j,gamma)
            if q:pool.append(q)
        if gamma==2:
            rps,tr=alns(C['seed']+10,gamma=gamma,iterations=80);alogs+=tr;pool.extend(p for p in POOL.values() if p['gamma']==gamma)
        p,l=master(pool,budget=C['budget_yuan'],minrate=.3,timelimit=20)
        if p:
            baseline.append({'algorithm':f'robust_Gamma_{gamma}',**total(p),**l});write(f'鲁棒方案_Gamma{gamma}.json',{'purpose':'转场预算缓冲方案','generation_logic':'逐前缀取最大Gamma个转场偏差，资源模拟后MILP选列','plans':p,'metrics':total(p),'solver':l})
    # 训练情景只用2015-2023天气。按固定任务包评价，无第二阶段自由重排，属于单阶段SAA+CVaR。
    sp,sl=master(nominal_pool,budget=C['budget_yuan'],minrate=.3,scenarios=training_dates,cvar_weight=.25,timelimit=30)
    if sp:write('随机风险方案.json',{'purpose':'训练历史天气情景下期望+CVaR损失','generation_logic':'固定路线一次选择，按历史天气模拟完成；保留未完成不计覆盖','training_dates':training_dates,'plans':sp,'metrics':total(sp),'solver':sl});baseline.append({'algorithm':'SAA_CVaR',**total(sp),**sl})
    outcsv('算法对照.csv',baseline,'同输入算法差异和计算性能','启发式无最优性证明；MILP/LP界仅对候选池有效')
    outcsv('ALNS收敛轨迹.csv',alogs,'收敛、破坏算子和随机种子复现','每次邻域仅做资源模拟，不嵌套完整MILP')
    # 日期测试不提供预见式订单改变：固定已选任务包，对全部2024-2025八月天气重放。
    policies={'nominal':baseps}
    rp=R/'鲁棒方案_Gamma2.json'
    if rp.exists():policies['robust_gamma2']=json.loads(rp.read_text(encoding='utf-8'))['plans']
    if sp:policies['SAA_CVaR']=sp
    evals=[]
    for name,plans in policies.items():
        for date in sorted(d for d in WX if d[:4] in ['2024','2025'] and '-08-' in d and d!=nominal_date):
            qp=[schedule(p['route'],next(t for t in teams if t['id']==p['team']),date=date,gamma=p['gamma'],strict=False) for p in plans];z=total(qp);evals.append({'policy':name,'date':date,**z,'weather_eligible_minutes':int(WX[date].sum())})
    ed=outcsv('留出年份天气压力测试.csv',evals,'评估固定方案在未用于SAA拟合的天气中的表现','2024-2025八月剔除候选池代表日，共61日；不等于真实运营回测');summ=[]
    for name,g in ed.groupby('policy'):
        arr=g.risk_proxy_loss_mu.to_numpy();eta=float(np.quantile(arr,.9));cvar=eta+np.maximum(arr-eta,0).mean()/.1;summ.append({'policy':name,'n':len(g),'mean_loss_mu':float(arr.mean()),'CVaR90_loss_mu':float(cvar),'mean_timely_rate':float(g.timely_rate.mean()),'mean_worst_group_rate':float(g.worst_group_rate.mean())})
    outcsv('留出天气汇总.csv',summ,'期望与尾部损失','样本CVaR=eta+mean positive excess/(1-alpha)，alpha=.9')
    # 单独改变瓶颈资源，同一候选路线结构重模拟并重选；不推定数量真实存在。
    resource_rows=[]
    for par,values in [('batteries_per_team',[1,2,3,4]),('charge_min',[9,12,20,30]),('vehicle_liquid_capacity_L',[200,400,600,1000]),('drones_per_team',[1,2])]:
        for v in values:
            cfg=copy.deepcopy(C);cfg[par]=v;pp=[]
            for p in nominal_pool:
                q=schedule(p['route'],next(t for t in teams if t['id']==p['team']),cfg=cfg)
                if q:pp.append(q)
            p,l=master(pp,budget=C['budget_yuan'],minrate=.3,timelimit=10);row={'parameter':par,'value':v,'status':l['status'],'pool_routes':len(pp)}
            if p:row.update(total(p))
            resource_rows.append(row)
    outcsv('补给与无人机瓶颈灵敏度.csv',resource_rows,'资源边际收益对比','同一结构路线池重模拟；多无人机队共用一充电器，充电可随车进行为研究假设')
    # 通行数据价值：只考察最后接入时间的不确定；同真实需求做条件对照，不宣称最优VOI。
    gaps=np.r_[0,U.lastmile_gap_m.to_numpy()];last=(gaps[:,None]+gaps[None,:])/1000/6*60;info=[]
    for label,factor in [('optimistic_connection',.5),('base_connection',1.),('slow_connection',2.)]:
        actual_tm=ROAD+last*factor;np.fill_diagonal(actual_tm,0);pp=[]
        for p in nominal_pool:
            q=schedule(p['route'],next(t for t in teams if t['id']==p['team']),tm=actual_tm)
            if q:pp.append(q)
        p,l=master(pp,budget=C['budget_yuan'],minrate=.3,timelimit=15)
        blind=[schedule(q['route'],next(t for t in teams if t['id']==q['team']),tm=actual_tm,strict=False) for q in baseps]
        row={'information_condition':label,'connection_factor':factor,'status':l['status'],'blind_fixed_loss_mu':total(blind)['risk_proxy_loss_mu']}
        if p:row.update(total(p));row['conditional_reoptimization_gain_mu']=row['blind_fixed_loss_mu']-row['risk_proxy_loss_mu']
        info.append(row)
    outcsv('接入信息条件对照.csv',info,'展示接入误差如何影响排程','路线池固定；gain为条件重优化收益，不是精确事前VOI；观测成本未标定')
    # 规模预实验：已运行实例，不对Gurobi内存/首解作无证据推断。
    scale=[]
    for n in [5,10,20,50]:
        pp=[p for p in nominal_pool if max(p['route'])<n];p,l=master(pp,budget=C['budget_yuan'],minrate=0.,timelimit=10);scale.append({'tasks_with_columns':n,**l,'unserviceable_tasks':N-n})
    outcsv('求解规模预实验.csv',scale,'记录真实稀疏主模型规模和运行时','全需求保留未服务变量，只给前n任务列；报告该定义，不当完整n任务最优实例')
    outcsv('主方案任务完成表.csv',[{'team':p['team'],'unit_id':U.unit_id.iloc[i],'complete_min_after_0600':v,'clock_time':f'{6+int(v)//60:02d}:{int(v)%60:02d}','area_mu':float(A[i]),'on_time':v<=C['recommended_deadline_min'],'contract_payment_yuan':p['cost'],'group':U.group.iloc[i]} for p in baseps for i,v in p['completed'].items()],'论文甘特图与执行任务表','按所选路线完成时间提取；合同支付为整路线值，不能逐行求和')
    outcsv('主方案事件表.csv',[dict(team=p['team'],**e) for p in baseps for e in p['events']],'独立库存/飞行/充电/转场复核','逐事件输出，充电允许途中由车载设备持续工作')
    write('运行环境.json',{'purpose':'复现环境','generation_logic':'运行时版本及种子记录','python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'pandas':pd.__version__,'seed':C['seed'],'nominal_date':nominal_date,'training_dates':training_dates,'source_task_count':N,'source_area_mu':float(A.sum()),'pool_routes':len(nominal_pool),'cache_size':len(CACHE),'Gurobi_used':False,'solver':'SciPy milp / HiGHS'})
    print('DONE',total(baseps),'validation',validate(baseps)['passed'],flush=True)
if __name__=='__main__':run()
