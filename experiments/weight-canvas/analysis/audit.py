"""Recompute results and verify frozen source without loading language models."""
import hashlib,importlib.util,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from controller import metrics,scenarios,feedback,version
counts={};source_counts={};arrivals=0
for name,folder,base in [('constrained',root/'results/pilot',root),('free',root/'free-program/results',root),('native',root/'native-weights/results',root)]:
 manifest=json.loads((folder/'source-manifest.json').read_text())
 for file,expected in manifest.items():
  assert hashlib.sha256((base/file).read_bytes()).hexdigest()==expected,(name,file)
 source_counts[name]=len(manifest)
 rows=[json.loads(s) for s in (folder/'records.jsonl').read_text().splitlines()]
 assert len(rows)==(5 if name=='native' else 30)
 assert len({(r['task'],r['condition']) for r in rows})==len(rows)
 counts[name]=len(rows)
 if name!='constrained':
  spec=importlib.util.spec_from_file_location('programs_'+name,folder.parent/'programs.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 for r in rows:
  held=scenarios(r['heldout_seed'],512);practice=scenarios(r['practice_seed'],64)
  assert not set(map(tuple,held))&set(map(tuple,practice))
  assert metrics(r['initial'],r['initial'],held)==r['initial_metrics']
  if name=='constrained':
   assert metrics(r['final'],r['initial'],held)==r['final_metrics']
   assert r['true_feedback']==feedback(r['candidate'],practice)
   assert r['lock_violations']==0
  else:
   try:e=module.interpret(r['final_text'],r['initial']);valid=True
   except (ValueError,SyntaxError,TypeError,IndexError):e=None;valid=False
   assert valid==r['valid'] and e==r['final']
   if valid:assert metrics(e,r['initial'],held)==r['final_metrics']
   assert r['deployable_caught']==(r['final_metrics']['caught'] if valid else 0)
   for part in r['parts']:
    assert part['lock_violations']==0
    a=part['arrival']
    if a:
     arrivals+=1;assert a['remaining_content_masks']>0
     assert a['candidate_hash']==version(a['candidate'])
     assert a['locked_hash']==hashlib.sha256(json.dumps(a['locked_tokens']).encode()).hexdigest()
     truth=feedback(a['candidate'],practice)
     if name=='native':
      truth['weights']=[[v-2 for v in a['candidate'][:3]],[v-2 for v in a['candidate'][3:]]];del truth['weight_codes']
     assert truth==a['true_feedback']
result=dict(passed=True,records=counts,total_records=sum(counts.values()),frozen_source_files=source_counts,
            free_program_active_arrivals=arrivals,score_recomputations='all valid final controllers',
            heldout_practice_overlap=False,source_hash_mismatches=0)
(root/'results/audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
