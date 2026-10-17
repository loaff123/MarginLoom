"""Independent Fraction arithmetic checks, never an optimality certificate.

Numerical reconstruction here deliberately does not reuse the producer's codec,
rounding helpers, graph construction, objective accounting or optimizer.
"""
from fractions import Fraction
import re
from .model import Verification

_SCOPE = 'feasibility_and_arithmetic_not_optimality'
_DECIMAL = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')

def _number(token):
    # Expanded output decimals can be longer than compact input tokens.
    if not isinstance(token,str) or len(token)>4096 or not _DECIMAL.fullmatch(token):
        raise ValueError('not an admissible decimal string')
    exponent = token.lower().partition('e')[2]
    if exponent and abs(int(exponent)) > 1000:
        raise ValueError('decimal exponent exceeds +/-1000')
    return Fraction(token)

def _text(value):
    value = Fraction(value)
    if not value: return '0'
    denominator = value.denominator; twos=fives=0
    while denominator%2==0: denominator//=2; twos+=1
    while denominator%5==0: denominator//=5; fives+=1
    if denominator!=1: raise ValueError('nonterminating decimal')
    places = max(twos,fives)
    coefficient = value.numerator*10**places//value.denominator
    sign = '-' if coefficient<0 else ''
    digits = str(abs(coefficient))
    if not places: return sign+digits
    digits = digits.zfill(places+1)
    return sign+(digits[:-places]+'.'+digits[-places:]).rstrip('0').rstrip('.')

def _bounds(x):
    return x.numerator//x.denominator, -((-x.numerator)//x.denominator)

def _nearest(x):
    lo=x.numerator//x.denominator; rem=x-lo
    return lo+int(rem>Fraction(1,2) or (rem==Fraction(1,2) and lo%2!=0))

def _same(a,b):
    if type(a) is not type(b): return False
    if isinstance(a,dict): return a.keys()==b.keys() and all(_same(a[k],b[k]) for k in a)
    if isinstance(a,list): return len(a)==len(b) and all(_same(x,y) for x,y in zip(a,b))
    return a==b

def _problem(table,contract):
    if table.row_label != contract.row_label:
        raise ValueError('table/contract row_label mismatch')
    q=_number(contract.quantum)
    if q<=0: raise ValueError('nonpositive quantum')
    a=[[_number(v) for v in row] for row in table.values]
    if contract.nonnegative and any(v<0 for row in a for v in row): raise ValueError('negative source')
    m,n=len(a),len(a[0]); b=[[_bounds(v/q)[0] for v in row] for row in a]
    rs=[sum(row) for row in a]; cs=[sum(a[i][j] for i in range(m)) for j in range(n)]
    rb=[sum(row) for row in b]; cb=[sum(b[i][j] for i in range(m)) for j in range(n)]
    rc=[sum(v/q!=floor for v,floor in zip(row,brow)) for row,brow in zip(a,b)]
    cc=[sum(a[i][j]/q!=b[i][j] for i in range(m)) for j in range(n)]
    diagnostic=None
    if contract.mode=='balanced':
        row_bounds=[_bounds(v/q) for v in rs]; col_bounds=[_bounds(v/q) for v in cs]
        grand=_nearest(sum(rs)/q)
    elif contract.mode=='prescribed':
        if set(contract.row_targets)!=set(table.row_ids) or set(contract.column_targets)!=set(table.column_ids):
            raise ValueError('target IDs mismatch')
        rt=[_number(contract.row_targets[k])/q for k in table.row_ids]
        ct=[_number(contract.column_targets[k])/q for k in table.column_ids]
        if any(x.denominator!=1 for x in rt+ct): raise ValueError('nonlattice target')
        rt=list(map(int,rt));ct=list(map(int,ct))
        row_bounds=[(x,x) for x in rt];col_bounds=[(x,x) for x in ct];grand=sum(rt)
        if sum(rt)!=sum(ct):
            diagnostic={'kind':'target_total_mismatch','message':'Prescribed row and column grand totals differ.',
                        'row_total':_text(sum(rt)*q),'column_total':_text(sum(ct)*q)}
        else:
            for axis,ids,targets,bases,caps in [('row',table.row_ids,rt,rb,rc),('column',table.column_ids,ct,cb,cc)]:
                for label,t,base,cap in zip(ids,targets,bases,caps):
                    if not base<=t<=base+cap:
                        diagnostic={'kind':'target_out_of_bounds','message':f'Prescribed {axis} {label!r} cannot be reached by floor/ceiling cell choices.',
                                    'axis':axis,'id':label,'target':_text(t*q),'lower':_text(base*q),'upper':_text((base+cap)*q)}
                        break
                if diagnostic:break
    else: raise ValueError('unknown contract mode')
    return q,a,b,rs,cs,rb,cb,row_bounds,col_bounds,grand,diagnostic

