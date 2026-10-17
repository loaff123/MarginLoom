import json
import tempfile
import unittest
from pathlib import Path
from marginloom.contracts import Contract
from marginloom.model import Table,InputError
from marginloom.table_io import load_table,load_contract

class InputTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)
        self.c=Contract.from_dict({'schema_version':1,'mode':'balanced','quantum':'.05','row_label':'id'})
    def put(self,name,text):
        p=self.p/name; p.write_text(text,encoding='utf-8'); return p
    def test_csv_bom_and_multiline(self):
        t=load_table(self.put('x.csv','\ufeffid,a,b\n"α\nβ",-1.25,9007199254740993.01\n'),self.c)
        self.assertEqual(t.row_ids,('α\nβ',)); self.assertEqual(t.column_ids,('a','b'))
        self.assertEqual(t.values,(('-1.25','9007199254740993.01'),))
    def test_row_label_can_be_middle(self):
        t=load_table(self.put('x.csv','a,id,b\n1,first,2\n'),self.c)
        self.assertEqual(t.values,(('1','2'),)); self.assertEqual(t.row_ids,('first',))
    def test_bad_csv(self):
        for s in ['id,a\n','id\nx\n','id,a,a\nx,1,2\n','id,a\nx,1\nx,2\n','id,a\nx,\n','id,a\nx,1,2\n','id,a\n,1\n','id,a\nx,NaN\n','id,a\nx, 1\n']:
            with self.subTest(s=s),self.assertRaises(InputError):load_table(self.put('x.csv',s),self.c)
    def test_json_strings_only(self):
        d={'schema_version':1,'row_label':'id','rows':['x'],'columns':['a'],'values':[['0.1']]}
        self.assertEqual(load_table(self.put('x.json',json.dumps(d)),self.c).values,(('0.1',),))
        d['values']=[[0.1]]
        with self.assertRaises(InputError):load_table(self.put('x.json',json.dumps(d)),self.c)
    def test_json_duplicate_unknown_and_bool_version(self):
        for s in ['{"mode":"balanced","mode":"prescribed"}', '{"schema_version":true,"mode":"balanced","quantum":"1","row_label":"id"}', '{"schema_version":1,"mode":"balanced","quantum":"1","row_label":"id","x":1}']:
            with self.assertRaises(InputError):load_contract(self.put('c.json',s))
    def test_bad_contract(self):
        for change in [{'quantum':'0'},{'quantum':'-1'},{'quantum':1},{'nonnegative':'yes'},{'mode':'auto'},{'row_targets':{}},{'schema_version':True}]:
            d={'schema_version':1,'mode':'balanced','quantum':'1','row_label':'id',**change}
            with self.subTest(change=change),self.assertRaises(InputError):Contract.from_dict(d)
    def test_table_validation(self):
        for rows,cols,vals in [([],['a'],[]),(['x'],[],[[]]),(['x','x'],['a'],[['1'],['2']]),(['x'],['a'],[['1','2']]),(['\0'],['a'],[['1']]),(['x'],['id'],[['1']])]:
            with self.assertRaises(InputError):Table(rows,cols,vals,'id')
    def test_api_float_rejected(self):
        with self.assertRaises(InputError):Table(['x'],['a'],[[0.1]],'id')
    def test_json_requires_arrays_and_unicode_ids(self):
        valid={'schema_version':1,'row_label':'id','rows':['x'],'columns':['a'],'values':[['1']]}
        for key,bad in [('rows',{'x':1}),('columns',{'a':1}),('values',{'x':['1']}),('rows',['\ud800'])]:
            d={**valid,key:bad}
            with self.subTest(key=key,bad=repr(bad)),self.assertRaises(InputError):load_table(self.put('x.json',json.dumps(d)),self.c)
