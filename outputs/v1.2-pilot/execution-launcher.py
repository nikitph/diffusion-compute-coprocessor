import os,time,pathlib,subprocess,json
root=pathlib.Path('/workspace/v1.2-pilot');os.chdir(root)
source=pathlib.Path('/workspace/hf');target=pathlib.Path('/dev/shm/v12-hf')
start=time.monotonic()
while True:
 st=pathlib.Path('/proc/593/stat')
 if not st.exists() or st.read_text().split()[2]=='Z':break
 if time.monotonic()-start>900:raise RuntimeError('cache copy timeout; no model run started')
 time.sleep(5)
a={str(p.relative_to(source)):p.stat().st_size for p in source.rglob('*') if p.is_file()}
b={str(p.relative_to(target)):p.stat().st_size for p in target.rglob('*') if p.is_file()}
assert a==b,'cache copy incomplete'
(root/'results-v1.2/cache-staging.json').write_text(json.dumps({'verified_file_sizes':len(a),'bytes':sum(a.values()),'destination':str(target)},indent=2))
os.environ.update(HF_HOME=str(target),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='8')
os.execv('/workspace/v11-venv/bin/python',['/workspace/v11-venv/bin/python','run_v12.py'])
