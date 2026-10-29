from pathlib import Path
p=Path('outputs/v1.1-pilot/report.py');s=p.read_text();needle="lines += ['', '## Edit audit (36 smoke tasks)', '']"
insert="""lines += ['', '## Delayed-result controls', '', '| Control | Delay (forward steps) | Re-mask off | Re-mask on |', '|---|---:|---:|---:|']
for name in ('hidden-delay','arithmetic-delay','variant-delay'):
 rs=rows(name)
 for c in sorted({r.get('condition',name) for r in rs}):
  for delay in (0,10,20,40):
   cells=[]
   for f3 in (False,True):
    subset=[r for r in rs if r.get('condition',name)==c and r['delay']==delay and r['f3']==f3]
    cells.append(str(sum(r['correct'] for r in subset))+'/'+str(len(subset)))
   lines.append(f'| {c} | {delay} | '+ ' | '.join(cells)+' |')
u=rows('upstream');lines += ['',f'Dense native-message upstream sampler control: {sum(r["correct"] for r in u)}/{len(u)} exact answers. These controls use supplied calls and are separate from autonomous call-adoption measurements.', '', '## Failed insertion opportunities', '', '| Condition | Absent | Occupied | Too short | Late |', '|---|---:|---:|---:|---:|']
for c in ('A1','A3','A4','A5','A7'):
 if c in a['full']:
  f=a['full'][c]['failed_opportunities'];lines.append('| '+c+' | '+' | '.join(str(f.get(k,0)) for k in ('absent','occupied','too_short','late'))+' |')
"""
assert needle in s;s=s.replace(needle,insert+needle);p.write_text(s)
