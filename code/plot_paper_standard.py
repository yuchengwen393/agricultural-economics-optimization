"""用途：由已完成的最终研究结果生成统一加粗、多面板标准论文图。
生成逻辑：先独立复算并锁定源文件，再只读可视化；不重求解、不改原始/最终结果。
输出：600dpi PNG、路径化SVG、嵌入字体的PDF图集、逐图数据、图注、审计记录。
"""
from pathlib import Path
import json,math,hashlib,re,warnings
import numpy as np,pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.text import Text
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MaxNLocator,FuncFormatter
import rasterio
from pypdf import PdfReader
from PIL import Image

B=Path('D:/Desktop/code');D=B/'02_处理数据';R=B/'04_求解结果';O=B/'08_标准论文图'
for sub in ['PNG_600dpi','SVG_矢量','绘图数据','核对与预览']:(O/sub).mkdir(parents=True,exist_ok=True)
FAMILIES=['Arial','Microsoft YaHei'];COLORS=['#0072B2','#009E73','#D55E00','#CC79A7','#E69F00','#566573','#56B4E9'];BLUE,GREEN,RED,PURPLE,ORANGE,GRAY,SKY=COLORS
font_paths={family:fm.findfont(fm.FontProperties(family=family,weight='bold'),fallback_to_default=False) for family in FAMILIES}
plt.rcParams.update({'font.family':FAMILIES,'font.weight':'bold','font.size':9,'axes.labelweight':'bold','axes.titleweight':'bold','axes.labelsize':9,'axes.titlesize':10,'xtick.labelsize':8.2,'ytick.labelsize':8.2,'legend.fontsize':8,'legend.title_fontsize':8,'axes.unicode_minus':False,'axes.linewidth':1.25,'lines.linewidth':1.65,'lines.markersize':5,'patch.linewidth':.75,'grid.linewidth':.4,'grid.alpha':.25,'grid.color':'#AAB2B7','xtick.major.width':1.1,'ytick.major.width':1.1,'xtick.major.size':3.5,'ytick.major.size':3.5,'xtick.minor.width':.65,'ytick.minor.width':.65,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'path','savefig.facecolor':'white','figure.facecolor':'white','axes.facecolor':'white','figure.constrained_layout.w_pad':.07,'figure.constrained_layout.h_pad':.08})
checks=[];source_records={};captions=[];text_checks=[]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def source(p):
    source_records[str(p)]={'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size,'purpose':'本次绘图只读来源','generation_logic':'绘图前校验和锁定；最终再次验证未改写'};return p
def data(p):return pd.read_csv(source(p))
def js(p):return json.loads(source(p).read_text(encoding='utf-8'))
def check(name,cond,detail=''):
    checks.append({'check':name,'passed':bool(cond),'detail':str(detail)})
    if not cond:raise AssertionError(name+': '+str(detail))
def outdata(n,tag,df,logic):
    q=df.copy();q['purpose']=f'Fig_{n:02d} {tag}精确绘图数据';q['generation_logic']=logic
    q.to_csv(O/'绘图数据'/f'Fig_{n:02d}_{tag}.csv',index=False,encoding='utf-8-sig')
def figgrid(nrows,ncols,height=5.7,width=7.2,**kwargs):return plt.subplots(nrows,ncols,figsize=(width,height),layout='constrained',**kwargs)
def title(ax,s):ax.set_title(s,loc='left',pad=9)
def style(ax,grid='y'):
    ax.set_axisbelow(True)
    for s in ['left','bottom']:ax.spines[s].set_linewidth(1.25)
    for s in ['right','top']:ax.spines[s].set_linewidth(.6);ax.spines[s].set_color('#68757D')
    if grid:ax.grid(axis=grid)
    ax.tick_params(direction='out')
    # 仅重设自动数值刻度；不能覆盖县名、班组、电池等显式分类刻度。
    if isinstance(ax.yaxis.get_major_locator(),matplotlib.ticker.AutoLocator):ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
def percent(ax):ax.set_ylim(0,108);ax.set_yticks([0,20,40,60,80,100])
def numeric_bars(ax,values,labels,colors=None,fmt='{:.2f}',horizontal=False):
    x=np.arange(len(values));fn=ax.barh if horizontal else ax.bar
    bars=fn(x,values,color=colors or BLUE,edgecolor='#263238',linewidth=.6,height=.65) if horizontal else fn(x,values,color=colors or BLUE,edgecolor='#263238',linewidth=.6,width=.65)
    if horizontal:ax.set_yticks(x,labels);ax.invert_yaxis()
    else:ax.set_xticks(x,labels)
    ax.bar_label(bars,labels=[fmt.format(v) for v in values],padding=3,fontsize=7.6,fontweight='bold')
    return bars
def save(fig,n,name,caption,logic,notes=''):
    stem=f'Fig_{n:02d}_{name}'
    if notes:fig.text(.03,-.012,notes,fontsize=7.6,fontweight='bold',ha='left',va='top',linespacing=1.35)
    # 统一包括色条、科学计数偏移、图例、刻度及所有数值注释。
    fig.canvas.draw()
    texts=[t for t in fig.findobj(Text) if t.get_text()]
    for t in texts:t.set_fontweight('bold');t.set_fontfamily(FAMILIES)
    fig.canvas.draw()
    check(stem+'全部文字加粗',all(t.get_fontweight()=='bold' for t in texts),len(texts))
    desc='用途：'+caption+'；生成逻辑：'+logic+'；半实证研究设计，非真实订单运营效果。字体Arial Bold/Microsoft YaHei Bold。'
    fig.savefig(O/'PNG_600dpi'/(stem+'.png'),dpi=600,bbox_inches='tight',pad_inches=.09,metadata={'Description':desc})
    fig.savefig(O/'SVG_矢量'/(stem+'.svg'),bbox_inches='tight',pad_inches=.09,metadata={'Title':stem,'Description':desc,'Creator':'plot_paper_standard.py'})
    book.savefig(fig,bbox_inches='tight',pad_inches=.09)
    # 预览为不降采样最终文件的新渲染，不是交付PNG的替代。
    fig.savefig(O/'核对与预览'/(stem+'_预览.png'),dpi=150,bbox_inches='tight',pad_inches=.09,metadata={'Description':'用途：视觉检查；生成逻辑：同一最终Figure150dpi输出'})
    captions.append({'figure':stem,'panels':sum(a.get_label()!='<colorbar>' for a in fig.axes),'caption':caption,'notes':notes,'purpose':caption,'generation_logic':logic});text_checks.append({'figure':stem,'text_objects':len(texts),'all_bold':True,'families':FAMILIES});plt.close(fig);print('完成',stem,flush=True)

U=data(D/'研究服务单元.csv');S=js(R/'主方案.json');ENV=js(R/'运行环境.json');C=js(B/'config.json');REG=js(D/'研究区摘要.json');ALG=data(R/'算法对照.csv');WE=data(R/'留出年份天气压力测试.csv');WS=data(R/'留出天气汇总.csv');PT=data(R/'转场扰动配对压力测试.csv');PS=data(R/'转场扰动压力汇总.csv');BUD=data(R/'预算与公平灵敏度.csv');FAIR=data(R/'服务承诺最低预算.csv');RES=data(R/'补给与无人机瓶颈灵敏度_增强列池.csv');INFO=data(R/'接入信息条件对照_增强列池.csv');INST=data(R/'外援参与制度对照.csv');TRACE=data(R/'ALNS收敛轨迹.csv');SCALE=data(R/'真实子实例规模实验.csv');DP=data(R/'动态规划子路线实验.csv');YEAR=data(D/'县域天气窗口_年统计.csv');DAY=data(D/'县域天气窗口_日统计.csv');W=data(D/'建平_逐小时窗口.csv');CROSS=data(D/'气象交叉产品核对.csv');NODES=data(D/'研究区OSM节点.csv');EDGES=data(D/'研究区OSM路段.csv');TASKS=data(R/'主方案任务完成表.csv')
area=U.area_mu.sum();served={int(i) for p in S['plans'] for i in p['completed']};metrics=S['metrics'];on=sum(U.area_mu.iloc[int(i)] for p in S['plans'] for i,t in p['completed'].items() if t<=C['recommended_deadline_min'])
check('面积与JSON',abs(area-ENV['source_area_mu'])<1e-7)
check('主方案唯一覆盖',sum(len(p['completed']) for p in S['plans'])==len(served)==len(TASKS))
check('及时面积独立重算',abs(on-metrics['timely_area_mu'])<1e-7 and abs(on/area-metrics['timely_rate'])<1e-10)
check('主方案整包支付只计一次',abs(sum(p['cost'] for p in S['plans'])-metrics['cost'])<1e-7)
for g in U.group.unique():
    rate=sum(U.area_mu.iloc[int(i)] for p in S['plans'] for i,t in p['completed'].items() if U.group.iloc[int(i)]==g and t<=600)/U.loc[U.group==g,'area_mu'].sum();check('分组率_'+g,abs(rate-metrics['group_rates'][g])<1e-10)
check('算法主行与JSON',np.allclose(ALG.loc[ALG.algorithm=='ALNS_pool_MILP',['cost','timely_rate','risk_proxy_loss_mu']].to_numpy()[0],[metrics['cost'],metrics['timely_rate'],metrics['risk_proxy_loss_mu']],atol=1e-7))
for policy,g in WE.groupby('policy'):
    check('61日期_'+policy,len(g)==61 and g.date.nunique()==61 and ENV['nominal_date'] not in g.date.values)
    row=WS[WS.policy==policy].iloc[0];arr=g.risk_proxy_loss_mu.to_numpy();eta=np.quantile(arr,.9)
    check('天气均值CVaR_'+policy,abs(arr.mean()-row.mean_loss_mu)<1e-7 and abs(eta+np.maximum(arr-eta,0).mean()/.1-row.CVaR90_loss_mu)<1e-7 and abs(g.timely_rate.mean()-row.mean_timely_rate)<1e-10)
check('天气日期完全配对',len({tuple(sorted(g.date)) for _,g in WE.groupby('policy')})==1)
for policy,g in PT.groupby('policy'):
    row=PS[PS.policy==policy].iloc[0];check('100次兑现汇总_'+policy,len(g)==100 and g.seed.nunique()==100 and abs(g.fulfilled_promised_rate.mean()-row.mean_fulfillment)<1e-10 and abs(g.fulfilled_promised_rate.min()-row.worst_fulfillment)<1e-10)
check('扰动种子配对',len({tuple(sorted(g.seed)) for _,g in PT.groupby('policy')})==1)
dates=pd.to_datetime(DAY.date);yr=DAY.assign(year=dates.dt.year).groupby(['county','year']).eligible_hours.sum();yc=YEAR.set_index(['county','year']).eligible_hours
check('20县11年日年累计一致',len(yc)==220 and np.allclose(yc.sort_index(),yr.sort_index()))
jp=DAY[(DAY.county=='建平县') & (DAY.date.str[5:7]=='08')].copy();check('建平八月日数',len(jp)==341)
wh=W.groupby('date').eligible.sum();dj=DAY[DAY.county=='建平县'].set_index('date').eligible_hours;check('建平小时日窗口一致',np.allclose(wh.sort_index(),dj.sort_index()))
check('最终资源表已增强',RES.pool_routes.min()>0 and RES.status.isin([0,1]).all())
check('服务承诺成本上下界',FAIR.dropna(subset=['cost']).eval('cost_lower_bound_yuan <= cost_upper_bound_yuan + 0.00001').all())
check('规模为真实子实例',set(SCALE.tasks)=={5,10,20,50} and (SCALE.variables==SCALE.pool_routes+SCALE.tasks).all())
check('DP状态布尔',DP.resource_feasible.isin([True,False]).all())

with PdfPages(O/'论文图集_标准版.pdf',metadata={'Title':'辽宁玉米植保调度标准论文图集','Author':'研究绘图','Subject':'用途：论文多面板图集；生成逻辑：核对最终CSV/JSON后绘制，600dpi与矢量同步导出','Creator':'Python Matplotlib / plot_paper_standard.py'}) as book:
    # 01 空间：历史玉米支持与任务次序；连线不当作GPS。
    fig,allaxes=figgrid(2,2,height=6.6);ax=allaxes[0];coords={int(z.osm_id):(z.lon,z.lat) for z in NODES.itertuples()};segments=[(coords[int(e.from_osm)],coords[int(e.to_osm)]) for e in EDGES.itertuples()];depot=REG['depot'];served_flags=np.array([i in served for i in range(len(U))]);space=U[['unit_id','lon','lat','area_mu','elevation_m','regional_slope_deg','lastmile_gap_m','group']].copy();space['served']=served_flags;outdata(1,'空间单元',space,'研究服务单元与JSON完成索引匹配；遥感支持不是订单')
    with rasterio.open(source(D/'建平_2020玉米裁剪.tif')) as ds:
        maize=np.ma.masked_where(ds.read(1)!=1,ds.read(1));bounds=ds.bounds;ax[0].imshow(maize,extent=[bounds.left,bounds.right,bounds.bottom,bounds.top],origin='upper',cmap=matplotlib.colors.ListedColormap(['#A5CDAF']),interpolation='nearest',zorder=0)
    for j,a in enumerate(ax):
        a.add_collection(LineCollection(segments,colors='#C4CACF',linewidths=.35,zorder=1));a.scatter(U.lon,U.lat,s=U.area_mu*.40,c=np.where(served_flags,GREEN,RED),edgecolor='white',linewidth=.35,zorder=4);a.scatter([depot['lon']],[depot['lat']],marker='*',s=85,c='#172D41',zorder=5)
        a.set_xlim(U.lon.min()-.008,U.lon.max()+.008);a.set_ylim(U.lat.min()-.008,U.lat.max()+.008);a.set_aspect(1/math.cos(math.radians(41.4)));a.set_xlabel('经度 (WGS84)');a.set_ylabel('纬度 (WGS84)');a.xaxis.set_major_locator(MaxNLocator(4));a.yaxis.set_major_locator(MaxNLocator(5));style(a,None);a.ticklabel_format(useOffset=False,style='plain')
    title(ax[0],'(a) 历史玉米空间支持');title(ax[1],'(b) 主方案任务次序')
    ax[0].legend(handles=[Patch(color='#A5CDAF',label='2020玉米像元'),Line2D([],[],marker='o',ls='',color=GREEN,label='完整服务'),Line2D([],[],marker='o',ls='',color=RED,label='未完整服务'),Line2D([],[],marker='*',ls='',color='#172D41',label='研究锚点')],loc='upper left',fontsize=7.2,framealpha=.96)
    for j,p in enumerate(sorted(S['plans'],key=lambda z:z['team'])):
        x=[depot['lon']]+U.iloc[p['route']].lon.tolist()+[depot['lon']];y=[depot['lat']]+U.iloc[p['route']].lat.tolist()+[depot['lat']];ax[1].plot(x,y,c=COLORS[j],lw=1.15,alpha=.85,label=p['team'],zorder=2)
    ax[1].legend(loc='upper left',fontsize=7.2,ncol=2,framealpha=.96)
    a=allaxes[1,0];bins=[15,30,45,60,75,90,110];a.hist(U.area_mu,bins=bins,color=BLUE,edgecolor='#263238',linewidth=.65);a.set_xlabel('玉米支持面积 (亩/单元)');a.set_ylabel('研究单元数');title(a,'(c) 服务单元面积分布');style(a);a.yaxis.set_major_locator(MaxNLocator(integer=True,nbins=5));a.set_xticks([15,45,75,110])
    a=allaxes[1,1];a.scatter(U.elevation_m,U.regional_slope_deg,c=np.where(served_flags,GREEN,RED),s=22,edgecolor='white',linewidth=.4);a.set_xlabel('DSM高程 (m)');a.set_ylabel('宏观坡度 (°)');title(a,'(d) DSM宏观地形支持');style(a,'both');a.set_ylim(0,U.regional_slope_deg.max()*1.18)
    counts,_=np.histogram(U.area_mu,bins=bins);outdata(1,'支持面积频数',pd.DataFrame({'lower_mu':bins[:-1],'upper_mu':bins[1:],'units':counts}),'numpy.histogram左闭右开，最后区间含右端点；样本50')
    save(fig,1,'研究区空间支持与任务排序','历史玉米空间支持、50服务网格面积及宏观地形、主方案5班组任务次序。','玉米类1像元、OSM边及主方案route绘制；面积映射点大小，DSM点值描述宏观地形。','格网不是确权地块；锚点未核验。连线不是导航；DSM宏观坡度不能认证机械入田。')

    # 02 区域均值、逐日热图与频数，不混淆不同时间汇总。
    fig=plt.figure(figsize=(7.2,6.2),layout='constrained');gs=fig.add_gridspec(2,2,width_ratios=[1,1.3]);a=fig.add_subplot(gs[:,0]);b=fig.add_subplot(gs[0,1]);c=fig.add_subplot(gs[1,1]);county=YEAR.groupby('county').eligible_hours.agg(['mean','min','max']).sort_values('mean');a.barh(county.index,county['mean'],color=[GREEN if v=='建平县' else BLUE for v in county.index],edgecolor='#263238',lw=.5);a.errorbar(county['mean'],np.arange(20),xerr=np.array([county['mean']-county['min'],county['max']-county['mean']]),fmt='none',ecolor='#52646F',elinewidth=.7,capsize=2);a.set_xlim(0,max(county['max'])*1.12);a.set_xlabel('7-8月合格窗口 (小时/年)');title(a,'(a) 县域窗口均值与年际范围');style(a,'x');a.tick_params(axis='y',labelsize=7.8)
    temp=jp.assign(year=pd.to_datetime(jp.date).dt.year,day=pd.to_datetime(jp.date).dt.day);heat=temp.pivot(index='year',columns='day',values='eligible_hours');im=b.imshow(heat,cmap='Blues',vmin=0,vmax=10,aspect='auto',interpolation='nearest');b.set_yticks(np.arange(11),heat.index);b.set_xticks([0,5,10,15,20,25,30],[1,6,11,16,21,26,31]);b.set_xlabel('八月日期');title(b,'(b) 建平逐日窗口');cb=fig.colorbar(im,ax=b,fraction=.045,pad=.025);cb.set_label('小时/日',fontsize=8);style(b,None)
    freq=jp.eligible_hours.value_counts().reindex(range(11),fill_value=0).sort_index();c.bar(freq.index,freq.values,color=GREEN,edgecolor='#263238',lw=.55);c.set_xticks([0,2,4,6,8,10]);c.set_xlabel('合格窗口 (小时/日)');c.set_ylabel('历史日数');title(c,'(c) 建平窗口频数 (n=341)');style(c);outdata(2,'县域均值范围',county.reset_index(),'20县各11年7—8月累计窗口取均值/min/max；范围不是置信区间');outdata(2,'建平日窗口',temp[['date','year','day','eligible_hours']],'2015—2025八月341日期');outdata(2,'日窗口频数',freq.rename('days').reset_index(),'341日频数；不包含其他月份')
    save(fig,2,'区域与日内天气窗口','20县历史作业窗口年际差异、建平八月逐日热图及日窗口分布。','逐小时窗口已与日/年累计独立核对；县域线段为11年min-max。','窗口为再分析代理：风≤3.3 m/s、无雨、温<32℃，06-18时避12-14时；不是现场安全认证。')

    # 03 算法四指标，用最好ALNS实际单行而不是合成不同行最优值。
    best=ALG[ALG.algorithm=='ALNS'].sort_values(['risk_proxy_loss_mu','cost']).iloc[[0]].copy();best['algorithm']='ALNS_best';order=['nearest','largest_first','benefit_density','ALNS_best','ALNS_pool_MILP','robust_Gamma_2','SAA_CVaR'];v=pd.concat([ALG[ALG.algorithm!='ALNS'],best]).set_index('algorithm').loc[order].reset_index();labs=['最近*','面积优先','效益密度','ALNS最佳','融合MILP','鲁棒Γ=2','SAA-CVaR'];colors=[GRAY,GRAY,GRAY,SKY,GREEN,ORANGE,PURPLE];fig,axs=figgrid(2,2,height=6.1)
    for a,key,label,tt,fmt in [(axs[0,0],'timely_rate','及时服务率 (%)','(a) 及时服务','{:.2f}'),(axs[0,1],'risk_proxy_loss_mu','风险面积代理 (亩)','(b) 未服务/逾期风险','{:.1f}'),(axs[1,0],'cost','作业服务支出 (元)','(c) 方案支出','{:.0f}')]:
        vals=v[key].to_numpy()*(100 if key=='timely_rate' else 1);numeric_bars(a,vals,labs,colors,fmt);a.tick_params(axis='x',rotation=42,labelsize=7.4);a.set_ylabel(label);title(a,tt);style(a)
        if key=='timely_rate':percent(a)
        else:a.set_ylim(0,max(vals)*1.22)
    a=axs[1,1];x=np.arange(len(v));a.bar(x-.18,v.timely_rate_near_road*100,.34,color=BLUE,label='近路组',edgecolor='#263238',lw=.55);a.bar(x+.18,v.timely_rate_far_road*100,.34,color=ORANGE,label='远路组',edgecolor='#263238',lw=.55);a.axhline(30,c=RED,lw=1.15,ls='--',label='30%承诺下限');a.set_xticks(x,labs,rotation=42,fontsize=7.4);a.set_ylabel('分组及时服务率 (%)');title(a,'(d) 分组服务与约束');style(a);percent(a);a.legend(loc='upper right',fontsize=7)
    outdata(3,'算法实际行',v,'ALNS最佳按风险面积/成本排序取真实完整单行；不拼接三种子结果')
    save(fig,3,'算法绩效四指标对照','贪心规则、最佳ALNS、融合MILP与风险方案的及时率、风险代理、支出及分组服务。','同输入最终算法对照CSV；ALNS3种子选择实际最佳行。','* 最近优先最差组29.71%，未满足30%承诺；ALNS最佳为3种子中选择，非期望值。')

    # 04 预算扫描：不可行保留缺口，限时点空心。
    fig,axs=figgrid(1,3,height=3.3,width=9.6);styles=[(BLUE,'o','-'),(GREEN,'s','--'),(ORANGE,'^',':')]
    for (floor,g),(color,marker,ls) in zip(BUD.groupby('fairness_floor'),styles):
        g=g.sort_values('budget');lab=f'分组下限 {floor:.0%}'
        for a,key in [(axs[0],'timely_rate'),(axs[1],'worst_group_rate')]:
            a.plot(g.budget,g[key]*100,color=color,ls=ls,lw=1.5,label=lab);ok=g[g.status==0];lim=g[g.status==1];a.scatter(ok.budget,ok[key]*100,c=color,marker=marker,s=25,zorder=4);a.scatter(lim.budget,lim[key]*100,facecolors='white',edgecolors=color,marker=marker,s=35,zorder=5)
    for a,tt,yy in [(axs[0],'(a) 预算与及时服务','及时服务率 (%)'),(axs[1],'(b) 预算与最差组','最差组及时服务率 (%)')]:
        title(a,tt);a.set_xlabel('预算上限 (千元)');a.xaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x/1000:g}'));a.set_ylabel(yy);a.set_ylim(0,85);style(a)
    axs[0].legend(loc='lower right',fontsize=7)
    a=axs[2];ok=FAIR.dropna(subset=['cost']);a.plot(ok.minimum_timely_rate*100,ok.cost/1000,c=BLUE);a.errorbar(ok.minimum_timely_rate*100,ok.cost/1000,yerr=[(ok.cost-ok.cost_lower_bound_yuan)/1000,np.zeros(len(ok))],fmt='none',ecolor=BLUE,capsize=4,elinewidth=1.1)
    for status,fill in [(0,BLUE),(1,'white')]:
        q=ok[ok.status==status];a.scatter(q.minimum_timely_rate*100,q.cost/1000,c=fill,edgecolor=BLUE,s=33,zorder=4)
    a.set_xlabel('两组最低承诺 (%)');a.set_ylabel('可行方案支出 (千元)');a.set_ylim(0,8.6);a.set_xlim(-3,100);title(a,'(c) 承诺支出与求解界');style(a);a.text(.95,.05,'75%、80%、90%\n当前列池不可行',transform=a.transAxes,ha='right',fontsize=7.2)
    outdata(4,'预算扫描',BUD,'24档离散预算—公平试验；缺解不补0，status1只为限时可行解');outdata(4,'服务承诺支出界',FAIR,'增强列池cost上下界；误差线为求解界而非置信区间')
    save(fig,4,'预算公平与服务承诺','不同预算/公平下限的服务权衡与实现服务承诺的成本上下界。','预算扫描按status绘制；status2缺解不连接，成本界来自保存gap。','实心：达到0.1%求解容差；空心：限时可行解；误差线：成本求解界，不是统计置信区间。')

    # 05 资源四面板：同Y尺度、整数资源刻度，不隐藏上限/零。
    fig,axs=figgrid(2,2,height=5.8);pars=[('batteries_per_team','(a) 电池数量','电池 (块/班组)'),('charge_min','(b) 充电周期','充电时间 (分钟)'),('vehicle_liquid_capacity_L','(c) 保障车液量','保障车液量 (L)'),('drones_per_team','(d) 无人机数量','无人机 (架/班组)')]
    for j,(a,(par,tt,xlab)) in enumerate(zip(axs.flat,pars)):
        g=RES[RES.parameter==par].sort_values('value');a.plot(g.value,g.timely_rate*100,'o-',c=COLORS[j]);a.margins(x=.13);a.set_xticks(g.value);a.set_xlabel(xlab);a.set_ylabel('及时服务率 (%)');percent(a);style(a);title(a,tt)
        for x,y in zip(g.value,g.timely_rate*100):a.annotate(f'{y:.2f}',(x,y),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
    outdata(5,'增强池资源敏感性',RES,'使用最终增强池；只读场景条件下的已有结果，不新求解')
    save(fig,5,'电池充电药液与无人机瓶颈','电池、充电时长、保障车液量和无人机数量的资源灵敏度。','最终增强池含原路线、可行前缀及共同种子重生成列；四面板同Y轴范围。','所有资源数量为研究设定；每班组共享电池、充电器及药液，增配结果不能外推为物理上限。')

    # 06 鲁棒保护、配对兑现及留出天气，不伪造显著性。
    fig,axs=figgrid(2,2,height=6.0);ga=ALG[ALG.algorithm.isin(['ALNS_pool_MILP','robust_Gamma_1','robust_Gamma_2','robust_Gamma_4'])].copy();ga['Gamma']=[0,1,2,4];a=axs[0,0];a.plot(ga.Gamma,ga.timely_rate*100,'o-',c=BLUE);a.margins(x=.13);a.set_xlabel('转场保护预算 Γ');a.set_ylabel('名义及时服务率 (%)');a.set_ylim(0,100);a.set_xticks([0,1,2,4]);style(a);title(a,'(a) 保护强度与名义服务')
    for x,y in zip(ga.Gamma,ga.timely_rate*100):a.annotate(f'{y:.2f}',(x,y),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
    a=axs[0,1]
    for policy,color,label in [('nominal',BLUE,'基准'),('robust_gamma2',ORANGE,'鲁棒 Γ=2')]:
        vals=np.sort(PT[PT.policy==policy].fulfilled_promised_rate.to_numpy()*100);a.step(np.r_[0,vals,105],np.r_[0,np.arange(1,101)/100,1],where='post',color=color,label=label)
    a.set_xlim(0,105);a.set_ylim(0,1.08);a.set_xlabel('事前承诺兑现率 (%)');a.set_ylabel('经验累计概率');style(a,'both');title(a,'(b) 同100扰动样本兑现分布');a.legend(loc='upper left',fontsize=7.4)
    policies=['nominal','robust_gamma2','SAA_CVaR'];plabs=['基准','鲁棒Γ=2','SAA-CVaR'];a=axs[1,0];arrays=[WE[WE.policy==p].sort_values('date').timely_rate.to_numpy()*100 for p in policies];bp=a.boxplot(arrays,tick_labels=plabs,patch_artist=True,widths=.48,medianprops={'color':'#172D41','linewidth':1.7},boxprops={'linewidth':1},whiskerprops={'linewidth':1},capprops={'linewidth':1},flierprops={'marker':'o','markersize':2})
    for patch,color in zip(bp['boxes'],[BLUE,ORANGE,PURPLE]):patch.set_facecolor(color);patch.set_alpha(.28)
    for j,arr in enumerate(arrays,1):a.scatter(j+np.linspace(-.13,.13,len(arr)),arr,s=5,c=[BLUE,ORANGE,PURPLE][j-1],alpha=.5,zorder=2)
    a.set_ylabel('及时服务率 (%)');percent(a);style(a);title(a,'(c) 61日期天气压力分布');a.tick_params(axis='x',labelsize=7.8)
    a=axs[1,1];q=WS.set_index('policy').loc[policies];x=np.arange(3);a.bar(x-.18,q.mean_loss_mu,.34,color=BLUE,label='平均',edgecolor='#263238',lw=.6);a.bar(x+.18,q.CVaR90_loss_mu,.34,color=ORANGE,label='CVaR90',edgecolor='#263238',lw=.6);a.set_xticks(x,plabs,fontsize=7.8);a.set_ylabel('风险面积代理 (亩)');a.set_ylim(0,2600);style(a);title(a,'(d) 平均风险与尾部风险');a.legend(loc='upper left',fontsize=7.4)
    outdata(6,'Gamma名义表现',ga,'不同保护路线池；不作为同规模算法速度比较');outdata(6,'配对兑现原样本',PT,'100共同种子；每任务路线最多两段25%以内扰动，非普遍可靠性认证');outdata(6,'61日期天气原样本',WE,'剔除代表日，所有政策同61日期；排序只用于绘图');outdata(6,'天气风险汇总',WS,'已独立核对均值/CVaR90')
    save(fig,6,'鲁棒保护兑现与天气尾部风险','鲁棒保守性、100次配对扰动的承诺兑现，以及61留出日期的天气服务与尾部风险。','不同承诺面积用兑现比例比较；天气箱体为Q1-Q3，中线中位数，须至1.5IQR内极值。','兑现试验与天气试验为不同压力情景；尾部改善未全面成立。箱线不是置信区间。')

    # 07 同步执行与资源内部轨迹：真实事件，而非各班汇总虚构时间。
    fig,axs=figgrid(3,1,height=7.2);plans=sorted(S['plans'],key=lambda p:p['team']);ec={'travel':BLUE,'prepare':'#AAB4BC','flight':GREEN,'refill':ORANGE};a=axs[0]
    for j,p in enumerate(plans):
        for e in p['events']:
            if e['type'] in ec:a.broken_barh([(e['start'],e['end']-e['start'])],(j-.3,.6),facecolors=ec[e['type']],edgecolors='white',linewidth=.2)
    a.set_yticks(range(5),[p['team'] for p in plans]);a.set_ylim(-.55,4.55);a.set_xlim(0,720);a.set_xticks(np.arange(0,721,120),[f'{h:02d}:00' for h in range(6,19,2)]);a.set_xlabel('设计作业日时刻');style(a,'x');title(a,'(a) 主方案5班组车机执行');a.legend(handles=[Patch(color=ec[k],label=v) for k,v in [('travel','转场'),('prepare','准备'),('flight','植保'),('refill','补水')]],loc='upper right',fontsize=7.4,ncol=4,framealpha=.97)
    p=next(p for p in plans if p['team']=='OWN1');points=[(0,C['vehicle_liquid_capacity_L'])];water=C['vehicle_liquid_capacity_L'];inventory=[]
    for e in sorted(p['events'],key=lambda z:z['start']):
        if e['type']=='refill':at=e['end'];water=C['vehicle_liquid_capacity_L']
        elif e['type']=='flight':at=e['start'];water-=e['liquid_L']
        else:continue
        points.append((at,water));inventory.append({'team':p['team'],'minute':at,'liquid_L':water,'event':e['type']})
    points.append((p['finish'],water));points=np.array(points);a=axs[1];a.step(points[:,0],points[:,1],where='post',c=BLUE,lw=1.7);a.set_xlim(0,420);a.set_ylim(0,670);a.set_xticks(np.arange(0,421,60),[f'{h:02d}:00' for h in range(6,14)]);a.set_ylabel('保障车剩余药液 (L)');a.set_xlabel('设计作业日时刻');title(a,'(b) OWN1药液库存');style(a);a.axhline(0,color=RED,ls=':',lw=1)
    for e in p['events']:
        if e['type']=='refill':a.axvspan(e['start'],e['end'],color=ORANGE,alpha=.2)
    a=axs[2]
    for e in p['events']:
        if e['type']=='flight':a.broken_barh([(e['start'],e['end']-e['start'])],(e['battery']-.25,.5),facecolors=GREEN,edgecolors='white',linewidth=.3)
        if e['type']=='charge':
            a.broken_barh([(e['return_at'],e['start']-e['return_at'])],(e['battery']-.25,.5),facecolors='#AAB4BC',edgecolors='white',linewidth=.3);a.broken_barh([(e['start'],e['end']-e['start'])],(e['battery']-.25,.5),facecolors=ORANGE,edgecolors='white',linewidth=.3)
    a.set_yticks([0,1,2],['电池1','电池2','电池3']);a.set_ylim(-.5,2.5);a.set_xlim(0,420);a.set_xticks(np.arange(0,421,60),[f'{h:02d}:00' for h in range(6,14)]);a.set_xlabel('设计作业日时刻');title(a,'(c) OWN1电池使用与充电');style(a,'x');a.legend(handles=[Patch(color=GREEN,label='飞行使用'),Patch(color='#AAB4BC',label='冷却/排队'),Patch(color=ORANGE,label='充电')],loc='upper center',bbox_to_anchor=(.5,-.30),fontsize=7.3,ncol=3)
    evrows=[{'team':p['team'],**e} for p in plans for e in p['events']];outdata(7,'资源事件',pd.DataFrame(evrows),'逐条读取主方案事件；无事件区间不补造作业');outdata(7,'OWN1库存',pd.DataFrame(inventory),'初始600L；架次开始扣液，补水结束恢复；严格按事件时刻')
    save(fig,7,'车机同步药液与电池周转','主方案同步甘特图及OWN1药液、电池、充电轨迹。','主方案事件直接绘制；库存逐条守恒计算，电池冷却/排队按return_at至charge_start。','(a)范围06-18时；(b)(c)放大06-13时。空白包含等候/就绪；车载供电和补水点待现场核验。')

    # 08 合同与条件信息收益，不把亩叫经济利润。
    fig,axs=figgrid(2,2,height=5.8);labs=['仅自有','购买外援','理想集中'];ins=INST.set_index('institution').loc[['owned_only','contract_participation','ideal_centralized']];numeric_bars(axs[0,0],ins.timely_rate*100,labs,[GRAY,GREEN,BLUE],'{:.2f}');title(axs[0,0],'(a) 参与制度与及时服务');axs[0,0].set_ylabel('及时服务率 (%)');percent(axs[0,0]);style(axs[0,0]);numeric_bars(axs[0,1],ins.cost,labs,[GRAY,GREEN,BLUE],'{:.0f}');title(axs[0,1],'(b) 制度下的服务支出');axs[0,1].set_ylabel('服务支出 (元)');axs[0,1].set_ylim(0,10000);style(axs[0,1])
    inf=INFO.sort_values('connection_factor');x=np.arange(len(inf));a=axs[1,0];a.bar(x-.18,inf.blind_loss_mu,.34,color=GRAY,label='固定不更新',edgecolor='#263238',lw=.6);a.bar(x+.18,inf.risk_proxy_loss_mu,.34,color=GREEN,label='条件重优化',edgecolor='#263238',lw=.6);a.set_xticks(x,[f'{v:g}' for v in inf.connection_factor]);a.set_xlabel('未知接入时间倍数');a.set_ylabel('风险面积代理 (亩)');a.set_ylim(0,1000);title(a,'(c) 接入条件变化');style(a);a.legend(loc='upper left',fontsize=7.5)
    a=axs[1,1];numeric_bars(a,inf.conditional_gain_mu,[f'{v:g}' for v in inf.connection_factor],[BLUE,BLUE,ORANGE],'{:.2f}');a.set_xlabel('未知接入时间倍数');a.set_ylabel('条件重优化收益 (亩)');a.set_ylim(0,145);title(a,'(d) 已知条件下的重优化收益');style(a);outdata(8,'外援制度',INST,'同增强池；理想集中忽略报价和机会收益，不是现实可免费实施');outdata(8,'接入条件收益',INFO,'盲目损失减重优化损失；单位亩，不是事前VOI或元')
    check('信息差值独立核对',np.allclose(INFO.blind_loss_mu-INFO.risk_proxy_loss_mu,INFO.conditional_gain_mu,atol=1e-7))
    save(fig,8,'外援参与制度与接入信息','外援采购的面积/成本权衡与已知接入条件后的重优化收益。','制度/信息最终增强池表；整包采购费只计一次；条件收益逐行做差核对。','理想集中不含报价/机会收益；108.30亩是条件风险代理改善，不是巡田净收益或农业收入。')

    # 09 方法计算：三种子收敛、样本变异、实际子问题时间与DP否定结果。
    fig,axs=figgrid(2,2,height=6.2);tr=TRACE[TRACE.seed.isin([20261002,20261003,20261004])].copy();a=axs[0,0]
    for j,(seed,g) in enumerate(tr.groupby('seed')):
        g=g.sort_values('iteration');check('ALNS轨迹单调_'+str(seed),len(g)==180 and (g.best_score.diff().dropna()<=1e-6).all());a.plot(g.iteration,g.best_score/1000,c=COLORS[j],ls=['-','--',':'][j],label=str(int(seed)))
    a.set_xlabel('ALNS迭代次数');a.set_ylabel('搜索评价值 (×10³)');title(a,'(a) ALNS三种子收敛');style(a);a.legend(fontsize=7.1,loc='upper right')
    aa=ALG[ALG.algorithm=='ALNS'].sort_values('seed');a=axs[0,1];numeric_bars(a,aa.timely_rate*100,['种子1','种子2','种子3'],COLORS[:3],'{:.2f}');a.set_ylabel('及时服务率 (%)');title(a,'(b) 三次实际搜索结果');percent(a);style(a)
    a=axs[1,0];a.plot(SCALE.tasks,SCALE.seconds,'o-',c=BLUE);a.set_yscale('log');a.set_xticks([5,10,20,50]);a.set_xlabel('真实子实例任务数');a.set_ylabel('主问题调用耗时 (秒，对数)');title(a,'(c) 受限主问题规模试验');style(a,'both');a.yaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10,numticks=4));a.yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x:g}'))
    for x,y in zip(SCALE.tasks,SCALE.seconds):a.annotate(f'{y:.3f}',(x,y),xytext=(0,7),textcoords='offset points',ha='center',fontsize=7.5)
    a=axs[1,1];x=np.arange(len(DP));a.bar(x-.18,DP.original_travel_minutes,.34,color=GRAY,label='原方案含补水转场',edgecolor='#263238',lw=.55);bars=a.bar(x+.18,DP.tsp_minutes,.34,color=BLUE,label='仅TSP排序',edgecolor='#263238',lw=.55)
    for bar,ok in zip(bars,DP.resource_feasible):
        if not ok:bar.set_hatch('///')
    a.set_xticks(x,DP.team,rotation=35,fontsize=7.7);a.set_ylabel('转场时间 (分钟)');a.set_ylim(0,180);title(a,'(d) DP排序仍需资源核验');style(a);a.legend(loc='upper left',fontsize=6.9)
    outdata(9,'三种子轨迹',tr,'排除额外鲁棒ALNS轨迹；3种子各180次');outdata(9,'搜索实际行',aa,'3次搜索，不据此推断统计显著性');outdata(9,'真实子实例',SCALE,'实际截取n任务及变量；时间包括主问题调用，不含完整ALNS/数据准备');outdata(9,'DP排序核验',DP,'TSP弧时间未含资源补水；原方案含补水，不作为净节时效率估计')
    save(fig,9,'邻域搜索计算规模与动态规划核验','三种子ALNS轨迹、实际结果、真实子实例主问题时间与DP资源可行核验。','严格使用真实子实例和DP状态；DP斜线标记资源模拟不可行。','主问题耗时不含完整列生成；DP斜线为资源不可行。两类转场口径不同，不估计净节时。')

    # 10 数据质量：风不同高度不比精度；跨产品差异不用站点准确率名。
    fig,axs=figgrid(2,2,height=5.8)
    for a,var,tt,unit in [(axs[0,0],'T2M','(a) 气温跨产品一致性','℃'),(axs[0,1],'PRECTOTCORR','(b) 降水跨产品一致性','mm/h')]:
        r=CROSS[CROSS.variable==var].iloc[0];numeric_bars(a,[r.bias,r.MAE,r.RMSE],['偏差','MAE','RMSE'],[GRAY,BLUE,GREEN],'{:.2f}');a.axhline(0,c='#263238',lw=1);a.set_ylabel(f'跨产品差异 ({unit})');title(a,tt);style(a);vals=np.array([r.bias,r.MAE,r.RMSE]);a.set_ylim(min(0,vals.min())*1.3,vals.max()*1.35)
    a=axs[1,0];vals=np.sort(U.lastmile_gap_m.to_numpy());a.step(np.r_[0,vals,1200],np.r_[0,np.arange(1,51)/50,1],where='post',c=BLUE);median=np.median(vals);a.axvline(median,c=ORANGE,ls='--',lw=1.15);a.set_xlabel('未核验接入距离 (m)');a.set_ylabel('样本累计比例');a.set_xlim(0,1250);a.set_ylim(0,1.07);title(a,'(c) 50单元接入距离');style(a,'both');a.text(.03,.94,f'中位数 {median:.2f} m',transform=a.transAxes,fontsize=8,va='top')
    a=axs[1,1];missing=np.array([(EDGES.surface=='unknown').mean(),(EDGES.width=='unknown').mean()])*100;x=np.arange(2);a.bar(x,100-missing,.58,color=GREEN,label='已记录',edgecolor='#263238',lw=.6);a.bar(x,missing,.58,bottom=100-missing,color=GRAY,label='缺失',edgecolor='#263238',lw=.6);a.set_xticks(x,['路面','宽度']);a.set_ylabel('OSM路段属性比例 (%)');percent(a);style(a);title(a,'(d) 道路证据缺口');a.legend(loc='lower right',fontsize=7.5)
    for j,v in enumerate(missing):a.text(j,100-v/2,f'缺失 {v:.2f}%',ha='center',va='center',color='white',fontsize=8)
    outdata(10,'跨产品误差',CROSS,'原比较气温/降水；不比较2m与10m风，不提供站点精度');outdata(10,'接入距离',U[['unit_id','lastmile_gap_m']],'已按≤1200m选样，CDF不能外推为完整区域');outdata(10,'道路缺失比例',pd.DataFrame({'attribute':['surface','width'],'missing_percent':missing,'n_edges':len(EDGES)}),'OSM3511研究路段属性统计，unknown计缺失')
    save(fig,10,'气象一致性接入距离与道路证据缺口','气温/降水再分析间差异、样本接入距离与道路字段缺失。','来源统计独立复核；偏差可为负，缺失不当零速度/已通行。','气象样本各16368小时，无站点真值；接入样本已截断≤1200m，不能认证入口或导航可行。')

