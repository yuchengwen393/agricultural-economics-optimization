"""用途：补充论文可视化，解释求解流程、执行进度、资源事件和天气配对差异。
生成逻辑：只读既有CSV/JSON，独立复算汇总，输出600dpi PNG、矢量SVG/PDF、
逐图绘图数据与来源哈希。绘图使用项目已配置Matplotlib环境，不重新求解模型。
"""
from pathlib import Path
import hashlib,json
import numpy as np,pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.patches import FancyBboxPatch,Patch
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import font_manager as fm
from PIL import Image

B=Path('D:/Desktop/code');R=B/'04_求解结果';O=B/'10_可视化增强论文/新增图表'
for x in ['PNG_600dpi','SVG_矢量','PDF_矢量','绘图数据','预览']:(O/x).mkdir(parents=True,exist_ok=True)
FONTS=['Arial','Microsoft YaHei'];COL=['#0072B2','#009E73','#D55E00','#CC79A7','#E69F00'];GRAY='#8A959E'
plt.rcParams.update({'font.family':FONTS,'font.weight':'bold','font.size':9,'axes.labelweight':'bold','axes.titleweight':'bold','axes.labelsize':9,'axes.titlesize':10,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'axes.unicode_minus':False,'axes.linewidth':1.2,'lines.linewidth':1.7,'grid.linewidth':.4,'grid.alpha':.25,'pdf.fonttype':42,'svg.fonttype':'path','savefig.facecolor':'white','figure.facecolor':'white'})
hashes={};checks=[];figures=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def src(p):hashes[str(p)]=sha(p);return p
def csv(p):return pd.read_csv(src(p))
def js(p):return json.loads(src(p).read_text(encoding='utf-8'))
def check(k,c,d=''):
    checks.append({'check':k,'passed':bool(c),'detail':str(d)})
    if not c:raise AssertionError(k+': '+str(d))
def out(no,tag,df,logic):
    q=df.copy();q['purpose']=f'新增Fig_{no} {tag}绘图数据';q['generation_logic']=logic
    q.to_csv(O/'绘图数据'/f'Fig_{no}_{tag}.csv',index=False,encoding='utf-8-sig')
def style(a,grid='y'):
    a.set_axisbelow(True)
    if grid:a.grid(axis=grid)
    for s in ['left','bottom']:a.spines[s].set_linewidth(1.2)
    for s in ['top','right']:a.spines[s].set_linewidth(.6);a.spines[s].set_color('#66747D')
def title(a,t):a.set_title(t,loc='left',pad=9)
def save(fig,no,name,caption,logic,note):
    stem=f'Fig_{no}_{name}'
    fig.text(.02,-.012,note,fontsize=7.5,ha='left',va='top',fontweight='bold')
    for t in fig.findobj(Text):t.set_fontfamily(FONTS);t.set_fontweight('bold')
    fig.canvas.draw();check(stem+'字体全部加粗',all(t.get_fontweight()=='bold' for t in fig.findobj(Text)))
    desc=f'用途：{caption}。生成逻辑：{logic}。{note}'
    png=O/'PNG_600dpi'/(stem+'.png');svg=O/'SVG_矢量'/(stem+'.svg');pdf=O/'PDF_矢量'/(stem+'.pdf')
    fig.savefig(png,dpi=600,bbox_inches='tight',pad_inches=.10,metadata={'Description':desc})
    fig.savefig(svg,bbox_inches='tight',pad_inches=.10,metadata={'Title':stem,'Description':desc})
    fig.savefig(pdf,bbox_inches='tight',pad_inches=.10,metadata={'Title':stem,'Subject':desc})
    book.savefig(fig,bbox_inches='tight',pad_inches=.10)
    with Image.open(png) as im:
        im.thumbnail((1500,1500));im.save(O/'预览'/(stem+'.png'))
    figures.append({'source_id':no,'name':name,'caption':caption,'generation_logic':logic,'note':note,'png':str(png),'svg':str(svg),'pdf':str(pdf)})
    plt.close(fig)

