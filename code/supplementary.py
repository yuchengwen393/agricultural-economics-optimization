"""用途：补充经济参与、公平强度、候选池截断、转场鲁棒性和小实例精确性检验。
生成逻辑：读取已保存候选列；对改变的资源条件加入可行前缀和45组重新生成的贪心列，避免只删列导致虚假瓶颈。
"""
import optimization as o
import numpy as np,pandas as pd,copy,json,time,itertools
P=json.loads((o.R/'候选路线池.json').read_text(encoding='utf-8'))['plans'];BASE=json.loads((o.R/'主方案.json').read_text(encoding='utf-8'))['plans']
# JSON对象键还原为整数。
for p in P+BASE:p['completed']={int(k):v for k,v in p['completed'].items()}
def make_pool(cfg=None,tm=None,regenerate=0):
    cfg=o.C if cfg is None else cfg;tm=o.TM if tm is None else tm;pool={}
    for p in P:
        t=next(t for t in o.teams if t['id']==p['team'])
        for length in range(1,len(p['route'])+1):
            r=p['route'][:length];q=o.schedule(r,t,cfg=cfg,tm=tm)
            if q:pool[(q['team'],tuple(r))]=q
    if regenerate:
        oldc=o.C;oldtm=o.TM;o.C=cfg;o.TM=tm;o.CACHE.clear();rr=np.random.default_rng(100)
        for i in range(regenerate):
            plans=o.greedy(rr.permutation(o.N))
            for p in plans:
                if p['route']:pool[(p['team'],tuple(p['route']))]=p
        o.C=oldc;o.TM=oldtm;o.CACHE.clear()
    return list(pool.values())

