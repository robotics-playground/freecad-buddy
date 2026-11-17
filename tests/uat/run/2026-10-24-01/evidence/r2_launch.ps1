# r2_launch.ps1 for phase R2 (from 2026-10-23-02 p10_launch.ps1): the UAT probe module, a temporary
# -u AND -s profile, no inherited FREECAD_BUDDY_* variable, the audit log in the run folder, then
# the scenario's extra variables. No profile pre-seed (TC-06-01 seeds AntiAliasing in its Given).
# Records the addon.log byte length before the launch, waits for the probe discovery file and
# rpc-<pid>.json (and, unless -NoProxy, /healthz naming the pid), copies the addon.log bytes after
# the offset to <tag>-addon.log (read only), appends one line to launch-log.tsv, and prints the
# developer user.cfg SHA-256 and whether the shell can open the process handle.
#   pwsh r2_launch.ps1 <tag> [-OpenFile <path>] [-NoProxy] [NAME=VALUE ...]
[CmdletBinding(PositionalBinding = $false)]
param([Parameter(Position = 0)][string]$Tag, [string]$OpenFile = "", [switch]$NoProxy,
      [Parameter(ValueFromRemainingArguments)][string[]]$Vars = @())
$ErrorActionPreference = "Stop"
$evidence = $PSScriptRoot
$repo = (Resolve-Path "$evidence\..\..\..\..\..").Path
$addonLog = "$env:APPDATA\FreeCAD\v1-1\freecad-buddy\addon.log"
$offset = if (Test-Path $addonLog) { (Get-Item $addonLog).Length } else { 0 }
"$offset" | Set-Content "$evidence\$Tag-addonlog-offset.txt"
Get-ChildItem env: | Where-Object Name -like "FREECAD_BUDDY_*" | ForEach-Object { Remove-Item "env:$($_.Name)" }
$env:FREECAD_BUDDY_AUDIT_LOG = "$evidence\$Tag-audit.jsonl"
foreach ($pair in $Vars) { $name, $value = $pair.Split("=", 2); Set-Item "env:$name" $value }
$profileDir = New-Item -ItemType Directory -Force "$env:TEMP\fcb-uat-r2-$Tag"
$arguments = @("-M", "`"$repo\tests\uat\probe`"", "-u", "`"$profileDir\user.cfg`"", "-s", "`"$profileDir\system.cfg`"")
if ($OpenFile) { $arguments += "`"$OpenFile`"" }
$start = Get-Date -Format o
$process = Start-Process -FilePath "C:\Program Files\FreeCAD 1.1\bin\freecad.exe" -ArgumentList $arguments -PassThru
$deadline = (Get-Date).AddSeconds(120)
$ready = $false
while ((Get-Date) -lt $deadline) {
    $discovery = Get-ChildItem "$env:APPDATA\FreeCAD\*\fcb-uat-probe\probe-$($process.Id).json" -EA SilentlyContinue
    $rpc = Test-Path "$env:APPDATA\FreeCAD\v1-1\freecad-buddy\rpc-$($process.Id).json"
    if ($NoProxy) {
        if ($discovery -and $rpc) { $ready = $true; break }
    } else {
        try { $health = Invoke-RestMethod http://127.0.0.1:8765/healthz -TimeoutSec 2 } catch { $health = $null }
        if ($health -and $health.freecad_pid -eq $process.Id -and $discovery) { $ready = $true; break }
    }
    Start-Sleep -Milliseconds 500
}
$envText = ((@("FREECAD_BUDDY_AUDIT_LOG=$env:FREECAD_BUDDY_AUDIT_LOG") + $Vars) -join " ") + $(if ($OpenFile) { " (file argument: $OpenFile)" } else { "" })
"R2 $Tag`t$start`t$($process.Id)`t$profileDir\user.cfg + system.cfg`t$envText`t" | Add-Content "$evidence\launch-log.tsv"
if (-not $ready) { throw "FreeCAD pid $($process.Id) not ready" }
if ($NoProxy) { Start-Sleep -Seconds 3 }
$stream = [System.IO.File]::Open($addonLog, "Open", "Read", "ReadWrite")
try {
    $null = $stream.Seek($offset, "Begin")
    $reader = New-Object System.IO.StreamReader($stream)
    $reader.ReadToEnd() | Set-Content "$evidence\$Tag-addon.log" -NoNewline
} finally { $stream.Dispose() }
$hash = (Get-FileHash "$env:APPDATA\FreeCAD\v1-1\user.cfg" -Algorithm SHA256).Hash.ToLower()
try { [void]$process.get_Handle(); $handle = "ok" } catch { $handle = "denied" }
"pid=$($process.Id) profile=$profileDir env=$envText handle=$handle user.cfg=$hash"
