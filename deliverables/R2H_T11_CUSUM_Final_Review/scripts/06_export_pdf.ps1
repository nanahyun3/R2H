# Word COM 으로 DOCX 의 목차·쪽 번호 필드를 갱신해 다시 저장하고, 같은 세션에서 PDF 로 내보낸다 (DOCX 와 PDF 의 쪽 흐름 일치).
# 사용: powershell.exe -ExecutionPolicy Bypass -File 06_export_pdf.ps1 -Docx C:\...\report.docx -Pdf C:\...\report.pdf
param([Parameter(Mandatory=$true)][string]$Docx, [Parameter(Mandatory=$true)][string]$Pdf)
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx, $false, $false)
    $doc.Fields.Update() | Out-Null
    foreach ($t in $doc.TablesOfContents) { $t.Update() | Out-Null }
    $doc.Repaginate()
    foreach ($t in $doc.TablesOfContents) { $t.UpdatePageNumbers() | Out-Null }
    foreach ($s in $doc.Sections) { foreach ($h in $s.Footers) { $h.Range.Fields.Update() | Out-Null } }
    $doc.Save()
    # 17 = wdExportFormatPDF (인수를 더 넘기면 이 환경의 COM 바인딩에서 오류 없이 파일이 생기지 않았다)
    $doc.ExportAsFixedFormat($Pdf, 17)
    if (-not (Test-Path $Pdf)) { throw "PDF not written: $Pdf" }
    "pages=" + $doc.ComputeStatistics(2)
    $doc.Close($false)
} finally {
    $word.Quit()
}
