"""用途：从论文源稿及已核验结果生成匿名参赛Word稿和规范参考文献。
生成逻辑：CSV/JSON只读取数；正文引用按首次出现重排；原生OMML公式；
Word字段目录、图表清单和页码由后续Word排版脚本更新。运行使用工作区捆绑Python。
"""
from pathlib import Path
from copy import deepcopy
import csv, hashlib, json, re
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
from docx.enum.section import WD_SECTION_START, WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

B=Path('D:/Desktop/code'); O=B/'10_可视化增强论文'; R=B/'04_求解结果'
SRC=O/'论文正文源稿.md'; OUT=O/'空天地信息支持下辽宁丘陵玉米植保协同调度优化研究_匿名可视化增强版.docx'
WIDTH=14.66
source_hashes={}
def readcsv(name):
    p=R/name; source_hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def n(v,d=2):
    return '—' if v in ('',None) else f'{float(v):.{d}f}'
def pct(v,d=2):return n(float(v)*100,d) if v not in ('',None) else '—'
def new(tag,attrs=None):
    e=OxmlElement(tag)
    for k,v in (attrs or {}).items():e.set(qn(k),str(v))
    return e
def mathrun(text):
    r=new('m:r');p=new('w:rPr');p.append(new('w:rFonts',{'w:ascii':'Cambria Math','w:hAnsi':'Cambria Math'}));r.append(p)
    t=new('m:t');t.text=text;r.append(t);return r
def mathseq(*items):
    out=[]
    for x in items:
        if isinstance(x,str):out.append(mathrun(x))
        elif isinstance(x,list):out.extend(x)
        else:out.append(x)
    return out
def sub(base,suffix):
    e=new('m:sSub');a=new('m:e');a.extend(mathseq(base));b=new('m:sub');b.extend(mathseq(suffix));e.extend([a,b]);return e
def sup(base,power):
    e=new('m:sSup');a=new('m:e');a.extend(mathseq(base));b=new('m:sup');b.extend(mathseq(power));e.extend([a,b]);return e
def frac(a,b):
    e=new('m:f');x=new('m:num');x.extend(mathseq(a));y=new('m:den');y.extend(mathseq(b));e.extend([x,y]);return e
def sm(lo,expr,hi=None):
    e=new('m:nary');p=new('m:naryPr');p.append(new('m:chr',{'m:val':'∑'}));p.append(new('m:limLoc',{'m:val':'subSup'}))
    if hi is None:p.append(new('m:supHide',{'m:val':1}))
    e.append(p);s=new('m:sub');s.extend(mathseq(lo));u=new('m:sup');u.extend(mathseq(hi or ''));body=new('m:e');body.extend(mathseq(expr));e.extend([s,u,body]);return e
