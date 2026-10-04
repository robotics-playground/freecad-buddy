"""Direct RPC probes for TC-01-04/06/07/08/09. Usage: tc-01-rpc.py <mode> [discovery-file]
modes: literal-06 | v06 | v07 | v07-omit | v08 | v08-badjson | hello
Without a discovery file argument the record for the live FreeCAD pid in fc.json is used.
Every mode prints each frame read and then a second readline to show whether the socket closed."""
import glob, json, os, socket, sys, time

D = os.path.expandvars(r'%APPDATA%/FreeCAD/v1-1/freecad-buddy')
E = os.path.dirname(os.path.abspath(__file__))
mode = sys.argv[1]
if mode == 'literal-06':
    path = sorted(glob.glob(f'{D}/rpc-*.json'))[-1]
elif len(sys.argv) > 2:
    path = sys.argv[2]
else:
    path = f"{D}/rpc-{json.load(open(f'{E}/fc.json'))['pid']}.json"
rec = json.load(open(path))
print('discovery file:', os.path.basename(path), 'pid', rec['pid'], 'port', rec['port'])
frames = {
    'literal-06': {'jsonrpc': '2.0', 'id': 1, 'method': 'rpc_hello', 'params': {'token': rec['token'], 'contract_version': '99'}},
    'v06': {'jsonrpc': '2.0', 'id': 1, 'method': 'rpc_hello', 'params': {'token': rec['token'], 'contract_version': '99'}},
    'v07': {'jsonrpc': '2.0', 'id': 7, 'method': 'rpc_hello', 'params': {'token': 'not-the-token', 'contract_version': '99'}},
    'v07-omit': {'jsonrpc': '2.0', 'id': 7, 'method': 'rpc_hello', 'params': {'contract_version': '99'}},
    'v08': {'jsonrpc': '2.0', 'id': 3, 'method': 'query_capabilities', 'params': {}},
    'hello': {'jsonrpc': '2.0', 'id': 1, 'method': 'rpc_hello', 'params': {'token': rec['token'], 'contract_version': rec['contract_version']}},
}
t0 = time.monotonic()
try:
    s = socket.create_connection((rec['host'], rec['port']), timeout=5)
    payload = b'not json\n' if mode == 'v08-badjson' else (json.dumps(frames[mode]) + '\n').encode()
    print('sent:', payload.decode().strip().replace(rec['token'], '<discovery token>') if mode != 'hello' else '(rpc_hello with discovery token, contract_version %s)' % rec['contract_version'])
    s.sendall(payload)
    f = s.makefile('r', encoding='utf-8')
    line1 = f.readline().strip()
    if mode == 'hello':
        r = json.loads(line1)
        caps = (r.get('result') or {}).get('capabilities') or {}
        print('frame1 keys:', sorted(r), 'result keys:', sorted(r.get('result') or {}))
        print('capabilities:', json.dumps({k: v for k, v in caps.items() if k != 'enums'}))
    else:
        print('frame1:', line1)
    try:
        print('frame2:', repr(f.readline()))
    except OSError as exc:
        print('frame2 read error:', type(exc).__name__, exc)
except OSError as exc:
    print('refused:', type(exc).__name__, exc)
print('elapsed', round(time.monotonic() - t0, 2))
