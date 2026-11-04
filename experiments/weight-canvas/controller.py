"""Deterministic 3->2 ReLU->3 controller; no model-generated code is executed."""
import hashlib,json,random

REFERENCE = [3,3,1,1,1,3]  # W1 = E - 2; positive and negative intercept error.
FAULTS = {
    'velocity_reversed': [3,1,1,1,3,3],
    'position_reversed': [1,3,1,3,1,3],
    'paddle_reversed': [3,3,3,1,1,1],
    'velocity_missing': [3,2,1,1,2,3],
    'one_hidden_dead': [2,2,2,1,1,3],
    'gain_doubled': [4,4,0,0,0,4],
}

def validate(e):
    if not isinstance(e,list) or len(e)!=6 or any(type(v)!=int or not 0<=v<=4 for v in e):
        raise ValueError('Expected six integer weight codes in [0,4]')
    return e

def program(e):
    validate(e)
    return ('E = [['+', '.join(map(str,e[:3]))+'], ['+', '.join(map(str,e[3:]))+']]\n'
            'W1 = [[v - 2 for v in row] for row in E]\n'
            'b1 = [0, 0]\nW2 = [[0, 1], [0, 0], [1, 0]]\nb2 = [-0.1, 0, -0.1]\n')

def version(e):return hashlib.sha256(program(e).encode()).hexdigest()[:16]

def action(e,obs):
    validate(e)
    h=[max(0,sum((e[r*3+j]-2)*obs[j] for j in range(3))) for r in range(2)]
    logits=[h[1]-.1,0,h[0]-.1]
    a=max(range(3),key=lambda i:logits[i])-1
    return a,logits

def scenarios(seed,n):
    r=random.Random(seed);rows=[]
    while len(rows)<n:
        p=r.uniform(.3,.7);target=p+r.uniform(-.29,.29);v=r.uniform(-.25,.25);x=target-v
        if 0<x<1 and 0<target<1:
            rows.append([round(x,6),round(v,6),round(p,6)])
    return rows

def evaluate(e,rows):
    outcomes=[]
    for obs in rows:
        a,logits=action(e,obs);x,v,p=obs
        miss=abs(x+v-(p+.2*a))
        outcomes.append(dict(observation=obs,action=a,logits=[round(v,6) for v in logits],miss=round(miss,6),caught=miss<=.1100001))
    return dict(version=version(e),n=len(rows),caught=sum(r['caught'] for r in outcomes),outcomes=outcomes)

def feedback(e,rows,shuffled=False):
    result=evaluate(e,rows)
    failures=[r for r in result['outcomes'] if not r['caught']]
    examples=(failures or result['outcomes'])[:3]
    if shuffled:
        # Deliberately mismatched evidence control: pair each outcome with another
        # observation; retain full true evaluation separately in the record.
        donor=scenarios(99173,len(examples))
        examples=[dict(row,observation=donor[i]) for i,row in enumerate(examples)]
    return dict(candidate=result['version'],weight_codes=e,caught=result['caught'],total=result['n'],examples=examples)

def metrics(e,baseline,rows):
    now=evaluate(e,rows);old=evaluate(baseline,rows)
    return dict(caught=now['caught'],total=now['n'],success_rate=now['caught']/now['n'],
                fixes=sum(not a['caught'] and b['caught'] for a,b in zip(old['outcomes'],now['outcomes'])),
                regressions=sum(a['caught'] and not b['caught'] for a,b in zip(old['outcomes'],now['outcomes'])),
                changed_weights=sum(a!=b for a,b in zip(e,baseline)))

if __name__=='__main__':
    rows=scenarios(20261104,512)
    print(json.dumps({k:metrics(e,REFERENCE,rows) for k,e in dict(reference=REFERENCE,**FAULTS).items()},indent=2))
