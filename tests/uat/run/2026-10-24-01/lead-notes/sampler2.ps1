param([int]$WezPid, [double]$MaxMinutes = 300)
$ErrorActionPreference = 'Continue'
$out = Split-Path $MyInvocation.MyCommand.Path
Add-Type -ReferencedAssemblies System.Drawing, System.Windows.Forms -TypeDefinition @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class P2 {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
  [StructLayout(LayoutKind.Sequential)] struct MOUSEINPUT { public int dx, dy; public uint data, flags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public MOUSEINPUT mi; public long pad; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO i);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string t);
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] static extern uint SendInput(uint n, INPUT[] i, int size);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int w, int ht, uint f);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc p, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int i);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  public static uint IdleMs() { var i = new LASTINPUTINFO(); i.cbSize = 8; GetLastInputInfo(ref i); return (uint)Environment.TickCount - i.dwTime; }
  public static string Hash(IntPtr h) {
    RECT r; if (h == IntPtr.Zero || !GetWindowRect(h, out r)) return "nohwnd";
    int w = r.R - r.L, ht = r.B - r.T; if (w <= 0 || ht <= 0) return "empty";
    using (var bmp = new Bitmap(w, ht, PixelFormat.Format32bppArgb)) {
      using (var g = Graphics.FromImage(bmp)) g.CopyFromScreen(r.L, r.T, 0, 0, new Size(w, ht));
      var d = bmp.LockBits(new Rectangle(0, 0, w, ht), ImageLockMode.ReadOnly, bmp.PixelFormat);
      var buf = new byte[d.Stride * ht]; Marshal.Copy(d.Scan0, buf, 0, buf.Length); bmp.UnlockBits(d);
      ulong f = 14695981039346656037UL; foreach (var x in buf) { f ^= x; f *= 1099511628211UL; }
      return f.ToString("X16");
    }
  }
  public static void Shot(string path) {
    var s = System.Windows.Forms.Screen.PrimaryScreen.Bounds;
    using (var bmp = new Bitmap(s.Width, s.Height)) { using (var g = Graphics.FromImage(bmp)) g.CopyFromScreen(s.X, s.Y, 0, 0, s.Size); bmp.Save(path, ImageFormat.Png); }
  }
  public static void SendMove(int dx, int dy) {
    var i = new INPUT[1]; i[0].type = 0; i[0].mi.dx = dx; i[0].mi.dy = dy; i[0].mi.flags = 1;
    SendInput(1, i, Marshal.SizeOf(typeof(INPUT)));
  }
  public static List<IntPtr> Overlays() {
    var o = new List<IntPtr>();
    EnumWindows((h, l) => { var c = new StringBuilder(128); GetClassName(h, c, 128); if (c.ToString() == "Cua.AgentCursorOverlay") o.Add(h); return true; }, IntPtr.Zero);
    return o;
  }
  public static List<string> ZOrder(int max) {
    var o = new List<string>(); int i = 0;
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h) || i >= max) return true;
      uint p; GetWindowThreadProcessId(h, out p); var c = new StringBuilder(128); GetClassName(h, c, 128);
      var t = new StringBuilder(80); GetWindowText(h, t, 80); RECT r; GetWindowRect(h, out r);
      if (r.R - r.L <= 1) return true;
      o.Add((i++) + " pid=" + p + " 0x" + h.ToString("X") + " ex=0x" + GetWindowLong(h, -20).ToString("X") + " " + c + " '" + t + "' " + r.L + "," + r.T + "," + r.R + "," + r.B);
      return true; }, IntPtr.Zero);
    return o;
  }
}
'@
[P2]::SetProcessDpiAwarenessContext([IntPtr]::new(-4)) | Out-Null
$log = Join-Path $out 'freeze2.log'
function Log($m) { $line = "{0:MM-dd HH:mm:ss} {1}" -f (Get-Date), $m; for ($i = 0; $i -lt 5; $i++) { try { [IO.File]::AppendAllText($log, $line + "`r`n"); break } catch { Start-Sleep -Milliseconds 200 } }; Write-Output $line }
$gdi = [P2]::FindWindow([NullString]::Value, 'FreezeProbe-GDI')
$wez = (Get-Process -Id $WezPid).MainWindowHandle
$topmost = [IntPtr]::new(-1)
[P2]::SetWindowPos($wez, $topmost, 0, 1255, 600, 120, 0x10) | Out-Null
[P2]::SetWindowPos($gdi, $topmost, 610, 1255, 420, 120, 0x10) | Out-Null
Log "START gdi=0x$($gdi.ToString('X')) wez=0x$($wez.ToString('X')) overlays=$(([P2]::Overlays() | % { '0x' + $_.ToString('X') }) -join ',')"
$prev = @{}; $stale = @{ gdi = 0; wez = 0 }; $fresh = 0
$phase = 'watch'; $t0 = Get-Date; $episode = 0; $steps = @(); $hidden = @()
$end = (Get-Date).AddMinutes($MaxMinutes); $n = 0
while ((Get-Date) -lt $end) {
  $n++
  $h = @{ gdi = [P2]::Hash($gdi); wez = [P2]::Hash($wez) }
  foreach ($k in 'gdi', 'wez') { if ($prev[$k] -eq $h[$k]) { $stale[$k]++ } else { $stale[$k] = 0 } }
  if ($stale.gdi -eq 0 -and $stale.wez -eq 0) { $fresh++ } else { $fresh = 0 }
  $prev = $h
  $idle = [P2]::IdleMs()
  $age = ((Get-Date) - $t0).TotalSeconds
  if ($n % 150 -eq 0) { Log "HEARTBEAT phase=$phase idle_s=$([int]($idle/1000)) episodes=$episode" }
  if ($phase -eq 'watch') {
    if ($stale.gdi -ge 4 -or $stale.wez -ge 4) {
      $episode++
      Log "FREEZE episode=$episode stale_gdi=$($stale.gdi) stale_wez=$($stale.wez) idle_s=$([int]($idle/1000)) fg=0x$([P2]::GetForegroundWindow().ToString('X'))"
      [P2]::ZOrder(14) | % { Log "  z $_" }
      [P2]::Shot((Join-Path $out ("ep$episode-freeze-{0:HHmmss}.png" -f (Get-Date))))
      if ($episode % 2 -eq 1) { $steps = @('hide-overlay', 'setcursor', 'sendinput') } else { $steps = @('setcursor', 'sendinput', 'hide-overlay') }
      $phase = 'step'; $t0 = Get-Date; $age = 99
    }
  }
  if ($phase -eq 'step' -and $age -ge 20) {
    if ($steps.Count -eq 0) { Log "NO-STEP-LEFT episode=$episode; waiting for natural resume"; $phase = 'wait-natural'; $t0 = Get-Date }
    else {
      $s = $steps[0]; $steps = @($steps | Select-Object -Skip 1)
      if ($s -eq 'hide-overlay') { $hidden = [P2]::Overlays(); foreach ($o in $hidden) { [P2]::ShowWindow($o, 0) | Out-Null }; Log "ACTION hide-overlay $(($hidden | % { '0x' + $_.ToString('X') }) -join ',')" }
      elseif ($s -eq 'setcursor') { $p = New-Object P2+POINT; [P2]::GetCursorPos([ref]$p) | Out-Null; [P2]::SetCursorPos($p.X + 1, $p.Y) | Out-Null; Start-Sleep -Milliseconds 100; [P2]::SetCursorPos($p.X, $p.Y) | Out-Null; Log "ACTION setcursor" }
      elseif ($s -eq 'sendinput') { [P2]::SendMove(1, 0); Start-Sleep -Milliseconds 100; [P2]::SendMove(-1, 0); Log "ACTION sendinput" }
      $last = $s; $t0 = Get-Date; $fresh = 0
    }
  }
  elseif (($phase -eq 'step' -or $phase -eq 'wait-natural') -and $fresh -ge 2) {
    $how = if ($phase -eq 'wait-natural') { "natural idle_s=$([int]($idle/1000))" } else { "after $last (+$([int]$age) s)" }
    Log "RESUME episode=$episode $how"
    if ($phase -eq 'step' -and $last -eq 'hide-overlay') { $phase = 'reshow-wait'; $t0 = Get-Date }
    else { if ($hidden.Count) { foreach ($o in $hidden) { [P2]::ShowWindow($o, 8) | Out-Null }; Log "ACTION reshow-overlay (restore)"; $hidden = @() }; $phase = 'watch' }
  }
  elseif ($phase -eq 'reshow-wait' -and $age -ge 10) {
    foreach ($o in $hidden) { [P2]::ShowWindow($o, 8) | Out-Null }
    Log "ACTION reshow-overlay (test)"; $phase = 'reshow-obs'; $t0 = Get-Date
  }
  elseif ($phase -eq 'reshow-obs') {
    if ($stale.gdi -ge 4 -or $stale.wez -ge 4) {
      Log "REFREEZE episode=$episode after reshow-overlay (+$([int]$age) s)"
      foreach ($o in $hidden) { [P2]::ShowWindow($o, 0) | Out-Null }
      Log "ACTION hide-overlay again"; $phase = 'step'; $steps = @(); $last = 'hide-overlay-again'; $t0 = Get-Date
    }
    elseif ($age -ge 40) { Log "NO-REFREEZE episode=$episode 40 s after reshow-overlay"; $hidden = @(); $phase = 'watch' }
  }
  Start-Sleep -Seconds 2
}
Log "END"
