# MCP proxy control for the TC-10 listener scenarios (phase P8).
#   pwsh p8_proxy.ps1 info  <freecad pid>          proxy processes (command line, parent), :8765 owner, listener port rows
#   pwsh p8_proxy.ps1 stop  <freecad pid> <tag>    Stop-Process the proxy that LISTENs on :8765 (the test case's "the
#                                                  MCP proxy is stopped"), then show :8765 and the listener port rows
#   pwsh p8_proxy.ps1 start <freecad pid> <tag>    restart it by hand with the command line recorded at stop time and
#                                                  the FREECAD_BUDDY_* values of the last "operator settings:" line of
#                                                  addon.log (the test case's Cleanup); stdout/stderr to <tag>-proxy.*.log
param([string]$Action, [int]$FreecadPid, [string]$Tag = "p8")
$ErrorActionPreference = "Stop"
$evidence = $PSScriptRoot
$record = Get-Content "$env:APPDATA\FreeCAD\v1-1\freecad-buddy\rpc-$FreecadPid.json" | ConvertFrom-Json
$listenerPort = $record.port

function Show-State {
    $proxies = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*freecad_buddy*serve*" }
    $proxies | ForEach-Object { "proxy process $($_.ProcessId) parent $($_.ParentProcessId): $($_.CommandLine)" }
    ":8765 rows:"; netstat -ano | Select-String ":8765\s"
    "listener port $listenerPort rows:"; netstat -ano | Select-String ":$listenerPort\s"
}

if ($Action -eq "info") { Show-State; return }

if ($Action -eq "stop") {
    $owner = (Get-NetTCPConnection -LocalPort 8765 -State Listen).OwningProcess | Select-Object -First 1
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$owner"
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.ParentProcessId)" -EA SilentlyContinue
    $launch = if ($parent -and $parent.CommandLine -like "*freecad_buddy*serve*") { $parent.CommandLine } else { $process.CommandLine }
    $launch | Set-Content "$evidence\$Tag-proxy-cmdline.txt"
    "stopping proxy pid $owner (parent $($process.ParentProcessId)); launch command: $launch"
    Stop-Process -Id $owner
    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300 }
    Start-Sleep -Seconds 1
    Show-State
    return
}

if ($Action -eq "start") {
    $launch = (Get-Content "$evidence\$Tag-proxy-cmdline.txt" -Raw).Trim()
    $settings = Select-String -Path "$env:APPDATA\FreeCAD\v1-1\freecad-buddy\addon.log" -Pattern "operator settings:" | Select-Object -Last 1
    $applied = @()
    foreach ($match in [regex]::Matches($settings.Line, "(FREECAD_BUDDY_[A-Z_]+)='([^']*)' \((env|preference|default)\)")) {
        $name = $match.Groups[1].Value; $value = $match.Groups[2].Value -replace '\\\\', '\'
        Set-Item "env:$name" $value
        $applied += "$name=$value"
    }
    if ($launch -match '^"([^"]+)"\s+(.*)$') { $exe = $Matches[1]; $rest = $Matches[2] } else { $exe, $rest = $launch.Split(" ", 2) }
    $process = Start-Process -FilePath $exe -ArgumentList $rest -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput "$evidence\$Tag-proxy.stdout.log" -RedirectStandardError "$evidence\$Tag-proxy.stderr.log"
    $deadline = (Get-Date).AddSeconds(60)
    $health = $null
    while ((Get-Date) -lt $deadline) {
        try { $health = Invoke-RestMethod http://127.0.0.1:8765/healthz -TimeoutSec 2 } catch { $health = $null }
        if ($health -and $health.freecad_pid -eq $FreecadPid) { break }
        Start-Sleep -Milliseconds 500
    }
    "restarted: $exe $rest (launcher pid $($process.Id)) with $($applied -join ' ')"
    "healthz: $($health | ConvertTo-Json -Compress)"
    Show-State
}
