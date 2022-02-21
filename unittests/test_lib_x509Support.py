#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinwms
Purpose:
    unit test of glideinwms/lib/x509Support.py

Author:
    Dennis Box dbox@fnal.gov
"""


import unittest

import xmlrunner

import glideinwms.lib.subprocessSupport

from glideinwms.unittests.unittest_utils import TestImportError

try:
    from glideinwms.lib.x509Support import extract_DN
except ImportError as err:
    raise TestImportError(str(err))


class TestExtractDN(unittest.TestCase):
    def test_extract_dn(self):
        fname = "fixtures/hostcert.pem"
        cmd = "openssl x509 -in %s -noout -subject" % fname
        out = glideinwms.lib.subprocessSupport.iexe_cmd(cmd)
        expected = " ".join(out.split()[1:])
        self.assertEqual(expected, extract_DN(fname))


if __name__ == "__main__":
    ofl = "unittests-reports"
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=ofl))
