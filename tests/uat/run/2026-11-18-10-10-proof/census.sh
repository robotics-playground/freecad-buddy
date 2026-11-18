#!/bin/bash
# Count lines per host-command kind in the UAT test cases (grep -c counts lines, not matches).
# Usage: LC_ALL=C.UTF-8 bash census.sh [testcases-dir]   (default: tests/uat/testcases of this repo)
# The --- section prints each remaining hit.
dir="${1:-$(git rev-parse --show-toplevel)/tests/uat/testcases}"
cd "$dir" || exit 1
declare -A P=(
 [K1]='cua-driver call|& cua-driver'
 [K1b]='cua-driver (status|doctor|kill_app|launch_app|list-tools|serve|stop)'
 [K2]='invoke_menu(?!\(\["View","Fit All"\]\))'
 [K3]='netstat'
 [K4]='tasklist|taskkill'
 [K5]='Get-Process|Stop-Process|Start-Process|powershell|pwsh|Get-CimInstance|Win32_Process|cmd\.exe|cmd /c'
 [K6]='Get-Content|Get-ChildItem|Get-Item|Remove-Item|Test-Path|Select-String|Select-Object|Measure-Object|Where-Object|ForEach-Object'
 [K7]='APPDATA|LOCALAPPDATA|USERPROFILE|%[A-Z]+%|\$env:'
 [K8]='\$TEMP|\.exe\b|[A-Za-z]:\\(?![nt])|Scripts[/\\]|\.cmd\b|[Jj]unction'
 [K9]='^(?!.*docker exec).*(curl [^`]*[^0-9]8765/|ipconfig|http\.server 8765|Invoke-RestMethod)'
 [K10]='launch_env|launch_app|^uv run python -c "$'
)
order="K1 K1b K2 K3 K4 K5 K6 K7 K8 K9 K10"
for k in $order; do
  printf '%s ' "$k"; grep -cP -- "${P[$k]}" TC-*.md | awk -F: '{s+=$2} END{print s}'
done
all=""
for k in $order; do all="${all:+$all|}(?:${P[$k]})"; done
printf 'ANY '; grep -hP -- "$all" TC-*.md | wc -l
if [ -n "$CENSUS_LIST" ]; then grep -nP -- "$all" TC-*.md | cut -c1-260; fi
