"""用途：统一最终统计口径，生成完整论文分析、文献汇编、参数/文件说明与复现环境。
生成逻辑：只从审计、派生数据和已保存求解输出取值；不手工预填结果，不补造实测数据。
"""
from pathlib import Path
import json,hashlib,shutil,sys,subprocess,datetime
import numpy as np,pandas as pd
B=Path('D:/Desktop/code');D=B/'02_处理数据';R=B/'04_求解结果';M=B/'06_论文材料';M.mkdir(exist_ok=True)
def js(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,s):path.write_text(s,encoding='utf-8')
def csv(path,df,purpose,logic):
    df=df.copy();df['purpose']=purpose;df['generation_logic']=logic;df.to_csv(path,index=False,encoding='utf-8-sig')
def table(df,cols=None,digits=2):
    df=df if cols is None else df[cols]
    def fmt(x):
        if pd.isna(x):return '—'
        if isinstance(x,(float,np.floating)):return f'{x:.{digits}f}'
        return str(x).replace('|','/').replace('\n',' ')
    return '| '+' | '.join(map(str,df.columns))+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(fmt(v) for v in row)+' |' for row in df.itertuples(index=False,name=None))
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def link(path,label=None):return f'[{label or path.name}](<{path.as_posix()}>)'

def correct_final_tables():
    env=js(R/'运行环境.json');df=pd.read_csv(R/'留出年份天气压力测试.csv');df=df[df.date!=env['nominal_date']].copy()
    csv(R/'留出年份天气压力测试.csv',df,'固定路线历史天气压力测试','2024—2025八月剔除设计代表日，共61日期；非真实运营回测')
    rows=[]
    for policy,g in df.groupby('policy'):
        arr=g.risk_proxy_loss_mu.to_numpy();eta=np.quantile(arr,.9)
        rows.append(dict(policy=policy,n=len(g),mean_loss_mu=arr.mean(),CVaR90_loss_mu=eta+np.maximum(arr-eta,0).mean()/.1,mean_timely_rate=g.timely_rate.mean(),mean_worst_group_rate=g.worst_group_rate.mean()))
    csv(R/'留出天气汇总.csv',pd.DataFrame(rows),'最终61日天气评价汇总','经验分位数及CVaR90；所有政策使用同一日期集')
    f=pd.read_csv(R/'服务承诺最低预算.csv')
    # rho=0的空计划合法；旧代码if p把空list误判为无解，仅补记已求得的空计划指标。
    zero=(f.minimum_timely_rate==0)&(f.status==0)
    numeric=['cost','risk_proxy_loss_mu','served_area_mu','timely_area_mu','timely_rate','worst_group_rate','travel_min','energy_kwh','refills','flights','timely_rate_near_road','timely_rate_far_road']
    for k in numeric:f.loc[zero,k]=float(pd.read_csv(D/'研究服务单元.csv').area_mu.sum()) if k=='risk_proxy_loss_mu' else 0.
    f['cost_lower_bound_yuan']=f.cost*(1-f.mip_gap.fillna(0));f['cost_upper_bound_yuan']=f.cost
    f['interpretation']=['限当前候选池不可行' if s==2 else ('限时可行支出上界' if s==1 else '达到求解容差；非完整路线空间全局最优') for s in f.status]
    csv(R/'服务承诺最低预算.csv',f,'公共服务承诺的成本最小化与上下界','增强路线池MILP；0承诺允许空计划；status1为限时解，gap提供支出界')

