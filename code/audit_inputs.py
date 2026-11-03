"""用途：只读审计原始数据并提取证据；生成逻辑：目录元数据、PDF文本、CSV首行和URL。
运行：bundled Python audit_inputs.py。原始文件不修改。
"""
from pathlib import Path
import json, csv, re, hashlib, sys
from collections import Counter
from pypdf import PdfReader

ROOT=Path('D:/Desktop/jianmo'); OUT=Path('D:/Desktop/code'); AUD=OUT/'01_数据审计'; AUD.mkdir(exist_ok=True)
def save(name,text): (AUD/name).write_text(text,encoding='utf-8')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and '11_本次公开补充' not in p.parts)
rows=[]
for p in files:
    rows.append({'path':str(p.relative_to(ROOT)), 'extension':p.suffix.lower(), 'bytes':p.stat().st_size,'purpose':'原始数据可追溯索引','generation_logic':'只读目录扫描','evidence_type':'用户提供原件'})
with (AUD/'原始文件索引.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
summary={'file_count':len(files),'bytes':sum(x['bytes'] for x in rows),'extensions':dict(Counter(x['extension'] for x in rows)), 'problem_original_found':False,'purpose':'数据包体量和赛题原文审计','generation_logic':'文件级只读扫描'}
save('审计汇总.json',json.dumps(summary,ensure_ascii=False,indent=2))
pdfs=[p for p in files if p.suffix.lower()=='.pdf' and ('在线版' not in str(p))]
extracts=[]; urlrows=[]; errors=[]
td=AUD/'PDF文本';td.mkdir(exist_ok=True)
for p in pdfs:
    try:
        reader=PdfReader(p); text='\n'.join((page.extract_text() or '') for page in reader.pages)
        name=p.stem+'.txt'; (td/name).write_text('用途：原始PDF检索与参数证据提取。生成逻辑：pypdf逐页抽取，表格须回查原件。\n来源：'+str(p)+'\n'+text,encoding='utf-8')
        urls=set(re.findall(r'https?://[^\s<>"）]+',text))
        for page in reader.pages:
            for a in page.get('/Annots',[]):
                ob=a.get_object(); ac=ob.get('/A',{}); uri=ac.get('/URI')
                if uri: urls.add(str(uri))
        urlrows.extend({'source':str(p.relative_to(ROOT)),'url':u,'purpose':'原始材料引用线索','generation_logic':'PDF文本及链接注释提取；不等于逐URL内容验证'} for u in sorted(urls))
        extracts.append({'file':str(p.relative_to(ROOT)),'pages':len(reader.pages),'chars':len(text),'text_file':name})
    except Exception as e:errors.append({'file':str(p),'error':str(e)})
save('PDF抽取清单.json',json.dumps({'purpose':'记录PDF抽取状态','generation_logic':'逐PDF抽取','files':extracts,'errors':errors},ensure_ascii=False,indent=2))
with (AUD/'原件URL线索.csv').open('w',encoding='utf-8-sig',newline='') as f:
    if urlrows:w=csv.DictWriter(f,fieldnames=urlrows[0]);w.writeheader();w.writerows(urlrows)
heads=[]
for p in files:
    if p.suffix.lower()=='.csv':
        try:
            with p.open(encoding='utf-8-sig') as f: h=[next(f,'').strip() for _ in range(7)]
            heads.append({'file':str(p.relative_to(ROOT)),'head':h})
        except Exception as e: heads.append({'file':str(p),'error':str(e)})
save('CSV结构摘要.json',json.dumps({'purpose':'确认列名、单位和注释格式','generation_logic':'每CSV前7行，只读','files':heads},ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False)); print('PDFs extracted',len(extracts),'errors',len(errors));print('CSV files',len(heads))
