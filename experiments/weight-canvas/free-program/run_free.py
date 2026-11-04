import argparse,pathlib,sys,json,hashlib,time,torch
ROOT=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent))
from models import Backend,DEVICE,sync
from controller import FAULTS,feedback,metrics,scenarios,version
from run import RULES
from programs import interpret
N=80;STEPS=40

def question(initial,candidate=None,report=None):
    text=RULES.replace('Return the weight program, no explanation.','Return only Python assignments to E. You may use E = [[...], [...]] and E[i][j] = value. Do not assign W1, W2 or biases. No explanation.')
    text+='E = '+str([initial[:3],initial[3:]])+'\n'
    if report is not None:
        text+='\nPrevious candidate:\n'+candidate+'\nEvaluator:\n'+json.dumps(report,separators=(',',':'))+'\nRepair the weights based on this report. Return only E assignments.\n'
    return text

def parse(text,initial):
    try:return interpret(text,initial),None
    except (ValueError,SyntaxError,TypeError,IndexError) as e:return None,type(e).__name__+': '+str(e)[:160]

def report_for(text,initial,practice,shuffle=False):
    e,error=parse(text,initial)
    if error:return dict(error=error),None
    return feedback(e,practice,shuffle),e

def text_of(b,values):
    vals=values.tolist() if hasattr(values,'tolist') else values
    if b.tok.eos_token_id in vals:vals=vals[:vals.index(b.tok.eos_token_id)]
    return b.tok.decode(vals,skip_special_tokens=True)

def sha(ids):return hashlib.sha256(json.dumps(ids).encode()).hexdigest()

@torch.inference_mode()
def diffusion(b,prefix,initial,practice,arm,inject=False):
    ids=prefix+[b.tok.mask_token_id]*N;x=torch.tensor([ids],device=DEVICE);P=len(prefix)
    events=[];arrival=None;stage=0;in_stage=0;calls=0;positions=0
    while True:
        before=x.clone();hidden=b.model.model(x,use_cache=False).last_hidden_state[:,P:P+N]
        logits=b.model.lm_head(hidden).float()[0];logits[:,b.tok.mask_token_id]=-torch.inf
        proposed=logits.argmax(-1);confidence=logits.softmax(-1).gather(-1,proposed[:,None]).squeeze(-1)
        mask=x[0,P:P+N]==b.tok.mask_token_id
        draft=torch.where(mask,proposed,x[0,P:P+N]);draft_text=text_of(b,draft)
        confidence[~mask]=-torch.inf;k=min(2,int(mask.sum()));select=confidence.topk(k).indices
        x[0,P+select]=proposed[select];calls+=1;positions+=x.shape[1];in_stage+=1
        assert x[0,:P].tolist()==prefix,'Prompt changed'
        if arrival is not None:assert x[0,P+N:].tolist()==arrival['locked_tokens'],'Feedback changed'
        events.append(dict(type='step',step=calls,stage=stage,masked=int((x[0,P:P+N]==b.tok.mask_token_id).sum()),
            provisional=draft_text,canvas=text_of(b,x[0,P:P+N]),canvas_hash=sha(x[0].tolist())))
        if inject and stage==0 and calls>=10:
            e,error=parse(draft_text,initial)
            eos=(draft==b.tok.eos_token_id).nonzero().flatten();end=int(eos[0]) if len(eos) else N
            content_masks=int((x[0,P:P+end]==b.tok.mask_token_id).sum())
            if error is None and content_masks>0:
                truth=feedback(e,practice);shown=feedback(e,practice,True) if arm=='D-shuffled' else truth
                if arm=='D-none':shown=None;message='\nContinue revising the E assignments above. No evaluation report is available.\n'
                else:message='\nEvaluator report for the provisional program above:\n'+json.dumps(shown,separators=(',',':'))+'\nRepair E above using these observations. Return only E assignments.\n'
                tokens=b.encode(message)
                arrival=dict(step=calls,remaining_content_masks=content_masks,candidate_text=draft_text,candidate=e,
                    candidate_hash=version(e),true_feedback=truth,displayed_feedback=shown,locked_tokens=tokens,
                    locked_hash=sha(tokens),position=P+N,prefix_hash=sha(prefix))
                x=torch.cat([x,torch.tensor([tokens],device=DEVICE)],dim=1)
                x[0,P:P+N]=b.tok.mask_token_id;stage=1;in_stage=0
                events.append(dict(type='arrival',**{k:v for k,v in arrival.items() if k!='locked_tokens'}))
        if in_stage==STEPS:break
    sync()
    return text_of(b,x[0,P:P+N]),dict(events=events,arrival=arrival,calls=calls,processed_positions=positions,lock_violations=0)