def seq(*x):return mathseq(*x)
def equations():
    return {
    'q':seq(sub('q','i'),'(C)=min{0.9,',frac(seq('max(0,C−',sub('d','i'),')'),'120'),'}'),
    'loss':seq(sub('F','T'),'=',sm('i∈I',seq(sub('w','i'),sub('A','i'),sub('u','i'))),'+',sm('p∈P',sm('i∈I',seq(sub('w','i'),sub('A','i'),sub('a','ip'),sub('q','i'),'(',sub('C','ip'),')',sub('λ','p'))))),
    'cost':seq('min ',sub('F','C'),'=',sm('p∈P',seq(sub('c','p'),sub('λ','p')))),
    'cover':seq(sm('p∈P',seq(sub('a','ip'),sub('λ','p'))),'+',sub('u','i'),'=1,  ∀i∈I'),
    'team':seq(sm(seq('p∈',sub('P','r')),sub('λ','p')),'≤1,  ∀r∈R'),
    'budget':seq(sm('p∈P',seq(sub('c','p'),sub('λ','p'))),'≤B'),
    'fair':seq(sm('p∈P',sm(seq('i∈',sub('I','g')),seq(sub('A','i'),sub('o','ip'),sub('λ','p')))),'≥',sub('ρ','g'),sm(seq('i∈',sub('I','g')),sub('A','i')),',  ∀g∈G'),
    'binary':seq(sub('λ','p'),',',sub('u','i'),'∈{0,1},  ∀p∈P, i∈I'),
    'lex':seq(sub('F','T'),'≤',sup(sub('F','T'),'∗'),'+',sup('10','−5')),
    'rate':seq('η=vbφ·',frac('3600','2000/3'),'=147.42  (亩/小时)'),
    'sortie':seq(sub('A','q'),'≤',frac(sub('Q','tank'),'l'),',  ',frac(seq('60',sub('A','q')),'η'),'≤',sub('t','max'),',  ',frac(seq('P',sub('A','q')),'η'),'+',sub('E','reserve'),'≤',sub('E','usable')),
    'contract':seq(sub('P','p'),'=max{250+6.3',sm('i∈I',seq(sub('A','i'),sub('a','ip'))),', ',sub('K','p'),'+150}'),
    'dp':seq('D(S,j)=',sub('min','i∈S∖{j}'),'{D(S∖{j},i)+',sub('τ','ij'),'}'),
    'robust':seq(sub('β','J'),'(Γ)=max{',sm('j∈J',seq('0.25',sub('τ','j'),sub('z','j'))),':0≤',sub('z','j'),'≤1,',sm('j∈J',sub('z','j')),'≤Γ}'),
    'scenario':seq(sub('L','s'),'=',sub('A','total'),'−',sm('p∈P',seq(sup(sub('b','p'),'s'),sub('λ','p')))),
    'cvar':seq('min ',frac('1','S'),sm('s=1',sub('L','s'),'S'),'+0.25[η+',frac('1','(1−0.9)S'),sm('s=1',sub('z','s'),'S'),']'),
    'excess':seq(sub('z','s'),'≥',sub('L','s'),'−η,  ',sub('z','s'),'≥0,  s=1,…,S'),
    }