# 保存论文图注、来源校验及统一规范；不重写求解数据。
for rec in source_records.values():check('来源未改写_'+Path(rec['path']).name,sha(Path(rec['path']))==rec['sha256'])
pdf=PdfReader(O/'论文图集_标准版.pdf');check('PDF页数',len(pdf.pages)==10)
pdf_fonts=set()
for page in pdf.pages:
    for ob in page.get('/Resources',{}).get('/Font',{}).values():pdf_fonts.add(str(ob.get_object().get('/BaseFont','')))
check('PDF嵌入加粗字体',any('Arial' in n for n in pdf_fonts) and any('MicrosoftYaHei' in n for n in pdf_fonts) and all('Bold' in n for n in pdf_fonts),sorted(pdf_fonts))
pngs=sorted((O/'PNG_600dpi').glob('Fig_*.png'));check('PNG/SVG各10图',len(pngs)==10 and len(list((O/'SVG_矢量').glob('Fig_*.svg')))==10)
for p in pngs:
    im=Image.open(p);check(p.stem+'600dpi元数据',min(im.info.get('dpi',[0,0]))>599 and '用途' in im.info.get('Description',''))
pd.DataFrame(source_records.values()).to_csv(O/'绘图数据来源与校验和.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(captions).to_csv(O/'图表清单与生成逻辑.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(checks).assign(purpose='最终图形数据/字体/来源核对',generation_logic='plot_paper_standard.py独立计算与文件检查').to_csv(O/'核对与预览/绘图核对明细.csv',index=False,encoding='utf-8-sig')
audit={'purpose':'标准论文图严格核对与样式验收','generation_logic':'绘图前后源文件哈希、独立汇总、字体及PDF/PNG检查','passed':all(c['passed'] for c in checks),'checks_count':len(checks),'figure_count':10,'text_checks':text_checks,'font_paths':font_paths,'pdf_fonts':sorted(pdf_fonts),'checks':checks,'visual_qa':'待主代理逐图检查与PDF渲染后填写','scope':'旧求解结果及旧图保留，新的绘图数据仅复制/透明聚合；未重求解或制造统计显著性'}
(O/'核对与预览/绘图验收.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 标准论文图注与绘图口径','用途：论文插图索引、图注、子图解释及数据口径。生成逻辑：plot_paper_standard.py只读最终结果，独立核对后绘图。中文微软雅黑Bold、英文数字Arial Bold，全部文字加粗。每图文件名前缀与编号一一对应。', 'PNG600dpi用于Word排版；SVG的字形路径化防止缺字体；PDF图集嵌入加粗字体。空间图的遥感底图是栅格，曲线/文字/坐标保持矢量；不把带栅格底图的PDF称作全矢量影像。']
for r in captions:lines+=['## '+r['figure'],r['caption'],'图注口径：'+r['notes'],'生成逻辑：'+r['generation_logic'],f'[600dpi PNG](<D:/Desktop/code/08_标准论文图/PNG_600dpi/{r["figure"]}.png>)　[SVG](<D:/Desktop/code/08_标准论文图/SVG_矢量/{r["figure"]}.svg>)']
(O/'图注与数据口径.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
(O/'README_标准论文图.md').write_text('''# 标准论文图交付入口

用途：定位本次统一加粗、标准命名的10张论文复合图。生成逻辑：plot_paper_standard.py核对最终源数据后绘图，保留此前05_论文图表全部旧文件。

本次标准图为Fig_01至Fig_10，共37个统计/布局子面板（色条不计子面板）。PNG_600dpi保存高分辨率图片，SVG_矢量保存路径化字形与可编辑图形，论文图集_标准版.pdf将10图合为10页。图注与数据口径.md给每图说明；绘图数据目录保存精确源行/透明聚合，缺解不补0、无统计依据不画置信区间。

字体：英文/数字Arial Bold（arialbd.ttf），中文Microsoft YaHei Bold（msyhbd.ttc），不使用花哨字体。标题10pt、轴/正文标签9pt、刻度8.2pt、数值注释7.6—8pt，全部加粗；双栏主体7.2英寸/约183mm；三面板宽图9.6英寸，可横向排版而不强行压缩小字。主轴框1.25pt、辅助框0.6pt、主曲线1.65pt、辅助网格0.4pt；白底，无3D/阴影，使用可区分配色与线型。

标准命名：Fig_编号_主题.png/svg。图内(a)(b)(c)(d)对应图注，按主题合并相关对比，正文建议整图插入避免随意拆分导致口径丢失。

严格核对：主面积与支付、分组率、三种子轨迹、20县11年日/年窗口、61配对天气日期、100配对扰动、均值/CVaR、服务承诺上下界、真实子实例规模以及来源校验和。主方案任务完成表的整包价格不可逐任务求和，本次仅按5班组计费。曲线箱线与成本求解界均有明确语义，未伪造显著性。

注意：数据是半实证设计；服务网格不是确权/真实订单，空间连线不是导航。最近优先不满足30%最差组承诺，ALNS最佳为三次搜索中所选实际方案。预算限时点为空心；资源采用增强路线池；DP的原方案转场含补水而TSP弧时间不含，不能称净节时。天气箱线不是置信区间，风险面积不能货币化为农户收入。

复现：使用D:/Desktop/code/.venv/Scripts/python.exe运行D:/Desktop/code/plot_paper_standard.py。脚本不改写任何求解源文件。核对与预览内包含检查明细、字体验收、PDF渲染和低分辨率预览，不作为投稿原图。图的视觉验收结论见绘图验收.json。
''',encoding='utf-8')
print('标准论文图完成；数据核对',len(checks),'全部通过',flush=True)
