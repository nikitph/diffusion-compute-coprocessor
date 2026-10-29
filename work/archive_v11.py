"""Create and independently verify a complete local experiment archive."""
import pathlib,hashlib,json,zipfile,datetime
root=pathlib.Path('/Users/nikitph/Documents/Codex/2026-10-28/can/outputs')
run=root/'v1.1-pilot'
assert (run/'RESULTS.md').exists()
v=json.loads((run/'results/final-verification.json').read_text())
folders=['v1.1-pilot','diffusion-pilot','syscall-pilot','llada22-pilot']
files=[p for folder in folders for p in (root/folder).rglob('*') if p.is_file() and not any(x.startswith('._') or x=='__pycache__' for x in p.parts) and p.name not in ('final-archive-manifest.json','final-archive-verification.json')]
manifest={str(p.relative_to(root)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)}
mp=run/'final-archive-manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
archive=root/'diffusion-experiment-complete-2026-10-29.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[mp]:z.write(p,p.relative_to(root))
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name,d in manifest.items():
  content=z.read(name);assert len(content)==d['bytes'];assert hashlib.sha256(content).hexdigest()==d['sha256'],name
record={'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'archive':archive.name,'files':len(files)+1,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'all_entry_hashes_verified':True}
(run/'final-archive-verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