def _record(source,chosen,lo,hi,q,label=None):
    d={'source':_text(source),'lower':_text(lo*q),'upper':_text(hi*q),
       'nearest':_text(_nearest(source/q)*q),'selected':_text(chosen),'delta':_text(chosen-source)}
    if label is not None:d['id']=label
    return d

def verify_result(table,contract,result:dict) -> Verification:
    errors=[]
    def check(ok,message):
        if not ok:errors.append(message)
    try:
        q,a,b,rs,cs,rb,cb,row_bounds,col_bounds,grand,diagnostic=_problem(table,contract)
        check(diagnostic is None,'input contract is infeasible')
        check(result.get('status')=='optimal','result is not a successful solver result')
        m,n=len(a),len(a[0]);raw=result['selected']
        if not isinstance(raw,list) or len(raw)!=m or any(not isinstance(row,list) or len(row)!=n for row in raw):
            raise ValueError('selected dimensions differ from input')
        chosen=[[_number(v) for v in row] for row in raw]
        cells=[]
        for i,row in enumerate(a):
            records=[]
            for j,x in enumerate(row):
                lo,hi=_bounds(x/q);v=chosen[i][j]
                check((v/q).denominator==1 and lo<=v/q<=hi,f'cell {table.row_ids[i]!r}/{table.column_ids[j]!r} violates quantum/floor/ceiling')
                records.append(_record(x,v,lo,hi,q))
            cells.append(records)
        cr=[sum(row) for row in chosen];cc=[sum(chosen[i][j] for i in range(m)) for j in range(n)]
        for axis,values,bounds in [('row',cr,row_bounds),('column',cc,col_bounds)]:
            for i,(v,(lo,hi)) in enumerate(zip(values,bounds)):
                check((v/q).denominator==1 and lo<=v/q<=hi,f'{axis} {i} violates contract')
        check(sum(cr)==grand*q,'grand total violates contract')
        margins={'rows':[_record(x,y,lo,hi,q,label) for x,y,(lo,hi),label in zip(rs,cr,row_bounds,table.row_ids)],
                 'columns':[_record(x,y,lo,hi,q,label) for x,y,(lo,hi),label in zip(cs,cc,col_bounds,table.column_ids)],
                 'grand':_record(sum(rs),sum(cr),grand,grand,q)}
        ce=sum(abs(chosen[i][j]-v) for i,row in enumerate(a) for j,v in enumerate(row))
        re_=sum(abs(x-y) for x,y in zip(rs,cr));coe=sum(abs(x-y) for x,y in zip(cs,cc));total=ce+re_+coe
        objective={'cells':_text(ce),'rows':_text(re_),'columns':_text(coe),'total_error':_text(total),'primary':_text(total if contract.mode=='balanced' else ce)}
        expected={'schema_version':1,'contract':contract.to_dict(),'row_label':table.row_label,
                  'rows':list(table.row_ids),'columns':list(table.column_ids),
                  'selected':[[_text(x) for x in row] for row in chosen],
                  'cells':cells,'margins':margins,'objective':objective,
                  'checks':{'cells':True,'rows':True,'columns':True,'grand':True},'verification_scope':_SCOPE}
        base_keys=set(expected)|{'status','backend'}
        check(set(result) in (base_keys,base_keys|{'sources','artifacts'}),'result has missing or unknown schema keys')
        for key,value in expected.items():check(_same(result.get(key),value),f'{key} claim differs from independent arithmetic')
        backend=result.get('backend',{})
        check(isinstance(backend,dict) and set(backend)=={'name','version','algorithm','tie_policy'} and backend.get('name')=='networkx' and backend.get('algorithm')=='network_simplex'
              and isinstance(backend.get('version'),str) and bool(backend['version'])
              and backend.get('tie_policy')=='fixed_input_order_same_backend; no_cross_version_or_lexicographic_guarantee','invalid backend provenance')
    except (KeyError,TypeError,ValueError,IndexError,AttributeError,ZeroDivisionError,OverflowError) as exc:
        errors.append(f'malformed or inconsistent result: {exc}')
    return Verification(not errors,errors)

