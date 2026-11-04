"""One frozen local pilot. Results append per completed case; safe resume by key."""
import argparse,hashlib,json,pathlib,time,platform,sys
from controller import FAULTS,REFERENCE,program,version,feedback,evaluate,metrics,scenarios
from models import Backend,DEVICE
ROOT=pathlib.Path(__file__).resolve().parent
RULES='''Repair the six first-layer weights of this small paddle-catching neural network.
Inputs: [ball_x, ball_horizontal_velocity, paddle_x]. The ball lands at ball_x + velocity after one second, with no wall bounces. Choose one action: left=-1, stay=0, right=1. The paddle ends at paddle_x + 0.2*action. Catch if distance to ball landing is <=0.11.
The network is h=ReLU(W1 @ input + b1), logits=W2 @ h + b2, action=argmax(logits)-1. W2 and biases are fixed. Repair W1 only.
Write the E matrix: each integer E must be 0,1,2,3,4 and actual weight W1=E-2. Thus 1 means -1, 2 means 0, 3 means +1. Do not copy damaged values blindly. Return the weight program, no explanation.
Damaged program:
'''

def prompt(b,initial,report=None,candidate=None):
    s=RULES+program(initial)
    if report is not None:
        s+='\nYour previous candidate:\n'+program(candidate)+'\nEvaluator report:\n'+json.dumps(report,separators=(',',':'))+'\nRevise the candidate to improve catching.\n'
    return b.prompt(s)

def scaffold(b,prefix,mask=True):
    ids=list(prefix)+b.encode('```python\nE = [[');slots=[]
    for i in range(6):
        slots.append(len(ids));ids.append(b.tok.mask_token_id if mask else b.tokens[2])
        ids+=b.encode('], [' if i==2 else ']]\n' if i==5 else ', ')
    ids+=b.encode(program([2]*6).split('\n',1)[1]+'```')
    return ids,slots

def tensor_codes(b,ids,slots):return [b.tokens.index(ids[p]) for p in slots]

def digest(ids):return hashlib.sha256(json.dumps(ids).encode()).hexdigest()

def diffuse(b,ids,slots,steps,events):
    proposed=None
    # Exact assignments outside numeric slots remain immutable across every step.
    locked=[(i,v) for i,v in enumerate(ids) if i not in slots]
    for _ in range(steps):
        choices,confidence=b.predict(ids,slots)
        proposed=[b.tokens.index(ids[p]) if ids[p]!=b.tok.mask_token_id else choices[j] for j,p in enumerate(slots)]
        free=[j for j,p in enumerate(slots) if ids[p]==b.tok.mask_token_id]
        if not free:raise AssertionError('No masked numerical slots')
        j=max(free,key=lambda j:confidence[j]);ids[slots[j]]=b.tokens[choices[j]]
        assert all(ids[i]==v for i,v in locked),'Locked scaffold/feedback changed'
        events.append(dict(type='denoise',step=b.calls,committed_slot=j,choice=choices[j],confidence=confidence[j],
                           provisional=proposed,remaining_masks=sum(ids[p]==b.tok.mask_token_id for p in slots),
                           canvas_hash=digest(ids),canvas=b.tok.decode(ids)))
    return proposed

def ar_fill(b,prefix,events):
    # Same fixed Python syntax and legal digits, but each weight sees only its prefix.
    ids=list(prefix)+b.encode('```python\nE = [[');e=[]
    for i in range(6):
        choices,conf=b.predict(ids,[len(ids)-1]);v=choices[0];e.append(v);ids.append(b.tokens[v])
        ids+=b.encode('], [' if i==2 else ']]\n' if i==5 else ', ')
        events.append(dict(type='ar_token',step=b.calls,slot=i,choice=v,confidence=conf[0]))
    return e

