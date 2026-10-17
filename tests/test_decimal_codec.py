import unittest
from marginloom.decimal_codec import parse_decimal, format_scaled, floor_ceil, nearest_even
from marginloom.model import InputError

class DecimalTests(unittest.TestCase):
    def test_parse_exact(self):
        self.assertEqual(parse_decimal('-1.25'), (-125,-2))
        self.assertEqual(parse_decimal('9.00719925474099301e15'), (900719925474099301,-2))
        self.assertEqual(parse_decimal('.05'), (5,-2))
        self.assertEqual(parse_decimal('-0e1000'), (0,0))
        self.assertEqual(parse_decimal('1e-1000'), (1,-1000))
        self.assertEqual(parse_decimal('1e1000'), (1,1000))
    def test_invalid_tokens(self):
        for x in ['', ' 1','1 ','NaN','inf','1_000','١','1e','.', True,1.5,'1e1001','1e-1001','9'*129]:
            with self.subTest(x=str(x)[:30]), self.assertRaises(InputError): parse_decimal(x)
    def test_floor_negative(self):
        self.assertEqual(floor_ceil(-125,10), (-13,-12))
        self.assertEqual(floor_ceil(-120,10), (-12,-12))
    def test_nearest_ties(self):
        self.assertEqual([nearest_even(i,2) for i in [-5,-3,-1,1,3,5]],[-2,-2,0,0,2,2])
    def test_format_original_units(self):
        for n,e,s in [(125,-2,'1.25'),(-120,-2,'-1.2'),(0,-1000,'0'),(5,-2,'0.05'),(12,2,'1200')]:
            self.assertEqual(format_scaled(n,e),s)
        self.assertEqual(format_scaled(1,1000),'1'+'0'*1000)
        self.assertEqual(format_scaled(1,-1000),'0.'+'0'*999+'1')
