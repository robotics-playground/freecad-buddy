# p3_launch.ps1 for phase P4: the UAT probe module, a temporary -u profile, no inherited
# FREECAD_BUDDY_* variable, the audit log in the run folder, then the scenario's extra variables.
# Records the addon.log byte length before the launch and, once /healthz names the pid, copies
# the bytes after that offset to <tag>-addon.log (read and copy only; addon.log is not touched).
# Appends one line to launch-log.tsv.
#   pwsh p4_launch.ps1 <tag> [NAME=VALUE ...]
param([string]$Tag, [Parameter(ValueFromRemainingArguments)][string[]]$Vars = @())
$ErrorActionPreference = "Stop"
$evidence = $PSScriptRoot
$repo = (Resolve-Path "$evidence\..\..\..\..\..").Path
$addonLog = "$env:APPDATA\FreeCAD\v1-1\freecad-buddy\addon.log"
$offset = if (Test-Path $addonLog) { (Get-Item $addonLog).Length } else { 0 }
"$offset" | Set-Content "$evidence\$Tag-addonlog-offset.txt"
Get-ChildItem env: | Where-Object Name -like "FREECAD_BUDDY_*" | ForEach-Object { Remove-Item "env:$($_.Name)" }
$env:FREECAD_BUDDY_AUDIT_LOG = "$evidence\$Tag-audit.jsonl"
foreach ($pair in $Vars) { $name, $value = $pair.Split("=", 2); Set-Item "env:$name" $value }
$profileDir = New-Item -ItemType Directory -Force "$env:TEMP\fcb-uat-p4-$Tag"
$arguments = @("-M", "`"$repo\tests\uat\probe`"", "-u", "`"$profileDir\user.cfg`"")
$start = Get-Date -Format o
$process = Start-Process -FilePath "C:\Program Files\FreeCAD 1.1\bin\freecad.exe" -ArgumentList $arguments -PassThru
$deadline = (Get-Date).AddSeconds(120)
$ready = $false
while ((Get-Date) -lt $deadline) {
    $discovery = Get-ChildItem "$env:APPDATA\FreeCAD\*\fcb-uat-probe\probe-$($process.Id).json" -EA SilentlyContinue
    try { $health = Invoke-RestMethod http://127.0.0.1:8765/healthz -TimeoutSec 2 } catch { $health = $null }
    if ($health -and $health.freecad_pid -eq $process.Id -and $discovery) { $ready = $true; break }
    Start-Sleep -Milliseconds 500
}
$envText = (@("FREECAD_BUDDY_AUDIT_LOG=$env:FREECAD_BUDDY_AUDIT_LOG") + $Vars) -join " "
"P4`t$start`t$($process.Id)`t$profileDir\user.cfg`t$envText`t" | Add-Content "$evidence\launch-log.tsv"
if (-not $ready) { throw "FreeCAD pid $($process.Id) not ready" }
$stream = [System.IO.File]::Open($addonLog, "Open", "Read", "ReadWrite")
try {
    $null = $stream.Seek($offset, "Begin")
    $reader = New-Object System.IO.StreamReader($stream)
    $reader.ReadToEnd() | Set-Content "$evidence\$Tag-addon.log" -NoNewline
} finally { $stream.Dispose() }
"pid=$($process.Id) profile=$profileDir\user.cfg env=$envText"
