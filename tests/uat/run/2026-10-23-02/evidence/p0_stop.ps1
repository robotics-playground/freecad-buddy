# End the FreeCAD p0_launch.ps1 started, the way the runner does (launch.stop): end the process,
# delete its probe discovery file, wait until :8765 is free, then write the end time into the
# matching launch-log.tsv line.
#   pwsh p0_stop.ps1 <pid>
param([int]$ProcessId)
$evidence = $PSScriptRoot
Stop-Process -Id $ProcessId -Force -EA SilentlyContinue
Wait-Process -Id $ProcessId -Timeout 30 -EA SilentlyContinue
Get-ChildItem "$env:APPDATA\FreeCAD\*\fcb-uat-probe\probe-$ProcessId.json" -EA SilentlyContinue | Remove-Item
$deadline = (Get-Date).AddSeconds(15)
while ((Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
}
$end = Get-Date -Format o
$log = "$evidence\launch-log.tsv"
(Get-Content $log) | ForEach-Object {
    $cells = $_.Split("`t")
    if ($cells[2] -eq "$ProcessId" -and $cells[5] -eq "") { $cells[5] = $end; $cells -join "`t" } else { $_ }
} | Set-Content $log
"freecad=$((Get-Process freecad* -EA SilentlyContinue | Measure-Object).Count) listen8765=$([bool](Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue))"