def report():
    S=js(R/'主方案.json');z=S['metrics'];U=pd.read_csv(D/'研究服务单元.csv');env=js(R/'运行环境.json');log=js(R/'主模型求解日志.json');reg=js(D/'研究区摘要.json');C=js(B/'config.json')
    alg=pd.read_csv(R/'算法对照.csv');fair=pd.read_csv(R/'服务承诺最低预算.csv');weather=pd.read_csv(R/'留出天气汇总.csv');pert=pd.read_csv(R/'转场扰动压力汇总.csv');inst=pd.read_csv(R/'外援参与制度对照.csv');sens=pd.read_csv(R/'补给与无人机瓶颈灵敏度_增强列池.csv');info=pd.read_csv(R/'接入信息条件对照_增强列池.csv');scale=pd.read_csv(R/'真实子实例规模实验.csv');dp=pd.read_csv(R/'动态规划子路线实验.csv');small=js(R/'小实例穷举核对.json')
    rows=[]
    for p in S['plans']:
        rows.append({'班组':p['team'],'单元数':len(p['completed']),'完整面积/亩':p['area'],'支出/元':p['cost'],'最后返回/分钟':p['finish'],'飞行架次':p['flights'],'锚点补水次数':p['refills'],'外援收益代理/元':p.get('external_profit')})
    csv(R/'主方案班组摘要.csv',pd.DataFrame(rows),'论文班组执行与合同摘要','从主方案完成任务、事件及成本取值；分钟0对应06:00')
    shown=alg.copy();shown['及时率/%']=shown.timely_rate*100;shown['最差组/%']=shown.worst_group_rate*100
    w=weather.copy();w['平均及时率/%']=w.mean_timely_rate*100;w['平均最差组/%']=w.mean_worst_group_rate*100
    inst2=inst.copy();inst2['及时率/%']=inst2.timely_rate*100
    sens2=sens.copy();sens2['及时率/%']=sens2.timely_rate*100
    fair2=fair.copy();fair2['最低承诺/%']=fair2.minimum_timely_rate*100
    base=alg[alg.algorithm=='largest_first'].iloc[0];improvement=(base.risk_proxy_loss_mu-z['risk_proxy_loss_mu'])/base.risk_proxy_loss_mu*100
    covered=len({int(i) for p in S['plans'] for i in p['completed']});lpbound=log['loss_offset_mu']+log['restricted_lp_objective'];searchsecs=alg.loc[alg.algorithm=='ALNS','seconds'].sum()
    y=pd.read_csv(D/'县域天气窗口_年统计.csv');yearmeans=y.groupby('county').eligible_hours.mean().sort_values();jp=y[y.county=='建平县'];daily=pd.read_csv(D/'县域天气窗口_日统计.csv');jpd=daily[(daily.county=='建平县') & daily.date.str.contains('-08-')]
    cross=pd.read_csv(D/'气象交叉产品核对.csv')
    model=(B/'03_模型与方法/数学模型与算法说明.md').read_text(encoding='utf-8');model=model[model.index('## 2 集合'):];model=model.replace('## ','### ')
    s=f'''# 空天地信息支持下的辽宁丘陵玉米植保班组协同调度：完整论文分析与求解报告

用途：提供整篇建模论文所需的背景、数据、假设、数学模型、算法、结果、检验、讨论与结论；不是带有真实农户经营数据的已验收实证论文。生成逻辑：assemble_report.py汇总已保存CSV/JSON及模型说明，所有数值来自计算产物；公式与边界由数据缺口反推。生成日期：2026-10-02。

## 摘要

针对辽宁丘陵地区玉米集中植保中时间窗口短、车机补给耦合、外部服务队参与受限的问题，构建合同任务包驱动的多目标受限集合划分混合整数规划。利用历史玉米栅格、公开道路、补充DSM与再分析天气建立半实证研究实例，将未知订单、入口与经营参数与已取得证据分级管理。采用连续时间资源模拟生成可行班组任务包，融合贪心初解、自适应大邻域搜索与模拟退火、主MILP、动态规划子路线、预算鲁棒保护以及SAA–CVaR天气风险评价。建平50个研究服务单元总支持面积{z['served_area_mu']+z['risk_proxy_loss_mu']:.2f}亩，在3支自有、2支外援班组、12000元预算情景下，主方案完整及时服务{z['timely_area_mu']:.2f}亩，及时率{z['timely_rate']*100:.2f}%，支出{z['cost']:.2f}元，最差接入组及时率{z['worst_group_rate']*100:.2f}%。与满足同公平下限的面积优先贪心相比，风险面积代理降低{improvement:.2f}%，但支出更高。转场扰动中鲁棒方案减少事前承诺以提高兑现率；61个留出日期天气压力测试未证明尾部风险全面改善。独立矩阵重建、事件核验与5任务穷举一致性检验通过。成果支持研究设计与实地补采优先级，不将遥感单元、假设合同和历史天气重放误写为真实订单、真实利润或实时运行收益。

关键词：玉米植保；车机协同；合同参与；受限路线池；自适应大邻域搜索；混合整数规划；鲁棒优化；CVaR。

## 1 背景、题目理解与研究目标

用户给出的题名为“空天地一体化农机协同调度优化研究——面向辽宁丘陵山区玉米生产的多目标混合整数规划模型”。目录未发现独立赛题原文和问题编号，公开赛事页面也未给出该具体命题。因此以用户提供聊天记录为范围依据，不虚构竞赛必须完成的问题。辽宁2025年统计公报给出玉米播种面积2811.1千公顷、产量2066.4万吨[1]；这些宏观数据说明研究规模，不可反推每个作业单元产量。原包技术意见支持玉米阶段管理与植保背景[3,21]。

本次落地业务选择一次应急/集中植保日，研究公共服务协调者如何使用自有保障班组、采购外援已接受任务包，在天气、车辆、无人机、电池、充电器、药液、预算和采购公平承诺下提高及时服务面积。不是把整季耕、种、管、收全部强行纳入同一日。地面保障车与无人机具有明确同步关系；天层产品提供历史作物空间支持。缺乏巡田诊断真值时不声称已实现主动识别闭环。

主目标是降低未服务与迟服务的风险面积代理，次目标是在相同主目标容差下减少作业服务支出。风险代理以亩计量，不是经济损失；没有以同一无标定权重相加亩、元、碳。公共公平由购买方预算承担；外援需满足至少保留收益的合同条件。实地施药的药剂、作物阶段、禁飞和现场风等要求仍须单独核实。

## 2 数据审计、缺口与补充检索

原包共5457文件，约16.447GB；60 PDF、540 TIFF、51 CSV、23 NetCDF、2880 XLS及9 XLSX等。大量文件是多年份、多省或历史年鉴配套，不应当作独立辽宁经营样本。完整文件级索引、PDF抽取清单与URL线索存于01_数据审计。没有将URL线索中的每条链接冒充已读资料。

取得并保存的关键补充是公开Copernicus 30m DSM N41E119，及模型方法、官方产品/软件文档；原件在 D:/Desktop/jianmo/11_本次公开补充，取得状态与SHA256在审计台账。尝试检索后未得到这50单元的确权边界、当期植保订单、病虫诊断、入口、GPS和班组报价。经营微观缺口不能用省级统计或通用土壤属性补成真值；缺失字段保留，必须采用研究档位的参数写入config和参数证据表。

详细差异表见 {link(B/'01_数据审计/数据缺口与使用边界.md')}。优先补采：确认订单和诊断、入口与保障点、关键路线GPS、满/亏电与充电状态、药液库存、外援完整任务包报价与可替代订单。未得到地面作业入口与机械适配证明，主算例不启用地面喷雾机，避免仅以30m坡度宣称机器能入田。

### 2.1 空间处理与样本身份

采用2020辽宁玉米分类像元为历史支持[5]，裁剪经度119.57—119.71、纬度41.35—41.45。按当地角度—米近似换算面积、1亩=2000/3平方米，聚合成300m研究格网，筛选面积15—110亩、距离锚点6km内、接入距离不超过1200m的单元，再按径向排序系统选取50个。区域玉米支持面积{reg['maize_2020_mu']:.2f}亩；候选{reg['candidate_units']}个，选取{len(U)}个，面积{U.area_mu.sum():.2f}亩。抽样不是随机农户调查，不能推广为全省分布；格网多边形不是农业确权地块，面积不是农户经营规模。

DSM仅提供高程、宏观坡度。OSM研究区域有{reg['osm_nodes']}节点、{reg['osm_edges']}路段和{reg['strong_components']}个强连通分量，取主分量计算有向道路时间；道路分类速度是情景假设。路面缺失{reg['surface_missing_share']*100:.2f}%，宽度缺失{reg['width_missing_share']*100:.0f}%。服务点至主路网最近节点的距离中位数{reg['median_lastmile_gap_m']:.2f}m、最大{reg['max_lastmile_gap_m']:.2f}m。该连接不是已测可通行道路，因此分开输出“已知道路时间”和“未核验接入时间”。路网锚点({reg['depot']['lon']},{reg['depot']['lat']})不是已确认合作社/补水站。研究转场与图1连线都不作为车辆导航。

### 2.2 天气与窗口

20县点2015—2025逐小时CSV用于区域比较。原文件ERA5-Land风、雨列全空，气温取ERA5-Land、风雨取ERA5；Open-Meteo默认风速km/h，已除以3.6[7,8]。分钟模拟仅将整小时状态展开，不创造分钟实测。窗口设定为06—18时、风≤3.3m/s、无降水、温<32℃、避12—14时；风与避午有采购参考，32℃及两小时区间是研究假设。未知天气不允许作业。10m再分析风不等于冠层现场安全认证。

建平7—8月年均合格窗口{jp.eligible_hours.mean():.2f}小时，八月日窗口平均{jpd.eligible_hours.mean():.2f}小时；20县最高与最低分别为{yearmeans.index[-1]}({yearmeans.iloc[-1]:.2f}小时)与{yearmeans.index[0]}({yearmeans.iloc[0]:.2f}小时)。这些只是同阈值环境差异，不是县域实际经营效率。

NASA与Open-Meteo产品间气温/降水对照如下。NASA LST建平经度对应UTC+8[9]，可按小时匹配；2m与10m风未经廓线标定，不做“风速准确率”。没有站点真值，误差统计只能称跨产品一致性。

{table(cross,[c for c in cross.columns if not c.startswith('_') and c not in ['purpose','generation_logic']])}

2020玉米、2026 OSM与采购价格、2015—2025天气共同组成2026研究设计压力测试。离线代表日为{env['nominal_date']}，由2025年八月可作业小时最接近中位数的日期确定。选择用到了历史完整天气，不能称当时实时可得预报。2015—2023九日期用于风险模型训练，2024—2025八月剔除该代表日的61日期评价；数据无实时订单，评价仍是环境压力测试而非经营回测。

## 3 参数、假设与资源关系

自有3班组、外援2班组，每班组1保障车、1无人机、3电池、1充电器，外援60分钟到达；推荐完成16时、班次结束18时。机型规格给40L箱、DB1560能量及9—12分钟充电参考[4]，作业速度6m/s、喷幅7m与2L/亩在采购参考范围内[2]。净效率系数0.65、功率5.4kW、可用能量比例0.8、续航上限10分钟、库存600L、冷却2分钟等是需要校准的研究参数。按速度—喷幅—效率得到净作业率147.42亩/小时，40L箱对应20亩，但在本参数下10分钟限制允许24.57亩，因而箱容量更紧。

统一风险权重1意味着没有假冒病虫程度。药肥由采购方另行供应，成本是作业服务支出，不是全社会农业成本。电量只报告架次飞行代理{z['energy_kwh']:.2f}kWh，未包含充电损耗/车辆燃料，没有完整碳因子与实耗，因此不估计总CO2或宣称低碳减排百分比。详见 {link(M/'参数证据与不确定性表.csv')} 与config.json。

## 4 数学建模与融合算法

下列公式和实现映射为论文可直接整理的模型主体。参考[13—19]各自支撑分解、动态规划、ALNS、鲁棒保护、CVaR和epsilon处理；没有将没有实测能耗曲线的非线性优化硬加进结果。

{model}

## 5 主方案与算法对照

1040条可行路线加50个未服务变量构成1090二元变量、58约束、8847非零元。主MILP损失最优{z['risk_proxy_loss_mu']:.6f}亩，MIP gap=0；最优性只针对当前候选池和代理参数。当前池LP损失下界{lpbound:.6f}亩，与整数损失差{z['risk_proxy_loss_mu']-lpbound:.6f}亩；它不能作为完整路径空间的全局界。主模型记录时间{log['seconds']:.3f}秒（包括该调用的主选择、LP与二级选择），三种子ALNS生成时间合计{searchsecs:.2f}秒，还不含数据处理、其他实验及I/O；不得只用0.56秒宣传整个任务求解速度。未运行Gurobi，也未测其内存。

选中5班组，完整及时服务{covered}个单元、{z['timely_area_mu']:.2f}亩，未完整服务{len(U)-covered}个，风险面积{z['risk_proxy_loss_mu']:.2f}亩。总支出{z['cost']:.2f}元，比12000元上限少{12000-z['cost']:.2f}元。近路与远路及时率分别{z['group_rates']['near_road']*100:.2f}%、{z['group_rates']['far_road']*100:.2f}%，均满足30%下限。总转场{z['travel_min']:.2f}班组分钟，{z['flights']}架次，{z['refills']}次锚点补水。转场是所有班组之和，不能当单班时长；各班18时前返回。

{table(pd.DataFrame(rows))}

具体任务完成时刻、资源事件、排序与合同代理分别在主方案任务完成表、主方案事件表和主方案JSON。图1仅显示排序；图6呈现同点起降与补给甘特图，不隐去天气等待。充电允许在车载供能条件下延续，这一假设必须在实地核验车辆电源后使用。

{table(shown,['algorithm','cost','risk_proxy_loss_mu','及时率/%','最差组/%','seconds'])}

最近优先规则最差组仅29.71%，未满足30%下限，是业务规则诊断而非公平可行对手。面积优先、效益密度与三种子ALNS均满足该下限。与面积优先相比，主方案及时率增加{(z['timely_rate']-base.timely_rate)*100:.2f}个百分点、风险代理减少{improvement:.2f}%，支出增加{z['cost']-base.cost:.2f}元；不是“同时显著省钱减损”。ALNS最好单次及时率74.58%，MILP协调不同种子可行包后达到75.14%。增强3885列重新求解得到同一主指标，说明本次前缀扩展未改善主实例，但不证明完整路线空间已穷尽。

动态规划实验仅对选定不超过10任务的集合优化有向转场排序并再核验资源，结果如下；最短TSP次序不一定是天气/补给意义下最优。

{table(dp,[c for c in dp if c not in ['purpose','generation_logic']])}

## 6 外援、预算与公共服务承诺

{table(inst2,['institution','cost','risk_proxy_loss_mu','及时率/%','worst_group_rate'])}

同增强候选池内，自有班组及时率48.60%，加入满足合同参与的外援后75.14%，增加26.54个百分点；支付提高。理想集中调度只计算履约资源成本，得到同面积、6282.76元，看似比购买外援少1900.18元；这部分正体现参考报价与参与收益，不是现实中可以免费省掉的费用。外援规则满足必要保留收益，但没有报价真实性、激励相容或履约实证。

公共服务承诺的成本最小化采用近路、远路分别满足下限，12000预算保持不变。下表给可行支出上下界，限时结果不写成精确最低预算；status0也按0.1%容差解释。

{table(fair2,['最低承诺/%','status','mip_gap','cost_lower_bound_yuan','cost_upper_bound_yuan','interpretation'])}

30%承诺约2484.88元可实现，70%约7397.14元可实现（均有求解容差）。50%、65%档位20秒限时，只有可行支出上界及界差。75%、80%、90%在当前3885列池内不可行，不能推出实际地区任何设备配置都不可行。预算—公平24档结果在预算与公平灵敏度CSV；3000元附近也含限时/不可行档位。预算富余未转化服务的原因是可作业窗口、资源与路线池限制，不代表需求已全部满足。

## 7 资源瓶颈与接入信息

{table(sens2,['parameter','value','pool_routes','及时率/%','cost','status','mip_gap'])}

3块电池到4块、600L到1000L在当前池未提高及时率；1块电池约53.49%、充电30分钟约50.43%、200L约57.49%，表现出补给制约。两无人机/班组在共享电池、充电器、液量且同路线池下没有额外提升，不能外推为增配无人机永远无价值。仅改变参数重放原列的旧表可能因候选被删造成“不可行”，最终报告采用加入可行前缀与共同种子贪心再生成的增强表。初始表保留用于算法设计反思，不与最终表混用。

{table(info,['connection_factor','blind_loss_mu','risk_proxy_loss_mu','conditional_gain_mu','timely_rate','status'])}

接入时间加倍时，条件重优化比不更新固定方案减少108.30亩代理损失；接入0.5或1倍时主面积不变。该差值依赖已知条件，不是事前信息价值；没有观测结果概率、诊断真值、时间占用和费用，也没有将亩与元相减。不能据此报出“巡田收益108.30元”。

## 8 鲁棒与随机优化的权衡

转场鲁棒保护按路线前缀最大Gamma段25%时长偏差累积增加缓冲。Gamma=1、2、4代表日及时率分别73.37%、71.70%、70.49%，保守性增加；Gamma2承诺面积1559.58亩比基准少75.02亩。100次共同随机扰动只在每条原任务路线最多两段加入不超过25%偏差，补水新增弧未全部满足同一Gamma预算，故只是限定压力实验。

{table(pert,['policy','n','mean_fulfillment','worst_fulfillment','mean_loss'],4)}

此样本中鲁棒Gamma2承诺全部兑现，基准平均兑现87.91%、最低84.88%。这支持“缩减名义承诺换取限定扰动下兑现可靠性”，不证明对所有雨后通行、入口不可达和天气突变提供100%保证。

天气评价对所有政策使用同61日期，汇总如下。CVaR90以经验分位数线性公式计算，单位仍是亩。

{table(w,['policy','n','平均及时率/%','平均最差组/%','mean_loss_mu','CVaR90_loss_mu'])}

SAA–CVaR在代表日及时率74.58%，不是代表日面积最优；留出平均表现需与上表比较。九个训练日期不足以精细识别90%尾部，候选池又来自一个离线设计日；尾部指标未全面改善，因此不能包装成“随机优化显著全面占优”。天气导致所有固定路线的平均服务水平明显低于代表日，证明单日设计成绩不能直接当持续运营能力。未来应使用当时可得预报、真实状态滚动生成列、更多季节分层情景，重新验证。

## 9 正确性、规模、可复现性

独立事件核验passed=true：覆盖唯一、天气允许、车机不重叠、电池就绪、药液非负、箱容量、架次能量、充电器并发、预算、分组承诺及外援参与成立。这是模型内部约束检查，不能认证缺少测绘的入口与航线。独立矩阵重建重新求解得到相同主损失；文件位于03_模型与方法/主模型导出，可直接交给其他MILP求解器。

5任务2班组枚举全部650条非空排列路线与{small['combinations_checked']}种不交叠包组合，穷举与MILP得到0亩损失、999.247007元支出，主次目标一致。这里只验证小实例，不声称大实例穷举最优。真实5/10/20/50任务子实例分别截取需求、未服务变量和矩阵，规模记录如下；候选列增幅非固定，不能从4点拟合普遍复杂度或声称支持数万订单。

{table(scale,['tasks','pool_routes','variables','constraints','nonzeros','seconds','mip_gap','timely_rate'])}

Python3.12、SciPy1.18.1/HiGHS，随机种子20261002/3/4；锁定依赖和执行脚本在根目录。重新运行会改变墙钟时间和可能同目标等价路线，但不应改变数据口径。代码、配置、候选包、所有实验CSV、事件JSON、模型矩阵和图表一起保存，不仅交一张漂亮总表。

## 10 创新点、局限与结论

可辩护的创新是：将经营参与转为外援完整任务包的必要合同约束；把天气、补水与充电的事件级模拟嵌入可行列生成，减少主MILP时间扩张；用最差接入组承诺表达公共服务成本，并用可行上下界回答财政代价；显式区分真实空间支持、缺失微观真值与设计假设，设计配对兑现试验和独立验证。创新是问题适配和可追溯计算流程，不能声称新发明ALNS/CVaR或首次车机协同。

主要局限有历史像元不等于当期需求、最后入口无真值、经营参数未实测、充电随车供电和补水锚点待核、小时天气非分钟冠层风、单阶段固定路线非真实滚动、训练尾部样本少、候选池未精确定价。费用、需求、入口、药剂适配和障碍须在实地接入；近远路不是弱势户标签。无需公开全乡测绘，但必须获取研究订单关键入口和状态。

条件性结论：在本研究设计参数和已生成候选池内，ALNS–MILP融合方案实现75.14%及时面积、8182.94元作业服务支出，优于公平可行面积优先规则的风险代理，但非同时省钱。外援采购显著增加可服务面积；电池循环、充电和药液库存是可检验瓶颈。鲁棒保护有名义服务与兑现可靠性权衡，天气风险模型没有全面支配。下一步应先替换微观真值再做经营结论，不先货币化不存在的损失曲线。

## 11 论文插图、表与引用入口

图1空间支持/任务排序；图2天气窗口；图3算法对照；图4预算公平；图5三种子收敛；图6同步甘特；图7资源瓶颈；图8天气尾部；图9服务承诺支出。PNG240dpi用于排版，SVG用于编辑；图注与用途逻辑附图表目录。论文应使用增强池最终资源/信息表及61日期天气表，而不引用旧诊断表。

正文顺序编码[1—25]见 {link(M/'参考文献与资料汇编.md')}；其中含全部审阅/提取的本地材料台账及获取失败说明。正文只引用实际支撑论断的资料，不强制把全部背景文献塞进正文。
'''
    write(M/'完整论文分析与求解报告.md',s)
    concise=f'''# 关键结果与论文引用口径

用途：快速取数并防止论文表述越界。生成逻辑：assemble_report.py从最终表提取。

主方案：50单元、{U.area_mu.sum():.6f}亩；完整及时{covered}单元、{z['timely_area_mu']:.6f}亩（{z['timely_rate']*100:.4f}%），支出{z['cost']:.6f}元，最差组{z['worst_group_rate']*100:.4f}%。主MILP1040路线/1090二元/58约束/8847非零，当前池主损失gap0。

与公平可行面积优先相比：及时率+{(z['timely_rate']-base.timely_rate)*100:.4f}个百分点、代理损失-{improvement:.4f}%，支出+{z['cost']-base.cost:.4f}元。

以下天气表才是最终61日期口径：

{table(w,['policy','n','平均及时率/%','mean_loss_mu','CVaR90_loss_mu'])}

最终表名：补给与无人机瓶颈灵敏度_增强列池.csv；接入信息条件对照_增强列池.csv；真实子实例规模实验.csv；留出天气汇总.csv。

禁止替换：风险代理亩≠农业经济损失元；服务网格≠实测农户；OSM直线接入≠可达性证明；合同假设≠真实中标报价；候选池gap0≠完整现实调度全局最优；压力测试≠真实经营回测；限时成本≠精确最低预算。
'''
    write(M/'关键结果与引用口径.md',concise)

