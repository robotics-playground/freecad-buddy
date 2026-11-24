import sys
p, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(p, encoding="utf-8", newline="").read()
old = old.encode().decode("unicode_escape"); new = new.encode().decode("unicode_escape")
n = s.count(old)
assert n == 1, (p, n)
open(p, "w", encoding="utf-8", newline="").write(s.replace(old, new))
