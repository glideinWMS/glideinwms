#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

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


import unittest

import xmlrunner

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


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
