#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import glideinwms.lib.subprocessSupport

import unittest2 as unittest
import xmlrunner

from glideinwms.lib.x509Support import extract_DN


class TestExtractDN(unittest.TestCase):

    def test_extract_dn(self):
        fname = 'fixtures/hostcert.pem'
        cmd = "openssl x509 -in %s -noout -subject" % fname
        out = glideinwms.lib.subprocessSupport.iexe_cmd(cmd)
        expected = ' '.join(out.split()[1:])
        self.assertEqual(expected, extract_DN(fname))


if __name__ == '__main__':
    ofl = 'unittests-reports'
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=ofl))
