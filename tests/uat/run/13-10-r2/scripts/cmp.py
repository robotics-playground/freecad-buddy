import json, sys
def walk(a,b,p,out):
    if type(a)!=type(b): out.append(f'{p} TYPE {repr(a)[:150]} | {repr(b)[:150]}'); return
    if isinstance(a,dict):
        for k in sorted(set(a)|set(b)): walk(a.get(k),b.get(k),p+'.'+k,out)
    elif isinstance(a,list):
        if len(a)!=len(b): out.append(f'{p} LEN {len(a)} {len(b)} {repr(a)[:200]} | {repr(b)[:200]}'); return
        for i,(x,y) in enumerate(zip(a,b)): walk(x,y,p+f'[{i}]',out)
    elif a!=b: out.append(f'{p} H={repr(a)[:200]} O={repr(b)[:200]}')
h=json.load(open(sys.argv[1]));f=json.load(open(sys.argv[2]))
print('ok', h['_test_ok'], f['_test_ok'], h['_errors'][:1], f['_errors'][:1])
for k in sorted(set(h)|set(f)):
    if k.startswith('_'): continue
    hv,fv=h.get(k),f.get(k)
    if isinstance(hv,dict) and 'envelope' in hv:
        o=[]; walk(hv['envelope'],fv['envelope'],'',o)
        s=lambda v: (v.get('status') or v.get('summary'), v.get('code'), v.get('app_active_after'), v.get('pending_after'))
        print(k, 'H', s(hv), '| O', s(fv), '| diffs', len(o))
        for line in o[:8]: print('   ', line)
    else: print(k, 'H', hv, '| O', fv)