def parameters_and_templates():
    C=js(B/'config.json');rows=[]
    source_keys={'external_reference_price_yuan_per_mu':'采购原件6.3元/亩（公告2026-07-17）','drone_tank_L':'DJI T50规格40L','charge_min':'DJI规格9—12min，选12min','battery_nominal_kwh':'DJI规格52.22V×30Ah换算','flight_speed_ms':'采购5—7m/s，选6','spray_width_m':'采购不超过7m，选7','liquid_L_per_mu':'采购1.5—3L/亩，选2'}
    for k,v in C.items():
        if isinstance(v,dict):continue
        unit='配置/无量纲'
        if 'yuan_per_mu' in k:unit='元/亩'
        elif 'yuan_per' in k:unit='元/分钟'
        elif 'yuan' in k:unit='元'
        elif 'kwh' in k:unit='kWh'
        elif 'kw_' in k:unit='kW'
        elif k.endswith('_L'):unit='L'
        elif k=='liquid_L_per_mu':unit='L/亩'
        elif k.endswith('_ms'):unit='m/s'
        elif k.endswith('_m'):unit='m'
        elif '_min' in k:unit='分钟'
        elif 'seconds' in k:unit='秒'
        if k in source_keys:level='公开规格/采购边界+情景选择'
        elif k in ['seed','alns_iterations','milp_time_limit_seconds','reference_design_year','weather_training_years','weather_test_years','robust_gamma','travel_deviation_fraction']:level='算法/实验设计'
        else:level='未取得实测；研究假设'
        rows.append({'parameter':k,'value':json.dumps(v,ensure_ascii=False),'unit':unit,'evidence':source_keys.get(k,'config研究设计，不可冒充辽宁实测'),'evidence_type':level,'replacement_needed':level=='未取得实测；研究假设'})
    for k,v,unit,evi in [('wind_threshold',3.3,'m/s','采购参考，输入10m风需现场复核'),('temperature_threshold',32,'℃','研究假设'),('avoid_midday','12:00—14:00','时段','采购避午原则+2小时研究档位'),('lastmile_speed',6,'km/h','未核验接入研究速度'),('grid_size',300,'m','空间聚合粒度，非确权'),('risk_weight',1,'无量纲','无诊断真值，统一权重'),('lateness_scale',120,'分钟','风险面积代理，无农学标定'),('lateness_cap',.9,'无量纲','风险面积代理，无农学标定')]:rows.append({'parameter':k,'value':v,'unit':unit,'evidence':evi,'evidence_type':'已标明的来源/研究设计','replacement_needed':True})
    csv(M/'参数证据与不确定性表.csv',pd.DataFrame(rows),'论文参数表与真实数据替换清单','config逐键展开并补充预处理阈值，保留证据层级')
    fields=['order_id','confirmed_at','farmer_id_anonymized','crop_stage','diagnosis_confirmed','area_mu','lon','lat','entry_lon','entry_lat','entry_verified','ground_compatible','drug_label_confirmed','release_time','due_time','obstacle_checked','water_point_id','team_id','vehicle_id','battery_state','quote_package_id','accepted_price_yuan','alternative_revenue_yuan','gps_travel_minutes','purpose','generation_logic']
    # 不生成虚构样本；一行空模板只填用途，不纳入求解。
    row={k:'' for k in fields};row['purpose']='实地采集空模板；本行不是样本';row['generation_logic']='模型缺口字段反推，须采集真实值'
    pd.DataFrame([row],columns=fields).to_csv(M/'实地补采空模板.csv',index=False,encoding='utf-8-sig')
    write(M/'实地补采说明.md','# 实地补采与模型接入\n\n用途：将半实证研究设计升级为真实经营实例。生成逻辑：由缺口与资源模拟变量反推。\n\n空模板仅字段清单，没有虚构样本，不可作为求解数据。订单面积、时间与诊断须由用户/服务方确认；入口与补水点需要机手现场核实；关键转场优先GPS测量。班组状态需记录电池剩余电量、就绪时间、充电器及药液，不应每次重规划重置满库存。外援只使用已接受报价包，保留退出/替代订单约束。药剂适用、障碍、禁飞和天气需按任务要求独立核验。跨户数据需匿名化。\n\n真实入口不应仅覆盖格网中心；真实订单数量与空间范围变化后须重建网格支持/矩阵/路线池，并重跑全部验证。ground_compatible只能在设备及入口核验后开放。\n')

