import subprocess,time,pathlib,json,collections,tarfile,io,os
root=pathlib.Path('/Users/nikitph/Documents/Codex/2026-10-28/can');dest=root/'outputs/v1.1-pilot'
base=['ssh','-i','/Users/nikitph/.ssh/id_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2','-o','UserKnownHostsFile='+str(root/'work/known_hosts'),'-p','14066','root@216.81.245.124']
while True:
 try:
  r=subprocess.run(base+['cd /workspace/v1.1-pilot && tar --exclude="._*" -czf - results'],capture_output=True,timeout=90)
  if r.returncode not in (0,1):raise RuntimeError(r.stderr.decode()[-300:])
  with tarfile.open(fileobj=io.BytesIO(r.stdout),mode='r:gz') as tf:
   n=0
   for m in tf.getmembers():
    if not m.isfile():continue
    rel=pathlib.PurePosixPath(m.name)
    if rel.is_absolute() or '..' in rel.parts or rel.parts[0]!='results':raise ValueError('Invalid archive path')
    p=dest/str(rel);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.sync-part');tmp.write_bytes(tf.extractfile(m).read());os.replace(tmp,p);n+=1
  print('Synced '+str(n)+' result files',flush=True)
 except Exception as e:print('Sync error: '+str(e),flush=True)
 time.sleep(45)
