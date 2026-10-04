# Stop only the MCP proxy (the :8765 listener and its .venv launcher parent). FreeCAD is not touched.
# Stop-Process is refused ("Access is denied") for the addon-spawned proxy from this shell, while
# OpenProcess(PROCESS_TERMINATE) is granted, so TerminateProcess is called directly.
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class K { [DllImport("kernel32.dll",SetLastError=true)] public static extern IntPtr OpenProcess(int a,bool b,int pid);
[DllImport("kernel32.dll",SetLastError=true)] public static extern bool TerminateProcess(IntPtr h,uint c);
[DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h); }
'@
function Invoke-Terminate([int]$id) { $h=[K]::OpenProcess(1,$false,$id); $ok=[K]::TerminateProcess($h,1); [K]::CloseHandle($h)|Out-Null; "terminate $id -> $ok" }
$l = (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue).OwningProcess
if (-not $l) { "no :8765 listener"; exit 0 }
$parent = (Get-CimInstance Win32_Process -Filter "ProcessId=$l").ParentProcessId
$pp = Get-Process -Id $parent -ErrorAction SilentlyContinue
"listener pid $l parent $parent ($($pp.ProcessName))"
Invoke-Terminate $l
if ($pp -and ($pp.ProcessName -like 'python*')) { Invoke-Terminate $parent }
Start-Sleep 1
"after: " + ((Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count) + " :8765 listeners"