def run_case(b,name,initial,arm,index):
    practice=scenarios(20261104+index,64);heldout=scenarios(20262104+index,512)
    start=time.perf_counter();before=b.counters();events=[];report=None
    if arm=='AR-round':
        first=ar_fill(b,prompt(b,initial),events)
        truth=feedback(first,practice);report=truth
        final=ar_fill(b,prompt(b,initial,report,first),events);arrival_masks=0
    else:
        ids,slots=scaffold(b,prompt(b,initial))
        first=diffuse(b,ids,slots,6 if arm=='D-round' else 3,events)
        # Provisional evaluation fills remaining masks with this pass's proposals.
        arrival_masks=sum(ids[p]==b.tok.mask_token_id for p in slots)
        assert arrival_masks==(0 if arm=='D-round' else 3)
        truth=feedback(first,practice)
        report=feedback(first,practice,shuffled=True) if arm=='D-shuffled' else truth
        if arm=='D-round':
            ids,slots=scaffold(b,prompt(b,initial,report,first))
        else:
            message='\nEvaluator report for the provisional candidate '+str(first)+':\n'
            if arm=='D-none':
                report=None;message='\nContinue revising the six numeric weights. No evaluator report is available.\n'
            else:message+=json.dumps(report,separators=(',',':'))+'\nRevise E above to improve catching.\n'
            lo=len(ids);injected=b.encode(message);ids+=injected
            # Preserve the existing canvas; only the declared writable numerical
            # region reopens. Feedback/scaffold are never generated or overwritten.
            for p in slots:ids[p]=b.tok.mask_token_id
            events.append(dict(type='feedback_arrival',candidate=version(first),remaining_masks_before=arrival_masks,
                feedback_position=lo,feedback_tokens=len(injected),locked_feedback_hash=digest(injected),
                reopened_slots=slots,canvas_hash=digest(ids)))
        diffuse(b,ids,slots,6,events);final=tensor_codes(b,ids,slots)
    after=b.counters()
    return dict(task=name,condition=arm,initial=initial,candidate=first,final=final,
        initial_program=program(initial),candidate_program=program(first),final_program=program(final),
        true_feedback=truth,displayed_feedback=report,arrival_masks=arrival_masks,events=events,
        initial_metrics=metrics(initial,initial,heldout),candidate_metrics=metrics(first,initial,heldout),
        final_metrics=metrics(final,initial,heldout),
        calls={k:after[k]-before[k] for k in before},wall_seconds=time.perf_counter()-start,
        lock_violations=0,practice_seed=20261104+index,heldout_seed=20262104+index)

def main():
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['diffusion','ar'],required=True)
    p.add_argument('--out',default='results/pilot');p.add_argument('--limit',type=int,default=6)
    a=p.parse_args();out=ROOT/a.out;out.mkdir(parents=True,exist_ok=True)
    manifest={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in ROOT.iterdir() if f.suffix in ['.py','.md','.txt']}
    freeze=out/'source-manifest.json'
    if freeze.exists():assert json.loads(freeze.read_text())==manifest,'Sources changed: choose a new output directory'
    else:freeze.write_text(json.dumps(manifest,indent=2))
    b=Backend(a.kind)
    env=dict(model=b.repo,revision=b.revision,device=DEVICE,platform=platform.platform(),precision='float32',
             python=sys.version,torch=__import__('torch').__version__,transformers=__import__('transformers').__version__)
    (out/f'environment-{a.kind}.json').write_text(json.dumps(env,indent=2))
    dest=out/'records.jsonl';done=set()
    if dest.exists():done={(r['task'],r['condition']) for r in map(json.loads,dest.read_text().splitlines())}
    arms=['D-active','D-round','D-shuffled','D-none'] if a.kind=='diffusion' else ['AR-round']
    for i,(name,initial) in enumerate(list(FAULTS.items())[:a.limit]):
        # Rotate arm order to reduce systematic thermal/timing ordering effects.
        order=arms[i%len(arms):]+arms[:i%len(arms)]
        for arm in order:
            if (name,arm) in done:continue
            r=run_case(b,name,initial,arm,i)
            with dest.open('a') as f:f.write(json.dumps(r)+'\n');f.flush()
            print(json.dumps(dict(task=name,condition=arm,initial=r['initial_metrics']['caught'],
                final=r['final_metrics']['caught'],weights=r['final'],seconds=r['wall_seconds'])),flush=True)
    (out/f'COMPLETE-{a.kind}.json').write_text(json.dumps(dict(completed=True,cases=a.limit,arms=arms)))
if __name__=='__main__':main()
