# vectors.npz 元数据

用途：模型公式、实现边界及稀疏交换文件，具体内容为vectors。

生成逻辑：模型推导、export_model.py独立重建。二进制采用本同名说明，不向数值矩阵插入文本。

大小：46512字节；SHA256：bb76c8a6585240c026f1786d51bc945fd8f517fd76203eb78c09150b4015d36f。

字段objective/cost/lower/upper/lb/ub/integrality/loss_offset。路线变量在前，未服务变量在后。目标省略常数loss_offset，风险面积需加回。
