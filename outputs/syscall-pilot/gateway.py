"""Loopback HTTP gateway; ALL seven operations execute in networkless Docker."""
import argparse,json,pathlib,subprocess,time,uuid,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
READS={'read_file','list_dir','stat','clock','run'};EFFECTS={'write_file','remove'}

class Gateway:
    def __init__(self,workspace,image='diffusion-syscall-pilot:local'):
        self.workspace=pathlib.Path(workspace).resolve();self.image=image
        self.semaphore=threading.Semaphore(4)
    def execute(self,call,committed=False):
        name=call.get('name');args=call.get('args',{})
        if name not in READS|EFFECTS:return {'ok':False,'output':'unsupported call'}
        if not isinstance(args,dict):return {'ok':False,'output':'args must be object'}
        if name in EFFECTS and not committed:return {'ok':False,'output':'effect requires committed call span'}
        container='dlm-call-'+uuid.uuid4().hex
        mount=f'type=bind,src={self.workspace},dst=/fixture'+('' if name in EFFECTS else ',readonly')
        cmd=['docker','run','--rm','-i','--name',container,'--network','none','--cpus','1','--memory','256m','--pids-limit','64',
             '--cap-drop','ALL','--security-opt','no-new-privileges','--mount',mount,self.image]
        start=time.monotonic()
        with self.semaphore:
            try:
                p=subprocess.run(cmd,input=json.dumps(call),text=True,capture_output=True,timeout=12)
                if p.returncode:result={'ok':False,'output':'container error: '+p.stderr[-1500:]}
                else:
                    try:result=json.loads(p.stdout)
                    except ValueError:result={'ok':False,'output':'invalid container response: '+p.stdout[-500:]}
            except subprocess.TimeoutExpired:
                subprocess.run(['docker','rm','-f',container],capture_output=True,timeout=5)
                result={'ok':False,'output':'gateway timeout','error':'timeout'}
        result['gateway_seconds']=time.monotonic()-start
        result['sandbox']={'network':'none','fresh_container':True,'persistent_write':name in EFFECTS}
        return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',required=True);parser.add_argument('--port',type=int,default=18765);a=parser.parse_args()
    gateway=Gateway(a.workspace)
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size=int(self.headers.get('Content-Length','0'))
            if self.path!='/execute' or not 0<size<=16384:self.send_error(400);return
            try:
                req=json.loads(self.rfile.read(size));result=gateway.execute(req['call'],bool(req.get('committed',False)))
                data=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except Exception as e:self.send_error(500,str(e))
        def log_message(self,*args):pass
    print(json.dumps({'ready':True,'bind':'127.0.0.1','port':a.port,'workspace':str(gateway.workspace)}),flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
if __name__=='__main__':main()
