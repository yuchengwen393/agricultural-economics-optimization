# 用途：从已有原包复现研究设计分析、模型、图表及验收，不修改用户原始数据。
# 生成逻辑：按输入依赖顺序调用各独立生成器，失败立即停止；网络补充是显式可选步骤。
param([switch]$FetchPublic)
$ErrorActionPreference = 'Stop'
$taskPython = 'D:\Desktop\code\.venv\Scripts\python.exe'
$taskRoot = 'D:\Desktop\code'
if (-not (Test-Path -LiteralPath $taskPython)) { throw '未找到本次Python环境；请先依据requirements.lock.txt准备Python3.12依赖。' }
$taskSteps = @('audit_inputs.py')
if ($FetchPublic) { $taskSteps += 'fetch_sources.py' }
$taskSteps += @('prepare_data.py','optimization.py','supplementary.py','export_model.py','make_figures.py','plot_paper_standard.py','finalize_paper_figures.py','validate_outputs.py')
foreach ($taskStep in $taskSteps) {
    Write-Host "运行 $taskStep"
    & $taskPython (Join-Path $taskRoot $taskStep)
    if ($LASTEXITCODE -ne 0) { throw "$taskStep 未完成；检查错误并保留已生成成果。" }
}
Write-Host '完成。入口：D:\Desktop\code\README_成果总入口.md'
