import json, socket, sys, time
rec = json.load(open(sys.argv[1]))
t0 = time.monotonic()
try:
    s = socket.create_connection((rec['host'], rec['port']), timeout=5)
    s.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':'rpc_hello',
        'params':{'token':rec['token'],'contract_version':rec['contract_version']}})+'\n').encode())
    print('reply:', s.makefile('r', encoding='utf-8').readline().strip())
except OSError as exc:
    print('refused:', type(exc).__name__, exc)
print('elapsed', round(time.monotonic()-t0, 2))