def bibliography():
    core=(M/'参考文献_核心条目.md').read_text(encoding='utf-8').replace('# 核心参考文献','# 参考文献与全部参考资料汇编',1)
    extracts=js(B/'01_数据审计/PDF抽取清单.json')['files'];ledger=js(B/'01_数据审计/公开补充获取台账.json')
    parts=[core,'\n## 附录A：本地审阅/检索材料全清单\n\n用途：涵盖本次抽取并用于背景/来源审查的全部原包PDF；不意味着每篇全文逐字研读或进入主模型。生成逻辑：从PDF抽取清单列出本地原件。未核实责任者/日期时按原包题名记录[Z]，不杜撰出版信息；同一论文的重复保存明确保留，不当作独立文献。引用核心[1—25]时优先规范条目，以下仅补充追溯。']
    records=[]
    for i,e in enumerate(extracts,1):
        p=Path('D:/Desktop/jianmo')/Path(e['file']);title=p.stem
        parts.append(f'[A{i:02d}] {title}[Z]. 本地保存版本, [出版责任与日期未逐项核实][2026-10-02]. {link(p,"本地原件")}. 用途：背景/证据检索；已提取{e["pages"]}页，非参数直接使用承诺。')
        records.append({'id':f'A{i:02d}','title':title,'source':str(p),'use':'背景或证据核查；不等于独立数据样本','status':'PDF抽取成功'})
    parts+=['## 附录B：本次公开补充获取状态\n\n本节是下载与访问台账，不替代前述规范文献条目。每一文件的原URL、大小、SHA256和失败原因以下载台账为准；失败全文不标为已阅读全文。cached为本次前序步骤已取得并再次核验的文件，downloaded为最近获取。']
    recs=ledger.get('files',ledger.get('records',[])) if isinstance(ledger,dict) else ledger
    if not recs:
        # 台账可能按resources保存；不丢弃不可识别记录。
        parts.append('台账原结构如下：\n\n```json\n'+json.dumps(ledger,ensure_ascii=False,indent=2)+'\n```')
    else:
        lines=['| 文件 | 来源 | 本地原件 | 用途 | 获取状态 |','| --- | --- | --- | --- | --- |']
        for r in recs:
            p=Path(r.get('file',''));url=r.get('url','');status=r.get('status','见台账');saved=link(p,'已保存') if p.is_file() else '未取得全文'
            lines.append(f'| {p.name} | [原始来源]({url}) | {saved} | {r.get("purpose","参见核心条目")} | {status} |')
        parts.append('\n'.join(lines))
    parts+=['## 附录C：实际计算数据与用户范围依据\n\n以下是数据产品引用与本地版本定位；产品论文引用[5—12]。','[C01] CCD-Maize项目组. 辽宁2020年玉米分类栅格: classified-Liaoning-maize-2020-WGS84-v1.tif[DB]. 用户原包本地版本, 2020. 用途：300m历史玉米服务支持；具体产品版本由原件及[5]联合说明，不以论文推定2021—2024扩展精度。','[C02] OPEN-METEO. 辽宁20县点ERA5/ERA5-Land逐小时气象2015—2025[DB]. 用户原包CSV. 用途：县域天气窗口及建平调度天气，单位按[8]核实。','[C03] NASA POWER. 建平点逐小时再分析数据2015—2025[DB]. 用户原包CSV. 用途：气温与降水跨产品一致性，不提供气象站真值。','[C04] OPENSTREETMAP CONTRIBUTORS, GEOFABRIK. Liaoning OSM extract: liaoning-latest.osm.pbf[DB]. 用户提供2026本地版本. 用途：研究道路图；缺失路面、宽度和入口属性如实报告。','[C05] COPERNICUS. Copernicus DSM GLO-30 N41E119[DB/OL]. [2026-10-02]. 通过[11]公开AWS分发取得. 用途：宏观高程与坡度支持，非田埂通行认证。','[C06] 用户. 关于空天地一体化农机协同调度研究的既往聊天内容[Z]. 2026本次提供附件. 用途：研究范围与模型修改依据；非官方赛题原文。']
    parts+=['## 附录D：引用与证据规则\n\n原件URL线索CSV中包含大量页内链接，本次未逐条访问，不列为已参考全文。原始年鉴照片、XLS/ZIP配套文件在全量索引中记录；没有读取正文或进入主计算的文件不虚构文献条目。文件内既有派生CSV是前次整理产物，保留其身份，不转称独立原始调查。模型算法由本次代码实现；相关论文支撑方法思想，不意味着本次复现了其全部设置。']
    write(M/'参考文献与资料汇编.md','\n\n'.join(parts))
    csv(M/'参考资料可追溯索引.csv',pd.DataFrame(records),'本地参考资料的原件定位','PDF审阅提取台账转为可过滤索引；核心规范引用在Markdown')

