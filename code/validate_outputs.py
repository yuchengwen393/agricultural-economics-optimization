"""用途：交付前独立验收，不调用主程序的模拟器或矩阵构造函数。
生成逻辑：从保存事件/CSV/NPZ分别重算覆盖、成本、资源约束与天气评价，并核查文件元数据/来源。
"""
from pathlib import Path
import json,math,time,re,hashlib,py_compile
import numpy as np,pandas as pd
from scipy.sparse import load_npz,vstack,csr_matrix
from scipy.optimize import milp,Bounds,LinearConstraint
from PIL import Image
import assemble_report as a
B=a.B;D=a.D;R=a.R;V=B/'07_验收核对';V.mkdir(exist_ok=True)
C=a.js(B/'config.json');U=pd.read_csv(D/'研究服务单元.csv');S=a.js(R/'主方案.json');P=a.js(R/'候选路线池.json')['plans'];E=B/'03_模型与方法/主模型导出';checks=[]
def check(name,condition,detail=''):
    checks.append({'check':name,'passed':bool(condition),'detail':str(detail)})
W=pd.read_csv(D/'建平_逐小时窗口.csv');ids=[];area=0.;cost=0.;energy=0.;flights=0
for p in S['plans']:
    team=p['team'];events=p['events'];ff=sorted((x for x in events if x['type']=='flight'),key=lambda x:x['start']);tt=[x for x in events if x['type']=='travel'];ch=[x for x in events if x['type']=='charge'];water=C['vehicle_liquid_capacity_L'];ids.extend(map(int,p['completed']));area+=p['area'];cost+=p['cost'];energy+=sum(x['energy_kwh'] for x in ff);flights+=len(ff)
    weather=np.repeat(W[W.date==p['date']].sort_values('hour').eligible.to_numpy(dtype=bool),60)[360:1080]
    check(team+'班次结束',p['finish']<=720+1e-6)
    check(team+'飞行窗口',all(weather[math.floor(f['start']):math.ceil(f['end'])].all() for f in ff))
    check(team+'车机同步',not any(t['start']<f['end']-1e-7 and t['end']>f['start']+1e-7 for t in tt for f in ff))
    access=True
    for f in ff:
        before=[x for x in tt if x['end']<=f['start']+1e-7]
        access &= bool(before) and max(before,key=lambda x:x['end'])['to']==f['vehicle_location']==f['unit']+1
    check(team+'起降位置',access)
    inventory=True
    for e in events:
        if e['type']=='refill':water=C['vehicle_liquid_capacity_L']
        if e['type']=='flight':
            water-=e['liquid_L'];inventory &= water>=-1e-6 and abs(water-e['water_after_L'])<1e-6 and e['liquid_L']<=C['drone_tank_L']+1e-6
    check(team+'药液台账',inventory)
    check(team+'架次能量',all(f['energy_kwh']+C['energy_reserve_kwh']<=C['battery_nominal_kwh']*C['battery_usable_fraction']+1e-6 for f in ff))
    charge_ok=True
    for j in range(C['charger_count_per_team']):
        q=sorted((x for x in ch if x['charger']==j),key=lambda x:x['start']);charge_ok &= all(y['start']>=x['end']-1e-7 for x,y in zip(q,q[1:]))
        charge_ok &= all(abs(x['end']-x['start']-C['charge_min'])<1e-6 and x['start']>=x['return_at']+C['cooling_min']-1e-7 for x in q)
    check(team+'充电器与冷却',charge_ok)
    reuse=True
    for j in range(C['batteries_per_team']):
        q=[x for x in ff if x['battery']==j]
        for x,y in zip(q,q[1:]):
            cc=[v for v in ch if v['battery']==j and abs(v['return_at']-x['end'])<1e-7]
            reuse &= len(cc)==1 and y['start']>=cc[0]['end']-1e-7
    check(team+'电池独立复用',reuse)
    drone_ok=True
    for j in range(C['drones_per_team']):
        q=[x for x in ff if x['drone']==j];drone_ok &= all(y['start']>=x['end']+C['turnaround_min_per_sortie']-1e-7 for x,y in zip(q,q[1:]))
    check(team+'无人机周转互斥',drone_ok)
    check(team+'任务面积守恒',all(abs(sum(f['mu'] for f in ff if f['unit']==int(i))-U.area_mu.iloc[int(i)])<1e-6 for i in p['completed']))
    flown=sum(f['mu'] for f in ff);arrival=C['external_arrival_min'] if team.startswith('EXT') else 0
    rc=C['owned_fixed_cost_yuan']+C['operating_cost_yuan_per_mu']*flown+C['vehicle_cost_yuan_per_travel_min']*sum(t['nominal_minutes'] for t in tt)+C['labor_cost_yuan_per_min']*(p['finish']-arrival)
    offer=C['external_mobilization_yuan']+C['external_reference_price_yuan_per_mu']*sum(U.area_mu.iloc[i] for i in p['route']);payment=max(offer,rc+C['external_opportunity_yuan']) if team.startswith('EXT') else rc
    check(team+'独立成本重算',abs(payment-p['cost'])<1e-5)
    if team.startswith('EXT'):check(team+'外援参与',payment-rc>=C['external_opportunity_yuan']-1e-6)
