# p0_launch.ps1 for phase P1: the UAT probe module, a temporary -u profile, no inherited
# FREECAD_BUDDY_* variable, the audit log in the run folder, then the scenario's extra variables.
# Without -NoProxy it waits for /healthz naming the pid; with -NoProxy (proxy suppressed or :8765
# held by another program) it waits for the probe discovery file and rpc-<pid>.json instead, then
# 15 s more so the addon's 10 s port wait is over. Appends one line to launch-log.tsv.
#   pwsh p1_launch.ps1 <tag> [-NoProxy] [NAME=VALUE ...]
param([string]$Tag, [switch]$NoProxy, [Parameter(ValueFromRemainingArguments)][string[]]$Vars = @())
$ErrorActionPreference = "Stop"
$evidence = $PSScriptRoot
$repo = (Resolve-Path "$evidence\..\..\..\..\..").Path
Get-ChildItem env: | Where-Object Name -like "FREECAD_BUDDY_*" | ForEach-Object { Remove-Item "env:$($_.Name)" }
$env:FREECAD_BUDDY_AUDIT_LOG = "$evidence\$Tag-audit.jsonl"
foreach ($pair in $Vars) { $name, $value = $pair.Split("=", 2); Set-Item "env:$name" $value }
$profileDir = New-Item -ItemType Directory -Force "$env:TEMP\fcb-uat-p1-$Tag"
$start = Get-Date -Format o
$process = Start-Process -FilePath "C:\Program Files\FreeCAD 1.1\bin\freecad.exe" `
    -ArgumentList "-M", "`"$repo\tests\uat\probe`"", "-u", "`"$profileDir\user.cfg`"" -PassThru
$deadline = (Get-Date).AddSeconds(120)
$ready = $false
while ((Get-Date) -lt $deadline) {
    $discovery = Get-ChildItem "$env:APPDATA\FreeCAD\*\fcb-uat-probe\probe-$($process.Id).json" -EA SilentlyContinue
    if ($NoProxy) {
        $rpc = Test-Path "$env:APPDATA\FreeCAD\v1-1\freecad-buddy\rpc-$($process.Id).json"
        if ($discovery -and $rpc) { $ready = $true; break }
    } else {
        try { $health = Invoke-RestMethod http://127.0.0.1:8765/healthz -TimeoutSec 2 } catch { $health = $null }
        if ($health -and $health.freecad_pid -eq $process.Id -and $discovery) { $ready = $true; break }
    }
    Start-Sleep -Milliseconds 500
}
$envText = (@("FREECAD_BUDDY_AUDIT_LOG=$env:FREECAD_BUDDY_AUDIT_LOG") + $Vars) -join " "
"P1`t$start`t$($process.Id)`t$profileDir\user.cfg`t$envText`t" | Add-Content "$evidence\launch-log.tsv"
if (-not $ready) { throw "FreeCAD pid $($process.Id) not ready" }
if ($NoProxy) { Start-Sleep -Seconds 15 }
"pid=$($process.Id) profile=$profileDir\user.cfg env=$envText"
