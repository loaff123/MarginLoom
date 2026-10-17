import copy
import inspect
import unittest
from unittest.mock import patch
from marginloom.model import Table
from marginloom.contracts import Contract
from marginloom.solve import solve
from marginloom.verify import verify_result,verify_diagnosis
import marginloom.verify as verifier
from test_flow import table,contract

class VerifyTests(unittest.TestCase):
    def test_roundtrip_no_optimizer(self):
        t=table([['-1.25','.04'],['0','9007199254740993.01']]); c=contract('.05')
        r=solve(t,c).to_dict()
        with patch('marginloom.flow.nx.network_simplex',side_effect=AssertionError('optimizer forbidden')):
            v=verify_result(t,c,r)
        self.assertTrue(v.valid,v.errors); self.assertIn('not_optimality',v.scope)
        source=inspect.getsource(verifier)
        for forbidden in ['from .flow','from .solve','from .decimal_codec']:
            self.assertNotIn(forbidden,source)
    def test_claim_tampering(self):
        t=table([['.25','.75']]);c=contract();r=solve(t,c).to_dict()
        changes=[('objective','primary','99'),('checks','cells',False),('margins','grand',{}),('backend','algorithm','mystery')]
        for key,sub,val in changes:
            bad=copy.deepcopy(r);bad[key][sub]=val
            with self.subTest(key=key):self.assertFalse(verify_result(t,c,bad).valid)
        for key,value in [('rows',['x']),('columns',['z','c1']),('selected',[['.5','.5']]),('schema_version',True),('verification_scope','optimality_proven')]:
            bad=copy.deepcopy(r);bad[key]=value
            with self.subTest(key=key):self.assertFalse(verify_result(t,c,bad).valid)
        bad=copy.deepcopy(r);bad['cells'][0][0]['lower']='-99'
        self.assertFalse(verify_result(t,c,bad).valid)
    def test_nonoptimal_feasible_does_not_prove_optimum(self):
        # One-dimensional .1/.9 is valid with selected 1/0, but suboptimal.
        t=table([['.1','.9']]);c=contract()
        r=solve(t,c).to_dict()
        r['selected']=[['1','0']]
        r['cells'][0][0].update(selected='1',delta='0.9')
        r['cells'][0][1].update(selected='0',delta='-0.9')
        r['margins']['columns'][0].update(selected='1',delta='0.9')
        r['margins']['columns'][1].update(selected='0',delta='-0.9')
        r['objective'].update(cells='1.8',columns='1.8',total_error='3.6',primary='3.6')
        v=verify_result(t,c,r)
        self.assertTrue(v.valid,v.errors);self.assertEqual(v.scope,'feasibility_and_arithmetic_not_optimality')
    def test_huge_output(self):
        t=table([['1e1000','-1e1000','1e-1000']]); c=contract('1e-1000')
        r=solve(t,c).to_dict();self.assertTrue(verify_result(t,c,r).valid)
    def test_cut_recomputation(self):
        t=table([['.3','.3','0'],['0','0','.3'],['0','0','.3']])
        c=contract(mode='prescribed',row_targets={'r0':'1','r1':'0','r2':'0'},column_targets={'c0':'0','c1':'0','c2':'1'})
        d=solve(t,c).data['diagnosis'];v=verify_diagnosis(t,c,d)
        self.assertTrue(v.valid,v.errors)
        for key,value in [('shortage',2),('required',0),('rows',[]),('demands',[]),('crossing_edges',[]),('nodes',[])]:
            bad=copy.deepcopy(d);bad[key]=value
            # Original witness has zero-capacity crossing arcs, which are still checked.
            with self.subTest(key=key):self.assertFalse(verify_diagnosis(t,c,bad).valid)
    def test_simple_diagnoses(self):
        t=table([['.3','.3']])
        for c in [contract(mode='prescribed',row_targets={'r0':'1'},column_targets={'c0':'0','c1':'0'}),contract(mode='prescribed',row_targets={'r0':'3'},column_targets={'c0':'2','c1':'1'})]:
            d=solve(t,c).data['diagnosis']; self.assertTrue(verify_diagnosis(t,c,d).valid)
            d['kind']='capacity_cut';self.assertFalse(verify_diagnosis(t,c,d).valid)