tables={}
def tabledef(key,title,heads,rows,widths):tables[key]={'title':title,'heads':heads,'rows':rows,'widths':widths}
tabledef('data','主要数据来源及模型用途',['资料','时间或粒度','模型用途与证据边界'],[
['统计公报与技术意见','2025年统计；2026年意见','农业背景；不反推单元订单或损失'],
['玉米分类及土地覆盖','2020年玉米；栅格产品','300m聚合空间支持；非当期确权地块'],
['OSM道路与补充DSM','2026年道路；约30m高程','转场网络、宏观地形；入口待核验'],
['ERA5与ERA5-Land','2015—2025年逐小时','适作窗口与历史压力情景'],
['设备规格与采购资料','T50规格；2026年公告','技术边界与6.3元/亩价格参考'],
['订单与经营参数','微观真值缺失','情景配置及敏感性分析，见附录1'],
],[3.0,3.3,8.36])
tabledef('symbols','核心符号及量纲',['符号','含义','量纲或取值'],[
['I，R，G','服务单元、班组及接入组集合','集合'],['Pᵣ，P','班组可行包及全部包集合','集合'],
['Aᵢ，wᵢ','单元面积、风险权重','亩；基准权重1'],['dᵢ，Cᵢₚ','推荐及实际完整完成时刻','自06:00起算的分钟'],
['aᵢₚ，oᵢₚ','完整及及时完整覆盖标识','0或1'],['cₚ，Kₚ，Pₚ','包支出、履约成本、外援支付','元'],
['B，ρg','预算、分组最低及时率','元；[0,1]'],['λₚ，uᵢ','选择包、未完整服务变量','二元决策变量'],
],[2.7,7.0,4.96])
teams=readcsv('主方案班组摘要.csv')
tabledef('teams','主方案班组任务与支出',['班组','单元数','面积/亩','支出/元','架次','补水次数'],[[x['班组'],x['单元数'],n(x['完整面积/亩']),n(x['支出/元']),x['飞行架次'],x['锚点补水次数']] for x in teams],[2,1.7,3,3.3,2,2.66])
algs=readcsv('算法对照.csv'); amap={x['algorithm']:x for x in algs if x['algorithm']!='ALNS'};best=min([x for x in algs if x['algorithm']=='ALNS'],key=lambda x:float(x['risk_proxy_loss_mu']))
selected=[('最近优先*',amap['nearest']),('面积优先',amap['largest_first']),('效益密度',amap['benefit_density']),('ALNS最好单次',best),('融合MILP',amap['ALNS_pool_MILP'])]
tabledef('algorithms','基准输入下的算法比较',['算法','及时率/%','风险/亩','支出/元','最差组/%'],[[name,pct(x['timely_rate']),n(x['risk_proxy_loss_mu']),n(x['cost']),pct(x['worst_group_rate'])] for name,x in selected],[3.6,2.6,2.8,2.86,2.8])
c=readcsv('服务承诺最低预算.csv')
tabledef('commitment','分组最低服务承诺与可行支出界',['承诺/%','下界/元','上界/元','间隙/%','求解状态'],[[pct(x['minimum_timely_rate'],0),n(x['cost_lower_bound_yuan']),n(x['cost_upper_bound_yuan']),pct(x['mip_gap']),{'0':'达到容差','1':'限时可行','2':'当前池不可行'}[x['status']]] for x in c],[2,3,3,2.2,4.46])
w=readcsv('留出天气汇总.csv');plabel={'nominal':'基准','robust_gamma2':'鲁棒Γ=2','SAA_CVaR':'SAA–CVaR'}
tabledef('weather','61日留出天气的政策表现',['政策','平均及时率/%','平均风险/亩','CVaR90/亩','平均最差组/%'],[[plabel[x['policy']],pct(x['mean_timely_rate']),n(x['mean_loss_mu']),n(x['CVaR90_loss_mu']),pct(x['mean_worst_group_rate'])] for x in w],[2.8,2.9,3.0,3,2.96])
tabledef('parameters','主要研究参数及来源等级',['参数','基准值','依据'],[
['自有与外援班组','3支与2支','研究设定'],['每班无人机/电池/充电器','1架/3块/1台','研究设定'],['预算/最差组承诺','12000元/30%','公共采购情景'],['外援到达/推荐完成/返回','07:00/16:00/18:00','研究设定'],['药箱容量/额定电池','40L/1.5666kWh','T50规格；电压×容量'],['速度/喷幅/耗液率','6m/s/7m/2L每亩','采购边界内研究档位'],['效率系数/飞行功率','0.65/5.4kW','未实测，待校准'],['飞行上限/保留能量','10min/0.2kWh','研究设定'],['电量可用比例','0.8','研究设定'],['充电/冷却/架次周转','12/2/2min','充电规格参考，其余假设'],['准备/补水时间','5/15min','研究设定'],['车载药液','600L','研究设定'],['固定/面积运行费用','300元/2元每亩','研究设定'],['转场/人员费用','1/0.5元每分钟','研究设定'],['外援报价/进场/机会收益','6.3元每亩/250元/150元','报价参考，其余研究设定'],['转场偏差界/保护预算','25%/Γ=2','压力试验设定'],['迟延尺度/惩罚上限','120min/0.9','未标定农业损失'],['天气温度/避午区间','低于32℃/12:00—14:00','研究档位'],
],[4.6,5.0,5.06])
d=readcsv('动态规划子路线实验.csv')
tabledef('dp','固定任务集合的动态规划排序检查',['班组','任务数','状态数','排序时间/min','原转场/min','资源可行'],[[x['team'],x['n'],x['states'],n(x['tsp_minutes']),n(x['original_travel_minutes']),'是' if x['resource_feasible'].lower()=='true' else '否'] for x in d],[2,1.5,1.8,3.1,3.1,3.16])
s=readcsv('真实子实例规模实验.csv')
tabledef('scale','真实子实例的主问题规模',['任务数','路线数','变量数','约束数','非零系数','耗时/s'],[[x['tasks'],x['pool_routes'],x['variables'],x['constraints'],x['nonzeros'],n(x['seconds'],3)] for x in s],[2,2.5,2.5,2.4,2.7,2.56])
rr=readcsv('补给与无人机瓶颈灵敏度_增强列池.csv');rnames={'batteries_per_team':'电池/块','charge_min':'充电/min','vehicle_liquid_capacity_L':'液量/L','drones_per_team':'无人机/架'}
tabledef('resources','增强候选池的单因素资源试验',['参数','档位','路线数','及时率/%','支出/元'],[[rnames[x['parameter']],n(x['value'],0),x['pool_routes'],pct(x['timely_rate']),n(x['cost'])] for x in rr],[3.4,2.4,2.8,3,3.06])
ii=readcsv('外援参与制度对照.csv');ilabel={'owned_only':'仅自有','contract_participation':'合同参与','ideal_centralized':'理想集中'}
tabledef('institutions','外援制度比较',['制度','及时率/%','支出/元','风险/亩'],[[ilabel[x['institution']],pct(x['timely_rate']),n(x['cost']),n(x['risk_proxy_loss_mu'])] for x in ii],[4.4,3.4,3.4,3.46])
info=readcsv('接入信息条件对照_增强列池.csv')
tabledef('information','接入信息条件与重新优化',['接入倍数','固定方案风险/亩','重优化风险/亩','条件收益/亩'],[[n(x['connection_factor'],1),n(x['blind_loss_mu']),n(x['risk_proxy_loss_mu']),n(x['conditional_gain_mu'])] for x in info],[2.6,4.2,4.0,3.86])
pr=readcsv('转场扰动压力汇总.csv')
tabledef('perturbation','100组配对转场扰动的兑现表现',['政策','样本数','平均兑现/%','最差兑现/%','平均风险/亩'],[[plabel[x['policy']],x['n'],pct(x['mean_fulfillment']),pct(x['worst_fulfillment']),n(x['mean_loss'])] for x in pr],[3,2,3.2,3.2,3.26])
tasks=readcsv('主方案任务完成表.csv')
tabledef('tasks','主方案完整服务任务及完成时刻',['单元','班组','面积/亩','完成时刻','及时完成'],[[x['unit_id'],x['team'],n(x['area_mu']),x['clock_time'],'是' if x['on_time'].lower()=='true' else '否'] for x in tasks],[2.6,2.6,3.4,3.4,2.66])