S=js(R/'主方案.json');M=S['metrics'];C=js(B/'config.json');LOG=js(R/'主模型求解日志.json')
TASK=csv(R/'主方案任务完成表.csv');EV=csv(R/'主方案事件表.csv');U=csv(B/'02_处理数据/研究服务单元.csv')
W=csv(R/'留出年份天气压力测试.csv');WS=csv(R/'留出天气汇总.csv');SC=csv(R/'真实子实例规模实验.csv')
TEAMS=['OWN1','OWN2','OWN3','EXT1','EXT2'];tc=dict(zip(TEAMS,COL))
check('50个唯一研究单元',len(U)==50 and U.unit_id.nunique()==50)
check('29个唯一完整任务',len(TASK)==29 and TASK.unit_id.nunique()==29)
check('完成面积与主结果一致',abs(TASK.area_mu.sum()-M['timely_area_mu'])<1e-7)
check('全部完整任务及时',TASK.on_time.all())
check('98架次与3次补水',sum(EV.type=='flight')==98 and sum(EV.type=='refill')==3)
check('药液消耗与面积一致',abs(EV.loc[EV.type=='flight','liquid_L'].sum()-2*TASK.area_mu.sum())<1e-7)
check('天气日期政策完整配对',W.groupby('policy').date.nunique().eq(61).all() and len(W)==183 and W.groupby(['policy','date']).size().eq(1).all())
P=W.pivot(index='date',columns='policy',values='risk_proxy_loss_mu').sort_index()
check('61共同日期无缺失',P.shape==(61,3) and not P.isna().any().any())
for policy in P:
    check('天气均值_'+policy,abs(P[policy].mean()-WS.set_index('policy').loc[policy,'mean_loss_mu'])<1e-7)

