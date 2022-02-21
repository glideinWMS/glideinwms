#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

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


import os
import unittest

import xmlrunner

from glideinwms.unittests.unittest_utils import TestImportError

try:
    from glideinwms.lib.pubCrypto import PubRSAKey, RSAKey
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
        decrypted = self.cr.decrypt(encrypted).decode("utf8")
        signed = self.cr.sign(plaintext)
        assert self.cr_pub.verify(plaintext, signed)
        assert plaintext == decrypted

    def test_symmetric_base64(self, plaintext="5105105105105100"):
        encrypted = self.cr_pub.encrypt_base64(plaintext)
        decrypted = self.cr.decrypt_base64(encrypted).decode("utf8")
        signed = self.cr.sign_base64(plaintext)
        assert self.cr_pub.verify_base64(plaintext, signed)
        assert plaintext == decrypted

    def test_symmetric_hex(self, plaintext="5105105105105100"):
        encrypted = self.cr_pub.encrypt_hex(plaintext)
        decrypted = self.cr.decrypt_hex(encrypted).decode("utf8")
        signed = self.cr.sign_hex(plaintext)
        assert self.cr_pub.verify_hex(plaintext, signed)
        assert plaintext == decrypted


if __name__ == "__main__":
    ofl = "unittests-reports"
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=ofl))
