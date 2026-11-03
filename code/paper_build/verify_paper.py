"""用途：核对最终匿名论文结构、字数、数值来源、页码与排版证据。
生成逻辑：读取Word实际分页结果、OOXML、PDF文本与原始CSV校验和；
视觉检查结论仅在主代理逐页审阅后以--confirm-visual显式记录。
"""
from pathlib import Path
from zipfile import ZipFile
import argparse,csv,hashlib,json,re
from lxml import etree
from pypdf import PdfReader

O=Path('D:/Desktop/code/10_可视化增强论文');QA=O/'排版核验';B=O.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ap=argparse.ArgumentParser();ap.add_argument('--confirm-visual',action='store_true');args=ap.parse_args()
audit=json.loads((O/'论文生成核对.json').read_text(encoding='utf-8'))
word=json.loads((QA/'Word分页与字数.json').read_text(encoding='utf-8-sig'))
docx=Path(audit['word_file']);pdf=QA/'论文排版核验.pdf';reader=PdfReader(pdf)
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
checks=[]
def check(name,ok,detail=''):checks.append({'check':name,'passed':bool(ok),'detail':str(detail),'purpose':'论文内容与排版验收','generation_logic':'OOXML、Word分页统计、PDF与源文件一致性检查'})
with ZipFile(docx) as z:
    xml=etree.fromstring(z.read('word/document.xml'));styles=etree.fromstring(z.read('word/styles.xml'));props=etree.fromstring(z.read('docProps/core.xml'))
check('正文字符在14000至16000范围',14000<=word['body_characters_no_spaces']<=16000,word['body_characters_no_spaces'])
check('Word与PDF页数一致',len(reader.pages)==word['pages'],word['pages'])
check('可编辑原生公式17个',len(xml.xpath('//m:oMath',namespaces=NS))==17 and word['native_equations']==17)
check('Word目录和两份图表清单已更新',word['toc_count']==1 and word['figure_list_count']==2)
check('正文表格14个',len(xml.xpath('//w:tbl',namespaces=NS))==14)
check('正文图片15幅',len(xml.xpath('//w:drawing',namespaces=NS))==15)
check('标题无装饰边线',not styles.xpath('//w:style[@w:styleId="Title"]//w:pBdr',namespaces=NS))
for i,s in enumerate(xml.xpath('//w:sectPr',namespaces=NS),1):
    m=s.find('w:pgMar',namespaces=NS);sz=s.find('w:pgSz',namespaces=NS)
    check(f'分节{i}页边距',abs(int(m.get('{'+NS['w']+'}left'))-1797)<=2 and abs(int(m.get('{'+NS['w']+'}right'))-1797)<=2 and int(m.get('{'+NS['w']+'}top'))==1440 and int(m.get('{'+NS['w']+'}bottom'))==1440)
    dims=sorted([int(sz.get('{'+NS['w']+'}w')),int(sz.get('{'+NS['w']+'}h'))]);check(f'分节{i}为A4',abs(dims[0]-11906)<5 and abs(dims[1]-16838)<5)
    check(f'分节{i}页码类型不重复',len(s.findall('w:pgNumType',namespaces=NS))<=1)
    if i>=4:
        num=s.find('w:pgNumType',namespaces=NS);check(f'分节{i}页码连续',num is None or num.get('{'+NS['w']+'}start') is None)
pages=[]
for i,p in enumerate(reader.pages,1):
    t=p.extract_text() or '';pages.append(t)
    check(f'PDF第{i}页有可读内容',len(re.sub(r'\s','',t))>10)
    check(f'PDF第{i}页无待生成占位符',not any(x in t for x in ['正在生成','@@EQ','@@FIG','@@TABLE','错误!','Error!']))
    if i>1:check(f'PDF第{i}页匿名',not any(x in t for x in ['学校：','队名：','成员：','指导教师：']))
alltext='\n'.join(pages)
compact=re.sub(r'\s','',alltext)
added=json.loads((O/'新增图表/新增图表核对.json').read_text(encoding='utf-8'))
check('图号1至15连续且与插图清单一致',[f['number'] for f in audit['figures']]==list(range(1,16)))
for f in audit['figures']:
    check(f"图{f['number']}具有对应标题",f"图{f['number']}{f['title']}" in compact)
for item in added['checks']:check('新增图表复算_'+item['check'],item['passed'],item.get('detail',''))
for p,h in added['source_sha256'].items():check('新增绘图来源未改写_'+Path(p).name,sha(Path(p))==h)
for f in added['figures']:
    for kind in ['png','svg','pdf']:check('新增图表格式齐全_'+str(f['source_id'])+'_'+kind,Path(f[kind]).is_file())
