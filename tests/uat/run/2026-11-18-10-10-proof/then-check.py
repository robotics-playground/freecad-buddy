"""AC3 of Story 10-10: no Then/And observable changed.

For every file in tests/uat/testcases the script reads the baseline (git show <baseline>:path) and the
working tree, takes each Then line and each And line that follows a Then line (outside code fences),
splits it at the first ' — verify:' and compares the text before the split (the observable).

  python then-check.py [--baseline 031d8e8] [--allow <file>:<n>:<n> ...] [--mechanical DIR] [--out FILE]

Exit 0 when the Then/And line count per file is equal and every head is equal except the allowed
lines (--allow TC-01-session-lifecycle-and-transport.md:368 names the line by its baseline line number).
With --mechanical DIR (the baseline testcases after the mechanical K1/K2/K3/K7 rules only) the
verify-clause changes are written to --out, one line each, tagged `rule:K<n>` when the working tree
equals the mechanical result and `hand` otherwise, with the baseline host words as the reason.
"""

import argparse
import glob
import os
import re
import subprocess
import sys

MARKER = " — verify:"
KINDS = {
    "K1": r"cua-driver call|& cua-driver",
    "K2": r"invoke_menu",
    "K3": r"netstat",
    "K4": r"tasklist|taskkill",
    "K5": r"Get-Process|Stop-Process|powershell|Win32_Process|cmd\.exe",
    "K6": r"Get-Content|Get-ChildItem|Get-Item|Test-Path|Select-String",
    "K7": r"APPDATA|%[A-Z]+%|\$env:",
    "K8": r"\$TEMP|\.exe\b|Scripts[/\\]|[Jj]unction|\.cmd\b",
    "K9": r"127\.0\.0\.1:8765|ipconfig|<LAN-IP>|Invoke-RestMethod",
    "K10": r"launch_env|launch_app|uv run python -c",
}


REASONS = {
    "K1": "cua-driver call form -> $FCB_CUA",
    "K2": "menu-path call -> leaf press by element_token",
    "K3": "netstat -> ss -ltnp (LISTENING -> LISTEN)",
    "K4": "tasklist/taskkill -> pgrep, ps -p, kill",
    "K5": "PowerShell process tool -> ps, pgrep, /proc cmdline, kill",
    "K6": "PowerShell file cmdlet -> grep, ls, stat, test, tail",
    "K7": "APPDATA path -> $FCB_USER_DIR or $FCB_CONFIG_DIR read in the container",
    "K8": "host temp, .exe, junction or venv -> container /tmp, $FCB_PYTHON, installed-addon hash",
    "K9": "host :8765 client or ipconfig -> relay :18765 or docker exec",
    "K10": "launch_env, launch_app or uv run snippet -> fcb-freecad start or $FCB_PYTHON",
}
NO_KIND_REASONS = {
    (
        "TC-01-session-lifecycle-and-transport.md",
        "368",
    ): "Windows chmod exception removed; POSIX 600 kept (the listed observable change)",
    (
        "TC-10-concurrency-timeout-and-quarantine.md",
        "159",
    ): "the connect runs in the container: the listener port is container-internal",
    (
        "TC-10-concurrency-timeout-and-quarantine.md",
        "608",
    ): "Windows-only reset explanation generalised; the closed-connection check is unchanged",
    (
        "TC-11-security-posture-and-artifact-hygiene.md",
        "358",
    ): "Windows attrib/icacls branch removed, POSIX stat -c %a kept",
    (
        "TC-11-security-posture-and-artifact-hygiene.md",
        "878",
    ): "backslash path spelling -> forward slashes of the container path",
    (
        "TC-11-security-posture-and-artifact-hygiene.md",
        "880",
    ): "backslash path spelling -> forward slashes of the container path",
    (
        "TC-11-security-posture-and-artifact-hygiene.md",
        "882",
    ): "backslash path spelling -> forward slashes of the container path",
    (
        "TC-11-security-posture-and-artifact-hygiene.md",
        "883",
    ): "backslash path spelling -> forward slashes of the container path",
    (
        "TC-01-session-lifecycle-and-transport.md",
        "576",
    ): "state word LISTENING -> LISTEN as ss prints it",
    (
        "TC-01-session-lifecycle-and-transport.md",
        "637",
    ): "bare addon.log grep -> docker exec grep on the container log",
    (
        "TC-01-session-lifecycle-and-transport.md",
        "639",
    ): "bare addon.log grep and discovery-file check -> docker exec",
    (
        "TC-10-concurrency-timeout-and-quarantine.md",
        "527",
    ): "host tools/list goes through the relay on :18765",
    (
        "TC-01-session-lifecycle-and-transport.md",
        "361",
    ): "legacy Mod folder sub-check kept: in the container FreeCAD/Mod does not exist",
    (
        "TC-01-session-lifecycle-and-transport.md",
        "578",
    ): "state word LISTENING -> LISTEN as ss prints it (D5)",
    (
        "TC-02-document-ingestion-and-handles.md",
        "240",
    ): "hide the Pad: token click and key -> foreground pixel click on the row and window-level space (Tree row toggle)",
    (
        "TC-02-document-ingestion-and-handles.md",
        "243",
    ): "restore step: Show All and fit leaf presses, plus the Tree row toggle route named in the clause",
    (
        "TC-12-gui-workflows.md",
        "272",
    ): "tree rows have no selected field: the document row click is read from the active document and the window title",
    (
        "TC-99-ad-conformance-gaps.md",
        "223",
    ): "backslash path spelling -> forward slashes of the container path",
    (
        "TC-99-ad-conformance-gaps.md",
        "227",
    ): "backslash path spelling -> forward slashes of the container path",
    (
        "TC-99-ad-conformance-gaps.md",
        "333",
    ): "backslash path spelling -> forward slashes of the container path",
    (
        "TC-12-gui-workflows.md",
        "388",
    ): "undo list read from doc.UndoNames: the toolbar dropdown does not open in the container",
    (
        "TC-12-gui-workflows.md",
        "390",
    ): "undo enabled read from the Undo leaf or button and UndoNames, not from a dropdown popup",
    (
        "TC-12-gui-workflows.md",
        "395",
    ): "visual check keeps the before and after captures; the entry label comes from UndoNames (route limitation)",
    (
        "TC-12-gui-workflows.md",
        "442",
    ): "expand a tree row by a pixel click on its arrow (C1-tree-expand)",
    ("TC-13-gui-mcp-parity.md", "519"): "FreeCAD working directory is /home/cua in the container",
}


