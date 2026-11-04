"""Bounded AST interpreter for weight assignments, not Python exec/eval."""
import ast,re,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from controller import validate

def interpret(text,initial):
    if len(text)>6000:raise ValueError('Program too long')
    blocks=re.findall(r'```(?:python)?\s*\n?(.*?)```',text,re.S)
    if blocks:text=blocks[0]
    elif '```' in text:raise ValueError('Unclosed code fence')
    tree=ast.parse(text.strip());e=[[v-2 for v in initial[:3]],[v-2 for v in initial[3:]]];writes=0
    if len(tree.body)>24:raise ValueError('Too many statements')
    for st in tree.body:
        if not isinstance(st,ast.Assign) or len(st.targets)!=1:raise ValueError('Only assignments are permitted')
        target=st.targets[0]
        if isinstance(target,ast.Name) and target.id=='W1':
            value=ast.literal_eval(st.value)
            if not isinstance(value,list) or len(value)!=2 or any(not isinstance(r,list) or len(r)!=3 for r in value):raise ValueError('W1 must be 2 by 3')
            validate([int(v)+2 if type(v) in (int,float) and v==int(v) else v for v in value[0]+value[1]]);e=[r[:] for r in value];writes+=1
        elif (isinstance(target,ast.Subscript) and isinstance(target.value,ast.Subscript)
              and isinstance(target.value.value,ast.Name) and target.value.value.id=='W1'):
            i=ast.literal_eval(target.value.slice);j=ast.literal_eval(target.slice);v=ast.literal_eval(st.value)
            if type(i)!=int or type(j)!=int or not 0<=i<2 or not 0<=j<3:raise ValueError('Index out of range')
            if type(v) not in (int,float) or v!=int(v) or not -2<=v<=2:raise ValueError('Weight out of range')
            e[i][j]=v;writes+=1
        else:raise ValueError('Only W1 or W1[i][j] assignments are permitted')
    if not writes:raise ValueError('No weight assignments')
    return validate([int(v)+2 for v in e[0]+e[1]])
