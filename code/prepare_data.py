"""用途：构建真实区域描述、天气窗口、公开路网与研究服务单元。生成逻辑见各输出元数据。
服务单元是300m玉米网格，并非确权地块或病虫订单。全程不填造实测入口/报价。
"""
from pathlib import Path
import json,math,time,hashlib,shutil
import numpy as np,pandas as pd,rasterio,osmium
from rasterio.windows import from_bounds
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components,dijkstra
ROOT=Path('D:/Desktop/jianmo');OUT=Path('D:/Desktop/code');D=OUT/'02_处理数据';D.mkdir(exist_ok=True)
META={}
def csv(df,name,purpose,logic,source,kind='真实数据派生'):
    df=df.copy();df['_purpose']=purpose;df['_generation_logic']=logic;df['_source']=source;df['_evidence_type']=kind
    df.to_csv(D/name,index=False,encoding='utf-8-sig');META[name]={'purpose':purpose,'generation_logic':logic,'source':source,'evidence_type':kind,'rows':len(df),'columns':{c:str(df[c].dtype) for c in df}}
def jwrite(name,obj): (D/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
print('weather',flush=True)
weather=[];yearly=[];daily=[]
for p in sorted(ROOT.rglob('*hourly_2015-2025_ERA5Land+ERA5.csv')):
    df=pd.read_csv(p,comment='#'); dt=pd.to_datetime(df.time); df['county']=p.name.split('_')[0]; df['year']=dt.dt.year;df['month']=dt.dt.month;df['hour']=dt.dt.hour;df['date']=dt.dt.date.astype(str)
    df['wind_ms']=df.wind_speed_10m_era5/3.6
    required=df[['wind_ms','precipitation_era5','temperature_2m_era5_land']].notna().all(axis=1)
    df['eligible']=required & (df.wind_ms<=3.3)&(df.precipitation_era5==0)&(df.temperature_2m_era5_land<32)&df.hour.between(6,17)&~df.hour.isin([12,13])
    gs=df[df.month.isin([7,8])].copy(); gs['eligible_int']=gs.eligible.astype(int)
    a=gs.groupby(['county','year']).agg(hours=('eligible_int','size'),eligible_hours=('eligible_int','sum'),mean_wind_ms=('wind_ms','mean'),rain_mm=('precipitation_era5','sum')).reset_index();a['eligible_share']=a.eligible_hours/a.hours;yearly.append(a)
    daily.append(gs.groupby(['county','date']).agg(eligible_hours=('eligible_int','sum'),max_wind_ms=('wind_ms','max'),rain_mm=('precipitation_era5','sum')).reset_index())
    if df.county.iloc[0]=='建平县': weather.append(gs[['time','date','year','month','hour','wind_ms','precipitation_era5','temperature_2m_era5_land','relative_humidity_2m_era5_land','eligible']])
csv(pd.concat(yearly),'县域天气窗口_年统计.csv','比较20县域逐年7-8月可作业窗口','风速km/h除3.6；风<=3.3m/s、无雨、温<32C、6-18时并避12-14时；温度及避午小时为研究假设','用户Open-Meteo ERA5-Land+ERA5逐小时CSV')
csv(pd.concat(daily),'县域天气窗口_日统计.csv','历史窗口分布与情景抽样','逐日累加满足全部条件的小时，不把缺测当可作业','同上')
w=pd.concat(weather);csv(w,'建平_逐小时窗口.csv','路线可行性天气输入','保存7-8月小时数据及统一筛选；历史再分析仅供离线实验','用户建平逐小时CSV')
cols=[]
for p in sorted(ROOT.rglob('*hourly_2015-2025_ERA5Land+ERA5.csv')):
    df=pd.read_csv(p,comment='#');cols.extend({'county':p.name.split('_')[0],'column':c,'missing_fraction':float(df[c].isna().mean()),'rows':len(df)} for c in df.columns)
csv(pd.DataFrame(cols),'气象列缺失率.csv','核验ERA5-Land风雨空列','逐列NaN比例','用户20县域CSV')
p=next(ROOT.rglob('建平县*hourly_GS*.csv'));lines=p.read_text(encoding='utf-8-sig').splitlines();skip=lines.index('-END HEADER-')+1;n=pd.read_csv(p,skiprows=skip).replace(-999,np.nan)
n['time']=pd.to_datetime({'year':n.YEAR,'month':n.MO,'day':n.DY,'hour':n.HR});e=pd.read_csv(next(ROOT.rglob('建平县*hourly_2015-2025_ERA5Land+ERA5.csv')),comment='#');e['time']=pd.to_datetime(e.time);m=n.merge(e,on='time');m=m[m.MO.isin([7,8])]
cross=[]
for a,b,unit in [('T2M','temperature_2m_era5_land','C'),('PRECTOTCORR','precipitation_era5','mm/h')]:
    diff=m[a]-m[b];cross.append({'variable':a,'unit':unit,'n':int(diff.notna().sum()),'bias':float(diff.mean()),'MAE':float(diff.abs().mean()),'RMSE':float(np.sqrt((diff**2).mean())),'time_caveat':'NASA LST按15度经度带，119.64E归UTC+8；与Asia/Shanghai逐小时对齐','wind_note':'NASA为2m风，ERA5为10m风，不计算同高度误差'})
csv(pd.DataFrame(cross),'气象交叉产品核对.csv','评估气象来源差异','同日期小时气温/雨量比较；再分析间差异不等于站点精度','NASA POWER MERRA-2与ERA5-Land/ERA5')
print('raster',flush=True)
p=next(ROOT.rglob('*Liaoning*2020*.tif'));bounds=(119.57,41.35,119.71,41.45)
with rasterio.open(p) as ds:
    win=from_bounds(*bounds,ds.transform).round_offsets().round_lengths();maize=ds.read(1,window=win);tr=ds.window_transform(win);profile=ds.profile.copy();profile.update(width=maize.shape[1],height=maize.shape[0],transform=tr)
    with rasterio.open(D/'建平_2020玉米裁剪.tif','w',**profile) as dst:
        dst.write(maize,1);dst.update_tags(purpose='Historical maize spatial support; not cadastral parcels or confirmed 2025 crop',generation_logic='Window crop from CCD-Maize Liaoning 2020',source=str(p))
META['建平_2020玉米裁剪.tif']={'purpose':'提供空间真实背景，2020产品在2025前已可取得','generation_logic':'rasterio窗口裁剪119.57-119.71E,41.35-41.45N','source':str(p),'evidence_type':'历史遥感分类，不是2025作物真值'}
rr,cc=np.where(maize==1);lat=tr.f+(rr+.5)*tr.e;lon=tr.c+(cc+.5)*tr.a
pix_m2=(111320*abs(tr.a)*np.cos(np.radians(lat)))*(111320*abs(tr.e));x=(lon-119.64)*111320*math.cos(math.radians(41.4));y=(lat-41.4)*111320
cell=pd.DataFrame({'gx':np.floor(x/300).astype(int),'gy':np.floor(y/300).astype(int),'area_m2':pix_m2,'lon':lon,'lat':lat})
u=cell.groupby(['gx','gy']).agg(area_m2=('area_m2','sum'),lon=('lon','mean'),lat=('lat','mean'),pixels=('lon','size')).reset_index();u['area_mu']=u.area_m2/(2000/3);u['x_m']=(u.lon-119.64)*111320*math.cos(math.radians(41.4));u['y_m']=(u.lat-41.4)*111320
u=u[(u.area_mu>=15)&(u.area_mu<=110)].copy();u['center_distance_m']=np.hypot(u.x_m,u.y_m)
dem=ROOT/'11_本次公开补充/DEM_N41E119.tif'
if dem.exists():
    with rasterio.open(dem) as ds:
        coords=list(zip(u.lon,u.lat));u['elevation_m']=[v[0] for v in ds.sample(coords)]
        a=ds.read(1);dy=abs(ds.transform.e)*111320;dx=abs(ds.transform.a)*111320*math.cos(math.radians(41.4));grad_y,grad_x=np.gradient(a,dy,dx);sl=np.degrees(np.arctan(np.hypot(grad_x,grad_y)))
        u['regional_slope_deg']=[float(sl[ds.index(lo,la)]) for lo,la in coords]
else:u['elevation_m']=np.nan;u['regional_slope_deg']=np.nan
print('osm',flush=True)
class Roads(osmium.SimpleHandler):
    def __init__(self):super().__init__();self.edges=[];self.nodes={};self.ways=0
    def way(self,w):
        h=w.tags.get('highway');
        if not h or h in ['footway','steps','cycleway','path','pedestrian','motorway','motorway_link']:return
        ns=[]
        for n in w.nodes:
            if n.location.valid():
                lo,la=n.lon,n.lat
                if 119.50<=lo<=119.78 and 41.29<=la<=41.51:ns.append((n.ref,lo,la))
                else:ns.append(None)
        self.ways+=1
        for a,b in zip(ns,ns[1:]):
            if a is None or b is None:continue
            self.nodes[a[0]]=(a[1],a[2]);self.nodes[b[0]]=(b[1],b[2]);dist=math.hypot((a[1]-b[1])*111320*math.cos(math.radians(41.4)),(a[2]-b[2])*111320)
            speed={'trunk':35,'primary':30,'secondary':25,'tertiary':20,'residential':15,'unclassified':12,'service':10,'track':6}.get(h,10)
            ow=w.tags.get('oneway','no');sf=w.tags.get('surface','unknown');width=w.tags.get('width','unknown');access=w.tags.get('motor_vehicle',w.tags.get('access','unknown'))
            if access in ['no','private']:continue
            self.edges.append((a[0],b[0],dist,h,speed,ow,sf,width,access))
road_copy=OUT/'liaoning_input_copy.pbf'
if not road_copy.exists():shutil.copy2(next(ROOT.rglob('liaoning-latest.osm.pbf')),road_copy)
roads=Roads();roads.apply_file(str(road_copy),locations=True)
ids=list(roads.nodes);ix={v:i for i,v in enumerate(ids)};ri=[];ci=[];val=[];edge_rows=[]
for a,b,dist,h,speed,ow,sf,width,access in roads.edges:
    minute=dist/1000/speed*60
    if ow=='-1':ri.append(ix[b]);ci.append(ix[a]);val.append(minute)
    else:
        ri.append(ix[a]);ci.append(ix[b]);val.append(minute)
        if ow not in ['yes','1','true']:ri.append(ix[b]);ci.append(ix[a]);val.append(minute)
    edge_rows.append({'from_osm':a,'to_osm':b,'length_m':dist,'highway':h,'surface':sf,'width':width,'access':access,'oneway':ow,'scenario_speed_kmh':speed,'minutes':minute})
# 重复边取最小时间，避免稀疏矩阵自动相加。速度只是研究假设。
ed=pd.DataFrame({'r':ri,'c':ci,'v':val}).groupby(['r','c']).v.min().reset_index();g=coo_matrix((ed.v,(ed.r,ed.c)),shape=(len(ids),len(ids))).tocsr()
nc,labels=connected_components(g,directed=True,connection='strong');big=np.bincount(labels).argmax();eligible=np.where(labels==big)[0];xy=np.array([((roads.nodes[ids[z]][0]-119.64)*111320*math.cos(math.radians(41.4)),(roads.nodes[ids[z]][1]-41.4)*111320) for z in eligible]);tree=cKDTree(xy)
snap,node=tree.query(u[['x_m','y_m']].to_numpy());u['lastmile_gap_m']=snap;u['anchor_index']=eligible[node];u['entry_verified']=False;u['confirmed_demand']=False
# 系统抽样覆盖区域：按径向距离排序，再在前6km候选中均匀选50个，防止只取最容易服务的邻近单元。
pool=u[(u.center_distance_m<=6000)&(u.lastmile_gap_m<=1200)].sort_values(['center_distance_m','gx','gy']).reset_index(drop=True)
sel=np.unique(np.round(np.linspace(0,len(pool)-1,50)).astype(int));units=pool.iloc[sel].copy().reset_index(drop=True);units['unit_id']=['U%03d'%(i+1) for i in range(len(units))];units['group']=np.where(units.lastmile_gap_m<=units.lastmile_gap_m.median(),'near_road','far_road');units['risk_weight']=1.0;units['recommended_deadline_min']=600;units['hard_deadline_min']=720;units['demand_status']='未核验；场景假设全部单元有需求';units['ground_compatible']=False;units['purpose']='研究服务网格，非农户地块';units['generation_logic']='2020玉米像元300m聚合，15-110亩范围系统抽样'
depot_dist,depot_node=tree.query([0,0]);depot_index=int(eligible[depot_node]);indices=[depot_index]+units.anchor_index.astype(int).tolist();dm=dijkstra(g,directed=True,indices=indices)[:,indices];gap=np.r_[0,units.lastmile_gap_m.to_numpy()];lastmile_minutes=(gap[:,None]+gap[None,:])/1000/6*60;times=dm+lastmile_minutes;np.fill_diagonal(times,0)
np.save(D/'转场时间矩阵.npy',times);np.save(D/'已知道路时间矩阵.npy',dm)
META['转场时间矩阵.npy']={'purpose':'路线研究的代理转场时间','generation_logic':'有向OSM路段最短时间 + 未核验连接长度/假设6kmh；该连接仅场景计算，不构造实际道路','source':'用户OSM pbf','evidence_type':'研究假设与公开路网派生；不是实测时间','shape':list(times.shape)}
META['已知道路时间矩阵.npy']={'purpose':'隔离公开已知路网部分，供最后接入敏感性分析','generation_logic':'有向最短路，仅主强连通分量','source':'OSM','evidence_type':'公开路段+假设速度','shape':list(dm.shape)}
tm=pd.DataFrame(times,columns=['depot']+units.unit_id.tolist());tm.insert(0,'from',['depot']+units.unit_id.tolist());csv(tm,'转场时间矩阵.csv','可读时间矩阵；分钟','与npy相同；未经核验的连接保持假设身份','OSM+研究连接速度','代理输入')
csv(units,'研究服务单元.csv','50单元半实证设计实例','玉米网格面积、DEM宏观坡度、OSM接入缺口；全部订单和地面适配保持未核验','CCD-Maize2020+CopernicusDSM+OSM','真实空间派生，需求为研究场景')
csv(u,'全部候选服务网格.csv','记录抽样母体','300m聚合及面积过滤，保留所有候选','同上')
csv(pd.DataFrame(edge_rows),'研究区OSM路段.csv','通行信息缺失诊断与研究网络','提取highway、surface、width及access；unknown不等于通行','用户OSM')
nodes=pd.DataFrame([{'osm_id':k,'lon':v[0],'lat':v[1]} for k,v in roads.nodes.items()]);csv(nodes,'研究区OSM节点.csv','道路制图及最短路复现','原节点坐标','用户OSM')
geo={'type':'FeatureCollection','purpose':'GIS研究服务网格及核验状态','generation_logic':'300m格网外框转经纬度；非确权边界','features':[]}
for _,z in units.iterrows():
    x0=z.gx*300;y0=z.gy*300;coordinates=[[(119.64+(xx)/(111320*math.cos(math.radians(41.4))),41.4+yy/111320) for xx,yy in [(x0,y0),(x0+300,y0),(x0+300,y0+300),(x0,y0+300),(x0,y0)]]]
    geo['features'].append({'type':'Feature','geometry':{'type':'Polygon','coordinates':coordinates},'properties':{'unit_id':z.unit_id,'area_mu':z.area_mu,'entry_verified':False,'demand_confirmed':False}})
jwrite('研究服务单元.geojson',geo)
# 投档清单是可购设备信息，不能当设备存量。
p=next(ROOT.rglob('6-2*.xls'));equip=pd.read_excel(p,header=1);mask=equip.astype(str).apply(lambda c:c.str.contains('植保|喷雾|无人机',regex=True)).any(axis=1);csv(equip[mask],'植保相关投档设备.csv','识别可购装备类别','关键词筛选补贴投档表；不推定任何县的实际设备数','辽宁2025第一批投档清单')
pre=pd.read_csv(next(ROOT.rglob('_辽宁CCD-Maize逐年玉米面积.csv')));csv(pre,'辽宁玉米面积_原包派生记录.csv','保留前次产品面积核查记录','拷贝原包统计记录，非本次全省像元独立重算','用户面积CSV','用户既有派生结果')
jwrite('研究区摘要.json',{'purpose':'真实空间和缺失字段统计','generation_logic':'本脚本输出聚合','bounds':bounds,'maize_2020_mu':float(pix_m2.sum()/(2000/3)),'selected_units':len(units),'selected_area_mu':float(units.area_mu.sum()),'candidate_units':len(pool),'osm_nodes':len(ids),'osm_edges':len(edge_rows),'strong_components':nc,'surface_missing_share':float((pd.DataFrame(edge_rows).surface=='unknown').mean()),'width_missing_share':float((pd.DataFrame(edge_rows).width=='unknown').mean()),'median_lastmile_gap_m':float(units.lastmile_gap_m.median()),'max_lastmile_gap_m':float(units.lastmile_gap_m.max()),'depot':{'lon':roads.nodes[ids[depot_index]][0],'lat':roads.nodes[ids[depot_index]][1],'status':'路网锚点，非真实合作社'},'ground_primary_mode':'无入口核验，主算例不启用地面喷雾机'})
jwrite('数据字典_用途与生成逻辑.json',{'purpose':'逐文件元数据与字段类型','generation_logic':'处理函数自动登记','files':META})
print('prepared',len(units),'units',float(units.area_mu.sum()),flush=True)
