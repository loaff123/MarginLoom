"""Practical admission-boundary qualification (not memory/security guarantees)."""
import tempfile
import unittest
from pathlib import Path
from marginloom.decimal_codec import parse_decimal
from marginloom.model import InputError,Table,MAX_BYTES
from marginloom.table_io import read_bytes

class LimitTests(unittest.TestCase):
    def test_mantissa_and_token_boundaries(self):
        self.assertEqual(parse_decimal('9'*128),(int('9'*128),0))
        with self.assertRaises(InputError):parse_decimal('9'*129)
        token='1e+'+'0'*249+'1000'
        self.assertEqual(len(token),256);self.assertEqual(parse_decimal(token),(1,1000))
        with self.assertRaises(InputError):parse_decimal(token+'0')
    def test_axis_id_and_cell_boundaries(self):
        self.assertEqual(len(Table(['x'*1024],['a'],[['0']]).row_ids[0]),1024)
        with self.assertRaises(InputError):Table(['x'*1025],['a'],[['0']])
        for count in (1000,1001):
            if count==1000:self.assertEqual(len(Table([str(i) for i in range(count)],['a'],[['0']]*count).row_ids),1000)
            else:
                with self.assertRaises(InputError):Table([str(i) for i in range(count)],['a'],[['0']]*count)
        with self.assertRaises(InputError):Table([str(i) for i in range(101)],[str(j) for j in range(100)],[['0']*100 for _ in range(101)])
    def test_file_size_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'file'
            with path.open('wb') as f:f.truncate(MAX_BYTES)
            self.assertEqual(len(read_bytes(path)),MAX_BYTES)
            with path.open('ab') as f:f.write(b'0')
            with self.assertRaises(InputError):read_bytes(path)
