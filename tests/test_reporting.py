import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from marginloom.reporting import write_report
from marginloom.verify import verify_report

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
        self.s=self.p/'source.csv';self.s.write_text('id,<script>,b\n<img src=x onerror=bad>,.3,.3\n')
        self.c=self.p/'contract.json';self.c.write_text('{"schema_version":1,"mode":"balanced","quantum":"1","row_label":"id"}')
        self.out=self.p/'out'
    def test_html_escape_and_hashes(self):
        self.assertEqual(write_report(self.s,self.c,self.out).status,'optimal')
        html=(self.out/'report.html').read_text()
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
        self.assertIn('&lt;img src=x onerror=bad&gt;',html)
        audit=json.loads((self.out/'audit.json').read_text());self.assertNotIn('audit.json',audit['artifacts'])
        for name,digest in audit['artifacts'].items():self.assertEqual(hashlib.sha256((self.out/name).read_bytes()).hexdigest(),digest)
        self.assertTrue(verify_report(self.s,self.c,self.out).valid)
    def test_deterministic_outputs(self):
        write_report(self.s,self.c,self.out);other=self.p/'other';write_report(self.s,self.c,other)
        for p in self.out.iterdir():self.assertEqual(p.read_bytes(),(other/p.name).read_bytes())
    def test_failures_leave_marker(self):
        for failure in [OSError('disk failed'),KeyboardInterrupt()]:
            out=self.p/('interrupt' if isinstance(failure,KeyboardInterrupt) else 'failed')
            with patch('marginloom.reporting._publish_file',side_effect=failure):
                result=write_report(self.s,self.c,out)
            self.assertEqual(result.status,'incomplete' if isinstance(failure,KeyboardInterrupt) else 'error')
            self.assertTrue((out/'INCOMPLETE').exists());self.assertFalse(verify_report(self.s,self.c,out).valid)
    def test_interrupted_after_audit_still_rejected(self):
        with patch('marginloom.reporting._finish',side_effect=KeyboardInterrupt()):
            result=write_report(self.s,self.c,self.out)
        self.assertEqual(result.status,'incomplete');self.assertTrue((self.out/'audit.json').exists())
        self.assertFalse(verify_report(self.s,self.c,self.out).valid)
    def test_verifier_detects_consistent_hash_csv_tampering(self):
        write_report(self.s,self.c,self.out)
        p=self.out/'rounded.csv';p.write_text('id,<script>,b\n<img src=x onerror=bad>,0,0\n')
        audit=json.loads((self.out/'audit.json').read_text());audit['artifacts']['rounded.csv']=hashlib.sha256(p.read_bytes()).hexdigest()
        (self.out/'audit.json').write_text(json.dumps(audit))
        v=verify_report(self.s,self.c,self.out);self.assertFalse(v.valid);self.assertTrue(any('rounded.csv' in x for x in v.errors))
