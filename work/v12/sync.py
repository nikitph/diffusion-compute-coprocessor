"""Copy results through a single SSH stream; verify every byte before replace."""
import subprocess,json,hashlib,base64,pathlib,time,sys,os
ROOT=pathlib.Path('/Users/nikitph/Documents/Codex/2026-10-28/can')
DEST=ROOT/'outputs/v1.2-pilot'
SSH=['ssh','-i','/Users/nikitph/.ssh/id_ed25519','-o','UserKnownHostsFile='+str(ROOT/'work/known_hosts'),'-o','ConnectTimeout=15','-p','19462','root@216.81.245.124']
script="""import pathlib,json,base64,hashlib
root=pathlib.Path('/workspace/v1.2-pilot')
for p in sorted(root.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts:continue
 rel=str(p.relative_to(root))
 if rel.startswith('results-v1.2/') or rel=='run.log':
  data=p.read_bytes()
  if p.suffix=='.jsonl' and data and not data.endswith(b'\\n'):data=data[:data.rfind(b'\\n')+1]
  print(json.dumps({'path':rel,'sha256':hashlib.sha256(data).hexdigest(),'data':base64.b64encode(data).decode()}))
"""
def sync():
 p=subprocess.run(SSH+['python3 -'],input=script,text=True,capture_output=True,timeout=55)
 if p.returncode:raise RuntimeError(p.stderr)
 hashes={}
 for line in p.stdout.splitlines():
  row=json.loads(line);data=base64.b64decode(row['data']);assert hashlib.sha256(data).hexdigest()==row['sha256']
  path=DEST/row['path'];path.parent.mkdir(exist_ok=True,parents=True);tmp=path.with_suffix(path.suffix+'.'+str(os.getpid())+'.tmp');tmp.write_bytes(data);tmp.replace(path);hashes[row['path']]=row['sha256']
 (DEST/'results-v1.2/local-copy-verification.json').write_text(json.dumps({'time':time.time(),'files':hashes,'all_verified':True},indent=2))
 counts={p.stem:len(p.read_text().splitlines()) for p in (DEST/'results-v1.2').glob('*.jsonl')}
 print(json.dumps({'verified':len(hashes),'counts':counts}),flush=True)
if __name__=='__main__':
 if '--loop' in sys.argv:
  for _ in range(360):
   try:sync()
   except Exception as e:print(type(e).__name__+': '+str(e),flush=True)
   if (DEST/'results-v1.2/COMPLETE.json').exists() or (DEST/'results-v1.2/PREREQUISITE_FAILED.json').exists():break
   time.sleep(45)
 else:sync()
