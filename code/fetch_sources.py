"""用途：补充公开DEM与方法原始资料。生成逻辑：仅下载明确URL，记录HTTP、大小和SHA256；失败保持显式。
缺失的订单/入口/报价不能用公开宏观数据代替。输出原件到jianmo，获取台账到code。
"""
from pathlib import Path
import requests,json,hashlib,time
ROOT=Path('D:/Desktop/jianmo/11_本次公开补充'); ROOT.mkdir(exist_ok=True)
sources=[
('DEM_N41E119.tif','https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N41_00_E119_00_DEM/Copernicus_DSM_COG_10_N41_00_E119_00_DEM.tif','区域起伏筛查；不用于农机入口判定'),
('Bertsimas_Sim_2004.pdf','https://www.mit.edu/~dbertsim/papers/melvyn/The-Price-Of-Robustness-OR52.pdf','预算不确定集合方法'),
('Ropke_Pisinger_2006.html','https://pubsonline.informs.org/doi/10.1287/trsc.1050.0135','ALNS原始论文元数据与摘要'),
('Mavrotas_2009.html','https://www.sciencedirect.com/science/article/pii/S0096300309002574','epsilon约束原始论文；失败保留记录'),
('SciPy_milp.html','https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html','开源MILP求解器接口'),
('Copernicus_DEM_AWS.html','https://registry.opendata.aws/copernicus-dem/','补充DEM分发及使用条件'),
('Copernicus_DEM_product.html','https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM','DSM空间尺度和适用性'),
('OpenMeteo_archive.html','https://open-meteo.com/en/docs/historical-weather-api','确认风速默认km/h和再分析属性'),
('DJI_T50_specs.html','https://ag.dji.com/t50/specs','无人机载荷、满电能量、充电约束'),
('CCD_Maize_2023.html','https://www.nature.com/articles/s41597-023-02573-6','玉米遥感产品论文'),
('ERA5Land_2021.html','https://essd.copernicus.org/articles/13/4349/2021/','ERA5-Land原始论文'),
('CLCD_2021.html','https://essd.copernicus.org/articles/13/3907/2021/','CLCD原始论文'),
('Dantzig_Wolfe_1960.html','https://pubsonline.informs.org/doi/10.1287/opre.8.1.101','集合划分分解思想'),
('Held_Karp_1962.html','https://epubs.siam.org/doi/10.1137/0110015','路线动态规划原始论文'),
('CVaR_2000.pdf','https://www.dropbox.com/scl/fi/djjdb9nqrw5iuk3dvo57a/CVaR1_JOR.pdf?raw=1&rlkey=tlzsycbj7p7hilpps72xzhxk4','情景尾部损失分析依据'),
('NASA_POWER_hourly.html','https://power.larc.nasa.gov/docs/services/api/temporal/hourly/','确认2m风和LST经度带'),
('Geofabrik_Liaoning.html','https://download.geofabrik.de/asia/china/liaoning.html','核查道路下载产品而非现场完整性'),
('Competition_2026.html','https://cxcygl.bhu.edu.cn/comp/front/comp/info?id=2239','仅核查赛事存在；此页没有具体赛题原文'),
]
records=[]
for name,url,purpose in sources:
    p=ROOT/name; rec={'file':str(p),'url':url,'purpose':purpose,'generation_logic':'requests下载，核验状态及文件格式','retrieval_date':'2026-10-02'}
    try:
        if p.exists() and p.stat().st_size>1000: rec['status']='cached'
        else:
            r=requests.get(url,timeout=(20,90),headers={'User-Agent':'AgriculturalOptimizationResearch/1.0'},stream=True);rec['http_status']=r.status_code;r.raise_for_status()
            data=b''.join(r.iter_content(1024*1024))
            if name.endswith('.pdf') and not data.startswith(b'%PDF'): raise ValueError('响应不是PDF')
            if name.endswith('.tif') and data[:4] not in [b'II*\x00',b'MM\x00*']: raise ValueError('响应不是TIFF')
            p.write_bytes(data);rec['status']='downloaded'
        rec['bytes']=p.stat().st_size;rec['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception as e:rec['status']='failed';rec['error']=str(e)
    if rec['status'] in ['downloaded','cached']:
        (ROOT/(name+'.说明.md')).write_text('# 原件用途与生成逻辑\n\n用途：'+purpose+'。\n\n获取逻辑：requests原件下载，不修改内容。\n\n来源：'+url+'\n\n获取日期：2026-10-02。校验和见获取台账。\n',encoding='utf-8')
    records.append(rec);print(name,rec['status'],flush=True)
    (Path('D:/Desktop/code/01_数据审计')/'公开补充获取台账.json').write_text(json.dumps({'purpose':'补充数据及参考资料的成功与失败可追溯记录','generation_logic':'逐URL下载','records':records},ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'README.md').write_text('# 本次公开补充资料\n\n用途：补充原包缺失的区域DEM栅格和模型方法原始资料。生成逻辑：由code/fetch_sources.py下载，URL、校验和及失败记录见code/01_数据审计/公开补充获取台账.json。\n\nDEM为区域DSM，不能认证地块入口。公开检索未取得本研究片区真实订单、入口实测、班组作业轨迹、外援报价和病虫诊断，相关结果保持为区域数据驱动的半实证设计实验。\n',encoding='utf-8')
