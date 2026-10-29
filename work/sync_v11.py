import subprocess,time,pathlib,json,collections
root=pathlib.Path('/Users/nikitph/Documents/Codex/2026-10-28/can');dest=root/'outputs/v1.1-pilot'
base=['scp','-r','-i','/Users/nikitph/.ssh/id_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','UserKnownHostsFile='+str(root/'work/known_hosts'),'-P','14066']
while True:
 r=subprocess.run(base+['root@216.81.245.124:/workspace/v1.1-pilot/results',str(dest)],capture_output=True,text=True)
 if r.returncode:print('sync error: '+r.stderr[-300:],flush=True)
 else:
  stats={}
  for name in ('smoke','repeat','full','mid','linux'):
   p=dest/'results'/(name+'.jsonl')
   if p.exists():
    rows=[]
    for line in p.read_text().splitlines():
     try:rows.append(json.loads(line))
     except ValueError:pass
    stats[name]=dict(collections.Counter(x.get('condition','') for x in rows))
  print(json.dumps(stats),flush=True)
 time.sleep(60)
