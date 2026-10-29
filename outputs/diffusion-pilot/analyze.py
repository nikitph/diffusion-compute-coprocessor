import collections,json,pathlib,sys,statistics,re
from pilot import posthoc,score
root=pathlib.Path(sys.argv[1]);records=[json.loads(x) for x in (root/'records.jsonl').read_text().splitlines()]
batches=[json.loads(x) for x in (root/'batches.jsonl').read_text().splitlines()]
# Preserve raw output records; independently regenerate the post-hoc control with
# the comma-aware result-span parser. No model inference output is altered.
rows={r['id']:r for r in json.loads((root/'dataset.json').read_text())}
records=[r for r in records if r['condition']!='posthoc_equations']
for r in list(records):
    if r['condition']=='base':
        corrected=posthoc(r['text'],r['kind'])
        records.append(dict(r,condition='posthoc_equations',text=corrected,**score(corrected,rows[r['id']])))
(root/'evaluated_records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
summary={}
for condition in sorted({r['condition'] for r in records}):
    rr=[r for r in records if r['condition']==condition];bb=[b for b in batches if b['condition']==condition]
    events=[e for b in bb for e in b['events']];injected=[e for e in events if e['status']=='injected']
    entry={'accuracy':{k:{'n':sum(r['kind']==k for r in rr),'correct':sum(r['kind']==k and r['correct'] for r in rr)} for k in ('direct','dependent')}}
    decisions=[r for r in rr if r['kind']=='dependent']
    entry['label_tolerant_decisions']={'n':len(decisions),'correct':sum(bool(re.findall(r'\b(YES|NO)\b',r['text'],re.I)) and re.findall(r'\b(YES|NO)\b',r['text'],re.I)[-1].upper()==r['expected'] for r in decisions)}
    if bb:
        entry.update(batch_seconds=[b['batch_seconds'] for b in bb],median_batch_seconds=statistics.median(b['batch_seconds'] for b in bb),hook_seconds=sum(b['hook_seconds'] for b in bb),
                     event_statuses=dict(collections.Counter(e['status'] for e in events)),injected_samples=len(injected),correct_operands=sum(e['operand_match'] for e in injected),
                     preserved_locks=sum(e['lock_preserved'] for e in injected),preserved_operands=sum(e['operands_preserved'] for e in injected),remaining_masks=sum(b['remaining_masks'] for b in bb),
                     kernel_calls=sum(b.get('kernel_calls',0) for b in bb))
    summary[condition]=entry
base={r['id']:r for r in records if r['condition']=='base'}
for condition,entry in summary.items():
    entry['paired_vs_base']={}
    for kind in ('direct','dependent'):
        rr=[r for r in records if r['condition']==condition and r['kind']==kind and r['id'] in base]
        entry['paired_vs_base'][kind]={'improved':sum(r['correct'] and not base[r['id']]['correct'] for r in rr),'regressed':sum(not r['correct'] and base[r['id']]['correct'] for r in rr)}
(root/'analysis.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
