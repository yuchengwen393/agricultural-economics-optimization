"""用途：生成论文可复用PNG/SVG图及图注。生成逻辑：只读取已经计算的表与方案，不改动求解结果。
PNG内嵌Description，SVG内嵌元数据；所有图强调服务网格和设计场景身份。
"""
from pathlib import Path
import json,math
import numpy as np,pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
B=Path('D:/Desktop/code');D=B/'02_处理数据';R=B/'04_求解结果';F=B/'05_论文图表';F.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':240})
U=pd.read_csv(D/'研究服务单元.csv');S=json.loads((R/'主方案.json').read_text(encoding='utf-8'));captions=[]
def save(fig,name,caption,logic):
    fig.tight_layout();desc='用途：'+caption+'；生成逻辑：'+logic+'；结果属性：半实证研究设计，不是实测经营效果。'
    fig.savefig(F/(name+'.png'),bbox_inches='tight',metadata={'Description':desc});fig.savefig(F/(name+'.svg'),bbox_inches='tight',metadata={'Description':desc,'Creator':'make_figures.py'});captions.append({'figure':name,'caption':caption,'purpose':caption,'generation_logic':logic});plt.close(fig)

nodes=pd.read_csv(D/'研究区OSM节点.csv');edges=pd.read_csv(D/'研究区OSM路段.csv');coords={int(z.osm_id):(z.lon,z.lat) for z in nodes.itertuples()};segs=[(coords[int(z.from_osm)],coords[int(z.to_osm)]) for z in edges.itertuples()]
fig,ax=plt.subplots(figsize=(9,7));ax.add_collection(LineCollection(segs,colors='#ccd3d8',linewidths=.5));served={int(i) for p in S['plans'] for i in p['completed']};col=['#278263' if i in served else '#bd5846' for i in range(len(U))];ax.scatter(U.lon,U.lat,c=col,s=U.area_mu*1.3,edgecolor='white',linewidth=.5,zorder=3);dep=json.loads((D/'研究区摘要.json').read_text(encoding='utf-8'))['depot'];ax.scatter([dep['lon']],[dep['lat']],marker='*',s=180,c='#202d45',zorder=5,label='路网锚点（非实测合作社）')
colors=['#195c85','#2f7c64','#ae6b28','#9367a5','#ca6c68']
for c,p in zip(colors,S['plans']):
    x=[dep['lon']]+U.iloc[p['route']].lon.tolist()+[dep['lon']];y=[dep['lat']]+U.iloc[p['route']].lat.tolist()+[dep['lat']];ax.plot(x,y,c=c,linewidth=1.05,alpha=.7,label=p['team']+'任务顺序')
