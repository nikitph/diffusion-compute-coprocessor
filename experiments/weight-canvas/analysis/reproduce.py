"""Run a fresh local reproduction without appending to preserved experiment records."""
import argparse,pathlib,shutil,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--destination',type=pathlib.Path,required=True)
p.add_argument('--variant',choices=['constrained','free','native'],default='free');a=p.parse_args()
if a.destination.exists():raise SystemExit('Choose a new destination; existing results are never overwritten')
shutil.copytree(root,a.destination,ignore=shutil.ignore_patterns('.venv','__pycache__','results','RESULTS.md'))
script={'constrained':'run.py','free':'free-program/run_free.py','native':'native-weights/run_free.py'}[a.variant]
for kind in ['diffusion','ar']:
 subprocess.run([sys.executable,str(a.destination/script),'--kind',kind],check=True)
print('Fresh reproduction saved to',a.destination.resolve())
