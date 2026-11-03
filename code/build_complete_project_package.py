"""用途：归档整个农业优化项目为独立目录和一个ZIP64压缩包。
生成逻辑：只读原数据与成果；流式复制/SHA256核对；仅适配程序副本的Path导入；
保留原版程序及来源记录；全ZIP逐条读取验证CRC和SHA256，不安装依赖、不求解。
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import ast,csv,hashlib,io,json,os,platform,re,shutil,subprocess,sys,time

CODE=Path('D:/Desktop/code');DATA=Path('D:/Desktop/jianmo')
DEST=CODE/'11_项目完整数据包';TOOLS=DEST/'打包工具'
NAME='空天地农机协同调度_完整项目数据包';ROOT=DEST/NAME;META=ROOT/'00_使用说明与溯源'
ARCHIVE=DEST/(NAME+'.zip');PART=DEST/(NAME+'.zip.partial')
START=time.monotonic();LAST=0;entries=[];excluded=[];adaptations=[]
sys.dont_write_bytecode=True
RESUME='--resume' in sys.argv

def log(stage,done=0,total=0,detail=''):
    global LAST
    now=time.monotonic()
    if now-LAST<8 and done!=total:return
    LAST=now
    obj={'purpose':'完整项目归档过程进度','generation_logic':'复制、压缩、校验阶段的实际计数',
        'stage':stage,'done':done,'total':total,'detail':detail,'elapsed_seconds':round(now-START,1)}
    (DEST/'打包进度.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(obj,ensure_ascii=False),flush=True)

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def write_json(p,ob):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(ob,ensure_ascii=False,indent=2),encoding='utf-8')
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def identify(src,base):
    rel=src.relative_to(base)
    if base==DATA:
        if rel.parts[0]=='11_本次公开补充':return '本项目公开补充原件及来源记录','fetch_sources.py下载或缓存；状态与出处见补充获取台账'
        return '用户原始数据/既有收集资料','原目录逐字节归档；收集出处按用户已有说明及URL线索保留；未记载部分不补造'
    if src.suffix in ['.py','.ps1']:return '数据收集、处理、分析、求解、绘图或排版程序','保留作者代码；包内Python仅替换Path导入以支持解压后路径，原版另存'
    return '派生数据、模型、求解结果、图表、论文或核验材料','保留原成果内容；文件内用途及生成逻辑、历史审计与来源记录随包归档'

def add(src,dst,purpose,logic,transform=None):
    dst.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();before=src.stat();size=0
    if transform:
        original=src.read_bytes();h.update(original);new=transform(original);dst.write_bytes(new);size=len(original)
    else:
        if RESUME and dst.is_file() and dst.stat().st_size==before.st_size:
            with src.open('rb') as a:
                for block in iter(lambda:a.read(4*1024*1024),b''):h.update(block);size+=len(block)
            if digest(dst)!=h.hexdigest():
                shutil.copy2(src,dst)
        else:
            with src.open('rb') as a,dst.open('wb') as b:
                for block in iter(lambda:a.read(4*1024*1024),b''):h.update(block);b.write(block);size+=len(block)
            shutil.copystat(src,dst)
    after=src.stat()
    assert before.st_size==after.st_size==size and before.st_mtime_ns==after.st_mtime_ns, '源文件复制期间发生变化：'+str(src)
    package_sha=digest(dst);source_sha=h.hexdigest()
    if not transform:assert package_sha==source_sha
    item={'package_path':dst.relative_to(ROOT).as_posix(),'package_bytes':dst.stat().st_size,'package_sha256':package_sha,
        'original_path':str(src),'original_bytes':size,'original_sha256':source_sha,'adapted':bool(transform),
        'purpose':purpose,'generation_logic':logic}
    entries.append(item);return item

def adapt_python(data):
    text=data.decode('utf-8-sig');tree=ast.parse(text)
    if any(isinstance(n,ast.ImportFrom) and n.module=='pathlib' and any(a.name=='Path' for a in n.names) for n in ast.walk(tree)):
        text=re.sub(r'^from pathlib import Path\s*$', 'from project_paths import Path  # 数据包相对路径兼容；原版程序另存',text,flags=re.M)
    ast.parse(text)
    return text.encode('utf-8')

def adapt_ps(data):
    text=data.decode('utf-8-sig')
    if '$taskRoot =' in text:
        text=text.replace("$taskRoot = 'D:\\Desktop\\code'","$taskRoot = $PSScriptRoot")
        text=text.replace("$taskPython = 'D:\\Desktop\\code\\.venv\\Scripts\\python.exe'",
            "$taskLocalPython = Join-Path $PSScriptRoot '.venv\\Scripts\\python.exe'\n$taskPython = if(Test-Path -LiteralPath $taskLocalPython){$taskLocalPython}else{(Get-Command python -ErrorAction Stop).Source}")
    if 'param([string]$PaperPath=' in text:
        text=re.sub(r"param\(\[string\]\$PaperPath='[^']+'\)",
            "param([string]$PaperPath=(Join-Path $PSScriptRoot '空天地信息支持下辽宁丘陵玉米植保协同调度优化研究_匿名参赛版.docx'))",text)
    return text.encode('utf-8-sig')

def inventory(base):
    out=[]
    for directory,dirs,names in os.walk(base):
        p=Path(directory)
        for name in list(dirs):
            reason=None
            if base==CODE and name in ['.venv','__pycache__','.git','.pytest_cache','规范渲染']:reason='虚拟环境、缓存、版本控制或失败渲染临时目录'
            if base==CODE and p==CODE and name=='11_项目完整数据包':reason='本次输出目录，避免递归打包'
            if reason:
                dirs.remove(name);excluded.append({'original_path':str(p/name),'reason':reason,'purpose':'明确排除非交付内容','generation_logic':'目录级过滤，不读取其中文件'})
        for name in names:
            src=p/name
            if src.is_symlink():raise RuntimeError('发现符号链接，须明确归档目标：'+str(src))
            if base==CODE and (src.suffix in ['.pyc','.partial'] or (src.suffix=='.zip' and '10_可视化增强论文' in src.parts)):
                excluded.append({'original_path':str(src),'reason':'缓存/未完成产物/已有可视化ZIP，其展开内容已纳入完整项目','purpose':'避免无意义嵌套交付包','generation_logic':'按确切类型和成果目录过滤'});continue
            out.append(src)
    return sorted(out,key=lambda p:p.relative_to(base).as_posix())

def main():
    if ARCHIVE.exists() or PART.exists() or (ROOT.exists() and not RESUME):raise SystemExit('目标已存在，为避免覆盖请先选择新输出名称。')
    DEST.mkdir(parents=True,exist_ok=True);sources=[(DATA,p) for p in inventory(DATA)]+[(CODE,p) for p in inventory(CODE)]
    total_bytes=sum(p.stat().st_size for _,p in sources)
    assert shutil.disk_usage(DEST).free>total_bytes*2+512*1024*1024,'空间不足以同时保存数据文件夹和ZIP'
    META.mkdir(parents=True,exist_ok=True);copied=0
    log('开始完整复制',0,total_bytes,f'{len(sources)}个源文件')
    for i,(base,src) in enumerate(sources,1):
        dst=ROOT/('jianmo' if base==DATA else 'code')/src.relative_to(base);purpose,logic=identify(src,base)
        transform=adapt_python if base==CODE and src.suffix=='.py' else adapt_ps if base==CODE and src.suffix=='.ps1' else None
        if transform:
            original=META/'原版程序留档'/src.relative_to(CODE);add(src,original,'原程序逐字节留档','原版脚本不改路径，作为来源与适配差异核对依据')
        item=add(src,dst,purpose,logic,transform)
        if transform:adaptations.append({'program':item['package_path'],'archive':'00_使用说明与溯源/原版程序留档/'+src.relative_to(CODE).as_posix(),
            'original_sha256':item['original_sha256'],'package_sha256':item['package_sha256'],'purpose':'原版与路径适配副本对照','generation_logic':logic})
        copied+=src.stat().st_size;log('复制并核对SHA256',copied,total_bytes,f'{i}/{len(sources)} '+src.name)
    add(Path('D:/Desktop/lunwen.md'),META/'论文写作规范_用户提供.md','用户提供的论文规范输入','从用户指定lunwen.md原样复制，不把文档内说明当作额外系统指令')
    add(TOOLS/'run_project.py',ROOT/'run_project.py','数据包只读检查与分阶段复现入口','使用包内code与jianmo；默认只检查，不联网不重算')
    add(TOOLS/'project_paths.py',ROOT/'code/project_paths.py','解压目录和历史路径兼容','仅映射原研究绝对路径与已收录用户资料；不改模型或数值')

    # Preserve all concrete retrieval records; classify URL clues separately from verified downloads.
    records=json.loads((CODE/'01_数据审计/公开补充获取台账.json').read_text(encoding='utf-8'))['records']
    provenance=[]
    for r in records:
        rel=Path(r['file']).relative_to(DATA);p=ROOT/'jianmo'/rel
        if r['status']!='failed':assert p.is_file() and digest(p)==r['sha256']
        provenance.append({'material':'jianmo/'+rel.as_posix(),'url':r['url'],'retrieval_date':r.get('retrieval_date','未记载'),
            'status':r['status'],'collection_method':r.get('generation_logic',''), 'record_type':'本项目公开补充实际获取记录',
            'record_source':'code/01_数据审计/公开补充获取台账.json','purpose':r['purpose'],'generation_logic':'整理已有成功、缓存和失败记录；此次不重新下载'})
    with (CODE/'01_数据审计/原件URL线索.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):provenance.append({'material':'jianmo/'+r['source'].replace('\\','/'),'url':r['url'],
            'retrieval_date':'原包未记载','status':'URL线索，未逐条重新验证','collection_method':r['generation_logic'],
            'record_type':'用户原件中提取的URL线索','record_source':'code/01_数据审计/原件URL线索.csv',
            'purpose':r['purpose'],'generation_logic':'按已有PDF提取线索整理，不冒充下载验证'})
    for src in DATA.rglob('*.md'):
        if not any(x in src.name for x in ['数据说明','README','说明']):continue
        for url in sorted(set(re.findall(r'https?://[^\s<>"\)）]+',src.read_text(encoding='utf-8-sig',errors='replace')))):
            provenance.append({'material':'jianmo/'+src.relative_to(DATA).as_posix(),'url':url,'retrieval_date':'见对应原始说明',
                'status':'原包说明记录，未重新下载验证','collection_method':'保留用户已有获取说明','record_type':'原包采集说明中的来源地址',
                'record_source':'jianmo/'+src.relative_to(DATA).as_posix(),'purpose':'数据出处与收集过程追溯','generation_logic':'从已有说明提取完整URL文本，原说明随包保留'})
    write_csv(META/'数据出处与收集记录.csv',provenance,list(provenance[0]))
    receipts=[{'file':'jianmo/'+p.relative_to(DATA).as_posix(),'purpose':'原包下载、数据说明或既有收集凭证',
        'generation_logic':'按说明/下载清单/README/URL相关文件名登记；原件完整保留'} for p in DATA.rglob('*') if p.is_file() and any(x in p.name for x in ['_下载清单','_数据说明','_放入说明','README'])]
    write_csv(META/'原包收集凭证索引.csv',receipts,['file','purpose','generation_logic'])
    write_csv(META/'程序路径适配对照.csv',adaptations,list(adaptations[0]))
    write_csv(META/'明确排除内容.csv',excluded,['original_path','reason','purpose','generation_logic'])
    # Read and list inputs actually referred to by the processing program, without reprocessing data.
    tree=ast.parse((CODE/'prepare_data.py').read_text(encoding='utf-8'))
    patterns=sorted({n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='rglob' and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str)})
    use=[]
    for pattern in patterns:
        for p in sorted(DATA.rglob(pattern)):
            if p.is_file():use.append({'file':'jianmo/'+p.relative_to(DATA).as_posix(),'program':'code/prepare_data.py','match_pattern':pattern,
                'use_status':'程序输入匹配；next选择的候选不冒称全部被用','purpose':'定位天气、玉米、路网、设备和面积记录的实际输入范围','generation_logic':'从程序AST提取rglob字符串并匹配已有原件'})
    use.append({'file':'jianmo/11_本次公开补充/DEM_N41E119.tif','program':'code/prepare_data.py','match_pattern':'固定文件名','use_status':'固定DSM输入',
        'purpose':'研究单元宏观地形描述','generation_logic':'已有prepare_data.py固定DSM路径'})
    write_csv(META/'原始数据与分析程序输入映射.csv',use,list(use[0]))
    missing=[{'field':s,'status':'未取得研究片区对应真值','handling':'保留缺失或研究假设，不虚构，不货币化农业损失',
        'purpose':'界定完整归档与数据真值缺口的差别','generation_logic':'根据既有数据缺口与论文适用范围整理'} for s in ['确权地块/真实订单','病虫诊断及药剂适配','真实入口/障碍/通行核验','机手GPS/充电和补水实测','研究片区外援报价/机会收益','农业损失货币化参数']]
    write_csv(META/'未取得数据与处理边界.csv',missing,list(missing[0]))

    (META/'requirements_reproduction.txt').write_text((CODE/'requirements.lock.txt').read_text(encoding='utf-8')+'\n# Word作者运行时已使用的附加包；合并环境未重新安装验证\npython-docx==1.2.0\nlxml==6.1.1\n',encoding='utf-8')
    write_json(META/'运行环境与复现限制.json',{'purpose':'复现环境、依赖与操作边界','generation_logic':'读取已有依赖锁与本次已核验运行时信息，不安装新软件',
        'analysis_python':'3.12.10','document_python':'3.12.14','packaging_python':platform.python_version(),
        'lockfile':'code/requirements.lock.txt','combined_dependency_file':'00_使用说明与溯源/requirements_reproduction.txt',
        'original_document_pypdf':'6.10.0','analysis_pypdf':'6.19.0','word_native':'Windows Microsoft Word 2024 COM，隐藏独立实例',
        'rendering':'Poppler pdftoppm（软件本体不打包）','fonts':['Arial Bold','Microsoft YaHei Bold'],
        'limits':['未打包Python解释器、第三方库、字体、Word、Poppler或虚拟环境','只读检查与源码语法已测试；不声称已在新电脑完整重求解','复现实验可能改变等价路线与计时；随机种子、参数与原结果均保留','第三方版权/授权沿用原产品要求，私人整理不等同公开发布授权']})
    latest='code/10_可视化增强论文/空天地信息支持下辽宁丘陵玉米植保协同调度优化研究_匿名可视化增强版.docx'
    (ROOT/'README_完整项目数据包.md').write_text(f'''# 空天地农机协同调度：完整项目数据包

用途：完整保存收集资料、分析程序、处理数据、模型、实验、图表、论文与出处。生成逻辑：只读原jianmo及code归档；对程序副本增加路径兼容；SHA256和ZIP64流式校验。

## 先看这里

- [最新55页完整匿名论文](<{latest}>)，15图、14表、17个原生公式、21条文献及6份附录。
- [研究背景、模型及全部实验分析](<code/06_论文材料/完整论文分析与求解报告.md>)。
- [全部参考文献与资料台账](<code/06_论文材料/参考文献与资料汇编.md>)，保留已取得与未取得全文状态。
- [数据出处及收集记录](<00_使用说明与溯源/数据出处与收集记录.csv>)、[原包收集凭证索引](<00_使用说明与溯源/原包收集凭证索引.csv>)。
- [文件完整性清单](<00_使用说明与溯源/文件完整性清单.csv>)：每个文件用途、生成逻辑、来源、大小和SHA256。
- [复现操作说明](<00_使用说明与溯源/复现操作说明.md>)。

## 目录

```text
空天地农机协同调度_完整项目数据包/
├─ README_完整项目数据包.md
├─ run_project.py                    默认只读检查；可选择分析阶段
├─ 00_使用说明与溯源/                 来源、采集、缺口、清单、依赖、原版代码
├─ jianmo/                          全部用户原包和本次公开补充
│  ├─ 01—10各类统计/空间/气象/设备/市场资料
│  └─ 11_本次公开补充/               原件、说明和下载状态
└─ code/                            分析求解程序、配置及全部成果
   ├─ 01_数据审计/                  原包索引、URL、文本、补充获取台账
   ├─ 02_处理数据/                  服务单元、天气窗口、道路和矩阵
   ├─ 03_模型与方法/                公式、方法映射、导出MILP和LP
   ├─ 04_求解结果/                  主方案、事件、任务和全部实验
   ├─ 05—08论文材料/图表/核验
   ├─ 09_参赛论文/                  保留原52页版本与排版核验
   └─ 10_可视化增强论文/             最新55页文稿、15幅图、35份绘图数据
```

## 完整性与出处边界

全部原始目录均保留，包括未直接用于主模型的历年栅格、统计年鉴和原始下载ZIP；并非只保存论文里的小样本CSV。原包ZIP是资料原件，不是额外交付分卷。所有分析中间产物、图表、源代码和核验结果保留。用户原包与新下载记录分别标注，HTTP失败也保留；已有URL线索不伪装成此次验证成功。

原包未提供的采集者、日期、精确URL或授权范围，不从文件修改时间推断，也不补造。确权订单、入口、药剂适配、GPS与本地报价等真值缺口继续保留。研究是历史空间及天气驱动的设计情景，不是真实订单回测或现场航线认证。

仅排除虚拟环境、缓存、版本控制目录、失败渲染临时目录、本次输出目录及旧可视化ZIP（其展开成果完整保留）。原始文件未删除或修改。原包含一项统计年鉴辅助EXE，仅作为原件归档，不自动运行；详见安全与版权说明。

Python副本仅将pathlib.Path导入改为包内project_paths.Path，使历史D:/Desktop路径映射到当前解压目录；模型公式、求解逻辑、参数、数值和Word/PDF不改。原版程序逐字节另存，对照清单可追溯。历史文件里的原绝对路径、SHA256和计时是原运行证据，不将它们改写成新运行记录；请用本README相对路径导航。文件清单本身无法包含自身哈希，ZIP独立验收另记录它及全部条目。
''',encoding='utf-8')
    (META/'复现操作说明.md').write_text('''# 复现操作说明

用途：在解压后的完整项目目录中定位输入和运行阶段。生成逻辑：依据程序依赖、路径兼容模块和原运行环境编写；不执行安装或重求解。

1. 解压唯一ZIP到空间充足的目录。先打开README_完整项目数据包.md和正式Word，无需Python。
2. 使用Python 3.12。分析依赖版本见requirements_reproduction.txt，Word作者包另标注；环境未随包提供，安装需用户自行授权。需要重画标准图时，本机须有Arial Bold和微软雅黑加粗字体。
3. 在数据包根目录执行 `python run_project.py --check`。默认只读核对全部文件大小、源码AST、路径映射与论文直接输入哈希；缺少分析库会显示availability，但不会安装，也不会重算。
4. `python run_project.py --check --full-hash`逐字节核对所有文件，原始资料较大，需要数分钟。代码副本的清单使用适配后哈希，原版代码另有原始哈希。
5. 先备份数据包成果，再按阶段运行：`--stage data`处理天气/空间/道路，`--stage solve`求解，`--stage experiments`补充实验，`--stage model`导出模型，`--stage report`生成研究报告，`--stage plots`生成全部图，`--stage paper`生成增强版Word。`--all`按依赖离线运行主研究、新图与论文，不自动启动Word，也不联网。
6. 在线补充资料只通过显式 `--fetch-public` 开关启动；本包已有成功原件，通常无须再下载。fetch_sources.py含具体URL与状态记录；失败资料不会虚构全文。
7. Word正文生成后，需在Windows安装Word的情况下使用code/09_参赛论文/update_word_layout.ps1，并显式传入增强版docx的PaperPath。独立实例隐藏运行，更新目录、图表清单与页码。Poppler逐页渲染后再核对；verify_paper.py --confirm-visual只能在实际完成全部页面审阅后使用。
8. code/10_可视化增强论文/复现脚本是上次交付的备份副本；正式运行请通过run_project.py指向code或code/10目录作者脚本。不要把副本程序重复执行并误作新实验。

可选 `python run_project.py --stage validate`会重新核验数值并更新验收文件。重跑会改变产物及清单哈希，旧的完整性清单是归档时点快照，不是自动实时清单。package --check未缺少文件不等于所有依赖已安装，也不代表新机器已完成全流程实验。
''',encoding='utf-8')
    (META/'安全与版权说明.md').write_text('''# 安全与版权说明

用途：区分研究私有归档、软件执行与公开分发。生成逻辑：依据原文件类型及公开产品来源记录整理，不作授权或法律结论。

本包收录用户既有原件及公开收集资料，不等于获得第三方文献、统计年鉴、影像、字体或软件的再分发权。公开上传或对外发布前应核对各产品许可与隐私要求；现有出处和原始说明均保留。

未收录Codex账号、浏览器Cookie、用户主目录配置、虚拟环境或系统字体。原始统计年鉴中辅助_start.exe原样归档但未执行，分析程序不依赖它，不应在不明信任条件下启动。原始HTML、Office/PDF材料也只作为既有资料留档。

不以猜测补全真实农户、订单、入口或经营信息。原始修改时间仅用于确认复制期间文件没有变化，不能作为真实采集日期。所有网络行为在此归档流程中保持关闭。
''',encoding='utf-8')

    # Syntax and relocation checks do not execute any analytical scripts.
    for p in (ROOT/'code').rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    sys.path.insert(0,str(ROOT/'code'));os.environ['AGRI_PROJECT_ROOT']=str(ROOT)
    import project_paths
    assert project_paths.Path('D:/Desktop/code/config.json')==ROOT/'code/config.json'
    assert project_paths.Path('D:/Desktop/jianmo/11_本次公开补充/DEM_N41E119.tif').is_file()
    # Generated metadata are included alongside source copies in the same manifest.
    known={e['package_path'] for e in entries}
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or p.relative_to(ROOT).as_posix() in known:continue
        entries.append({'package_path':p.relative_to(ROOT).as_posix(),'package_bytes':p.stat().st_size,'package_sha256':digest(p),
            'original_path':'本次归档生成','original_bytes':'','original_sha256':'','adapted':False,
            'purpose':'数据包导航、溯源、复现、授权边界或索引说明','generation_logic':'build_complete_project_package.py整理既有项目证据生成；不补造数据或收集事实'})
    write_csv(META/'文件完整性清单.csv',entries,list(entries[0]))
    check=subprocess.run([sys.executable,str(ROOT/'run_project.py'),'--check'],capture_output=True,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONIOENCODING':'utf-8'},check=True)
    result=json.loads(check.stdout);assert result['passed']
    validation={'purpose':'完整项目数据包归档前验收','generation_logic':'流式复制+SHA256；程序AST；相对路径及已有论文直接输入哈希；未重求解',
        'passed':True,'original_raw_files':sum(base==DATA for base,_ in sources),'original_project_files':sum(base==CODE for base,_ in sources),
        'raw_bytes':sum(p.stat().st_size for base,p in sources if base==DATA),'original_files_total':len(sources),'provenance_records':len(provenance),
        'adapted_programs':len(adaptations),'original_programs_archived':len(adaptations),'portable_check':result,
        'verified_supplement_success':sum(r['status']!='failed' for r in records),'preserved_supplement_failures':sum(r['status']=='failed' for r in records),
        'note':'清单本身及本验收文件在ZIP最终独立校验中额外校验，避免循环自引用；未声称依赖齐全或全流程已在新机器执行'}
    write_json(META/'数据包归档验收.json',validation)
    log('复制与离线检查完成',total_bytes,total_bytes,f'{len(entries)}条完整性清单')

    files=sorted((p for p in ROOT.rglob('*') if p.is_file()),key=lambda p:p.relative_to(ROOT).as_posix())
    expected={NAME+'/'+e['package_path']:(e['package_sha256'],int(e['package_bytes'])) for e in entries}
    for p in [META/'文件完整性清单.csv',META/'数据包归档验收.json']:
        expected[NAME+'/'+p.relative_to(ROOT).as_posix()]=(digest(p),p.stat().st_size)
    assert len(files)==len(expected)
    total=sum(p.stat().st_size for p in files);done=0
    stored_ext={'.zip','.gz','.7z','.rar','.png','.jpg','.jpeg','.pdf','.xlsx','.docx','.pbf','.kmz','.mht'}
    with ZipFile(PART,'w',allowZip64=True,compression=ZIP_DEFLATED,compresslevel=1) as z:
        z.comment='用途：完整农业建模项目；生成逻辑：原数据、来源、程序与成果ZIP64归档，逐文件SHA256与CRC校验'.encode('utf-8')
        for i,p in enumerate(files,1):
            z.write(p,NAME+'/'+p.relative_to(ROOT).as_posix(),compress_type=ZIP_STORED if p.suffix.lower() in stored_ext else ZIP_DEFLATED,compresslevel=1)
            done+=p.stat().st_size;log('生成单个ZIP64压缩包',done,total,f'{i}/{len(files)} '+p.name)
    done=0
    with ZipFile(PART) as z:
        assert set(z.namelist())==set(expected)
        for i,item in enumerate(z.infolist(),1):
            h=hashlib.sha256();size=0
            with z.open(item) as f:
                for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block);size+=len(block)
            assert (h.hexdigest(),size)==expected[item.filename], 'ZIP条目哈希不符：'+item.filename
            done+=size;log('逐条读取ZIP校验CRC和SHA256',done,total,f'{i}/{len(files)}')
    archive_hash=digest(PART);PART.rename(ARCHIVE)
    (DEST/(NAME+'.zip.sha256')).write_text(archive_hash+'  '+ARCHIVE.name+'\n',encoding='utf-8')
    report={**validation,'purpose':'完整项目单ZIP最终验收','generation_logic':'原始文件SHA256复制核对、适配副本对照、离线检查及全部ZIP条目CRC/SHA256复读',
        'passed':True,'package_folder':str(ROOT),'archive_file':str(ARCHIVE),'archive_files':len(files),'uncompressed_bytes':total,
        'archive_bytes':ARCHIVE.stat().st_size,'archive_sha256':archive_hash,'elapsed_seconds':round(time.monotonic()-START,1)}
    write_json(DEST/'完整项目压缩包验收.json',report);log('归档完成',total,total,f'ZIP {ARCHIVE.stat().st_size/1024**3:.2f} GiB，{len(files)}文件')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
