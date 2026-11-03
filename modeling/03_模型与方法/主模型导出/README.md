# 主模型交换文件

用途：供其他优化器独立复现。生成逻辑：export_model.py从已保存候选路线池重新构建，验证损失与主方案一致。

model.lp含最小损失目标（省略常数面积），二级成本优化见变量表；A_sparse.npz为CSR约束矩阵；vectors.npz保存obj/cost/lower/upper/lb/ub/integrality/loss_offset，各二元变量前m列为路线，后n列为未服务。数值二进制文件采用同目录本说明及逐文件说明作为元数据载体。不能将NPZ文件当作源地块/真实订单数据。
