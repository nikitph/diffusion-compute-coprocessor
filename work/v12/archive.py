import pathlib,hashlib,json,zipfile
root=pathlib.Path('/Users/nikitph/Documents/Codex/2026-10-28/can/outputs');dst=root/'v1.2-pilot';archive=root/'diffusion-v1.2-calibrated-results-2026-10-29.zip'
files=[]
for dirname in ('v1.2-pilot','syscall-pilot'):
 for p in (root/dirname).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts and not p.name.startswith('._') and not p.name.endswith('.tmp') and p.name not in ('archive-manifest.json','archive-verification.json'):files.append(p)
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
m=dst/'results-v1.2/archive-manifest.json';m.write_text(json.dumps(manifest,indent=2));files.append(m)
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(files):z.write(p,p.relative_to(root))
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(files)
 for p in files:assert hashlib.sha256(z.read(str(p.relative_to(root)))).hexdigest()==hashlib.sha256(p.read_bytes()).hexdigest()
result=dict(archive=str(archive),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(files),all_crc_and_hashes_verified=True)
(dst/'results-v1.2/archive-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
