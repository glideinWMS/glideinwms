#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/lib/exprParser.py

 Author:
   Dennis Box dbox@fnal.gov
"""


from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner


import glideinwms.lib.exprParser as ep

TEST_LIST = ['a or b', 'a and b', '3', 'None', 'False', 'a + b',
             'a*b', 'a/b', 'not a', 'x[:1]', 'str(a)', 'a<<3',
             '(a,b,x)', '[a,b,x]', 'a<3', 'a+b>4', 'a**b',
             'a>>3', 'a/b', 'a/3', 'lambda a,b:hash((a,b))',
             'a-b', 'a in x', 'x[0]', 'd[a]', 'a in d', ]

TEST_RAISE_LIST = ['a^b', 'a&b', 'a|b', 'a+=3', ]


class TestExprParserSymmetric(unittest.TestCase):

    def test_parse_symmetric(self):
        for itm in TEST_LIST:
            self.assertEqual(repr(ep.parse(ep.unparse(ep.parse(itm)))),
                             repr(ep.parse(itm)))

    def test_unparse_ret(self):
        for itm in TEST_LIST:
            self.assertTrue(isinstance(ep.unparse(ep.parse(itm)), str))

    def test__compile(self):
        a = 3
        b = 4
        x = [a, b]
        d = {a: b}

        # just test that nothing in TEST_LIST throws an exception when compiled
        for itm in TEST_LIST:
            try:
                eval(ep.compile(ep.parse(itm)))
            except Exception as err:
                bad_itm = str(err)
                bad_itm += " for expr:"
                bad_itm += itm
                raise RuntimeError(bad_itm)


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner('unittests-reports'))
