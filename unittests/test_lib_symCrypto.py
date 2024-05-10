#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Unit test for glideinwms/lib/symCrypto.py
"""


import string
import unittest

import hypothesis
import hypothesis.strategies as st
import xmlrunner

from glideinwms.lib import defaults
from glideinwms.lib.symCrypto import (
    AutoSymKey,
    MutableSymKey,
    ParametrizedSymKey,
    Sym3DESKey,
    SymAES128Key,
    SymAES256Key,
)
from glideinwms.unittests.unittest_utils import TestImportError

try:
    from glideinwms.lib.symCrypto import SymKey
except ImportError as err:
    raise TestImportError(str(err))


class TestMutableSymKey(unittest.TestCase):
    def setUp(self):
        self.key = MutableSymKey()

    def test___init__(self):
        self.assertTrue(isinstance(self.key, MutableSymKey))

    def test_get_wcrypto(self):
        nam, kstr, key_iv = self.key.get_wcrypto()
        self.assertTrue(nam is None)
        self.assertTrue(kstr is None)
        self.assertTrue(key_iv is None)

    def test_is_valid(self):
        self.assertFalse(self.key.is_valid())

    def test_redefine(self):
        self.key.redefine(cypher_name="aes_128_cbc", key_len=16, iv_len=16, key_str=None, iv_str=None, key_iv_code=None)


class TestParametrizedSymKey(unittest.TestCase):
    def test___init__(self):
        psk = ParametrizedSymKey("aes_128_cbc")
        self.assertTrue(isinstance(psk, ParametrizedSymKey))
        self.assertTrue(isinstance(psk, SymKey))
        try:
            psk2 = ParametrizedSymKey("bad_parameter")  # noqa: F841  # keep, triggers exception
            assert False
        except KeyError:
            pass


class TestAutoSymKey(unittest.TestCase):
    def setUp(self):
        self.key = AutoSymKey()

    def test_auto_load(self):
        self.key.auto_load()
        self.assertTrue(self.key.cypher_name is None)
        self.assertTrue(self.key.key_str is None)
        try:
            key2 = AutoSymKey("bogus,bogus,bogus")  # noqa: F841  # keep, triggers exception
            assert False
        except ValueError:
            pass


class TestSymAES128Key(unittest.TestCase):
    def setUp(self):
        self.key = SymAES128Key()
        self.key.new()
        self.key_iv_code = self.key.get_code()

    def test___init__(self):
        self.assertTrue(isinstance(self.key, SymAES128Key))
        self.assertTrue(isinstance(self.key, SymKey))
        self.assertTrue(self.key.is_valid())
        (knm, ivn) = self.key.get()
        self.assertTrue(isinstance(knm, bytes))
        self.assertTrue(isinstance(ivn, bytes))
        nmm = self.key.get_code()
        self.assertTrue(len(nmm) > 12)
        self.assertEqual("aes_128_cbc", self.key.cypher_name)

    @hypothesis.given(st.text(alphabet=string.printable, min_size=1))
    def test_symmetric(self, data):
        data = defaults.force_bytes(data)
        sk2 = AutoSymKey(key_iv_code=self.key_iv_code)
        self.assertEqual(data, sk2.decrypt(self.key.encrypt(data)))
        self.assertEqual(data, sk2.decrypt_hex(self.key.encrypt_hex(data)))
        self.assertEqual(data, sk2.decrypt_base64(self.key.encrypt_base64(data)))


class TestSymAES256Key(unittest.TestCase):
    def setUp(self):
        self.key = SymAES256Key()
        self.key.new()
        self.key_iv_code = self.key.get_code()

    def test___init__(self):
        self.assertTrue(isinstance(self.key, SymAES256Key))
        self.assertTrue(isinstance(self.key, SymKey))
        self.assertTrue(self.key.is_valid())
        (knm, ivn) = self.key.get()
        self.assertTrue(isinstance(knm, bytes))
        self.assertTrue(isinstance(ivn, bytes))
        nmm = self.key.get_code()
        self.assertTrue(len(nmm) > 12)
        self.assertEqual("aes_256_cbc", self.key.cypher_name)

    @hypothesis.given(st.text(alphabet=string.printable, min_size=1))
    def test_symmetric(self, data):
        data = defaults.force_bytes(data)
        sk2 = AutoSymKey(key_iv_code=self.key_iv_code)
        self.assertEqual(data, sk2.decrypt(self.key.encrypt(data)))
        self.assertEqual(data, sk2.decrypt_hex(self.key.encrypt_hex(data)))
        self.assertEqual(data, sk2.decrypt_base64(self.key.encrypt_base64(data)))


class TestSym3DESKey(unittest.TestCase):
    def setUp(self):
        self.key = Sym3DESKey()
        self.key.new()
        self.key_iv_code = self.key.get_code()

    def test___init__(self):
        self.assertTrue(isinstance(self.key, Sym3DESKey))
        self.assertTrue(isinstance(self.key, SymKey))
        self.assertTrue(self.key.is_valid())
        (knm, ivn) = self.key.get()
        self.assertTrue(isinstance(knm, bytes))
        self.assertTrue(isinstance(ivn, bytes))
        nmm = self.key.get_code()
        self.assertTrue(len(nmm) > 12)
        self.assertEqual("des3", self.key.cypher_name)

    @unittest.skip("des3 decrypt throws exception, come back to this later")
    @hypothesis.given(st.text(alphabet=string.printable, min_size=1))
    def test_symmetric(self, data):
        data = defaults.force_bytes(data)
        sk2 = AutoSymKey(key_iv_code=self.key_iv_code)
        self.assertEqual(data, sk2.decrypt(self.key.encrypt(data)))
        self.assertEqual(data, sk2.decrypt_hex(self.key.encrypt_hex(data)))
        self.assertEqual(data, sk2.decrypt_base64(self.key.encrypt_base64(data)))


if __name__ == "__main__":
    OFL = "unittests-reports"
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=OFL))
