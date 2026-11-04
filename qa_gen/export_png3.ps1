$ErrorActionPreference = "Stop"
$src = "C:\Users\25416\Desktop\agent for pollution\文献下载与命题流程_20260928.pptx"
$tmp = "C:\Users\25416\Downloads\deck_tmp.pptx"
Copy-Item $src $tmp -Force
$out = "C:\Users\25416\Desktop\agent for pollution\qa_gen\render"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$pres = $null
foreach ($progid in @("KWPP.Application", "wpp.Application", "PowerPoint.Application")) {
    try {
        $app = New-Object -ComObject $progid
        try { $pres = $app.Presentations.Open($tmp, -1, 0, 0); Write-Output "opened via $progid"; break }
        catch { Write-Output "open-fail $progid : $($_.Exception.Message.Split("`n")[0])"; $app = $null }
    } catch { Write-Output "no $progid" }
}
if ($null -eq $pres) { throw "all COM open attempts failed" }
$i = 1
foreach ($slide in $pres.Slides) {
    $slide.Export("$out\slide-$i.png", "PNG", 1600, 900)
    $i++
}
$pres.Close()
Write-Output "exported $($i - 1) slides"