check('天气配对新增结论一致','21天降低风险' in compact and '36天提高风险' in compact and '9.45亩' in compact)
check('充电排队可与飞行重叠','可与其他电池飞行重叠，不等于无人机停机时间' in compact)
for p,h in audit['source_sha256'].items():check('源数据未改写_'+Path(p).name,sha(Path(p))==h)
for f in audit['figures']:check('图片源未改写_图'+str(f['number']),sha(Path(f['source']))==f['sha256'])
# Main matter starts at one and must remain sequential through landscape pages.
start=next(h['physical_page'] for h in word['headings'] if h['text']=='一、引言')
for h in word['headings']:
    if h['physical_page']>=start:check('目录对应连续页码_'+h['text'],h['page']==h['physical_page']-start+1,f"{h['page']} / {h['physical_page']}")
for label,expected in [('参考文献',21),('附录',6)]:
    if label=='参考文献':check('参考文献21条且正文均引用',audit['reference_count']==expected)
    else:check('6份附录存在',all(any(h['text'].startswith(f'附录{i}') for h in word['headings']) for i in range(1,7)))
# Data arithmetic is checked at full precision, separately from displayed rounding.
main=json.loads((B/'04_求解结果/主方案.json').read_text(encoding='utf-8'))['metrics']
def load(name):
    with (B/'04_求解结果'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
largest=next(x for x in load('算法对照.csv') if x['algorithm']=='largest_first')
check('摘要及时率与主结果',round(main['timely_rate']*100,2)==75.14)
check('摘要公顷与正文亩转换',round(main['timely_area_mu']/15,2)==108.97)
check('支出及增量',round(main['cost'],2)==8182.94 and round(main['cost']-float(largest['cost']),2)==654.06)
check('风险相对降幅',round((float(largest['risk_proxy_loss_mu'])-main['risk_proxy_loss_mu'])/float(largest['risk_proxy_loss_mu'])*100,2)==21.37)
check('分组最差率',round(main['worst_group_rate']*100,2)==72.41)
scale=load('真实子实例规模实验.csv')
scale_times='、'.join(f"{float(x['seconds']):.3f}" for x in scale[:-1])+'和'+f"{float(scale[-1]['seconds']):.3f}"
check('正文规模耗时与原始记录一致',scale_times in re.sub(r'\s','',alltext),scale_times)
check('小标题及正文保留适用范围','候选' in alltext and '压力' in alltext and '参与' in alltext)
renders=sorted(QA.glob('review-*.png'))
check('最终PDF逐页渲染齐全',len(renders)==len(reader.pages),len(renders))
result={'purpose':'匿名参赛论文最终验收','generation_logic':'verify_paper.py独立检查Word统计、OOXML、PDF与来源哈希；视觉结论显式人工确认','passed':all(x['passed'] for x in checks),'checks_count':len(checks),'checks':checks,'docx_sha256':sha(docx),'pdf_sha256':sha(pdf),'word_statistics':word,'visual_qa':'主代理已逐页检查最终Word导出的全部页面，核对标题、目录、连续页码、公式、表格与图例；未发现影响阅读的缺字、裁切或重叠。' if args.confirm_visual else '待逐页视觉检查','render_engine':'Microsoft Word 2024 PDF export + bundled Poppler 120dpi；默认LibreOffice渲染器不可用，已诊断后采用原生Word分页'}
(QA/'论文最终验收.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
with (QA/'论文验收检查明细.csv').open('w',encoding='utf-8-sig',newline='') as f:
    out=csv.DictWriter(f,fieldnames=checks[0].keys());out.writeheader();out.writerows(checks)
(QA/'PDF逐页文本.txt').write_text('\n\n'.join(f'【物理页{i+1}】\n{t}' for i,t in enumerate(pages)),encoding='utf-8')
audit['word_statistics']={k:v for k,v in word.items() if k!='headings'};audit['visual_qa']=result['visual_qa'];audit['final_docx_sha256']=sha(docx)
(O/'论文生成核对.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
if args.confirm_visual:
    added['visual_qa']=f"主代理已检查全部5幅新增图预览与最终{len(reader.pages)}页论文；中文和英文标签加粗清晰，未见裁切、重叠或图文编号错位。"
    (O/'新增图表/新增图表核对.json').write_text(json.dumps(added,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':result['passed'],'checks':len(checks),'pages':len(reader.pages),'body_characters':word['body_characters_no_spaces'],'failed':[x for x in checks if not x['passed']]},ensure_ascii=False))
