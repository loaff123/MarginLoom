"""Contract orchestration and exact result accounting in original units."""
import networkx as nx
from .decimal_codec import format_scaled, floor_ceil, nearest_even
from .model import Result
from .flow import prepare, build_network, feasibility, optimize

TIE_POLICY = 'fixed_input_order_same_backend; no_cross_version_or_lexicographic_guarantee'

def _margin(p,source,selected,lo,hi,label=None):
    fmt = lambda x: format_scaled(x,p.exponent)
    item = {'source':fmt(source),'lower':fmt(lo*p.quantum),'upper':fmt(hi*p.quantum),
            'nearest':fmt(nearest_even(source,p.quantum)*p.quantum),
            'selected':fmt(selected*p.quantum),'delta':fmt(selected*p.quantum-source)}
    if label is not None: item['id'] = label
    return item

def account(p,units):
    q = p.quantum; fmt = lambda x: format_scaled(x,p.exponent)
    m,n = len(p.table.row_ids),len(p.table.column_ids)
    rows = [sum(row) for row in units]
    cols = [sum(units[i][j] for i in range(m)) for j in range(n)]
    base_rows = [sum(row) for row in p.floors]
    base_cols = [sum(p.floors[i][j] for i in range(m)) for j in range(n)]
    cells = [[_margin(p,a,units[i][j],*floor_ceil(a,q)) for j,a in enumerate(row)] for i,row in enumerate(p.amounts)]
    rm = [_margin(p,a,v,b+lo,b+hi,label) for a,v,b,(lo,hi),label in zip(p.row_sums,rows,base_rows,p.row_bounds,p.table.row_ids)]
    cm = [_margin(p,a,v,b+lo,b+hi,label) for a,v,b,(lo,hi),label in zip(p.column_sums,cols,base_cols,p.column_bounds,p.table.column_ids)]
    cell_error = sum(abs(units[i][j]*q-a) for i,row in enumerate(p.amounts) for j,a in enumerate(row))
    row_error = sum(abs(v*q-a) for v,a in zip(rows,p.row_sums))
    col_error = sum(abs(v*q-a) for v,a in zip(cols,p.column_sums))
    total = cell_error+row_error+col_error
    return {'schema_version':1,'contract':p.contract.to_dict(),'row_label':p.table.row_label,
            'rows':list(p.table.row_ids),'columns':list(p.table.column_ids),
            'selected':[[fmt(x*q) for x in row] for row in units],'cells':cells,
            'margins':{'rows':rm,'columns':cm,'grand':_margin(p,sum(p.row_sums),sum(rows),p.grand_units,p.grand_units)},
            'objective':{'cells':fmt(cell_error),'rows':fmt(row_error),'columns':fmt(col_error),
                         'total_error':fmt(total),'primary':fmt(total if p.contract.mode=='balanced' else cell_error)},
            'checks':{'cells':True,'rows':True,'columns':True,'grand':True},
            'backend':{'name':'networkx','version':nx.__version__,'algorithm':'network_simplex','tie_policy':TIE_POLICY},
            'verification_scope':'feasibility_and_arithmetic_not_optimality'}

def solve(table,contract) -> Result:
    p = prepare(table,contract)
    if p.diagnosis: return Result('infeasible',{'diagnosis':p.diagnosis})
    try:
        model = build_network(p)
        diagnosis = feasibility(model)
        if diagnosis: return Result('infeasible',{'diagnosis':diagnosis})
        units = optimize(model)
        return Result('optimal',account(p,units))
    except KeyboardInterrupt:
        return Result('incomplete',{'diagnosis':{'kind':'interrupted','message':'Rounding was interrupted.'}})
    except Exception as exc:
        return Result('error',{'diagnosis':{'kind':'backend_error','message':f'{type(exc).__name__}: {exc}'}})

def inspect_table(table,contract) -> dict:
    p = prepare(table,contract)
    fmt = lambda x: format_scaled(x,p.exponent)
    data = {'schema_version':1,'mode':p.contract.mode,'quantum':p.contract.quantum,
            'rows':[{'id':label,'source':fmt(a),'nearest':fmt(nearest_even(a,p.quantum)*p.quantum)} for label,a in zip(table.row_ids,p.row_sums)],
            'columns':[{'id':label,'source':fmt(a),'nearest':fmt(nearest_even(a,p.quantum)*p.quantum)} for label,a in zip(table.column_ids,p.column_sums)],
            'source_grand':fmt(sum(p.row_sums)),'required_grand':fmt(p.grand_units*p.quantum)}
    row_bases=[sum(row) for row in p.floors]
    column_bases=[sum(row[j] for row in p.floors) for j in range(len(table.column_ids))]
    for key,bases,bounds,targets in [('rows',row_bases,p.row_bounds,p.contract.row_targets),('columns',column_bases,p.column_bounds,p.contract.column_targets)]:
        for item,base,(lo,hi) in zip(data[key],bases,bounds):
            item.update(lower=fmt((base+lo)*p.quantum),upper=fmt((base+hi)*p.quantum))
            if targets is not None:item['target']=targets[item['id']]
    data['independently_nearest_totals_agree'] = (sum(nearest_even(x,p.quantum) for x in p.row_sums)==sum(nearest_even(x,p.quantum) for x in p.column_sums)==nearest_even(sum(p.row_sums),p.quantum))
    try:
        diagnosis = p.diagnosis or feasibility(build_network(p))
        data['status'] = 'infeasible' if diagnosis else 'feasible'
        if diagnosis: data['diagnosis'] = diagnosis
    except Exception as exc:
        data.update(status='error',diagnosis={'kind':'backend_error','message':f'{type(exc).__name__}: {exc}'})
    return data
