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
        """Testing DN extraction. Need to adapt to change in behavior of openssl

        On EL8: "openssl x509 -noout -subject -nameopt compat -in %s" returns the desired /DN=... string
        and "openssl x509 -noout -subject -in %s" returns DN = org, DC =...
        On El7 happens exactly the opposite
        """
        fname = "fixtures/hostcert.pem"
        cmd = f"openssl x509 -noout -subject -in {fname}"
        out = glideinwms.lib.subprocessSupport.iexe_cmd(f"{cmd} -nameopt compat")
        expected = "=".join(out.split("=")[1:]).strip(" \n")
        if not expected.startswith("/"):
            out = glideinwms.lib.subprocessSupport.iexe_cmd(cmd)
            expected = " ".join(out.split()[1:])
        self.assertEqual(expected, extract_DN(fname))


if __name__ == "__main__":
    ofl = "unittests-reports"
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=ofl))