ax.set_xlim(U.lon.min()-.015,U.lon.max()+.015);ax.set_ylim(U.lat.min()-.01,U.lat.max()+.01);ax.set_aspect(1/math.cos(math.radians(41.4)));ax.set_xlabel('经度（WGS84）');ax.set_ylabel('纬度（WGS84）');ax.set_title('建平研究服务单元与主方案任务顺序');ax.legend(loc='upper left',fontsize=8);ax.text(.01,.01,'绿：完整服务；红：未服务\n连线表示排序，不表示实际车辆导航路径',transform=ax.transAxes,fontsize=8,bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'});save(fig,'图1_空间与任务排序','50个300m服务单元的空间支持、OSM及路线顺序','从OSM节点/边和主方案绘图；地图锚点及需求为设计场景')

y=pd.read_csv(D/'县域天气窗口_年统计.csv');means=y.groupby('county').eligible_hours.mean().sort_values();fig,(ax,bx)=plt.subplots(1,2,figsize=(12,7),gridspec_kw={'width_ratios':[1.1,1]});ax.barh(means.index,means.values,color='#2c7791');ax.set_xlabel('7—8月年均可作业小时（2015—2025）');ax.set_title('县域历史窗口差异');d=pd.read_csv(D/'县域天气窗口_日统计.csv');jp=d[(d.county=='建平县') & d.date.str.contains('-08-')];bx.hist(jp.eligible_hours,bins=np.arange(-.5,11.5,1),color='#39947b',edgecolor='white');bx.set_xlabel('建平八月每日可作业小时');bx.set_ylabel('历史日数');bx.set_xticks(range(11));bx.set_title('日内窗口分布');save(fig,'图2_天气窗口','县域年均窗口与建平八月日窗口分布','ERA5风雨+ERA5-Land气温；风<=3.3m/s、无雨、温<32℃，避午研究设定')

a=pd.read_csv(R/'算法对照.csv');shown=a[a.algorithm.isin(['nearest','largest_first','benefit_density','ALNS_pool_MILP','robust_Gamma_2','SAA_CVaR'])].copy();fig,ax=plt.subplots(figsize=(9,4.5));names={'nearest':'最近优先*','largest_first':'面积优先','benefit_density':'效益密度','ALNS_pool_MILP':'ALNS–MILP','robust_Gamma_2':'鲁棒 Γ=2','SAA_CVaR':'SAA–CVaR'};ax.bar(shown.algorithm.map(names),shown.timely_rate*100,color=['#9baab2']*3+['#22796b','#a16d46','#627aa2']);ax.set_ylabel('及时服务面积比例（%）');ax.set_ylim(0,100);ax.tick_params(axis='x',rotation=15);ax.set_title('同一研究实例的算法对照');ax.axhline(75.144,color='#aaa',ls='--',lw=.7);ax.text(.02,.95,'* 最近优先未满足30%最差组下限',transform=ax.transAxes,va='top',fontsize=8);save(fig,'图3_算法对照','贪心规则、融合方法及风险模型的及时服务率','从算法对照表作图；nearest未满足30%最差组下限，作为原始业务规则而非可行基准')

b=pd.read_csv(R/'预算与公平灵敏度.csv');fig,(ax,bx)=plt.subplots(1,2,figsize=(11,4.5))
for f,g in b.groupby('fairness_floor'):
    g=g.dropna(subset=['cost']).sort_values('budget');ax.plot(g.cost,g.timely_rate*100,'o-',label=f'分组下限{f:.0%}');bx.plot(g.budget,g.worst_group_rate*100,'o-',label=f'分组下限{f:.0%}')
ax.set_xlabel('实际方案支出（元）');ax.set_ylabel('及时服务率（%）');ax.set_title('支出与及时服务的离散权衡');bx.set_xlabel('预算上限（元）');bx.set_ylabel('最差组及时服务率（%）');bx.set_title('公共服务承诺与预算');ax.legend(fontsize=8);bx.legend(fontsize=8);save(fig,'图4_预算公平权衡','预算epsilon扫描及公平约束效果','同候选池离散阈值，限时点不冒充证明最优，不可行档位不绘制')

t=pd.read_csv(R/'ALNS收敛轨迹.csv');fig,ax=plt.subplots(figsize=(8,4.5))
for seed,g in t.groupby('seed'):
    if len(g)>=180:ax.plot(g.iteration,g.best_score,label=str(seed))
ax.set_xlabel('ALNS迭代次数');ax.set_ylabel('搜索评价值（含成本/缺口罚项）');ax.set_title('三随机种子的ALNS收敛');ax.legend(title='随机种子',fontsize=8);save(fig,'图5_ALNS收敛','邻域搜索评价的收敛轨迹','评价值为算法搜索用标量，非农业货币损失')

fig,ax=plt.subplots(figsize=(11,4.5));ec={'travel':'#6a8dab','prepare':'#a9b1b7','flight':'#278263','refill':'#daaa55'}
for j,p in enumerate(S['plans']):
    for e in p['events']:
        if e['type'] in ec:ax.broken_barh([(e['start'],e['end']-e['start'])],(j-.28,.56),facecolors=ec[e['type']],edgecolor='white',linewidth=.3)
ax.set_yticks(range(len(S['plans'])),[p['team'] for p in S['plans']]);ax.set_xticks(np.arange(0,721,60),[f'{h:02d}:00' for h in range(6,19)]);ax.set_xlim(0,720);ax.set_xlabel('设计作业日时刻');ax.set_title('主方案车机同步甘特图（空白包含等候）')
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=ec[k],label=v) for k,v in [('travel','转场'),('prepare','准备'),('flight','植保架次'),('refill','锚点补水')]],loc='upper center',bbox_to_anchor=(.5,-.20),ncol=4,fontsize=8);save(fig,'图6_执行甘特图','完整事件计划的转场、准备、植保与补水','所选代表日天气只用于离线设计实验，未把充电与空闲期涂成作业')

