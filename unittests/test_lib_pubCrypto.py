#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# Description:
#   unit test for glideinwms/lib/pubCrypto.py
#
# Author:
#   Dennis Box dbox@fnal.gov
#

from __future__ import absolute_import
from __future__ import print_function
import os
import unittest2 as unittest
import xmlrunner


from glideinwms.unittests.unittest_utils import TestImportError
try:
    from glideinwms.lib.pubCrypto import PubRSAKey
    from glideinwms.lib.pubCrypto import RSAKey
except ImportError as err:
    raise TestImportError(str(err))



class TestPubCrypto(unittest.TestCase):

    def setUp(self):
        self.privkey_file = "priv.pem"
        self.pubkey_file = "pub.pem"
        self.key_length = 1024
        self.cr = RSAKey()
        self.cr.new(self.key_length)
        self.cr_pub = self.cr.PubRSAKey()
        self.cr.save(self.privkey_file)
        self.cr_pub.save(self.pubkey_file)

    def tearDown(self):
        os.remove(self.privkey_file)
        os.remove(self.pubkey_file)

    def test_symmetric(self, plaintext="5105105105105100"):
        encrypted = self.cr_pub.encrypt(plaintext)
        decrypted = self.cr.decrypt(encrypted)
        signed = self.cr.sign(plaintext)
        assert self.cr_pub.verify(plaintext, signed)
        assert plaintext == decrypted

    def test_symmetric_base64(self, plaintext="5105105105105100"):
        encrypted = self.cr_pub.encrypt_base64(plaintext)
        decrypted = self.cr.decrypt_base64(encrypted)
        signed = self.cr.sign_base64(plaintext)
        assert self.cr_pub.verify_base64(plaintext, signed)
        assert plaintext == decrypted

    def test_symmetric_hex(self, plaintext="5105105105105100"):
        encrypted = self.cr_pub.encrypt_hex(plaintext)
        decrypted = self.cr.decrypt_hex(encrypted)
        signed = self.cr.sign_hex(plaintext)
        assert self.cr_pub.verify_hex(plaintext, signed)
        assert plaintext == decrypted


if __name__ == '__main__':
    ofl = 'unittests-reports'
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=ofl))
