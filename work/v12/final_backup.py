import subprocess,pathlib,json,base64,hashlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).parent));from sync import SSH,DEST,sync
sync()
script="""import pathlib,json,hashlib,base64
root=pathlib.Path('/workspace/v1.2-pilot')
assert (root/'results-v1.2/COMPLETE.json').exists(),'Experiment not complete'
for p in sorted(root.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts:continue
 data=p.read_bytes()
 print(json.dumps(dict(path=str(p.relative_to(root)),sha256=hashlib.sha256(data).hexdigest(),data=base64.b64encode(data).decode())))
"""
p=subprocess.run(SSH+['python3 -'],input=script,text=True,capture_output=True,timeout=55);assert p.returncode==0,p.stderr
hashes={};snapshot=DEST/'remote-snapshot'
for line in p.stdout.splitlines():
 row=json.loads(line);data=base64.b64decode(row['data']);assert hashlib.sha256(data).hexdigest()==row['sha256']
 target=snapshot/row['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);hashes[row['path']]=row['sha256']
freeze=json.load(open(snapshot/'results-v1.2/frozen-source-manifest.json'))
assert all(hashes[name]==digest for name,digest in freeze['files'].items()),'Remote frozen source changed'
assert all(hashlib.sha256((snapshot/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
(DEST/'results-v1.2/final-remote-manifest.json').write_text(json.dumps(hashes,indent=2))
(DEST/'results-v1.2/final-backup-verification.json').write_text(json.dumps(dict(all_hashes_verified=True,frozen_source_verified=True,files=len(hashes)),indent=2))
print(json.dumps(dict(verified_files=len(hashes),frozen_source_verified=True)))
