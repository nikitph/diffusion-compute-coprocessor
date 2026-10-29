import subprocess,pathlib,json,hashlib,tarfile,io,shutil,datetime
root=pathlib.Path('/Users/nikitph/Documents/Codex/2026-10-28/can');dest=root/'outputs/v1.1-pilot';stage=root/'work/v11-final-snapshot';stage.mkdir(exist_ok=True)
ssh=['ssh','-i','/Users/nikitph/.ssh/id_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','UserKnownHostsFile='+str(root/'work/known_hosts'),'-p','14066','root@216.81.245.124']
code='''import pathlib,json,hashlib
root=pathlib.Path('/workspace/v1.1-pilot'); assert 'ALL STAGES COMPLETE' in (root/'finish.log').read_text(); assert ('CROSS HOST COMPLETE' in (root/'cross-host.log').read_text() or 'SUPPLEMENTAL CHECK ABORTED' in (root/'cross-host.log').read_text())
cross=json.loads((root/'results/cross-host-verification.json').read_text()); assert cross['n']==30 or cross.get('status')=='not_completed'
names=[n+'.py' for n in 'pilot finish_run event_sampler old_sampler arithmetic_hook arith_reference gpu_arithmetic async_engine native_tools call_parser linux_runner cross_host_repeat'.split()]+['requirements.txt','linux-tasks.json','finish.log','cross-host.log','after_main.sh','after-main.log']
files=[root/n for n in names]+[p for p in (root/'results').iterdir() if p.is_file() and not p.name.startswith('._') and p.name!='final-remote-manifest.json']
d={str(p.relative_to(root)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
(root/'results/final-remote-manifest.json').write_text(json.dumps(d,indent=2));print(len(d))
'''
r=subprocess.run(ssh+['/workspace/v11-venv/bin/python -'],input=code.encode(),capture_output=True,check=True);print('Remote manifest files:',r.stdout.decode().strip())
names='pilot.py finish_run.py event_sampler.py old_sampler.py arithmetic_hook.py arith_reference.py gpu_arithmetic.py async_engine.py native_tools.py call_parser.py linux_runner.py cross_host_repeat.py requirements.txt linux-tasks.json finish.log cross-host.log after_main.sh after-main.log'
r=subprocess.run(ssh+['cd /workspace/v1.1-pilot && tar --exclude="._*" -czf - results '+names],capture_output=True,check=True)
(root/'work/v11-final-remote.tar.gz').write_bytes(r.stdout)
with tarfile.open(fileobj=io.BytesIO(r.stdout),mode='r:gz') as tf:
 for m in tf.getmembers():
  if not m.isfile():continue
  rel=pathlib.PurePosixPath(m.name);assert not rel.is_absolute() and '..' not in rel.parts
  p=stage/str(rel);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(tf.extractfile(m).read())
manifest=json.loads((stage/'results/final-remote-manifest.json').read_text())
for name,d in manifest.items():
 content=(stage/name).read_bytes();assert len(content)==d['bytes'];assert hashlib.sha256(content).hexdigest()==d['sha256'],name
for p in stage.rglob('*'):
 if p.is_file():
  target=dest/p.relative_to(stage);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
record={'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pod_id':'hex6gc4ufd8xt6','remote_files_verified':len(manifest),'all_remote_hashes_match_local':True}
(dest/'results/final-local-copy-verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
