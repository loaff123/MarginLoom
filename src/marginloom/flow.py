"""Finite exact-integer lower-bounded transportation model and backend adapter."""
from dataclasses import dataclass
import networkx as nx
from .contracts import Contract
from .decimal_codec import common_scale, floor_ceil, nearest_even, format_scaled
from .model import Table, InputError

@dataclass
class Prepared:
    table: Table
    contract: Contract
    amounts: list[list[int]]
    quantum: int
    exponent: int
    floors: list[list[int]]
    remainders: list[list[int]]
    row_sums: list[int]
    column_sums: list[int]
    row_bounds: list[tuple[int,int]]
    column_bounds: list[tuple[int,int]]
    grand_units: int
    diagnosis: dict | None = None

@dataclass
class FlowModel:
    prepared: Prepared
    graph: nx.DiGraph
    lower: dict[tuple[str,str],int]

def prepare(table: Table, contract: Contract) -> Prepared:
    contract = Contract.from_dict(contract.to_dict())
    if table.row_label != contract.row_label: raise InputError('row_label differs from contract')
    flat = [v for row in table.values for v in row]
    targets = []
    if contract.mode == 'prescribed':
        if set(contract.row_targets) != set(table.row_ids) or set(contract.column_targets) != set(table.column_ids):
            raise InputError('prescribed target IDs must exactly match the input axes')
        targets = [contract.row_targets[x] for x in table.row_ids] + [contract.column_targets[x] for x in table.column_ids]
    scaled, exponent = common_scale(flat+[contract.quantum]+targets)
    count = len(flat); quantum = scaled[count]
    m,n = len(table.row_ids),len(table.column_ids)
    amounts = [scaled[i*n:(i+1)*n] for i in range(m)]
    if contract.nonnegative and any(x < 0 for row in amounts for x in row):
        raise InputError('nonnegative contract rejects negative source values')
    floors = [[x//quantum for x in row] for row in amounts]
    remainders = [[x%quantum for x in row] for row in amounts]
    row_sums = [sum(row) for row in amounts]
    column_sums = [sum(amounts[i][j] for i in range(m)) for j in range(n)]
    row_base = [sum(row) for row in floors]
    col_base = [sum(floors[i][j] for i in range(m)) for j in range(n)]
    row_cap = [sum(r>0 for r in row) for row in remainders]
    col_cap = [sum(remainders[i][j]>0 for i in range(m)) for j in range(n)]
    diagnosis = None
    if contract.mode == 'balanced':
        rb = [(lo-b,hi-b) for v,b in zip(row_sums,row_base) for lo,hi in [floor_ceil(v,quantum)]]
        cb = [(lo-b,hi-b) for v,b in zip(column_sums,col_base) for lo,hi in [floor_ceil(v,quantum)]]
        grand = nearest_even(sum(row_sums),quantum)
    else:
        target_amounts = scaled[count+1:]
        if any(x % quantum for x in target_amounts):
            raise InputError('every prescribed target must be an exact quantum multiple')
        rt = [x//quantum for x in target_amounts[:m]]
        ct = [x//quantum for x in target_amounts[m:]]
        rb = [(v-b,v-b) for v,b in zip(rt,row_base)]
        cb = [(v-b,v-b) for v,b in zip(ct,col_base)]
        grand = sum(rt)
        fmt = lambda x: format_scaled(x*quantum,exponent)
        if sum(rt) != sum(ct):
            diagnosis = {'kind':'target_total_mismatch','message':'Prescribed row and column grand totals differ.',
                         'row_total':fmt(sum(rt)),'column_total':fmt(sum(ct))}
        if diagnosis is None:
            for axis,ids,ts,base,caps in [('row',table.row_ids,rt,row_base,row_cap),('column',table.column_ids,ct,col_base,col_cap)]:
                for label,t,b,cap in zip(ids,ts,base,caps):
                    if not b <= t <= b+cap:
                        diagnosis = {'kind':'target_out_of_bounds','message':f'Prescribed {axis} {label!r} cannot be reached by floor/ceiling cell choices.',
                                     'axis':axis,'id':label,'target':fmt(t),'lower':fmt(b),'upper':fmt(b+cap)}
                        break
                if diagnosis: break
    return Prepared(table,contract,amounts,quantum,exponent,floors,remainders,row_sums,column_sums,rb,cb,grand,diagnosis)

def build_network(p: Prepared) -> FlowModel:
    if p.diagnosis: raise ValueError('cannot construct flow for invalid target bounds')
    g = nx.DiGraph(); lower = {}
    m,n = len(p.table.row_ids),len(p.table.column_ids)
    residual_total = p.grand_units-sum(sum(row) for row in p.floors)
    g.add_node('source',demand=-residual_total)
    for i in range(m): g.add_node(f'row:{i}',demand=0)
    for j in range(n): g.add_node(f'column:{j}',demand=0)
    g.add_node('sink',demand=residual_total)
    def edge(u,v,lo,hi,cost):
        if not 0 <= lo <= hi: raise ValueError('invalid residual lower/upper bounds')
        lower[u,v] = lo
        g.nodes[u]['demand'] += lo; g.nodes[v]['demand'] -= lo
        g.add_edge(u,v,capacity=hi-lo,weight=cost)
    for i,(lo,hi) in enumerate(p.row_bounds):
        cost = p.quantum-2*(p.row_sums[i]%p.quantum) if hi>lo else 0
        edge('source',f'row:{i}',lo,hi,cost)
    for i,row in enumerate(p.remainders):
        for j,r in enumerate(row):
            if r: edge(f'row:{i}',f'column:{j}',0,1,p.quantum-2*r)
    for j,(lo,hi) in enumerate(p.column_bounds):
        cost = p.quantum-2*(p.column_sums[j]%p.quantum) if hi>lo else 0
        edge(f'column:{j}','sink',lo,hi,cost)
    return FlowModel(p,g,lower)

def feasibility(model: FlowModel) -> dict | None:
    g = model.graph
    h = nx.DiGraph()
    h.add_nodes_from(g.nodes)
    for u,v,d in g.edges(data=True): h.add_edge(u,v,capacity=d['capacity'])
    h.add_node('super_source'); h.add_node('super_sink')
    supply = 0
    for node,d in g.nodes(data=True):
        demand = d['demand']
        if demand < 0:
            h.add_edge('super_source',node,capacity=-demand); supply -= demand
        elif demand > 0: h.add_edge(node,'super_sink',capacity=demand)
    value,(reachable,_) = nx.minimum_cut(h,'super_source','super_sink',flow_func=nx.algorithms.flow.edmonds_karp)
    if value == supply: return None
    chosen = [node for node in g.nodes if node in reachable]
    chosen_set = set(chosen)
    crossing = [{'from':u,'to':v,'capacity':d['capacity']} for u,v,d in g.edges(data=True) if u in chosen_set and v not in chosen_set]
    required = -sum(g.nodes[node]['demand'] for node in chosen)
    available = sum(edge['capacity'] for edge in crossing)
    if required <= available: raise RuntimeError('backend produced an invalid deficient cut')
    p = model.prepared
    return {'kind':'capacity_cut','message':'This named node set needs more residual flow than its outgoing edges permit.',
            'units':'integer_quantum_increments','nodes':chosen,
            'rows':[p.table.row_ids[i] for i in range(len(p.table.row_ids)) if f'row:{i}' in chosen_set],
            'columns':[p.table.column_ids[j] for j in range(len(p.table.column_ids)) if f'column:{j}' in chosen_set],
            'includes_source':'source' in chosen_set,'includes_sink':'sink' in chosen_set,
            'demands':[{'node':node,'demand':g.nodes[node]['demand']} for node in chosen],
            'crossing_edges':crossing,'required':required,'available':available,'shortage':required-available}

def optimize(model: FlowModel) -> list[list[int]]:
    _,flow = nx.network_simplex(model.graph)
    p = model.prepared
    return [[b+flow.get(f'row:{i}',{}).get(f'column:{j}',0) for j,b in enumerate(row)] for i,row in enumerate(p.floors)]
