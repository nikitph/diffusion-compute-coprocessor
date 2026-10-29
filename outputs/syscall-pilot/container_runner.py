"""Runs INSIDE a disposable Linux container. Never runs on the user's host."""
import json,os,pathlib,shutil,subprocess,sys,time
ROOT=pathlib.Path('/fixture')
def safe(path):
    p=(ROOT/path).resolve()
    if not p.is_relative_to(ROOT.resolve()):raise PermissionError('path escapes synthetic workspace')
    return p

def execute(call):
    name=call['name'];a=call.get('args',{})
    if name=='read_file':
        offset=int(a.get('offset',0));length=int(a.get('length',4096))
        if offset<0 or not 0<=length<=8192:raise ValueError('invalid offset/length')
        with safe(a['path']).open('rb') as f:f.seek(offset);out=f.read(length).decode('utf-8',errors='replace')
    elif name=='list_dir':out=json.dumps(sorted(p.name for p in safe(a.get('path','.')).iterdir()))
    elif name=='stat':
        p=safe(a['path']);s=p.stat();out=json.dumps({'size':s.st_size,'is_file':p.is_file(),'is_dir':p.is_dir()})
    elif name=='clock':out=json.dumps({'unix_ns':time.time_ns(),'monotonic_ns':time.monotonic_ns()})
    elif name=='write_file':
        data=a['data'].encode();p=safe(a['path'])
        if len(data)>8192:raise ValueError('write too large')
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);out=f'wrote {len(data)} bytes'
    elif name=='remove':safe(a['path']).unlink();out='removed'
    elif name=='run':
        cmd=a['cmd'];timeout=int(a.get('timeout_ms',2000))
        if not isinstance(cmd,list) or not cmd or not all(isinstance(x,str) for x in cmd):raise ValueError('cmd must be argv list')
        if not 1<=timeout<=5000:raise ValueError('timeout_ms out of range')
        shutil.copytree(ROOT,'/work',dirs_exist_ok=True)
        try:
            p=subprocess.run(cmd,input=a.get('stdin',''),text=True,capture_output=True,cwd='/work',timeout=timeout/1000)
            return {'ok':p.returncode==0,'output':p.stdout[:32768],'stderr':p.stderr[:4096],'exit_code':p.returncode,'truncated_bytes':len(p.stdout)>32768}
        except subprocess.TimeoutExpired:return {'ok':False,'output':'timeout','error':'timeout'}
    else:raise ValueError('unknown call')
    return {'ok':True,'output':out}
try:
    request=json.load(sys.stdin);print(json.dumps(execute(request)),flush=True)
except Exception as e:
    print(json.dumps({'ok':False,'output':f'{type(e).__name__}: {e}','error':type(e).__name__}),flush=True)