def then_lines(text):
    """Yield (line_number, item) for each Then line and each And line that follows a Then line.

    The item is the line plus its continuation lines: the following lines up to a blank line, a
    keyword line, a code fence, a heading, a bullet or a table row.
    """
    lines = text.split("\n")
    scope = ""
    fence = False
    for index, line in enumerate(lines):
        if line.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        match = re.match(r"\*\*(Given|When|Then|And)\*\*", line)
        if not match:
            continue
        if match.group(1) != "And":
            scope = match.group(1)
        if scope != "Then":
            continue
        item = [line]
        for follower in lines[index + 1 :]:
            if not follower.strip() or re.match(r"(\*\*|```|#|- |\|)", follower):
                break
            item.append(follower)
        yield index + 1, "\n".join(item)


def baseline_text(baseline, path):
    relative = path.replace(os.sep, "/")
    return subprocess.run(
        ["git", "show", f"{baseline}:{relative}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout


def split(line):
    head, _, tail = line.partition(MARKER)
    return head, tail


def kinds_of(text):
    found = [kind for kind, pattern in KINDS.items() if re.search(pattern, text)]
    return ",".join(found) or "none"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="031d8e8")
    parser.add_argument("--allow", nargs="*", default=[])
    parser.add_argument("--mechanical")
    parser.add_argument("--out")
    args = parser.parse_args()
    allowed = {tuple(item.rsplit(":", 1)) for item in args.allow}
    failures, report = [], []
    total = changed = 0
    for path in sorted(glob.glob("tests/uat/testcases/TC-*.md")):
        name = os.path.basename(path)
        base = list(then_lines(baseline_text(args.baseline, path)))
        with open(path, encoding="utf-8", newline="") as handle:
            now = list(then_lines(handle.read()))
        if len(base) != len(now):
            failures.append(f"{name}: Then/And count {len(base)} -> {len(now)}")
            continue
        mechanical = {}
        if args.mechanical:
            with open(os.path.join(args.mechanical, name), encoding="utf-8", newline="") as handle:
                mechanical = dict(enumerate((line for _, line in then_lines(handle.read()))))
        for index, ((base_no, base_line), (_, now_line)) in enumerate(zip(base, now)):
            total += 1
            base_head, base_tail = split(base_line)
            now_head, now_tail = split(now_line)
            if base_head != now_head and (name, str(base_no)) not in allowed:
                failures.append(
                    f"{name}:{base_no}: head differs\n  before: {base_head[:160]}\n  after:  {now_head[:160]}"
                )
            if base_tail != now_tail:
                changed += 1
                if args.mechanical:
                    tag = (
                        "rule:" + kinds_of(base_tail).split(",")[0]
                        if mechanical.get(index) == now_line
                        else "hand"
                    )
                    kinds = kinds_of(base_tail)
                    reason = NO_KIND_REASONS.get((name, str(base_no)))
                    reason = reason or "; ".join(
                        REASONS[k] for k in kinds.split(",") if k in REASONS
                    )
                    reason = reason or "UNEXPLAINED"
                    if reason == "UNEXPLAINED":
                        failures.append(f"{name}:{base_no}: verify clause changed without a reason")
                    report.append(
                        f"{name}:{base_no} {tag} [{kinds}] {reason if tag == 'hand' else ''}".rstrip()
                    )
    print(
        f"Then/And lines compared: {total}; verify clauses changed: {changed}; failures: {len(failures)}"
    )
    for failure in failures:
        print("FAIL", failure)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(report) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
