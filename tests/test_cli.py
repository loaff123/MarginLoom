import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
        self.source=self.p/'source.csv';self.source.write_text('id,a,b\nx,0.3,0.3\ny,-1.25,9007199254740993.01\n')
        self.contract=self.p/'contract.json';self.contract.write_text(json.dumps({'schema_version':1,'mode':'balanced','quantum':'.05','row_label':'id'}))
        self.out=self.p/'report'
    def run_cli(self,*args):
        return subprocess.run([sys.executable,'-m','marginloom',*map(str,args)],capture_output=True,text=True)
    def test_round_inspect_verify(self):
        r=self.run_cli('round',self.source,'--contract',self.contract,'--out',self.out)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['status'],'optimal')
        self.assertEqual({p.name for p in self.out.iterdir()},{'rounded.csv','margins.csv','audit.json','report.html'})
        a=json.loads((self.out/'audit.json').read_text());self.assertEqual(a['selected'][1][1],'9007199254740993')
        v=self.run_cli('verify',self.source,'--contract',self.contract,'--report',self.out)
        self.assertEqual(v.returncode,0,v.stderr);self.assertTrue(json.loads(v.stdout)['valid']);self.assertIn('not_optimality',v.stdout)
        i=self.run_cli('inspect',self.source,'--contract',self.contract)
        self.assertEqual(i.returncode,0,i.stderr);self.assertEqual(json.loads(i.stdout)['status'],'feasible')
    def test_nonclobber_and_tamper(self):
        self.assertEqual(self.run_cli('round',self.source,'--contract',self.contract,'--out',self.out).returncode,0)
        original=(self.out/'audit.json').read_bytes()
        r=self.run_cli('round',self.source,'--contract',self.contract,'--out',self.out)
        self.assertEqual(r.returncode,1);self.assertEqual(original,(self.out/'audit.json').read_bytes())
        for name in ['rounded.csv','margins.csv','report.html']:
            path=self.out/name;raw=path.read_bytes();path.write_bytes(raw+b'changed')
            self.assertEqual(self.run_cli('verify',self.source,'--contract',self.contract,'--report',self.out).returncode,4)
            path.write_bytes(raw)
        (self.out/'extra.txt').write_text('extra')
        self.assertEqual(self.run_cli('verify',self.source,'--contract',self.contract,'--report',self.out).returncode,4)
    def test_invalid_exit(self):
        self.source.write_text('id,a\nx,NaN\n')
        r=self.run_cli('round',self.source,'--contract',self.contract,'--out',self.out)
        self.assertEqual(r.returncode,2);self.assertNotIn('Traceback',r.stderr);self.assertFalse(self.out.exists())
    def test_prescribed_rejection_then_explicit_balanced(self):
        self.source.write_text('id,a,b,c\nx,.3,.3,0\ny,0,0,.3\nz,0,0,.3\n')
        self.contract.write_text(json.dumps({'schema_version':1,'mode':'prescribed','quantum':'1','row_label':'id','row_targets':{'x':'1','y':'0','z':'0'},'column_targets':{'a':'0','b':'0','c':'1'}}))
        r=self.run_cli('round',self.source,'--contract',self.contract,'--out',self.out)
        self.assertEqual(r.returncode,3,r.stderr);self.assertEqual({p.name for p in self.out.iterdir()},{'diagnosis.json','report.html'})
        self.assertEqual(self.run_cli('verify',self.source,'--contract',self.contract,'--report',self.out).returncode,0)
        self.contract.write_text(json.dumps({'schema_version':1,'mode':'balanced','quantum':'1','row_label':'id'}))
        self.assertEqual(self.run_cli('round',self.source,'--contract',self.contract,'--out',self.p/'balanced').returncode,0)
    def test_json_and_updated_source(self):
        self.source=self.p/'source.json';self.source.write_text(json.dumps({'schema_version':1,'row_label':'id','rows':['x'],'columns':['a'],'values':[['1.23']]}))
        self.assertEqual(self.run_cli('round',self.source,'--contract',self.contract,'--out',self.out).returncode,0)
        self.source.write_text(self.source.read_text().replace('1.23','1.29'))
        self.assertEqual(self.run_cli('verify',self.source,'--contract',self.contract,'--report',self.out).returncode,4)
        self.assertEqual(self.run_cli('round',self.source,'--contract',self.contract,'--out',self.p/'updated').returncode,0)
