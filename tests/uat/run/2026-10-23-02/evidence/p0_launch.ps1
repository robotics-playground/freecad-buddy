# Start FreeCAD 1.1.4 the way the runner does (launch.py): the UAT probe module, a temporary -u
# profile, no inherited FREECAD_BUDDY_* variable, the audit log in the run folder, then the extra
# variables of the scenario's launch map. Waits for /healthz naming the pid and the probe
# discovery file, then appends one line to launch-log.tsv.
#   pwsh p0_launch.ps1 <tag> [NAME=VALUE ...]
param([string]$Tag, [string[]]$Vars = @())
$ErrorActionPreference = "Stop"
$evidence = $PSScriptRoot
$repo = (Resolve-Path "$evidence\..\..\..\..\..").Path
Get-ChildItem env: | Where-Object Name -like "FREECAD_BUDDY_*" | ForEach-Object { Remove-Item "env:$($_.Name)" }
$env:FREECAD_BUDDY_AUDIT_LOG = "$evidence\$Tag-audit.jsonl"
foreach ($pair in $Vars) { $name, $value = $pair.Split("=", 2); Set-Item "env:$name" $value }
$profileDir = New-Item -ItemType Directory -Force "$env:TEMP\fcb-uat-p0-$Tag"
$start = Get-Date -Format o
$process = Start-Process -FilePath "C:\Program Files\FreeCAD 1.1\bin\freecad.exe" `
    -ArgumentList "-M", "`"$repo\tests\uat\probe`"", "-u", "`"$profileDir\user.cfg`"" -PassThru
$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline) {
    try { $health = Invoke-RestMethod http://127.0.0.1:8765/healthz -TimeoutSec 2 } catch { $health = $null }
    $discovery = Get-ChildItem "$env:APPDATA\FreeCAD\*\fcb-uat-probe\probe-$($process.Id).json" -EA SilentlyContinue
    if ($health -and $health.freecad_pid -eq $process.Id -and $discovery) { break }
    Start-Sleep -Milliseconds 500
}
if (-not ($health -and $health.freecad_pid -eq $process.Id)) { throw "FreeCAD pid $($process.Id) not ready" }
$envText = (@("FREECAD_BUDDY_AUDIT_LOG=$env:FREECAD_BUDDY_AUDIT_LOG") + $Vars) -join " "
"P0`t$start`t$($process.Id)`t$profileDir\user.cfg`t$envText`t" | Add-Content "$evidence\launch-log.tsv"
"pid=$($process.Id) profile=$profileDir\user.cfg env=$envText"