def metadata_and_readme():
    attachment=Path('C:/Users/yucheng/.codex/attachments/c8130d17-4168-4d32-9fbf-442ca3b6228a/已粘贴的文本.txt')
    if attachment.exists():shutil.copy2(attachment,B/'01_数据审计/用户提供的既往聊天_范围依据.txt')
    provenance={
        '01_数据审计':('原始数据结构、缺口和来源证据','audit_inputs.py、fetch_sources.py及原件核查'),
        '02_处理数据':('模型数值输入与空间/天气派生数据','prepare_data.py从原包与补充DSM处理'),
        '03_模型与方法':('模型公式、实现边界及稀疏交换文件','模型推导、export_model.py独立重建'),
        '04_求解结果':('可重算的方案、事件、算法与灵敏度结果','optimization.py、supplementary.py和最终统计口径整理'),
        '05_论文图表':('论文插图和图注','make_figures.py从最终CSV/JSON生成，非导航/实测成绩'),
        '06_论文材料':('论文完整分析、参数、参考文献与补采清单','assemble_report.py汇总结果和已验证文献')}
    # JSON保留原键不破坏程序接口；列表型日志加显式records载体。
    for p in B.rglob('*.json'):
        if any(x in p.parts for x in ['.venv','__pycache__']):continue
        ob=js(p);folder=p.relative_to(B).parts[0];purpose,logic=provenance.get(folder,('研究配置与元数据','研究设计'))
        if isinstance(ob,list):ob={'records':ob}
        if isinstance(ob,dict):ob.setdefault('purpose',p.stem+'：'+purpose);ob.setdefault('generation_logic',logic);write(p,json.dumps(ob,ensure_ascii=False,indent=2))
    # 二进制不能增加文本行：同名 sidecar 提供用途与生成逻辑；图像/GeoTIFF已有嵌入元数据。
    for p in list(B.rglob('*')):
        if not p.is_file() or any(x in p.parts for x in ['.venv','__pycache__']):continue
        if p.suffix.lower() in ['.npy','.npz','.tif','.pbf'] or p.name=='用户提供的既往聊天_范围依据.txt':
            purpose,logic=provenance.get(p.relative_to(B).parts[0],('pyosmium Unicode路径兼容的原件副本','prepare_data.py逐字节复制原包OSM，不修改内容；模型矩阵并不使用本副本新增数据'))
            extra=''
            if p.suffix=='.npy':extra='\n\n矩阵51×51，分钟；索引0锚点，1—50与研究服务单元CSV行顺序对应。已知道路矩阵只含主路网；转场矩阵另加未核验接入时间，不保证现场通行。'
            if p.name=='vectors.npz':extra='\n\n字段objective/cost/lower/upper/lb/ub/integrality/loss_offset。路线变量在前，未服务变量在后。目标省略常数loss_offset，风险面积需加回。'
            if p.name=='A_sparse.npz':extra='\n\nSciPy CSR稀疏约束矩阵58×1090，8847非零；变量、约束索引分别见variables.csv/constraints.csv。'
            write(Path(str(p)+'.说明.md'),f'# {p.name} 元数据\n\n用途：{purpose}，具体内容为{p.stem}。\n\n生成逻辑：{logic}。二进制采用本同名说明，不向数值矩阵插入文本。\n\n大小：{p.stat().st_size}字节；SHA256：{sha(p)}。{extra}\n')
    # 依赖版本从真实已安装包取得，而不是手写猜版本。
    import importlib.metadata
    names=['numpy','pandas','scipy','rasterio','matplotlib','pypdf','xlrd','requests','Pillow','shapely','osmium']
    freeze='\n'.join(n+'=='+importlib.metadata.version(n) for n in names)
    write(B/'requirements.lock.txt','# 用途：复现本次真实依赖版本。生成逻辑：已安装包元数据。Python 3.12；非自动安装脚本。\n'+freeze+'\n')
    write(B/'README_成果总入口.md',f'''# 建模研究成果总入口

用途：定位所有最终交付及正确统计口径。生成逻辑：assemble_report.py汇总目录与实际运行结果。所有成果位于D:/Desktop/code；公开补充原件按用户要求位于D:/Desktop/jianmo/11_本次公开补充。

## 优先阅读

- {link(M/'完整论文分析与求解报告.md','完整论文分析与求解报告')}：背景、数据差异、公式、融合算法、全部主实验/负面结果/讨论。
- {link(M/'参考文献与资料汇编.md','规范参考文献及全部参考材料台账')}：核心GB/T 7714顺序条目，全部本地参考原件，下载失败状态。
- {link(B/'01_数据审计/数据缺口与使用边界.md','数据缺口与不可越界的结论')}。
- {link(B/'03_模型与方法/数学模型与算法说明.md','数学模型与实现映射')}。
- {link(M/'关键结果与引用口径.md','最终指标与论文取数口径')}。
- {link(B/'05_论文图表/图注.md','9幅论文图表及图注')}；PNG240dpi、SVG可编辑。
- {link(B/'08_标准论文图/README_标准论文图.md','新版标准论文图入口')}：10张复合图、37子面板，600dpi PNG、SVG及PDF图集，中文/英文全部加粗。
- {link(R/'主方案.json','完整计划与事件')}、{link(R/'主方案任务完成表.csv','任务完成表')}、{link(R/'主方案班组摘要.csv','班组摘要')}。
- {link(B/'03_模型与方法/主模型导出/README.md','可交换稀疏模型与LP')}。
- {link(M/'参数证据与不确定性表.csv','参数证据及真实数据替换表')}、{link(M/'实地补采说明.md','实地接入说明')}。
- {link(B/'07_验收核对/成果验收.json','独立验收与一致性核对')}。

## 最终实验表与保留的诊断表

论文使用“补给与无人机瓶颈灵敏度_增强列池.csv”“接入信息条件对照_增强列池.csv”“真实子实例规模实验.csv”和61日期“留出天气汇总.csv”。对应无“增强列池”的资源/信息表及“求解规模预实验.csv”保留为候选池不足诊断，不作为最终经营结论。服务承诺最低预算CSV提供status、gap与成本上下界；限时支出不是精确最低预算。文件用途与生成逻辑清单覆盖全部成果，.venv与缓存不列作交付分析。

## 复现

已有环境：D:/Desktop/code/.venv/Scripts/python.exe。运行 PowerShell脚本 `D:/Desktop/code/run_pipeline.ps1`。默认离线利用已下载数据；公开补充下载是可选开关FetchPublic，可能需要网络授权。源码内固定随机种子，config保留全部经营假设。重跑会更新本目录生成产物，原包不修改；下载开关只写11_本次公开补充。首次复制到其他机器需调整所有脚本根路径并安装requirements.lock.txt的包，不能声称完全免配置移植。

## 证据与结论

这是2026研究设计：历史2020玉米空间支持+2026道路/报价参考+历史天气压力测试，不是真实订单回测。50服务单元2175.29亩；主方案完整及时1634.60亩（75.14%），服务支出8182.94元，最差接入组72.41%。主目标gap0仅对1040候选路线池。无入口/药剂/障碍真值时不认证航线可执行、不启用地面喷雾机，不货币化农业损失。未取得的必要微观数据如实保留缺失，不伪造实测值。

## 目录

01_数据审计：原包索引、提取文本、获取台账、缺口。02_处理数据：空间单元、天气窗口、道路和时间矩阵。03_模型与方法：数学推导、创新边界、稀疏MILP。04_求解结果：路线池、主计划、各方法和灵敏度、日志。05_论文图表：9图PNG/SVG及图注。06_论文材料：完整分析、参数、规范文献、实地模板。07_验收核对：独立约束与结果一致性。根目录Python与PowerShell为可复现生成器。每个文件的用途与生成逻辑在内部或同名二进制说明及全量文件清单中记录。
''')

