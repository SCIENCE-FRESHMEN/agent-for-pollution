$ErrorActionPreference = "Stop"
$src = "C:\Users\25416\Desktop\agent for pollution\文献下载与命题流程_20260928.pptx"
$out = "C:\Users\25416\Desktop\agent for pollution\qa_gen\render"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$app = $null
foreach ($progid in @("PowerPoint.Application", "KWPP.Application", "wpp.Application")) {
    try { $app = New-Object -ComObject $progid; Write-Output "using $progid"; break } catch { Write-Output "fail $progid" }
}
if ($null -eq $app) { throw "no COM app" }
$pres = $app.Presentations.Open($src, -1, 0, 0)
$i = 1
foreach ($slide in $pres.Slides) {
    $slide.Export("$out\slide-$i.png", "PNG", 1600, 900)
    $i++
}
$pres.Close()
$app.Quit()
Write-Output "exported $($i - 1) slides"