def verify_diagnosis(table,contract,diagnosis:dict) -> Verification:
    errors=[]
    try:
        q,a,b,rs,cs,rb,cb,row_bounds,col_bounds,grand,simple=_problem(table,contract)
        if simple is not None:
            if not _same(diagnosis,simple):errors.append('simple infeasibility diagnosis differs from source arithmetic')
        else:
            if diagnosis.get('kind')!='capacity_cut':raise ValueError('no independently established obstruction')
            m,n=len(a),len(a[0]);nodes=['source']+[f'row:{i}' for i in range(m)]+[f'column:{j}' for j in range(n)]+['sink']
            demands={node:0 for node in nodes};demands['source']=-(grand-sum(rb));demands['sink']=grand-sum(rb)
            edges=[]
            def edge(u,v,lower,upper):
                demands[u]+=lower;demands[v]-=lower;edges.append((u,v,upper-lower))
            for i,((lo,hi),base) in enumerate(zip(row_bounds,rb)):edge('source',f'row:{i}',lo-base,hi-base)
            for i,row in enumerate(a):
                for j,x in enumerate(row):
                    if x/q!=b[i][j]:edge(f'row:{i}',f'column:{j}',0,1)
            for j,((lo,hi),base) in enumerate(zip(col_bounds,cb)):edge(f'column:{j}','sink',lo-base,hi-base)
            selected=diagnosis['nodes']
            if not isinstance(selected,list) or not selected or any(not isinstance(x,str) for x in selected):raise ValueError('invalid cut node set')
            subset=set(selected)
            if len(subset)!=len(selected) or not subset<=set(nodes):raise ValueError('invalid cut node set')
            canonical=[x for x in nodes if x in subset]
            crossing=[{'from':u,'to':v,'capacity':capacity} for u,v,capacity in edges if u in subset and v not in subset]
            required=-sum(demands[x] for x in subset);available=sum(x['capacity'] for x in crossing)
            expected={'kind':'capacity_cut','message':'This named node set needs more residual flow than its outgoing edges permit.',
                      'units':'integer_quantum_increments','nodes':canonical,
                      'rows':[table.row_ids[i] for i in range(m) if f'row:{i}' in subset],
                      'columns':[table.column_ids[j] for j in range(n) if f'column:{j}' in subset],
                      'includes_source':'source' in subset,'includes_sink':'sink' in subset,
                      'demands':[{'node':x,'demand':demands[x]} for x in canonical],
                      'crossing_edges':crossing,'required':required,'available':available,'shortage':required-available}
            if required<=available:errors.append('cut has no positive shortage')
            if not _same(diagnosis,expected):errors.append('cut claims differ from independently reconstructed capacities/demands')
    except (KeyError,TypeError,ValueError,IndexError,AttributeError,ZeroDivisionError,OverflowError) as exc:
        errors.append(f'malformed or unsupported diagnosis: {exc}')
    return Verification(not errors,errors,'infeasibility_arithmetic')