check('唯一覆盖',len(ids)==len(set(ids)))
check('主面积汇总',abs(sum(U.area_mu.iloc[i] for i in ids)-S['metrics']['served_area_mu'])<1e-6)
check('支出汇总与预算',abs(cost-S['metrics']['cost'])<1e-6 and cost<=C['budget_yuan'])
check('电量汇总',abs(energy-S['metrics']['energy_kwh'])<1e-6)
check('架次汇总',flights==S['metrics']['flights'])
for g in U.group.unique():
    rate=sum(U.area_mu.iloc[int(i)] for p in S['plans'] for i,t in p['completed'].items() if U.group.iloc[int(i)]==g and t<=C['recommended_deadline_min'])/U.loc[U.group==g,'area_mu'].sum()
    check('分组承诺_'+g,rate>=C['minimum_group_timely_rate']-1e-8 and abs(rate-S['metrics']['group_rates'][g])<1e-8)
mat=load_npz(E/'A_sparse.npz');vec=np.load(E/'vectors.npz');x=np.zeros(mat.shape[1]);lookup={(p['team'],tuple(p['route'])):j for j,p in enumerate(P)}
for p in S['plans']:x[lookup[(p['team'],tuple(p['route']))]]=1
for i in range(len(U)):x[len(P)+i]=i not in ids
vx=mat@x;violation=max(float(np.maximum(vec['lower']-vx,0).max()),float(np.maximum(vx-vec['upper'],0).max()))
check('保存方案满足独立矩阵',violation<=1e-5,violation)
check('保存方案目标与独立矩阵',abs(vec['objective']@x+vec['loss_offset']-S['metrics']['risk_proxy_loss_mu'])<1e-5)
# 独立精确容差二级成本复核，不改变已有主方案。
sec_mat=vstack([mat,csr_matrix(vec['objective'].reshape(1,-1))]);sec_hi=np.r_[vec['upper'],vec['objective']@x+1e-5];sec_lo=np.r_[vec['lower'],-np.inf];start=time.perf_counter()
res=milp(vec['cost'],integrality=vec['integrality'],bounds=Bounds(vec['lb'],vec['ub']),constraints=LinearConstraint(sec_mat,sec_lo,sec_hi),options={'time_limit':30,'mip_rel_gap':0})
secondary={'purpose':'独立二级成本最优性复核','generation_logic':'NPZ矩阵加固定主目标容差cut，mip_rel_gap=0','status':int(res.status),'mip_gap':float(res.mip_gap) if res.x is not None else None,'objective':float(res.fun) if res.x is not None else None,'reference_cost':S['metrics']['cost'],'seconds':time.perf_counter()-start}
check('独立二级成本一致',res.x is not None and abs(res.fun-S['metrics']['cost'])<.001,secondary)
a.write(V/'独立二级成本核对.json',json.dumps(secondary,ensure_ascii=False,indent=2))
for f in ['独立可行性验证.json','小实例穷举核对.json']:
    v=a.js(R/f);check(f,v.get('passed',v.get('loss_agrees',False)) and v.get('cost_agrees',True))
