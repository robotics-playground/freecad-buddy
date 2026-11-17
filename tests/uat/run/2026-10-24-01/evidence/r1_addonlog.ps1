# r1_addonlog.ps1 <tag>: print the addon.log bytes after the offset r1_launch.ps1 recorded for <tag>
# (read only; the file is opened with ReadWrite sharing and never changed).
param([string]$Tag)
$offset = [long](Get-Content "$PSScriptRoot\$Tag-addonlog-offset.txt")
$stream = [System.IO.File]::Open("$env:APPDATA\FreeCAD\v1-1\freecad-buddy\addon.log", "Open", "Read", "ReadWrite")
try { $null = $stream.Seek($offset, "Begin"); (New-Object System.IO.StreamReader($stream)).ReadToEnd() } finally { $stream.Dispose() }