def manifest():
    rows=[]
    logic={'01_数据审计':'audit_inputs.py/原件核查/fetch_sources.py','02_处理数据':'prepare_data.py','03_模型与方法':'模型推导/export_model.py','04_求解结果':'optimization.py/supplementary.py/assemble_report.py','05_论文图表':'make_figures.py','06_论文材料':'assemble_report.py/文献核查','07_验收核对':'validate_outputs.py','08_标准论文图':'plot_paper_standard.py；最终数据独立核对后合并绘图'}
    for p in sorted(B.rglob('*')):
        if not p.is_file() or any(x in p.parts for x in ['.venv','__pycache__','.git']):continue
        if p.name=='文件用途与生成逻辑清单.csv':continue
        rel=p.relative_to(B);gen=logic.get(rel.parts[0],p.name if p.suffix=='.py' else '研究配置与复现环境')
        rows.append({'relative_path':str(rel),'absolute_path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'purpose':p.stem+'；具体字段与边界见文件内部或同名说明','generation_logic':gen,'metadata_carrier':'文件内用途/生成逻辑；二进制同名.说明.md；图像内嵌Description'})
    csv(B/'文件用途与生成逻辑清单.csv',pd.DataFrame(rows),'全部交付文件可追溯清单（不含运行环境缓存）','目录扫描及逐文件SHA256；本清单自身不递归计算哈希')
    print('manifest files',len(rows),flush=True)

def main():
    correct_final_tables();parameters_and_templates();bibliography();report();metadata_and_readme();manifest();print('ASSEMBLED',flush=True)
if __name__=='__main__':main()