@torch.inference_mode()
def autoregressive(b,text):
    ids=b.prompt(text);x=torch.tensor([ids],device=DEVICE)
    y=b.model.generate(x,attention_mask=torch.ones_like(x),max_new_tokens=N,do_sample=False,use_cache=True,pad_token_id=b.tok.eos_token_id)
    sync();out=y[0,len(ids):];tokens=len(out)
    return text_of(b,out),dict(calls=tokens,processed_positions=len(ids)+max(0,tokens-1),events=[],arrival=None,lock_violations=0)

def case(b,name,initial,index,arm):
    start=time.perf_counter();practice=scenarios(20261104+index,64);held=scenarios(20262104+index,512)
    if arm=='AR-round':
        first,m1=autoregressive(b,question(initial));truth,candidate=report_for(first,initial,practice)
        final,m2=autoregressive(b,question(initial,first,truth));parts=[m1,m2]
    elif arm=='D-round':
        first,m1=diffusion(b,b.prompt(question(initial)),initial,practice,arm)
        truth,candidate=report_for(first,initial,practice)
        final,m2=diffusion(b,b.prompt(question(initial,first,truth)),initial,practice,arm);parts=[m1,m2]
    else:
        final,m1=diffusion(b,b.prompt(question(initial)),initial,practice,arm,True);parts=[m1]
        arrival=m1['arrival'];first=arrival['candidate_text'] if arrival else None
        candidate=arrival['candidate'] if arrival else None;truth=arrival['true_feedback'] if arrival else None
    e,error=parse(final,initial)
    return dict(task=name,condition=arm,initial=initial,candidate=candidate,candidate_text=first,final=e,final_text=final,
        valid=e is not None,error=error,true_feedback=truth,parts=parts,
        initial_metrics=metrics(initial,initial,held),final_metrics=metrics(e,initial,held) if e else None,
        deployable_caught=metrics(e,initial,held)['caught'] if e else 0,
        forward_calls=sum(p['calls'] for p in parts),processed_positions=sum(p['processed_positions'] for p in parts),
        wall_seconds=time.perf_counter()-start,heldout_seed=20262104+index,practice_seed=20261104+index)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--kind',choices=['diffusion','ar'],required=True);a=ap.parse_args()
    out=ROOT/'results';out.mkdir(exist_ok=True)
    files=list(ROOT.glob('*.py'))+list(ROOT.glob('*.md'))+[ROOT.parent/'models.py',ROOT.parent/'modeling_a2d.py',ROOT.parent/'controller.py',ROOT.parent/'run.py']
    manifest={str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    dest=out/'source-manifest.json'
    if dest.exists():assert json.loads(dest.read_text())==manifest
    else:dest.write_text(json.dumps(manifest,indent=2))
    b=Backend(a.kind);(out/f'environment-{a.kind}.json').write_text(json.dumps(dict(model=b.repo,revision=b.revision,device=DEVICE,torch=torch.__version__,precision='float32'),indent=2))
    path=out/'records.jsonl';done=set()
    if path.exists():done={(r['task'],r['condition']) for r in map(json.loads,path.read_text().splitlines())}
    arms=['D-active','D-round','D-shuffled','D-none'] if a.kind=='diffusion' else ['AR-round']
    for i,(name,e) in enumerate(FAULTS.items()):
        for arm in arms[i%len(arms):]+arms[:i%len(arms)]:
            if (name,arm) in done:continue
            r=case(b,name,e,i,arm)
            with path.open('a') as f:f.write(json.dumps(r)+'\n');f.flush()
            print(json.dumps(dict(task=name,arm=arm,valid=r['valid'],initial=r['initial_metrics']['caught'],final=r['deployable_caught'],weights=r['final'],seconds=r['wall_seconds'])),flush=True)
    (out/f'COMPLETE-{a.kind}.json').write_text(json.dumps(dict(complete=True,cases=6,arms=arms)))
if __name__=='__main__':main()
