#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

import glideinwms.lib.exprParser as ep

TEST_LIST = ['a or b', '3',  'None', 'False', 'a + b',
             'a*b', 'a/b', 'not a', 'x[:1]', 'str(a)', 'a<<3',
             '(a,b,x)', '[a,b,x]', 'a<3', 'a+b>4', 'a**b', ]

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

        # just test that nothing in TEST_LIST throws an exception when compiled
        for itm in TEST_LIST:
            eval(ep.compile(ep.parse(itm)))


if __name__ == '__main__':
    ofl = 'unittests-reports'
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=ofl))
