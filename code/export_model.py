"""用途：把实际主模型导出为可复用稀疏矩阵、LP和变量/约束表。
生成逻辑：独立读取保存路线池，重建覆盖、班组、预算及公平系数，并复核主损失目标。
"""
from pathlib import Path
import json,numpy as np,pandas as pd
from scipy.sparse import lil_matrix,save_npz
from scipy.optimize import milp,Bounds,LinearConstraint
B=Path('D:/Desktop/code');D=B/'02_处理数据';R=B/'04_求解结果';E=B/'03_模型与方法/主模型导出';E.mkdir(parents=True,exist_ok=True)
C=json.loads((B/'config.json').read_text(encoding='utf-8'));U=pd.read_csv(D/'研究服务单元.csv');P=json.loads((R/'候选路线池.json').read_text(encoding='utf-8'))['plans'];n=len(U);m=len(P);area=U.area_mu.to_numpy();groups=list(U.group.unique());teams=sorted(set(p['team'] for p in P));a=lil_matrix((n+len(teams)+3,m+n));lo=[];hi=[];names=[];obj=np.zeros(m+n);cost=np.zeros(m+n)
for i in range(n):
    a[i,m+i]=1
    for j,p in enumerate(P):
        if str(i) in p['completed']:a[i,j]=1
    names.append('cover_'+U.unit_id.iloc[i]);lo.append(1);hi.append(1)
for t,team in enumerate(teams):
    row=n+t
    for j,p in enumerate(P):
        if p['team']==team:a[row,j]=1
    names.append('team_'+team);lo.append(0);hi.append(1)
row=n+len(teams)
for j,p in enumerate(P):obj[j]=-p['benefit'];cost[j]=p['cost'];a[row,j]=p['cost']
names.append('budget');lo.append(0);hi.append(C['budget_yuan'])
for z,g in enumerate(groups):
    row=n+len(teams)+1+z
    for j,p in enumerate(P):a[row,j]=sum(area[int(i)] for i,v in p['completed'].items() if U.group.iloc[int(i)]==g and v<=C['recommended_deadline_min'])
    names.append('fair_'+g);lo.append(C['minimum_group_timely_rate']*sum(area[U.group==g]));hi.append(np.inf)
mat=a.tocsr();save_npz(E/'A_sparse.npz',mat);np.savez(E/'vectors.npz',objective=obj,cost=cost,lower=np.array(lo),upper=np.array(hi),loss_offset=area.sum(),lb=np.zeros(m+n),ub=np.ones(m+n),integrality=np.ones(m+n))
pd.DataFrame({'variable':['lambda_'+str(j) for j in range(m)]+['u_'+str(i) for i in range(n)],'objective_coefficient':obj,'cost_coefficient':cost,'purpose':'变量与目标系数','generation_logic':'由保存路线池直接重建'}).to_csv(E/'variables.csv',index=False,encoding='utf-8-sig')
pd.DataFrame({'constraint':names,'lower':lo,'upper':hi,'purpose':'约束边界和业务含义','generation_logic':'覆盖等式、班组最多一包、预算及两组及时服务'}).to_csv(E/'constraints.csv',index=False,encoding='utf-8-sig')
def expr(row):
    return ' '.join(('+' if v>=0 else '-')+' '+format(abs(v),'.12g')+' '+('lambda_'+str(j) if j<m else 'u_'+str(j-m)) for j,v in zip(row.indices,row.data)) or '0'
lines=['\\ Purpose: executable restricted route-pool MILP; generated from candidate routes.','\\ Loss objective offset = '+str(float(area.sum()))+' mu.','Minimize',' obj: '+expr(__import__('scipy').sparse.csr_matrix(obj.reshape(1,-1))),'Subject To']
for r,name in enumerate(names):
    ex=expr(mat[r])
    if lo[r]==hi[r]:lines.append(' '+name+': '+ex+' = '+str(lo[r]))
    else:
        if np.isfinite(lo[r]) and lo[r]!=0:lines.append(' '+name+'_lb: '+ex+' >= '+str(lo[r]))
        if np.isfinite(hi[r]):lines.append(' '+name+'_ub: '+ex+' <= '+str(hi[r]))
lines+=['Binary']+[' lambda_'+str(j) for j in range(m)]+[' u_'+str(i) for i in range(n)]+['End'];(E/'model.lp').write_text('\n'.join(lines),encoding='utf-8')
res=milp(obj,integrality=np.ones(m+n),bounds=Bounds(np.zeros(m+n),np.ones(m+n)),constraints=LinearConstraint(mat,lo,hi),options={'time_limit':30,'mip_rel_gap':.001});primary=json.loads((R/'主方案.json').read_text(encoding='utf-8'))['metrics']['risk_proxy_loss_mu'];check={'purpose':'独立导出矩阵求解与主程序目标核对','generation_logic':'重建稀疏模型并重新求解；不共享主程序的矩阵构造函数','variables':m+n,'constraints':mat.shape[0],'nonzeros':mat.nnz,'status':int(res.status),'exported_loss_mu':float(res.fun+area.sum()),'original_loss_mu':primary,'objective_agrees':bool(abs(res.fun+area.sum()-primary)<1e-4)};(E/'导出模型核对.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8');(E/'README.md').write_text('# 主模型交换文件\n\n用途：供其他优化器独立复现。生成逻辑：export_model.py从已保存候选路线池重新构建，验证损失与主方案一致。\n\nmodel.lp含最小损失目标（省略常数面积），二级成本优化见变量表；A_sparse.npz为CSR约束矩阵；vectors.npz保存obj/cost/lower/upper/lb/ub/integrality/loss_offset，各二元变量前m列为路线，后n列为未服务。数值二进制文件采用同目录本说明及逐文件说明作为元数据载体。不能将NPZ文件当作源地块/真实订单数据。\n',encoding='utf-8');print(check)