z=pd.read_csv(R/'补给与无人机瓶颈灵敏度_增强列池.csv');fig,axes=plt.subplots(2,2,figsize=(10,7));labels={'batteries_per_team':'每班组电池数量','charge_min':'充电时长（分钟）','vehicle_liquid_capacity_L':'保障车液量（L）','drones_per_team':'每班组无人机数量'}
for ax,(par,g) in zip(axes.flat,z.groupby('parameter',sort=False)):
    g=g.sort_values('value');ax.plot(g.value,g.timely_rate*100,'o-',color='#2e8273');ax.set_xlabel(labels[par]);ax.set_ylabel('及时服务率（%）');ax.set_ylim(35,100);ax.set_title(labels[par]+'敏感性')
save(fig,'图7_资源瓶颈','增强候选路线池下的资源灵敏度','同结构原列+可行前缀+共同随机种子生成列；不把未生成方案当物理不可行')

e=pd.read_csv(R/'留出年份天气压力测试.csv');e=e[e.date!='2025-08-06'];fig,(ax,bx)=plt.subplots(1,2,figsize=(10,4.5));policies=list(e.policy.unique());ax.boxplot([e[e.policy==p].timely_rate*100 for p in policies],tick_labels=policies,patch_artist=True,boxprops={'facecolor':'#a1c4c2'});ax.set_ylabel('及时服务率（%）');ax.set_title('61个留出日期天气压力测试');s=pd.read_csv(R/'留出天气汇总.csv');x=np.arange(len(s));bx.bar(x-.18,s.mean_loss_mu,width=.36,label='平均');bx.bar(x+.18,s.CVaR90_loss_mu,width=.36,label='CVaR90');bx.set_xticks(x,s.policy,rotation=15);bx.set_ylabel('风险面积代理（亩）');bx.set_title('平均损失与尾部损失');bx.legend(fontsize=8);save(fig,'图8_天气风险','历史日期压力测试的服务分布和尾部风险','剔除生成池代表日，2015-2023训练、2024-2025其余八月评价；仍非真实运营回测')

f=pd.read_csv(R/'服务承诺最低预算.csv');fig,ax=plt.subplots(figsize=(8,4.5));ok=f.dropna(subset=['cost']);ax.plot(ok.minimum_timely_rate*100,ok.cost,'-',color='#3c6e91');ax.errorbar(ok.minimum_timely_rate*100,ok.cost,yerr=np.array([ok.cost-ok.cost_lower_bound_yuan,np.zeros(len(ok))]),fmt='none',capsize=5,color='#3c6e91',label='可行支出到求解下界');proved=ok[ok.status==0];limited=ok[ok.status==1];ax.scatter(proved.minimum_timely_rate*100,proved.cost,c='#3c6e91',label='达到0.1%求解容差');ax.scatter(limited.minimum_timely_rate*100,limited.cost,facecolors='white',edgecolors='#ad6c32',s=55,label='20秒限时可行解');ax.set_xlabel('两组最低及时服务率（%）');ax.set_ylabel('满足承诺的可行方案支出（元）');ax.set_title('服务承诺的支出与求解界');ax.legend(fontsize=8,loc='upper left');save(fig,'图9_服务承诺代价','用成本最小化表达公平成本的财政承担','增强候选池min cost；限时点是可行上界，最优界与gap见CSV；不可行仅限当前候选池')
pd.DataFrame(captions).to_csv(F/'图表用途与生成逻辑.csv',index=False,encoding='utf-8-sig');(F/'图注.md').write_text('# 论文图注\n\n用途：对应论文图片及其统计口径。生成逻辑：make_figures.py从CSV/JSON读取。所有图为研究场景，不是经营实测。PNG可直接插入文档，SVG可无损编辑。\n\n'+'\n\n'.join('## '+z['figure']+'\n\n'+z['caption']+'。生成逻辑：'+z['generation_logic']+'。' for z in captions),encoding='utf-8');print('figures',len(captions))
