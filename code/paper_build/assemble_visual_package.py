"""用途：按最终论文编号汇总15幅图、35份绘图数据、文稿与来源，形成完整交付包。
生成逻辑：只读已验收文件，复制二进制图；CSV仅改图号与用途、不改数值字符串；
将原10页与新增5页矢量图集按正文次序重新组合，输出SHA256逐文件清单与ZIP。
运行条件：已有D:/Desktop/code完整研究工作区，Python含pypdf；不重求解。
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import csv, hashlib, json, re, shutil
from pypdf import PdfReader, PdfWriter

O=Path('D:/Desktop/code/10_可视化增强论文'); B=O.parent
F=O/'论文配图'; QA=O/'排版核验'
audit=json.loads((O/'论文生成核对.json').read_text(encoding='utf-8'))
added=json.loads((O/'新增图表/新增图表核对.json').read_text(encoding='utf-8'))
validation=json.loads((QA/'论文最终验收.json').read_text(encoding='utf-8'))
assert validation['passed'] and added['passed'], '必须先通过数据与论文验收'
assert '已逐页检查' in validation['visual_qa'], '必须先完成最终论文视觉检查'
for sub in ['PNG_600dpi','SVG_矢量','绘图数据']:(F/sub).mkdir(parents=True,exist_ok=True)
with (B/'08_标准论文图/图表清单与生成逻辑.csv').open(encoding='utf-8-sig',newline='') as f:
    old_meta={int(re.search(r'Fig_(\d+)',x['figure'])[1]):x for x in csv.DictReader(f)}
new_meta={x['source_id']:x for x in added['figures']}
original=PdfReader(B/'08_标准论文图/论文图集_标准版.pdf');book=PdfWriter()
assert len(original.pages)==10
mapping=[];files=[];data_count=0

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def record(p,purpose,logic,source=''):
    files.append({'file':str(p.relative_to(O)).replace('\\','/'),'bytes':p.stat().st_size,
        'sha256':sha(p),'purpose':purpose,'generation_logic':logic,'source':str(source)})
for fig in audit['figures']:
    no=fig['number']; png=Path(fig['source']);srcid=int(re.search(r'Fig_(\d+)',png.name)[1])
    root=png.parent.parent;stem=f"Fig_{no:02d}_{fig['title']}"
    new=srcid>10;meta=new_meta[srcid] if new else old_meta[srcid]
    notes=meta['note'] if new else meta['notes'];logic=meta['generation_logic']
    outputs=[]
    for kind,ext in [('PNG_600dpi','.png'),('SVG_矢量','.svg')]:
        src=root/kind/(png.stem+ext);dst=F/kind/(stem+ext);shutil.copy2(src,dst)
        assert sha(src)==sha(dst)
        record(dst,f"论文图{no}：{fig['title']}，{'600dpi位图' if ext=='.png' else '路径化矢量图'}",logic,src)
        outputs.append(str(dst.relative_to(O)).replace('\\','/'))
    if new:
        page=PdfReader(meta['pdf']).pages[0]
    else:page=original.pages[srcid-1]
    book.add_page(page);book.add_outline_item(f"图{no} {fig['title']}",no-1)
    row_data=[]
    for src in sorted((root/'绘图数据').glob(f'Fig_{srcid:02d}_*.csv')):
        dst=F/'绘图数据'/re.sub(r'^Fig_\d+',f'Fig_{no:02d}',src.name)
        with src.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        assert 'purpose' in fields and 'generation_logic' in fields
        for row in rows:
            row['purpose']=re.sub(r'Fig_\d+',f'Fig_{no:02d}',row['purpose'])
        with dst.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
        # Numerical strings, dates, event types and all other fields must be identical.
        with src.open(encoding='utf-8-sig',newline='') as f:before=list(csv.DictReader(f))
        with dst.open(encoding='utf-8-sig',newline='') as f:after=list(csv.DictReader(f))
        assert len(before)==len(after)
        assert all(all(a[k]==b[k] for k in fields if k!='purpose') for a,b in zip(before,after))
        record(dst,f"论文图{no}未舍入绘图数据",'复制已有取数表，仅按正式论文图号修改文件名和purpose字段；所有数值与生成逻辑原样保留',src)
        data_count+=1;row_data.append(dst.name)
    mapping.append({'paper_figure':no,'title':fig['title'],'source_id':srcid,'source_set':'新增图表' if new else '08_标准论文图',
        'png':outputs[0],'svg':outputs[1],'drawing_data':'; '.join(row_data),
        'purpose':f"定位正文图{no}及其未舍入数据",'generation_logic':logic,'interpretation_boundary':notes})
book.add_metadata({'/Title':'可视化增强论文全部15幅图集','/Subject':'用途：论文配图；生成逻辑：已验收矢量页面按正式论文图号重排'})
fullbook=F/'全部15幅论文图集_矢量版.pdf'
with fullbook.open('wb') as f:book.write(f)
assert len(PdfReader(fullbook).pages)==15
record(fullbook,'按正文编号浏览或打印全部论文图','从原标准图集和新增矢量PDF按1至15重排，不栅格化')
mapfile=F/'图表目录与数据映射.csv'
with mapfile.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=mapping[0]);w.writeheader();w.writerows(mapping)
record(mapfile,'对应论文图号、原图号、绘图数据与结论边界','依据最终Word生成记录合并新旧图元数据')
figure_readme=F/'README_全部论文图.md'
figure_readme.write_text('# 全部15幅论文图\n\n用途：论文配图、后续修改与数据追溯。生成逻辑：assemble_visual_package.py按最终Word图号汇总。\n\n'
    'PNG_600dpi用于Word插图；SVG_矢量用于无损缩放，文字已路径化以避免字体替换；PDF图集保留矢量与嵌入字体。'
    '中英文分别采用微软雅黑加粗与Arial Bold，图例、坐标、数据标签统一加粗，主轴线与辅助线区分粗细。\n\n'
    '绘图数据共'+str(data_count)+'份，数值原样保留未舍入精度；每表含purpose与generation_logic。论文图号不同于历史原图号，'
    '使用本目录图号，不要再把08目录原图号直接当作论文编号。图表目录与数据映射.csv列出对应关系。\n\n'
    'PNG/SVG二进制用途与生成逻辑详见交付文件清单.csv和图表映射表。图集不是论文分页检查PDF。\n\n'
    '|论文图号|图名|来源|\n|---|---|---|\n'+''.join(f"|{r['paper_figure']}|{r['title']}|{r['source_set']} 原图{r['source_id']}|\n" for r in mapping),encoding='utf-8')
record(figure_readme,'配图目录用途与数据口径说明','按15幅图及数据数量自动汇总')

source_dir=O/'取数来源';source_dir.mkdir(exist_ok=True)
sources={**audit['source_sha256'],**added['source_sha256']}
for srcpath,expected in sources.items():
    src=Path(srcpath);assert sha(src)==expected
    rel=src.relative_to(B);dst=source_dir/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    record(dst,'生成论文表格与新增图表使用的原始求解或派生记录','按来源SHA256核对后只读复制；参数与代理假设保留原标记',src)
source_readme=source_dir/'README_取数来源.md'
source_readme.write_text('# 取数来源\n\n用途：保存此次论文表格和新增绘图的具体CSV/JSON输入，便于核对数值。'
    '生成逻辑：合并两份来源哈希清单，核对后保留相对于原code目录的路径复制。\n\n'
    '这是本次直接取数来源，不是整个原始GIS、天气与公开文献数据包。完整研究、原始大文件与历史10幅图重画输入仍在原工作区。'
    '每份数据的用途、生成逻辑及校验和见交付文件清单.csv；JSON中的source路径用于来源追溯。\n',encoding='utf-8')
record(source_readme,'界定直接输入备份与完整研究数据的差别','固定说明，避免将局部源文件包误作完整原始数据')

scripts=O/'复现脚本';scripts.mkdir(exist_ok=True)
for src in [O/'build_paper.py',O/'verify_paper.py',O/'plot_added_figures.py',O/'assemble_visual_package.py',
    B/'plot_paper_standard.py',B/'finalize_paper_figures.py',B/'requirements.lock.txt',B/'09_参赛论文/update_word_layout.ps1']:
    dst=scripts/src.name;shutil.copy2(src,dst)
    record(dst,'论文或科学绘图生成、校验及依赖说明','保存已执行或历史已执行的作者脚本；运行步骤与工作区依赖见交付说明',src)

docx=Path(audit['word_file'])
for name,purpose,logic in [
    (docx.name,'匿名完整论文，正式Word文稿','build_paper.py生成；隐藏Word更新目录与连续页码；逐页渲染检查'),
    ('论文正文源稿.md','编辑正文与图表位置的可复现源稿','保留原正文并插入5幅新图及分析；@@标记由Word生成器解释'),
    ('论文全文_便于检索.md','检索完整论文与表格内容','生成器展开正文表格，Markdown不作为最终排版版'),
    ('参考文献_论文引用版.md','论文实际引用的21条规范参考文献','按正文首次引用重新编号，与原资料完整台账区分'),
    ('论文生成核对.json','文稿结构、来源哈希与最终Word统计','生成记录经独立最终验收补充')]:record(O/name,purpose,logic)
for src,purpose in [(QA/'论文最终验收.json','361项最终结构、取数、分页检查与视觉记录'),
    (QA/'论文验收检查明细.csv','逐项验收结论'),(O/'新增图表/新增图表核对.json','新增图表37项复算、字体与来源证据')]:
    record(src,purpose,'独立核对脚本记录，视觉结果在逐页检查后显式确认')

stats=validation['word_statistics'];README=O/'README_完整交付说明.md'
README.write_text(f'''# 论文可视化增强版：完整交付说明

用途：定位本次完整论文、15幅配图、数据及复现材料。生成逻辑：依据最终Word统计、已验收图表映射及文件清单汇总。

## 正式文稿

[完整匿名Word论文](<{docx.name}>)：{stats['pages']}页，正文Word不含空格字符{stats['body_characters_no_spaces']:,}，在14,000—16,000要求内；15幅图、14张表、17个可编辑原生公式、21条参考文献、6份附录。保留匿名评审正文和封面填写栏位。

全文保留题目、中英文摘要、关键词、目录、图表清单、八章正文、参考文献、附录与致谢。正文图1—12及表1—6，附录图13—15及表7—14；目录、页码、图表序号与引用已更新。原09目录52页版本保留，本目录为最新增强版本。

## 新增图与正文融入

|正式图号|新增图|正文位置与价值|
|---|---|---|
|图3|数据资源模拟与融合求解流程|第五章，区分可行包生成、整数选择与风险比较的实现层次|
|图5|任务面积分解与累计服务进度|第六章，展示5班组面积、自有/外援/未服务分解和完整任务累计进度|
|图6|全班组药液库存与充电排队|第六章，展示5班组库存、冷却后充电队列、架次和补水|
|图8|候选路线池最优性界与扩池稳定性|第六章，解释LP松弛界、整数解与不同候选池结果|
|图12|天气政策配对差异与逐日及时率|第六章，展示61个共同日期的风险差与统一色标日历|

每幅新图均有图前说明、规范图题和图后分析，并非仅添加图片。比较图合并为多面板，原有10幅图保留，所有图及正文交叉引用按正式编号重排。

## 关键新增取数与边界

主方案自有完成1035.88亩、外援598.72亩、未服务540.69亩，占总需求47.62%、27.52%、24.86%。五队共98架次与3次补水；EXT1、EXT2最低药液0.30L、2.26L，提示该计划中低液量记录，不据此推断现场安全阈值。平均单次充电排队2.04—3.27分钟，可与其他电池飞行重叠，不等于无人机停机。

同1040池LP风险下界532.261116亩、整数最优540.686250亩，差8.425134亩；整数MIP间隙为0仅证明候选池内最优。扩至3885池目标未改善不能证明全局路线最优。SAA–CVaR在61个共同日期中21天风险下降、36天上升、4天相同，平均下降9.45亩；计数不是统计显著性或未来总体胜率。

所有新增图只读取既有数据，没有伪造微观实测或重新包装为真实经营回测。原始数据与求解结果哈希未变化。最终{validation['checks_count']}项独立验收全部通过，5幅新图预览和{stats['pages']}页Word导出页面已检查，修复两张小表末行跨页问题。

## 文件与目录

- 正式.docx：完整可编辑匿名论文。
- 论文正文源稿.md：后续修改与重新生成的作者源稿；其中@@标记不是最终正文。
- 论文全文_便于检索.md：检索用全文，不等同于Word版式。
- 参考文献_论文引用版.md：21条实际引用参考文献；全部检索资料台账仍保留于原06目录。
- 论文配图/PNG_600dpi：15张按论文图号命名的高分辨率图；中文微软雅黑加粗、英文Arial Bold，全部文字加粗，框线区分粗细。
- 论文配图/SVG_矢量：15张路径化矢量图；适合无损缩放。
- 论文配图/全部15幅论文图集_矢量版.pdf：按论文编号排列的15页图集，不是论文分页核验PDF。
- 论文配图/绘图数据：{data_count}份未舍入数据CSV，每表含purpose及generation_logic；数值字符串逐字段与原表核对。
- 论文配图/图表目录与数据映射.csv：正式图号与原图号、取数、生成逻辑和边界映射。
- 取数来源：本次直接使用的求解/派生输入备份；不是原始大数据包的完整副本。
- 复现脚本：新增绘图、历史标准绘图、Word生成、字段更新、核对、打包程序和依赖清单。
- 交付文件清单.csv：每个交付文件用途、生成逻辑、来源、字节数和SHA256；二进制文件说明通过此清单关联。
- 排版核验：Word实际统计、最终验收、55页图及文本，仅用于核验；ZIP不包含核验PDF/页图。
- 新增图表：生成器原始输出及复算记录；这里原图11—15不等于论文编号，正式编号请用论文配图目录。

## 复现与使用

优先直接打开正式Word；目录域已更新，修改后可在Word再次更新域。请先保留最终稿备份，避免试验重跑覆盖成稿。

绘图用已有D:/Desktop/code/.venv/Scripts/python.exe运行plot_added_figures.py；Word生成及打包用捆绑Python，需python-docx/lxml/pypdf。执行顺序：新增绘图→build_paper.py→update_word_layout.ps1（传入本次PaperPath）→Poppler渲染逐页检查→verify_paper.py --confirm-visual→assemble_visual_package.py。--confirm-visual仅在实际完成视觉检查后使用。

脚本依赖原D:/Desktop/code完整研究工作区及C:/Windows/Fonts中的Arial Bold和微软雅黑加粗字体；复制到其他电脑须调整根目录并准备依赖与原始GIS/天气输入，不宣称免配置独立复现。打包后的Word、PNG、SVG和图集可独立查看，无需运行Python。此次默认文档渲染器缺少LibreOffice，已采用独立隐藏Word实例实际分页并以Poppler渲染核验，未安装新软件。
''',encoding='utf-8')
record(README,'正式文稿、图表、数据及边界总入口','依据最终55页Word统计及15图映射自动生成')
manifest=O/'交付文件清单.csv'
with manifest.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=files[0]);w.writeheader();w.writerows(files)
archive=O/'论文与全部配图_完整交付.zip'
with ZipFile(archive,'w',compression=ZIP_DEFLATED,compresslevel=6) as z:
    for item in files:z.write(O/item['file'],item['file'])
    z.write(manifest,manifest.name)
with ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(files)+1
    assert not any('review-' in x or '论文排版核验.pdf' in x for x in z.namelist())
result={'purpose':'完整论文可视化成果交付包验收','generation_logic':'只读复制、CSV数值字符串不变、PDF页面数检查、ZIP CRC与条目数核对',
    'passed':True,'figures':len(mapping),'drawing_csv_files':data_count,'archive_files':len(files)+1,
    'pages':stats['pages'],'body_characters':stats['body_characters_no_spaces'],'zip_sha256':sha(archive),
    'zip_bytes':archive.stat().st_size,'archive':str(archive),'docx_sha256':sha(docx)}
(O/'交付包核对.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
