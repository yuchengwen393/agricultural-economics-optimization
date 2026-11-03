# A_sparse.npz 元数据

用途：模型公式、实现边界及稀疏交换文件，具体内容为A_sparse。

生成逻辑：模型推导、export_model.py独立重建。二进制采用本同名说明，不向数值矩阵插入文本。

大小：26148字节；SHA256：bd8ff5cfc85d76aaff93bc083f2352ccf9e8ab4b04cd8d79e97ae63c2347a45e。

SciPy CSR稀疏约束矩阵58×1090，8847非零；变量、约束索引分别见variables.csv/constraints.csv。
