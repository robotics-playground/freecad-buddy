Add-Type @'
using System; using System.Runtime.InteropServices;
public static class K { [DllImport("kernel32.dll",SetLastError=true)] public static extern IntPtr OpenProcess(int a,bool b,int pid);
[DllImport("kernel32.dll",SetLastError=true)] public static extern bool TerminateProcess(IntPtr h,uint c); }
'@
$h=[K]::OpenProcess(1,$false,32336); "terminate 32336 -> " + [K]::TerminateProcess($h,1)