text=SRC.read_text(encoding='utf-8')
added_audit=json.loads((O/'新增图表/新增图表核对.json').read_text(encoding='utf-8'))
assert added_audit['passed']
source_hashes.update(added_audit['source_sha256'])
ref_order=[]
def renumber(m):
    nums=[]
    for v in m.group(1).split(','):
        if '-' in v:
            a,b=map(int,v.split('-'));nums.extend(range(a,b+1))
        else:nums.append(int(v))
    out=[]
    for v in nums:
        if v not in ref_order:ref_order.append(v)
        out.append(str(ref_order.index(v)+1))
    return '['+','.join(out)+']'
text=re.sub(r'\[(\d+(?:[-,]\d+)*)\]',renumber,text)
ref_source=(B/'06_论文材料/参考文献_核心条目.md').read_text(encoding='utf-8')
refs={}
for line in ref_source.splitlines():
    m=re.match(r'\[(\d+)\] (.*)',line)
    if not m:continue
    entry=m.group(2).split(' 用途：')[0]
    entry=re.sub(r'\[[^\]]+\]\((D:/[^)]+)\)\.?','',entry)
    entry=re.sub(r'\[[^\]]+\]\((https?://[^)]+)\)',r'\1',entry).strip()
    refs[int(m.group(1))]=entry
reference_lines=[f'[{i+1}] {refs[v]}' for i,v in enumerate(ref_order)]
(O/'参考文献_论文引用版.md').write_text('# 论文参考文献\n\n用途：与匿名参赛稿正文引用一一对应。生成逻辑：依据已有核对资料，按正文首次出现顺序重排编号；完整资料台账另存06_论文材料。\n\n'+'\n\n'.join(reference_lines),encoding='utf-8')

