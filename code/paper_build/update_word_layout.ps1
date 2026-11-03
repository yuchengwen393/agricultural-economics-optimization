# 用途：以独立隐藏Word实例更新目录、图表清单与页码，并导出排版检查PDF。
# 生成逻辑：仅打开本次生成文稿；更新字段并统计正文字符，关闭独立实例。
param([string]$PaperPath='D:\Desktop\code\09_参赛论文\空天地信息支持下辽宁丘陵玉米植保协同调度优化研究_匿名参赛版.docx')
$ErrorActionPreference='Stop'
$paperRoot=Split-Path -Parent $PaperPath
$qaRoot=Join-Path $paperRoot '排版核验'
New-Item -ItemType Directory -Path $qaRoot -Force | Out-Null
$wordApp=$null
$paperDoc=$null
try {
    $wordApp=New-Object -ComObject Word.Application
    $wordApp.Visible=$false
    $wordApp.DisplayAlerts=0
    $paperDoc=$wordApp.Documents.Open($PaperPath,$false,$false)
    Write-Output 'Word document opened; updating fields.'
    for($sectionIndex=4;$sectionIndex -le $paperDoc.Sections.Count;$sectionIndex++){
        $paperDoc.Sections.Item($sectionIndex).Footers.Item(1).PageNumbers.RestartNumberingAtSection=$false
    }
    $paperDoc.Fields.Update() | Out-Null
    $paperDoc.Repaginate()
    foreach($toc in $paperDoc.TablesOfContents){$toc.Update()}
    foreach($tof in $paperDoc.TablesOfFigures){$tof.Update()}
    $paperDoc.Repaginate()
    foreach($toc in $paperDoc.TablesOfContents){$toc.UpdatePageNumbers()}
    foreach($tof in $paperDoc.TablesOfFigures){$tof.UpdatePageNumbers()}
    $paperDoc.Save()
    $bodyRange=$paperDoc.Range($paperDoc.Bookmarks.Item('body_start').Range.Start,$paperDoc.Bookmarks.Item('body_end').Range.End)
    $stats=[ordered]@{purpose='Word实际分页、正文字符与字段检查';generation_logic='独立Word COM实例更新全部域，正文起止书签范围ComputeStatistics';pages=$paperDoc.ComputeStatistics(2);body_characters_no_spaces=$bodyRange.ComputeStatistics(3);body_characters_with_spaces=$bodyRange.ComputeStatistics(5);body_words=$bodyRange.ComputeStatistics(0);native_equations=$paperDoc.OMaths.Count;word_version=$wordApp.Version;toc_count=$paperDoc.TablesOfContents.Count;figure_list_count=$paperDoc.TablesOfFigures.Count}
    $headings=@()
    foreach($p in $paperDoc.Paragraphs){
        if($p.OutlineLevel -le 2){$headings+=@{text=$p.Range.Text.Trim();page=$p.Range.Information(1);physical_page=$p.Range.Information(3)}}
    }
    $stats['headings']=$headings
    $stats | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $qaRoot 'Word分页与字数.json') -Encoding utf8
    $pdfPath=Join-Path $qaRoot '论文排版核验.pdf'
    $paperDoc.ExportAsFixedFormat($pdfPath,17)
    [pscustomobject]$stats | Select-Object pages,body_characters_no_spaces,body_words,native_equations,toc_count,figure_list_count | ConvertTo-Json
} finally {
    if($null -ne $paperDoc){$paperDoc.Close(0);[void][Runtime.InteropServices.Marshal]::ReleaseComObject($paperDoc)}
    if($null -ne $wordApp){$wordApp.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp)}
}