def verify_report(input_path,contract_path,report_path) -> Verification:
    """Check saved report identity, arithmetic and CSV consistency, not optimality."""
    import csv
    import hashlib
    import io
    from pathlib import Path
    from .table_io import load_contract,load_table,strict_json,decode,read_bytes
    errors=[]
    report=Path(report_path)
    try:
        names={p.name for p in report.iterdir()}
        if 'INCOMPLETE' in names:return Verification(False,['report is marked INCOMPLETE'])
        success=names=={'rounded.csv','margins.csv','audit.json','report.html'}
        rejected=names=={'diagnosis.json','report.html'}
        if not(success or rejected):return Verification(False,['report members do not match an exact supported report layout'])
        if any(not (report/name).is_file() for name in names):return Verification(False,['report members must be files'])
        contract=load_contract(contract_path);table=load_table(input_path,contract)
        name='audit.json' if success else 'diagnosis.json'
        data=strict_json(decode((report/name).read_bytes()))
        if not isinstance(data,dict):raise ValueError('report metadata must be an object')
        binding={'input_sha256':hashlib.sha256(read_bytes(input_path)).hexdigest(),
                 'contract_sha256':hashlib.sha256(read_bytes(contract_path)).hexdigest()}
        if not _same(data.get('sources'),binding):errors.append('input/contract source hashes differ')
        expected_artifacts={'rounded.csv','margins.csv','report.html'} if success else {'report.html'}
        hashes=data.get('artifacts')
        if not isinstance(hashes,dict) or set(hashes)!=expected_artifacts:errors.append('artifact manifest identities differ')
        else:
            for artifact in sorted(expected_artifacts):
                if hashes[artifact]!=hashlib.sha256((report/artifact).read_bytes()).hexdigest():errors.append(f'{artifact} hash differs')
        if success:
            errors.extend(verify_result(table,contract,data).errors)
            rounded=list(csv.reader(io.StringIO(decode((report/'rounded.csv').read_bytes()),newline=''),strict=True))
            expected=[[table.row_label,*table.column_ids]]+[[label,*row] for label,row in zip(table.row_ids,data['selected'])]
            if not _same(rounded,expected):errors.append('rounded.csv values or IDs differ from audit')
            margin_rows=list(csv.reader(io.StringIO(decode((report/'margins.csv').read_bytes()),newline=''),strict=True))
            fields=['source','lower','upper','nearest','selected','delta']
            expected=[['axis','id',*fields]]
            for axis,plural in [('row','rows'),('column','columns')]:
                for item in data['margins'][plural]:expected.append([axis,item['id'],*[item[k] for k in fields]])
            expected.append(['grand','',*[data['margins']['grand'][k] for k in fields]])
            if not _same(margin_rows,expected):errors.append('margins.csv claims differ from audit')
            return Verification(not errors,errors)
        if set(data)!={'schema_version','status','contract','rows','columns','diagnosis','sources','artifacts'}:errors.append('diagnosis has missing or unknown schema keys')
        if type(data.get('schema_version')) is not int or data['schema_version']!=1 or data.get('status')!='infeasible':errors.append('invalid diagnosis metadata')
        if not _same(data.get('contract'),contract.to_dict()):errors.append('diagnosis contract differs')
        if not _same(data.get('rows'),list(table.row_ids)) or not _same(data.get('columns'),list(table.column_ids)):errors.append('diagnosis IDs differ')
        errors.extend(verify_diagnosis(table,contract,data['diagnosis']).errors)
        return Verification(not errors,errors,'infeasibility_arithmetic')
    except (OSError,KeyError,TypeError,ValueError,IndexError,AttributeError,csv.Error) as exc:
        return Verification(False,errors+[f'cannot verify report: {exc}'])