doc=Document(); props=doc.core_properties
props.title='空天地信息支持下辽宁丘陵玉米植保协同调度优化研究';props.subject='辽宁省大学生农业经济建模大赛最优化建模类';props.author='';props.last_modified_by='';props.comments=''
def fontstyle(st,east='宋体',size=14,bold=False):
    st.font.name='Times New Roman';st.font.size=Pt(size);st.font.bold=bold;st.font.color.rgb=RGBColor(0,0,0)
    rp=st.element.get_or_add_rPr();rf=rp.find(qn('w:rFonts'))
    if rf is None:rf=new('w:rFonts');rp.insert(0,rf)
    for attr in list(rf.attrib):
        if attr.lower().endswith('theme'):del rf.attrib[attr]
    for k,v in [('w:eastAsia',east),('w:ascii','Times New Roman'),('w:hAnsi','Times New Roman')]:rf.set(qn(k),v)
    lang=rp.find(qn('w:lang'))
    if lang is None:lang=new('w:lang');rp.append(lang)
    lang.set(qn('w:eastAsia'),'zh-CN');lang.set(qn('w:val'),'en-US')
    pf=st.paragraph_format;pf.line_spacing=1.25;pf.space_before=Pt(size*.5);pf.space_after=Pt(0)
fontstyle(doc.styles['Normal']);doc.styles['Normal'].paragraph_format.first_line_indent=Pt(28)
for name,size in [('Heading 1',15),('Heading 2',14),('Heading 3',14)]:
    fontstyle(doc.styles[name],'黑体' if name!='Heading 3' else '宋体',size);doc.styles[name].paragraph_format.first_line_indent=Pt(0);doc.styles[name].paragraph_format.keep_with_next=True
fontstyle(doc.styles['Title'],'宋体',16,True);doc.styles['Title'].paragraph_format.space_before=Pt(0);doc.styles['Title'].paragraph_format.line_spacing=1
fontstyle(doc.styles['Caption'],'宋体',12,True);doc.styles['Caption'].paragraph_format.first_line_indent=Pt(0)
# Remove bundled template decoration, including Title's inherited blue rule.
for st in doc.styles:
    for border in list(st.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
for nm,size in [('Front Title',14),('Abstract',12),('Reference',12),('Table Text',10.5),('TOC 1',12),('TOC 2',10.5),('Figure List',12),('Equation',12)]:
    st=doc.styles.add_style(nm,1) if nm not in doc.styles else doc.styles[nm]
    fontstyle(st,'黑体' if nm=='Front Title' else '宋体',size,nm=='Table Text');st.paragraph_format.first_line_indent=Pt(0 if nm!='Abstract' else 24)
doc.styles['Reference'].paragraph_format.left_indent=Pt(24);doc.styles['Reference'].paragraph_format.first_line_indent=Pt(-24)
doc.styles['Table Text'].paragraph_format.line_spacing=1;doc.styles['Table Text'].paragraph_format.space_before=Pt(3);doc.styles['Table Text'].paragraph_format.space_after=Pt(3)
for nm in ['TOC 1','TOC 2','Figure List']:
    doc.styles[nm].paragraph_format.space_before=Pt(2);doc.styles[nm].paragraph_format.space_after=Pt(0)
    doc.styles[nm].paragraph_format.tab_stops.add_tab_stop(Cm(WIDTH),WD_TAB_ALIGNMENT.RIGHT)
doc.styles['TOC 2'].paragraph_format.left_indent=Pt(14)

def page_setup(s):
    s.page_width=Cm(21);s.page_height=Cm(29.7);s.top_margin=Cm(2.54);s.bottom_margin=Cm(2.54);s.left_margin=Cm(3.17);s.right_margin=Cm(3.17);s.header_distance=Cm(1.2);s.footer_distance=Cm(1.25)
page_setup(doc.sections[0])
settings=doc.settings.element;settings.append(new('w:updateFields',{'w:val':'true'}))
def field(p,instruction,cache=''):
    r=new('w:r');r.append(new('w:fldChar',{'w:fldCharType':'begin'}));p._p.append(r)
    r=new('w:r');t=new('w:instrText');t.set(qn('xml:space'),'preserve');t.text=' '+instruction+' ';r.append(t);p._p.append(r)
    r=new('w:r');r.append(new('w:fldChar',{'w:fldCharType':'separate'}));p._p.append(r)
    p.add_run(cache)
    r=new('w:r');r.append(new('w:fldChar',{'w:fldCharType':'end'}));p._p.append(r)
def bookmark(p,name,id):
    p._p.insert(0,new('w:bookmarkStart',{'w:id':id,'w:name':name}));p._p.append(new('w:bookmarkEnd',{'w:id':id}))
def footer(s,fmt='decimal',start=1):
    s.footer.is_linked_to_previous=False;p=s.footer.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0)
    field(p,'PAGE','1')
    for old in list(s._sectPr.findall(qn('w:pgNumType'))):s._sectPr.remove(old)
    num=new('w:pgNumType',{'w:fmt':fmt,'w:start':start});s._sectPr.append(num)
    for r in p.runs:r.font.size=Pt(10.5)
