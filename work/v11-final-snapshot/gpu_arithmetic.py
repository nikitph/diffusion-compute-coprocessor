"""One Triton launch for batched exact +, -, * on unsigned <=64-digit inputs.
Output: 128 little-endian decimal digits plus sign. Host encoding/decoding is
outside the kernel; this alone does not establish an end-to-end GPU-only hook.
"""
import json, random, time
import torch
import triton
import triton.language as tl

@triton.jit
def arithmetic(A,B,OP,OUT,SIGN,N:tl.constexpr,D:tl.constexpr):
    row=tl.program_id(0)
    j=tl.arange(0,D)
    av=tl.load(A+row*D+j); bv=tl.load(B+row*D+j)
    op=tl.load(OP+row)
    highest=tl.max(tl.where(av!=bv,j,-1),0)
    negative=tl.sum(tl.where(j==highest,av-bv,0),0)<0
    tl.store(SIGN+row,tl.where((op==1)&negative,-1,1))
    carry=0
    for k in range(2*D):
        if op==2:
            bi=k-j
            bvals=tl.load(B+row*D+bi,mask=(bi>=0)&(bi<D),other=0)
            raw=tl.sum(av*bvals,0)+carry
            digit=raw%10; carry=raw//10
        else:
            a=tl.load(A+row*D+k,mask=k<D,other=0)
            b=tl.load(B+row*D+k,mask=k<D,other=0)
            if op==0:
                raw=a+b+carry
                digit=raw%10; carry=raw//10
            else:
                large=tl.where(negative,b,a); small=tl.where(negative,a,b)
                raw=large-small+carry
                digit=tl.where(raw<0,raw+10,raw);carry=tl.where(raw<0,-1,0)
        tl.store(OUT+row*(2*D)+k,digit)

def encode(values,D=64):
    if any(v<0 or len(str(v))>D for v in values):raise ValueError('unsigned operands must fit digit budget')
    return torch.tensor([[int(c) for c in str(v)[::-1]]+[0]*(D-len(str(v))) for v in values],dtype=torch.int32,device='cuda')

def compute(a,b,ops):
    if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=64:raise ValueError('expected matching [batch,64] operands')
    out=torch.empty((a.shape[0],128),dtype=torch.int32,device=a.device)
    signs=torch.empty(a.shape[0],dtype=torch.int32,device=a.device)
    arithmetic[(a.shape[0],)](a,b,ops,out,signs,a.shape[0],64,num_warps=4)
    return out,signs

def decode(out,signs):
    return [int(''.join(map(str,row[::-1])))*sign for row,sign in zip(out.tolist(),signs.tolist())]

def main():
    rng=random.Random(20261028); cases=[]
    for digits in (1,2,5,10,20,32,64):
        for a,b in [(0,0),(10**digits-1,1),(1,10**digits-1),(10**digits-1,10**digits-1)]+[(rng.randrange(10**digits),rng.randrange(10**digits)) for _ in range(32)]:
            for op in range(3):cases.append((a,b,op))
    a=encode([r[0] for r in cases]); b=encode([r[1] for r in cases]);ops=torch.tensor([r[2] for r in cases],dtype=torch.int32,device='cuda')
    expected=[x+y if op==0 else x-y if op==1 else x*y for x,y,op in cases]
    outputs=compute(a,b,ops);actual=decode(*outputs)
    bad=[dict(case=cases[i],actual=str(v),expected=str(expected[i])) for i,v in enumerate(actual) if v!=expected[i]]
    # Warm kernel only: excludes parsing, transfers, output allocation and decoding.
    out,signs=outputs
    begin=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
    begin.record()
    for _ in range(100):arithmetic[(len(cases),)](a,b,ops,out,signs,len(cases),64,num_warps=4)
    end.record();torch.cuda.synchronize()
    result=dict(cases=len(cases),failures=len(bad),examples=bad[:3],kernel_ms=begin.elapsed_time(end)/100,gpu=torch.cuda.get_device_name(),scope='isolated arithmetic kernel; not end-to-end sampling')
    print(json.dumps(result,indent=2));assert not bad
if __name__=='__main__':main()