with PdfPages(O/'新增论文图集.pdf',metadata={'Title':'植保协同调度补充可视化图集','Subject':'用途：新增五幅论文图；生成逻辑：只读既有结果复算与绘制'}) as book:
    # Fig11: diagram describes implemented pipeline only.
    fig,ax=plt.subplots(figsize=(7.2,3.8));ax.set_xlim(0,10);ax.set_ylim(0,5.3);ax.axis('off')
    boxes=[(0.15,3.2,'数据与需求表示','50个支持单元\n天气、道路、设备假设'),(3.5,3.2,'资源事件模拟','架次、电池、药液\n逐事件检查可行性'),(6.85,3.2,'规则与ALNS探索','3种业务初解\n3个种子各180轮'),(6.85,.65,'受限MILP协调','1040候选包 + 50变量\n风险主目标与费用次目标'),(3.5,.65,'不确定性比较','转场保护 Γ\n天气SAA–CVaR'),(.15,.65,'独立检验与评价','小实例穷举\n61天气日、100组扰动')]
    flow=[]
    for k,(x,y,h,t) in enumerate(boxes,1):
        ax.add_patch(FancyBboxPatch((x,y),2.95,1.55,boxstyle='round,pad=.06',facecolor='#F4F7F8',edgecolor='#506672',linewidth=1.1))
        ax.text(x+1.475,y+1.17,h,ha='center',va='center',fontsize=10)
        ax.text(x+1.475,y+.53,t,ha='center',va='center',fontsize=8.6,linespacing=1.6)
        flow.append({'order':k,'stage':h,'content':t.replace('\n','；')})
    for a,b in [((3.12,3.95),(3.42,3.95)),((6.46,3.95),(6.76,3.95)),((8.32,3.1),(8.32,2.3)),((6.75,1.42),(6.47,1.42)),((3.42,1.42),(3.12,1.42))]:
        ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','lw':1.6,'color':'#314956'})
    out(11,'流程节点',pd.DataFrame(flow),'依据现有optimization.py、supplementary.py及论文模型顺序；不增加未实施算法')
    save(fig,11,'数据资源模拟与融合求解流程','数据输入、可行任务包搜索、整数规划与风险评价的关系','依据现有方法及运行配置绘制六阶段流程','箭头表示研究计算顺序；风险模型分别比较，不表示已实施现场滚动调度。')

    # Fig12: completed tasks, demand partition and cumulative whole-task area.
    fig=plt.figure(figsize=(7.2,5.5),layout='constrained');gs=fig.add_gridspec(2,2,height_ratios=[1,1.25]);a=fig.add_subplot(gs[0,0]);b=fig.add_subplot(gs[0,1]);d=fig.add_subplot(gs[1,:])
    ag=TASK.groupby('team').agg(area_mu=('area_mu','sum'),tasks=('unit_id','count')).reindex(TEAMS)
    bars=a.bar(TEAMS,ag.area_mu,color=COL,edgecolor='#263238',lw=.6)
    a.bar_label(bars,labels=[f'{x:.2f}' for x in ag.area_mu],padding=3,fontsize=8);a.set_ylim(0,420);a.set_ylabel('完整服务面积 (亩)');title(a,'(a) 五班组服务面积');style(a)
    total=float(U.area_mu.sum());vals=[float(ag.loc[TEAMS[:3],'area_mu'].sum()),float(ag.loc[TEAMS[3:],'area_mu'].sum()),total-float(TASK.area_mu.sum())]
    labs=['自有班组','外援班组','未完整服务'];bars=b.bar(labs,vals,color=[COL[0],COL[1],GRAY],edgecolor='#263238',lw=.6)
    b.bar_label(bars,labels=[f'{v:.2f}\n{v/total*100:.2f}%' for v in vals],padding=3,fontsize=8);b.set_ylim(0,1350);b.set_ylabel('需求面积 (亩)');title(b,'(b) 总需求的服务分解');style(b)
    tt=TASK.sort_values('complete_min_after_0600').copy();tt['cumulative_area_mu']=tt.area_mu.cumsum()
    for label,selection,color,ls in [('全部',tt,'#202B33','-'),('自有',tt[tt.team.str.startswith('OWN')],COL[0],'--'),('外援',tt[tt.team.str.startswith('EXT')],COL[1],':')]:
        times=np.r_[0,selection.complete_min_after_0600.to_numpy(),600];areas=np.r_[0,selection.area_mu.cumsum().to_numpy(),selection.area_mu.sum()]
        d.step(times,areas,where='post',label=label,color=color,ls=ls)
    d.set_xticks(np.arange(0,601,120),[f'{h:02d}:00' for h in range(6,17,2)]);d.set_xlim(0,600);d.set_ylim(0,1900);d.set_xlabel('完整任务完成时刻');d.set_ylabel('累计完整服务面积 (亩)');d.legend(loc='upper left',ncol=3);title(d,'(c) 完整任务累计进度');style(d)
    last=float(tt.complete_min_after_0600.max());clock=f'{6+int(last)//60:02d}:{int(last)%60:02d}'
    d.annotate(f'29项完成 {clock}\n{TASK.area_mu.sum():.2f}亩',xy=(last,TASK.area_mu.sum()),xytext=(440,1280),arrowprops={'arrowstyle':'->','color':'#314956'},fontsize=8)
    out(12,'班组面积',ag.reset_index(),'任务表按班组聚合唯一完整任务；不累计逐任务重复整包支付')
    out(12,'需求分解',pd.DataFrame({'category':labs,'area_mu':vals,'share':np.array(vals)/total}),'以全部50单元面积为分母；剩余为未完整服务面积')
    out(12,'完整任务累计',tt,'按完整完成时刻升序累计面积；部分喷施不计为完整服务')
    save(fig,12,'任务面积分解与累计服务进度','班组分工、需求服务状态与累计完整完成进度','唯一任务聚合，按完成时刻构造阶梯线','面积统计以完整任务为准；累计完成提前不代表后续天气、电池和返回条件允许新增任务。')

    # Fig13: all teams' inventory, charging queues and work volumes.
    fig=plt.figure(figsize=(7.2,5.4),layout='constrained');gs=fig.add_gridspec(2,2,height_ratios=[1.2,1]);a=fig.add_subplot(gs[0,:]);b=fig.add_subplot(gs[1,0]);d=fig.add_subplot(gs[1,1])
    inventory=[];queue=[]
    cool=float(C['cooling_min']);cap=float(C['vehicle_liquid_capacity_L'])
    for team in TEAMS:
        plan=next(p for p in S['plans'] if p['team']==team);events=EV[EV.team==team];fl=events[events.type=='flight'];ch=events[events.type=='charge'].copy()
        rows=[{'team':team,'minute':60. if team.startswith('EXT') else 0.,'inventory_L':cap,'event':'initial'}]
        for e in events.itertuples():
            if e.type=='flight':rows.append({'team':team,'minute':e.start,'inventory_L':e.water_after_L,'event':'flight_departure'})
            elif e.type=='refill':rows.append({'team':team,'minute':e.end,'inventory_L':cap,'event':'refill_complete'})
        rows.append({'team':team,'minute':plan['finish'],'inventory_L':rows[-1]['inventory_L'],'event':'return'})
        rows=sorted(rows,key=lambda z:z['minute']);inventory+=rows
        a.step([z['minute'] for z in rows],[z['inventory_L'] for z in rows],where='post',color=tc[team],label=team)
        ref=[z for z in rows if z['event']=='refill_complete']
        if ref:a.scatter([z['minute'] for z in ref],[cap]*len(ref),marker='^',s=45,color=tc[team],edgecolor='white',zorder=4)
        ch['queue_after_cooling_min']=(ch.start-ch.return_at-cool).clip(lower=0)
        check('充电器不并发_'+team,(ch.sort_values('start').start.to_numpy()[1:]+1e-7>=ch.sort_values('start').end.to_numpy()[:-1]).all())
        check('库存非负_'+team,fl.water_after_L.min()>=-1e-7)
        queue.append({'team':team,'flights':len(fl),'refills':sum(events.type=='refill'),'min_inventory_L':fl.water_after_L.min(),'total_charger_queue_min':ch.queue_after_cooling_min.sum(),'max_charger_queue_min':ch.queue_after_cooling_min.max(),'mean_charger_queue_min':ch.queue_after_cooling_min.mean(),'flight_air_min':(fl.end-fl.start).sum(),'charge_busy_min':(ch.end-ch.start).sum(),'flight_area_mu':fl.mu.sum()})
    a.set_xticks(np.arange(0,421,60),[f'{h:02d}:00' for h in range(6,14)]);a.set_xlim(0,420);a.set_ylim(0,680);a.set_ylabel('车载剩余药液 (L)');a.legend(loc='lower left',ncol=5,fontsize=7.7);title(a,'(a) 库存阶梯与补水完成事件');style(a)
    q=pd.DataFrame(queue).set_index('team').reindex(TEAMS);x=np.arange(5)
    z=b.bar(x-.18,q.mean_charger_queue_min,.36,label='平均',color=COL[0]);z2=b.bar(x+.18,q.max_charger_queue_min,.36,label='最大',color=COL[1]);b.bar_label(z,fmt='%.1f',fontsize=7,padding=2);b.bar_label(z2,fmt='%.1f',fontsize=7,padding=2);b.set_xticks(x,TEAMS);b.set_ylim(0,max(q.max_charger_queue_min)*1.32+1);b.set_ylabel('冷却后的充电排队 (min)');b.legend(ncol=2);title(b,'(b) 逐电池充电排队');style(b)
    bars=d.bar(TEAMS,q.flights,color=COL,edgecolor='#263238',lw=.6);d.bar_label(bars,labels=[f'{int(n)} / {int(r)}' for n,r in zip(q.flights,q.refills)],fontsize=8,padding=3);d.set_ylim(0,28);d.set_ylabel('飞行架次');title(d,'(c) 架次及补水次数');style(d)
    out(13,'药液库存事件',pd.DataFrame(inventory),'初始600L；每次起飞减liquid_L，补水完成恢复600L；按事件时间排序')
    out(13,'班组充电资源',q.reset_index(),'排队=max(0,charge.start-return_at-冷却2min)；均值以每次充电为样本，不等同无人机停机等待')
    save(fig,13,'全班组药液库存与充电排队','全班组库存变化、充电排队及架次补水分布','事件表提取库存、冷却后充电等待及飞行计数','三角标记为补水完成；柱顶为架次 / 补水次数；充电器排队可与其他电池飞行重叠。')

    # Fig14: paired dates, improvement counted with numeric tolerance; no inference test.
    delta=pd.DataFrame({'date':P.index,'SAA_gain_mu':P.nominal-P.SAA_CVaR,'robust_gain_mu':P.nominal-P.robust_gamma2}).set_index('date')
    fig=plt.figure(figsize=(7.2,5.3),layout='constrained');gs=fig.add_gridspec(2,2,height_ratios=[1,1.2]);a=fig.add_subplot(gs[0,0]);b=fig.add_subplot(gs[0,1]);d=fig.add_subplot(gs[1,:])
    labels=['SAA–CVaR','鲁棒Γ=2'];stats=[]
    for j,key in enumerate(['SAA_gain_mu','robust_gain_mu']):
        values=delta[key].to_numpy();counts=[int(sum(values>1e-6)),int(sum(abs(values)<=1e-6)),int(sum(values< -1e-6))];stats.append({'policy':labels[j],'better_days':counts[0],'same_days':counts[1],'worse_days':counts[2],'mean_gain_mu':values.mean(),'min_gain_mu':values.min(),'max_gain_mu':values.max()})
        left=0
        for k,(count,lab,color) in enumerate(zip(counts,['风险下降','相同','风险上升'],[COL[1],GRAY,COL[2]])):
            a.barh(j,count,left=left,color=color,label=lab if j==0 else None,edgecolor='white',height=.6)
            if count:a.text(left+count/2,j,str(count),ha='center',va='center',fontsize=8,color='white' if k!=1 else 'black')
            left+=count
        order=np.sort(values);b.plot(np.arange(1,62),order,color=[COL[1],COL[2]][j],label=labels[j])
    a.set_yticks([0,1],labels);a.set_xlim(0,61);a.set_xlabel('共同留出日期数');a.legend(loc='lower center',bbox_to_anchor=(.5,-.50),ncol=3,fontsize=7);title(a,'(a) 相对基准的日期胜负');style(a,'x')
    b.axhline(0,color='#263238',lw=.8,ls='--');b.set_xlabel('收益升序排列的日期序号');b.set_ylabel('基准风险 − 政策风险 (亩)');b.legend(fontsize=7.5);title(b,'(b) 配对风险差分布');style(b)
    heat=np.full((6,31),np.nan);widx=W.set_index(['policy','date']);rows=[]
    for year in [2024,2025]:
        for k,policy in enumerate(['nominal','SAA_CVaR','robust_gamma2']):
            row=(year-2024)*3+k;rows.append(f'{year} '+{'nominal':'基准','SAA_CVaR':'SAA','robust_gamma2':'鲁棒'}[policy])
            for day in range(1,32):
                date=f'{year}-08-{day:02d}'
                if (policy,date) in widx.index:heat[row,day-1]=float(widx.loc[(policy,date),'timely_rate'])*100
    cm=plt.get_cmap('Blues').copy();cm.set_bad('#DDDDDD');im=d.imshow(heat,cmap=cm,vmin=0,vmax=100,aspect='auto',interpolation='nearest');d.set_yticks(range(6),rows);d.set_xticks([0,5,10,15,20,25,30],[1,6,11,16,21,26,31]);d.axhline(2.5,color='white',lw=2);d.set_xlabel('八月日期');title(d,'(c) 共同日期的及时率日历');cb=fig.colorbar(im,ax=d,fraction=.022,pad=.025);cb.set_label('及时率 (%)');style(d,None)
    out(14,'天气配对风险差',delta.reset_index(),'同日期基准风险减政策风险，正值为风险代理下降；不进行显著性推断')
    out(14,'日期胜负统计',pd.DataFrame(stats),'61共同日期；以1e-6亩容差判断相同；样本计数不表示总体胜率')
    out(14,'天气及时率日历',W[['policy','date','timely_rate','weather_eligible_minutes']],'2024/2025八月；排除设计代表日2025-08-06，灰格为排除而非零及时率')
    save(fig,14,'天气政策配对差异与逐日及时率','共同天气日期中的政策风险差和逐日及时率','风险按日期严格配对，统一0–100%色标绘制61日历','正差为相对基准风险下降；灰格排除2025-08-06；排序位置不是同日期，配对先于排序。')

    # Fig15: restricted LP lower bound vs integer optimum and pool stability.
    lp=float(LOG['loss_offset_mu']+LOG['restricted_lp_objective']);ip=float(M['risk_proxy_loss_mu']);gap=ip-lp
    check('LP下界与整数解一致',abs(lp-532.2611164378773)<1e-7 and abs(gap-8.4251337988948)<1e-7)
    enhanced=SC[SC.tasks==50].iloc[0];check('增强池结果稳定',abs(enhanced.risk_proxy_loss_mu-ip)<1e-7)
    fig,(a,b)=plt.subplots(1,2,figsize=(7.2,3.25),layout='constrained')
    a.plot([lp,ip],[0,0],color='#506672',lw=2);a.scatter([lp,ip],[0,0],s=65,color=[COL[0],COL[2]],zorder=4)
    a.text(lp,.14,f'LP下界\n{lp:.6f}',ha='center',fontsize=8);a.text(ip,-.28,f'整数最优\n{ip:.6f}',ha='center',fontsize=8)
    a.annotate('',xy=(ip,.58),xytext=(lp,.58),arrowprops={'arrowstyle':'<->','color':'#314956'});a.text((lp+ip)/2,.68,f'差值 {gap:.6f}亩',ha='center',fontsize=8)
    a.set_xlim(lp-5,ip+5);a.set_ylim(-.6,.95);a.set_yticks([]);a.set_xlabel('当前1040路线池风险代理 (亩)');title(a,'(a) 松弛界与整数解');style(a,'x')
    pools=[int(LOG['pool_routes']),int(enhanced.pool_routes)];rates=[M['timely_rate']*100,float(enhanced.timely_rate)*100]
    b.plot(pools,rates,'o-',color=COL[1]);b.set_xlim(0,4300);b.set_ylim(0,100);b.set_xticks(pools,[str(v) for v in pools]);b.set_xlabel('候选路线数量');b.set_ylabel('及时率 (%)');title(b,'(b) 扩池后的主结果稳定性');style(b)
    for x,y in zip(pools,rates):b.annotate(f'{y:.2f}%',xy=(x,y),xytext=(0,10),textcoords='offset points',ha='center',fontsize=8)
    out(15,'受限最优性界',pd.DataFrame({'result':['restricted_LP','restricted_MILP'],'risk_proxy_mu':[lp,ip],'pool_routes':[1040,1040]}),'将求解器负收益目标加loss_offset_mu，还原风险代理；LP为同池整数问题下界')
    out(15,'扩池稳定性',pd.DataFrame({'pool_routes':pools,'timely_rate':np.array(rates)/100,'risk_proxy_mu':[ip,float(enhanced.risk_proxy_loss_mu)]}),'1040池主日志与3885池真实50任务子实例行；仅比较目标与服务率')
    save(fig,15,'候选路线池最优性界与扩池稳定性','同池LP下界、整数风险最优及扩池后的目标稳定性','还原风险目标并比较1040与3885候选池','左图为区间点图；零MIP间隙只证明池内整数最优，扩大路线池结果相同不证明池外最优。')

for p,h in hashes.items():check('来源未改写_'+Path(p).name,sha(Path(p))==h)
report={'purpose':'新增论文图表取数与字体核验','generation_logic':'只读来源、独立复算、绘图前后SHA256对照','passed':all(x['passed'] for x in checks),'checks':checks,'source_sha256':hashes,'figures':figures,'fonts':{f:fm.findfont(fm.FontProperties(family=f,weight='bold'),fallback_to_default=False) for f in FONTS},'visual_qa':'待检查图表与最终论文页面'}
(O/'新增图表核对.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
md=['# 新增图表用途与生成逻辑','', '用途：说明新增五幅图的取数和论文引用。生成逻辑：从plot_added_figures.py记录导出。','']
for z in figures:md+= [f"## 原图编号 {z['source_id']}　{z['name']}",'',z['caption']+'。', '', '生成逻辑：'+z['generation_logic']+'。','', '口径：'+z['note'],'']
(O/'图注与生成逻辑.md').write_text('\n'.join(md),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'figures':len(figures),'checks':len(checks),'latest_complete_min':float(TASK.complete_min_after_0600.max()),'weather_comparison':stats,'resource_summary':queue},ensure_ascii=False))