def fronttitle(t):
    p=doc.add_paragraph(t,'Front Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;return p
def rich(p,t):
    # Numeric citations are superscript; document metadata never contains team identity.
    for part in re.split(r'(\[\d+(?:,\d+)*\])',t):
        if not part:continue
        r=p.add_run(part)
        if re.fullmatch(r'\[\d+(?:,\d+)*\]',part):r.font.superscript=True;r.font.size=Pt(10)
    return p
def para(t,style=None):return rich(doc.add_paragraph(style=style),t)

p=doc.add_paragraph('辽宁省大学生农业经济建模大赛','Front Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Cm(2)
p=doc.add_paragraph('空天地信息支持下辽宁丘陵\n玉米植保协同调度优化研究','Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Cm(1.5);p.paragraph_format.space_after=Cm(1)
p=doc.add_paragraph('基于合同任务包的多目标混合整数规划与风险决策','Front Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
for t in ['参赛类别：最优化建模类','学校：________________________','队名：________________________','成员：________________________','指导教师：____________________','提交日期：____________________']:
    p=doc.add_paragraph(t);p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.left_indent=Cm(2.3);p.paragraph_format.space_before=Pt(16)
s=doc.add_section(WD_SECTION_START.NEW_PAGE);page_setup(s);footer(s,'upperRoman',1)
fronttitle('目录');field(doc.add_paragraph(),'TOC \\o "1-2" \\h \\z \\u','目录正在生成')
doc.add_page_break();fronttitle('表格和插图清单');fronttitle('表格清单');field(doc.add_paragraph(),'TOC \\h \\z \\c "表"','表格清单正在生成')
doc.add_page_break();fronttitle('插图清单');field(doc.add_paragraph(),'TOC \\h \\z \\c "图"','插图清单正在生成')

table_count=0;eq_count=0;fig_records=[];table_records=[];eq_records=[];body_started=False;ref_added=False;main_start_p=None;main_end_p=None
def addtable(key):
    global table_count
    table_count+=1;t=tables[key]
    p=doc.add_paragraph(style='Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True
    p.add_run('表');field(p,'SEQ 表 \\* ARABIC',str(table_count));p.add_run('  '+t['title']);bookmark(p,f'table_{table_count}',200+table_count)
    tb=doc.add_table(rows=1,cols=len(t['heads']));tb.alignment=WD_TABLE_ALIGNMENT.CENTER;tb.autofit=False
    tbpr=tb._tbl.tblPr;borders=new('w:tblBorders')
    for side in ['top','left','bottom','right','insideH','insideV']:borders.append(new('w:'+side,{'w:val':'single','w:sz':4,'w:color':'D9D9D9'}))
    tbpr.append(borders);marg=new('w:tblCellMar')
    for side in ['top','bottom','left','right']:marg.append(new('w:'+side,{'w:w':70 if side in ['top','bottom'] else 90,'w:type':'dxa'}))
    tbpr.append(marg)
    for col,width in zip(tb.columns,t['widths']):col.width=Cm(width)
    for cell,txt,width in zip(tb.rows[0].cells,t['heads'],t['widths']):cell.width=Cm(width);cell.text=str(txt)
    tb.rows[0]._tr.get_or_add_trPr().append(new('w:tblHeader'))
    for values in t['rows']:
        cells=tb.add_row().cells
        for cell,txt,width in zip(cells,values,t['widths']):cell.width=Cm(width);cell.text=str(txt)
    for i,row in enumerate(tb.rows):
        row._tr.get_or_add_trPr().append(new('w:cantSplit'))
        for j,cell in enumerate(row.cells):
            cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if i==0:cell._tc.get_or_add_tcPr().append(new('w:shd',{'w:fill':'E7E6E6'}))
            for p in cell.paragraphs:
                p.style='Table Text';p.alignment=WD_ALIGN_PARAGRAPH.CENTER if i==0 or key not in ['data','symbols','parameters'] else WD_ALIGN_PARAGRAPH.LEFT
                if i==0 or (key in ['algorithms','dp'] and i<len(tb.rows)-1):p.paragraph_format.keep_with_next=True
                for r in p.runs:r.font.bold=True
    table_records.append({'number':table_count,'key':key,'title':t['title'],'rows':len(t['rows'])})
    if key=='algorithms':para('注：*最近优先未达到30%最差组承诺；ALNS为三次运行中所选实际最好方案。','Reference')
def addfig(no,old,title):
    root=O/'新增图表/PNG_600dpi' if int(old)>10 else B/'08_标准论文图/PNG_600dpi'
    path=next(root.glob(f'Fig_{old}_*.png'))
    landscape=old=='04'
    if landscape:
        s=doc.add_section(WD_SECTION_START.NEW_PAGE);page_setup(s);s.orientation=WD_ORIENT.LANDSCAPE;s.page_width=Cm(29.7);s.page_height=Cm(21)
        # Continue Arabic numbering across orientation change.
        for pg in list(s._sectPr.findall(qn('w:pgNumType'))):s._sectPr.remove(pg)
        s._sectPr.append(new('w:pgNumType',{'w:fmt':'decimal'}))
    p=doc.add_paragraph();p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_before=Pt(7);p.paragraph_format.keep_with_next=True;p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    shape=p.add_run().add_picture(str(path),width=Cm(23.0 if landscape else 14.5));shape._inline.docPr.set('descr',title)
    p=doc.add_paragraph(style='Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run('图');field(p,'SEQ 图 \\* ARABIC',str(no));p.add_run('  '+title);bookmark(p,f'figure_{no}',100+no)
    fig_records.append({'number':no,'source':str(path),'title':title,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    if landscape:
        s=doc.add_section(WD_SECTION_START.NEW_PAGE);page_setup(s)
        for pg in list(s._sectPr.findall(qn('w:pgNumType'))):s._sectPr.remove(pg)
        s._sectPr.append(new('w:pgNumType',{'w:fmt':'decimal'}))
def addeq(key):
    global eq_count
    eq_count+=1;p=doc.add_paragraph(style='Equation');p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_before=Pt(8);p.paragraph_format.space_after=Pt(8)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(6.75),WD_TAB_ALIGNMENT.CENTER);p.paragraph_format.tab_stops.add_tab_stop(Cm(WIDTH),WD_TAB_ALIGNMENT.RIGHT)
    p.add_run('\t');m=new('m:oMath');m.extend(deepcopy(equations()[key]));p._p.append(m);p.add_run(f'\t（{eq_count}）');bookmark(p,f'equation_{eq_count}',300+eq_count)
    eq_records.append({'number':eq_count,'key':key})
def references():
    doc.add_page_break();p=doc.add_heading('参考文献',1)
    for r in p.runs:r.font.size=Pt(14)
    for x in reference_lines:para(x,'Reference')

for line in text.splitlines()[1:]:
    line=line.strip()
    if not line:continue
    if line=='<!-- BODY_START -->':
        s=doc.add_section(WD_SECTION_START.NEW_PAGE);page_setup(s);footer(s,'decimal',1);body_started=True;continue
    if line=='<!-- BODY_END -->':
        main_end_p=doc.paragraphs[-1];bookmark(main_end_p,'body_end',901);references();ref_added=True;continue
    if line.startswith('@@TABLE:'):addtable(line.split(':')[1].replace('@@',''));continue
    if line.startswith('@@FIG:'):
        _,num,old,title=line[:-2].split(':',3);addfig(int(num),old,title);continue
    if line.startswith('@@EQ:'):addeq(line.split(':')[1].replace('@@',''));continue
    if line.startswith('## '):
        title=line[3:]
        if title in ['中文摘要','English Abstract']:
            doc.add_page_break();p=doc.add_heading('中文摘要' if title=='中文摘要' else '英文摘要',1);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:r.font.size=Pt(14)
            continue
        if title.startswith('附录') or title=='致谢':doc.add_page_break()
        p=doc.add_heading(title,1)
        if body_started and main_start_p is None:main_start_p=p;bookmark(p,'body_start',900)
        continue
    if line.startswith('### '):doc.add_heading(line[4:],2);continue
    p=para(line,'Abstract' if not body_started else None)
    if line.startswith(('关键词：','Keywords:')):p.paragraph_format.first_line_indent=Pt(0)

assert table_count==14 and len(fig_records)==15 and eq_count==17
doc.save(OUT)
body=text.split('<!-- BODY_START -->')[1].split('<!-- BODY_END -->')[0]
prose=re.sub(r'@@.*?@@','',body);prose=re.sub(r'(?m)^#+\s*','',prose)
body_chars=len(re.sub(r'\s','',prose))
manifest={'purpose':'参赛论文内容结构、取数及格式生成核验','generation_logic':'只读求解CSV/JSON；引用首次出现重排；按用户规范生成Word及OMML','title':props.title,'body_prose_nonspace_characters':body_chars,'body_han_characters':len(re.findall(r'[\u4e00-\u9fff]',prose)),'source_sha256':source_hashes,'figures':fig_records,'tables':table_records,'equations':eq_records,'references_old_to_new':{str(v):i+1 for i,v in enumerate(ref_order)},'reference_count':len(reference_lines),'word_file':str(OUT),'visual_qa':'待Word分页、渲染与逐页检查'}
(O/'论文生成核对.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
expanded=text
for key,t in tables.items():
    tab='| '+' | '.join(t['heads'])+' |\n| '+' | '.join(['---']*len(t['heads']))+' |\n'+'\n'.join('| '+' | '.join(map(str,x))+' |' for x in t['rows'])
    expanded=expanded.replace(f'@@TABLE:{key}@@',tab)
for f in fig_records:
    expanded=re.sub(r'@@FIG:'+str(f['number'])+r':\d+:.*?@@',lambda m:f"![图{f['number']}  {f['title']}]({Path(f['source']).as_posix()})",expanded)
for e in eq_records:
    formula=''.join(x.text or '' for node in equations()[e['key']] for x in node.iter(qn('m:t')))
    expanded=expanded.replace(f"@@EQ:{e['key']}@@",f"公式（{e['number']}）见Word原生公式。线性检索文本：{formula}")
expanded=expanded.replace('<!-- BODY_END -->','\n## 参考文献\n\n'+'\n\n'.join(reference_lines)).replace('<!-- BODY_START -->','')
(O/'论文全文_便于检索.md').write_text(expanded,encoding='utf-8')
print(json.dumps({'docx':str(OUT),'body_prose_nonspace':body_chars,'tables':table_count,'figures':len(fig_records),'equations':eq_count,'references':len(ref_order)},ensure_ascii=False))