def run():
    df=pd.read_csv(o.R/'留出年份天气压力测试.csv');df=df[df.date!=o.nominal_date];df['generation_logic']='2024-2025八月剔除候选池代表日，共61日；不等于真实运营回测';df.to_csv(o.R/'留出年份天气压力测试.csv',index=False,encoding='utf-8-sig');summary=[]
    for name,g in df.groupby('policy'):
        arr=g.risk_proxy_loss_mu.to_numpy();eta=float(np.quantile(arr,.9));summary.append({'policy':name,'n':len(g),'mean_loss_mu':float(arr.mean()),'CVaR90_loss_mu':float(eta+np.maximum(arr-eta,0).mean()/.1),'mean_timely_rate':float(g.timely_rate.mean()),'mean_worst_group_rate':float(g.worst_group_rate.mean())})
    o.outcsv('留出天气汇总.csv',summary,'固定方案留出日期压力测试最终表','剔除代表日共61日，预见式环境压力测试，不是实时调度验证')
    rows=[]
    for param,values in [('batteries_per_team',[1,2,3,4]),('charge_min',[9,12,20,30]),('vehicle_liquid_capacity_L',[200,400,600,1000]),('drones_per_team',[1,2])]:
        for val in values:
            cfg=copy.deepcopy(o.C);cfg[param]=val;pool=make_pool(cfg,regenerate=45);p,l=o.master(pool,minrate=.3,timelimit=12);row={'parameter':param,'value':val,'status':l['status'],'pool_routes':len(pool),'mip_gap':l['mip_gap']}
            if p:row.update(o.total(p))
            rows.append(row);print(param,val,row.get('timely_rate'),flush=True)
    o.outcsv('补给与无人机瓶颈灵敏度_增强列池.csv',rows,'资源参数敏感性最终使用表','完整池+可行前缀+45组共同种子重生成贪心列；非完整全局最优')
    gaps=np.r_[0,o.U.lastmile_gap_m.to_numpy()];last=(gaps[:,None]+gaps[None,:])/1000/6*60;rows=[]
    for factor in [.5,1,2]:
        tm=o.ROAD+last*factor;np.fill_diagonal(tm,0);pool=make_pool(tm=tm,regenerate=45);blind=[o.schedule(p['route'],next(t for t in o.teams if t['id']==p['team']),tm=tm,strict=False) for p in BASE]
        p,l=o.master(pool,minrate=.3,timelimit=15);row={'connection_factor':factor,'status':l['status'],'pool_routes':len(pool),'blind_loss_mu':o.total(blind)['risk_proxy_loss_mu']}
        if p:row.update(o.total(p));row['conditional_gain_mu']=row['blind_loss_mu']-row['risk_proxy_loss_mu']
        rows.append(row)
    o.outcsv('接入信息条件对照_增强列池.csv',rows,'信息条件最终表','包含盲目方案可行前缀，避免删列造成负的伪信息收益；非事前VOI')
    rows=[];fairplans=[];fullpool=make_pool(regenerate=45)
    for rate in [0,.3,.5,.65,.7,.75,.8,.9]:
        p,l=o.master(fullpool,minrate=rate,mode='cost',timelimit=20);row={'minimum_timely_rate':rate,'status':l['status'],'mip_gap':l['mip_gap'],'seconds':l['seconds']}
        if p:row.update(o.total(p));fairplans.append({'rate':rate,'plans':p,'solver':l})
        rows.append(row)
    o.outcsv('服务承诺最低预算.csv',rows,'公平服务强度的最低支出及缺口','min cost满足两组及时率下限，12000预算；空服务rate0为合理成本0基准')
    o.write('服务承诺代表计划.json',{'purpose':'查验服务承诺预算的具体任务包','generation_logic':'增强候选池MILP成本最小化','plans':fairplans})
    rows=[]
    for label in ['owned_only','contract_participation','ideal_centralized']:
        pool=copy.deepcopy(fullpool)
        if label=='owned_only':pool=[p for p in pool if p['team'].startswith('OWN')]
        if label=='ideal_centralized':
            for p in pool:p['cost']=p['resource_cost']
        p,l=o.master(pool,minrate=.3,timelimit=15);row={'institution':label,'status':l['status'],'mip_gap':l['mip_gap']}
        if p:row.update(o.total(p))
        rows.append(row)
    o.outcsv('外援参与制度对照.csv',rows,'购买外援与理想集中调度的差异','同增强路线池；ideal只用履约资源成本，忽略机会收益，仅理论基准')
    # 两类政策同一旅行扰动分布，记录其对事前承诺的兑现率，而非仅比较不同计划的绝对面积。
    policies={'nominal':BASE};rp=json.loads((o.R/'鲁棒方案_Gamma2.json').read_text(encoding='utf-8'))['plans']
    for p in rp:p['completed']={int(k):v for k,v in p['completed'].items()}
    policies['robust_gamma2']=rp;rows=[]
    for seed in range(100):
        rr=np.random.default_rng(seed+900);noise=rr.random(o.TM.shape);np.fill_diagonal(noise,0)
        for label,plans in policies.items():
            actual=[]
            for p in plans:
                tm=o.TM.copy();route=p['route'];legs=list(zip([0]+[i+1 for i in route],[i+1 for i in route]+[0]));worst=sorted(legs,key=lambda ij:noise[ij],reverse=True)[:2]
                for a,b in worst:tm[a,b]*=1+.25*noise[a,b]
                q=o.schedule(route,next(t for t in o.teams if t['id']==p['team']),tm=tm,strict=False);actual.append(q)
            promised=sum(p['area'] for p in plans);z=o.total(actual);rows.append({'policy':label,'seed':seed,'promised_area_mu':promised,'fulfilled_promised_rate':z['served_area_mu']/promised,**z})
    df=o.outcsv('转场扰动配对压力测试.csv',rows,'Gamma保护对应的承诺兑现压力测试','共同随机矩阵，每条任务间路线至多2段偏差；补给插入弧不保证同一Gamma预算，说明限制')
    summary=df.groupby('policy').agg(n=('seed','size'),mean_fulfillment=('fulfilled_promised_rate','mean'),worst_fulfillment=('fulfilled_promised_rate','min'),mean_loss=('risk_proxy_loss_mu','mean')).reset_index();o.outcsv('转场扰动压力汇总.csv',summary.to_dict('records'),'比较不同承诺面积下的兑现可靠性','同100配对扰动样本；不能跨承诺面积只比较绝对损失')
    # 小实例：全部5任务排列与MILP选择核对，验证主问题索引与目标线性化。2支自有班组。
    oldN,oldU,oldA,oldTM,oldteams=o.N,o.U,o.A,o.TM,o.teams
    o.N=5;o.U=oldU.iloc[:5].copy();o.A=oldA[:5];o.TM=oldTM[:6,:6];o.teams=oldteams[:2];exact=[]
    for team in o.teams:
        for length in range(1,6):
            for route in itertools.permutations(range(5),length):
                p=o.schedule(route,team)
                if p:exact.append(p)
    p,l=o.master(exact,minrate=0,budget=12000,timelimit=20)
    # 固定两路线，穷举不交叠包对及单包，用同目标/次级成本检验。
    best=(float(o.A.sum()),0);count=0
    a=[p for p in exact if p['team']==o.teams[0]['id']];b=[p for p in exact if p['team']==o.teams[1]['id']]
    for p1 in [None]+a:
        for p2 in [None]+b:
            pp=[p for p in [p1,p2] if p];ids=[i for p in pp for i in p['completed']]
            if len(ids)!=len(set(ids)):continue
            z=o.total(pp);count+=1
            if z['cost']<=12000:best=min(best,(round(z['risk_proxy_loss_mu'],6),z['cost']))
    z=o.total(p);o.write('小实例穷举核对.json',{'purpose':'独立穷举验证MILP选择/词典序最优','generation_logic':'5单元2班组全部排列路线，遍历不交叠任务包对','routes':len(exact),'combinations_checked':count,'enumerated_loss':best[0],'enumerated_cost':best[1],'MILP_loss':z['risk_proxy_loss_mu'],'MILP_cost':z['cost'],'loss_agrees':abs(best[0]-z['risk_proxy_loss_mu'])<1e-5,'cost_agrees':abs(best[1]-z['cost'])<1e-4,'solver':l})
    o.N,o.U,o.A,o.TM,o.teams=oldN,oldU,oldA,oldTM,oldteams
    rows=[]
    for n in [5,10,20,50]:
        o.N=n;o.U=oldU.iloc[:n].copy();o.A=oldA[:n];o.TM=oldTM[:n+1,:n+1];pool=[p for p in fullpool if max(p['route'])<n];p,l=o.master(pool,minrate=0,timelimit=10);row={'tasks':n,**l}
        if p:row.update(o.total(p))
        rows.append(row)
    o.N,o.U,o.A,o.TM=oldN,oldU,oldA,oldTM;o.outcsv('真实子实例规模实验.csv',rows,'独立n任务子实例规模','真实截取前n单元及时间矩阵，完整未服务变量n；用增强池对应列')
    print('supplementary DONE',flush=True)
if __name__=='__main__':run()
