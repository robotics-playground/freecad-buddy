import json,socket,sys,time
host,port,token=sys.argv[1],int(sys.argv[2]),sys.argv[3]
def hello(tok):
    t0=time.monotonic()
    s=socket.create_connection((host,port),timeout=5)
    tc=time.monotonic()-t0
    s.sendall((json.dumps({"jsonrpc":"2.0","id":1,"method":"rpc_hello","params":{"contract_version":"1","client":"uat-s2","token":tok}})+"\n").encode())
    t1=time.monotonic(); buf=b""
    while b"\n" not in buf:
        c=s.recv(65536)
        if not c: break
        buf+=c
    dt=time.monotonic()-t1
    s.settimeout(3)
    try: nxt=s.recv(65536)
    except Exception as e: nxt=repr(e)
    print("connect_s=%.3f first_frame_s=%.3f frame=%s next_recv=%r"%(tc,dt,buf.decode().strip(),nxt))
print("B valid token"); hello(token)
print("C wrong token"); hello("wrong-token")
