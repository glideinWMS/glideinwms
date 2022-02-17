#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/lib/exprParser.py

 Author:
   Dennis Box dbox@fnal.gov
"""


import ast
import unittest

import xmlrunner

import glideinwms.lib.exprParser as ep

TEST_LIST = [
    "a or b",
    "a and b",
    "3",
    "None",
    "False",
    "a + b",
    "a*b",
    "a/b",
    "not a",
    "x[:1]",
    "str(a)",
    "a<<3",
    "(a,b,x)",
    "[a,b,x]",
    "a<3",
    "a+b>4",
    "a**b",
    "a>>3",
    "a/b",
    "a/3",
    "lambda a,b:hash((a,b))",
    "a-b",
    "a in x",
    "x[0]",
    "d[a]",
    "a in d",
]

TEST_RAISE_LIST = [
    "a^b",
    "a&b",
    "a|b",
    "a+=3",
]


class TestExprParserSymmetric(unittest.TestCase):
    def test_parse_symmetric(self):
        for itm in TEST_LIST:
            self.assertEqual(
                ast.dump(ep.exp_parse(ep.exp_unparse(ep.exp_parse(itm)))),
                ast.dump(ep.exp_parse(itm)),
            )

    def test_unparse_ret(self):
        for itm in TEST_LIST:
            self.assertTrue(isinstance(ep.exp_unparse(ep.exp_parse(itm)), str))

    def test__compile(self):
        a = 3
        b = 4
        x = [a, b]
        d = {a: b}

        # just test that nothing in TEST_LIST throws an exception when compiled
        for itm in TEST_LIST:
            try:
                eval(ep.exp_compile(ep.exp_parse(itm)))
            except Exception as err:
                bad_itm = str(err)
                bad_itm += " for expr:"
                bad_itm += itm
                raise RuntimeError(bad_itm)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner("unittests-reports"))
