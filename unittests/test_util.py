#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# Description:
#   unit test for glideinwms/lib/util.py
#
# Author:
#   Marco Mascheroni
#

from __future__ import absolute_import
from __future__ import print_function
import xmlrunner
import unittest2 as unittest

from glideinwms.lib.util import safe_boolcomp

class TestUtils(unittest.TestCase):
    def test_safe_boolcomp(self):
        self.assertTrue(safe_boolcomp("True", True))
        self.assertTrue(safe_boolcomp(True, True))
        self.assertTrue(safe_boolcomp("False", False))
        self.assertTrue(safe_boolcomp(False, False))
        self.assertFalse(safe_boolcomp("True", False))
        self.assertFalse(safe_boolcomp(True, False))
        self.assertFalse(safe_boolcomp("False", True))
        self.assertFalse(safe_boolcomp(False, True))
        self.assertFalse(safe_boolcomp("foo", True))
        self.assertFalse(safe_boolcomp("foo", False))

if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
