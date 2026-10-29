"""Nonblocking barrier coordinator. No Future.result() unless done()."""
import concurrent.futures,json,time,urllib.request
READS={'read_file','list_dir','stat','clock','run'};EFFECTS={'write_file','remove'}

def signature(call):return json.dumps(call,sort_keys=True,separators=(',',':'))

def remote_execute(call,committed=False,url='http://127.0.0.1:18766/execute'):
    body=json.dumps({'call':call,'committed':committed}).encode()
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'}),timeout=20) as response:return json.load(response)
    except Exception as e:return {'ok':False,'output':f'gateway error: {type(e).__name__}: {e}'}

class Engine:
    def __init__(self,execute=remote_execute,commit_rule=True,max_calls=64,delay_steps=0):
        self.execute=execute;self.commit_rule=commit_rule;self.max_calls=max_calls;self.delay_steps=delay_steps
        self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.states={};self.jobs=[];self.inflight={};self.events=[];self.calls=0;self.waits_on_pending=0
    def barrier(self,observations,step):
        started=time.perf_counter();current={o['anchor']:o for o in observations};delivered=[]
        # Validate completions against the CURRENT draft before any new submission.
        for job in list(self.jobs):
            if not job['future'].done() or step<job['submit_step']+self.delay_steps:continue
            result=job['future'].result() # proven complete; no pending wait
            obs=current.get(job['anchor']);state=self.states.get(job['anchor'])
            same=obs is not None and signature(obs['call'])==job['signature'] and state is job['state']
            event=dict(wall_time=time.time(),type='completion' if same else 'stale_completion',anchor=job['anchor'],step=step,submit_step=job['submit_step'],steps_to_land=step-job['submit_step'],result=result)
            self.events.append(event)
            if same:
                delivered.append(dict(anchor=job['anchor'],call=obs['call'],result=result,submit_step=job['submit_step'],step=step))
                state['delivered']=True
            self.jobs.remove(job)
        # Retire revised spans. An effect already dispatched from an immutable span
        # must never be revised by the sampler; count violations for the E3 control.
        for anchor,state in list(self.states.items()):
            obs=current.get(anchor)
            if obs is None or signature(obs['call'])!=state['signature']:
                if state['call']['name'] in EFFECTS:
                    self.events.append(dict(type='stray_effect' if state['submitted'] else 'dropped_effect',anchor=anchor,step=step,call=state['call']))
                del self.states[anchor]
        for obs in observations:
            anchor=obs['anchor'];call=obs['call'];name=call.get('name')
            if name not in READS|EFFECTS:continue
            state=self.states.setdefault(anchor,dict(call=call,signature=signature(call),submitted=False,delivered=False))
            if state['submitted'] or self.calls>=self.max_calls or not obs.get('eligible',True):continue
            effect=name in EFFECTS
            if effect and self.commit_rule and not obs['committed']:continue
            # Read-only/isolated calls can share an in-flight job. Writes are per-span.
            key=state['signature'] if not effect else (anchor,state['signature'])
            future=self.inflight.get(key)
            if future is None or future.done():
                future=self.pool.submit(self.execute,call,committed=effect)
                self.inflight[key]=future;self.calls+=1
                self.events.append(dict(type='submit',wall_time=time.time(),anchor=anchor,step=step,call=call,committed=bool(obs['committed']),effect=effect))
            else:self.events.append(dict(type='deduplicated',anchor=anchor,step=step))
            state['submitted']=True
            self.jobs.append(dict(anchor=anchor,signature=state['signature'],state=state,future=future,submit_step=step))
        self.events.append(dict(type='barrier',step=step,seconds=time.perf_counter()-started,pending=len(self.jobs)))
        return delivered
    def close(self):self.pool.shutdown(wait=True)
