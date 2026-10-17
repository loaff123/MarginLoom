import unittest
from unittest.mock import patch
from marginloom.model import Table,InputError
from marginloom.contracts import Contract
from marginloom.flow import prepare, build_network, feasibility
from marginloom.solve import solve, inspect_table

def contract(q='1',mode='balanced',**kw):
    return Contract.from_dict({'schema_version':1,'mode':mode,'quantum':q,'row_label':'id',**kw})
def table(values):
    return Table([f'r{i}' for i in range(len(values))],[f'c{j}' for j in range(len(values[0]))],values,'id')

class FlowTests(unittest.TestCase):
    def test_lower_transform(self):
        p=prepare(table([['.6','.6'],['.6','.6']]),contract())
        m=build_network(p)
        self.assertEqual(m.graph.nodes['source']['demand'],0)
        self.assertEqual(m.graph.nodes['row:0']['demand'],-1)
        self.assertEqual(m.graph.nodes['column:0']['demand'],1)
        self.assertEqual(m.graph['source']['row:0']['capacity'],1)
        self.assertEqual(m.graph['source']['row:0']['weight'],6)
        self.assertEqual(m.graph['row:0']['column:0']['weight'],-2)
    def test_signed_and_zero(self):
        r=solve(table([['-1.25','0','1.25']]),contract('.1'))
        self.assertEqual(r.status,'optimal')
        self.assertEqual(r.data['selected'][0][1],'0')
        self.assertEqual(r.data['margins']['grand']['selected'],'0')
        self.assertIn(r.data['selected'][0][0],['-1.3','-1.2'])
    def test_fixed_integral(self):
        r=solve(table([['-20','0'],['40','60']]),contract('20'))
        self.assertEqual(r.status,'optimal'); self.assertEqual(r.data['objective']['primary'],'0')
        self.assertEqual(r.data['selected'],[['-20','0'],['40','60']])
    def test_cut_named(self):
        t=table([['.3','.3','0'],['0','0','.3'],['0','0','.3']])
        c=contract(mode='prescribed',row_targets={'r0':'1','r1':'0','r2':'0'},column_targets={'c0':'0','c1':'0','c2':'1'})
        r=solve(t,c); self.assertEqual(r.status,'infeasible')
        d=r.data['diagnosis']; self.assertEqual(d['kind'],'capacity_cut')
        self.assertEqual((d['required'],d['available'],d['shortage']),(1,0,1))
        self.assertIn('r0',d['rows']); self.assertIn('c0',d['columns'])
    def test_totals_and_individual_bounds(self):
        t=table([['.3','.3']])
        c=contract(mode='prescribed',row_targets={'r0':'1'},column_targets={'c0':'0','c1':'0'})
        self.assertEqual(solve(t,c).data['diagnosis']['kind'],'target_total_mismatch')
        c=contract(mode='prescribed',row_targets={'r0':'3'},column_targets={'c0':'2','c1':'1'})
        self.assertEqual(solve(t,c).data['diagnosis']['kind'],'target_out_of_bounds')
    def test_invalid_targets_and_nonnegative(self):
        t=table([['-.3']])
        for c in [contract(nonnegative=True),contract(mode='prescribed',row_targets={'r0':'.1'},column_targets={'c0':'.1'}),contract(mode='prescribed',row_targets={'wrong':'0'},column_targets={'c0':'0'})]:
            with self.assertRaises(InputError):solve(t,c)
    def test_objective_mode(self):
        t=table([['.3','.3']]); balanced=solve(t,contract()).data
        c=contract(mode='prescribed',row_targets={'r0':'0'},column_targets={'c0':'0','c1':'0'})
        prescribed=solve(t,c).data
        self.assertEqual(prescribed['objective'],{'cells':'0.6','rows':'0.6','columns':'0.6','total_error':'1.8','primary':'0.6'})
        self.assertEqual(balanced['objective']['primary'],balanced['objective']['total_error'])
    def test_backend_error_is_not_infeasible(self):
        with patch('marginloom.flow.nx.network_simplex',side_effect=RuntimeError('broken backend')):
            self.assertEqual(solve(table([['.3']]),contract()).status,'error')
    def test_deterministic_tie_and_inspect(self):
        t=table([['.5','.5'],['.5','.5']]); c=contract()
        self.assertEqual(solve(t,c).to_dict(),solve(t,c).to_dict())
        with patch('marginloom.flow.nx.network_simplex',side_effect=AssertionError('inspect must not optimize')):
            self.assertEqual(inspect_table(t,c)['status'],'feasible')
    def test_large_exponents(self):
        t=table([['1e1000','-1e1000','1e-1000']])
        r=solve(t,contract('1e-1000')); self.assertEqual(r.status,'optimal')
        self.assertEqual(r.data['objective']['primary'],'0')