check('导出模型独立求解',a.js(E/'导出模型核对.json')['objective_agrees'])
df=pd.read_csv(R/'留出年份天气压力测试.csv');summary=pd.read_csv(R/'留出天气汇总.csv');nom=a.js(R/'运行环境.json')['nominal_date']
check('留出61日期且剔除代表日',all(g.date.nunique()==61 for _,g in df.groupby('policy')) and nom not in set(df.date))
check('三政策配对相同日期',len({tuple(sorted(g.date)) for _,g in df.groupby('policy')})==1)
for _,row in summary.iterrows():
    g=df[df.policy==row.policy];arr=g.risk_proxy_loss_mu.to_numpy();eta=np.quantile(arr,.9)
    check('留出汇总_'+row.policy,len(g)==row.n and abs(arr.mean()-row.mean_loss_mu)<1e-6 and abs(eta+np.maximum(arr-eta,0).mean()/.1-row.CVaR90_loss_mu)<1e-6)
check('地面喷雾未未经核验启用',not U.entry_verified.any() and not U.ground_compatible.any() and not U.confirmed_demand.any())
tm=np.load(D/'转场时间矩阵.npy');road=np.load(D/'已知道路时间矩阵.npy');check('矩阵形状与有限非负',tm.shape==(51,51) and np.isfinite(tm).all() and (tm>=0).all() and (tm+1e-8>=road).all() and np.diag(tm).max()==0)
fs=list((B/'05_论文图表').glob('*.png'));check('9图PNG/SVG',len(fs)==9 and len(list((B/'05_论文图表').glob('*.svg')))==9)
for p in fs:
    im=Image.open(p);check('图像说明_'+p.stem,'用途' in im.info.get('Description','') and im.width>1000)
for p in B.glob('*.py'):
    py_compile.compile(str(p),doraise=True)
check('源码语法',True,'全部根目录Python可编译')
for p in B.rglob('*.csv'):
    if '.venv' in p.parts:continue
    h=pd.read_csv(p,nrows=0).columns
    check('CSV用途逻辑_'+p.name,('purpose' in h and 'generation_logic' in h) or ('_purpose' in h and '_generation_logic' in h))
for p in B.rglob('*.json'):
    if '.venv' in p.parts:continue
    ob=a.js(p);check('JSON用途逻辑_'+p.name,isinstance(ob,dict) and 'purpose' in ob and 'generation_logic' in ob)
report=(B/'06_论文材料/完整论文分析与求解报告.md').read_text(encoding='utf-8');readme=(B/'README_成果总入口.md').read_text(encoding='utf-8')
for text in [report,readme]:
    for path in re.findall(r'\]\(<(D:/[^>]+)>\)',text):
        if path.endswith('成果验收.json'):continue
        check('链接存在_'+Path(path).name,Path(path).exists())
ledger=a.js(B/'01_数据审计/公开补充获取台账.json')['records']
for r in ledger:
    if r['status']!='failed':check('下载原件SHA_'+Path(r['file']).name,Path(r['file']).exists() and a.sha(Path(r['file']))==r['sha256'])
result={'purpose':'最终交付验收、数值一致性与独立约束核对','generation_logic':'validate_outputs.py读取保存产物独立核算；不共用主程序模拟/矩阵函数','passed':all(c['passed'] for c in checks),'checks_count':len(checks),'checks':checks,'limits':'仅模型内部与文件完整性核对；无入口/诊断/经营真值，不认证实地导航及真实利润','visual_qa':'全部9图由主代理查看，中文字/图例可读；甘特图图例移到图外避免遮挡，承诺支出图标识限时点与上下界；不自动等同现场可执行性'}
a.write(V/'成果验收.json',json.dumps(result,ensure_ascii=False,indent=2));a.csv(V/'验收检查明细.csv',pd.DataFrame(checks),'验收项逐条结果','保存事件/矩阵/统计表/来源校验独立核算')
print('QA passed:',result['passed'],'checks:',len(checks),'failed:',[c for c in checks if not c['passed']],flush=True)
a.manifest()
if not result['passed']:raise SystemExit(1)
