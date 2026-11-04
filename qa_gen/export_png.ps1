$ErrorActionPreference = "Stop"
$src = "C:\Users\25416\Desktop\agent for pollution\文献下载与命题流程_20260928.pptx"
$out = "C:\Users\25416\Desktop\agent for pollution\qa_gen\render"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$pp = New-Object -ComObject PowerPoint.Application
$pres = $pp.Presentations.Open($src, $true, $false, $false)
$i = 1
foreach ($slide in $pres.Slides) {
    $slide.Export("$out\slide-$i.png", "PNG", 1600, 900)
    $i++
}
$pres.Close()
$pp.Quit()
Write-Output "exported $i slides"
