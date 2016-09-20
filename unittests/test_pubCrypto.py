#!/usr/bin/env python
import unittest2 as unittest
import xmlrunner
from unittest_utils import runTest

from glideinwms.lib import pubCrypto


class TestPubCrypto(unittest.TestCase):
    """
    Test the pubCrypto module 
    """
    def setUp(self):
        """
        Create the reference string and necessary RSA key objects
        """

        self.reference_string = "This is just a simple reference string"
        self.key_length = 1024
        self.private_key = pubCrypto.RSAKey()
        self.private_key.new(self.key_length)
        self.public_key = self.private_key.PubRSAKey()


    def test_encryptDecrypt_rsa(self):
        """
        1. Encrypt the reference string using public RSA key
        2. Check to ensure that the encoded string does not match the
           reference string (i.e. that it has actually been encrypted)
           Fail if strings match
        3. Decrypt the string using the private RSA key
        4. Compare decrypted string with the reference string
           Fail if strings do not match
        """

        encrypted_string = self.public_key.encrypt(self.reference_string)
        msg = "(RSA) Reference string was not encrypted"
        self.assertNotEqual(encrypted_string, self.reference_string, msg)

        decrypted_string = self.private_key.decrypt(encrypted_string)
        msg = "(RSA) Decrypted content does not match reference"
        self.assertEqual(decrypted_string, self.reference_string, msg)


    def test_encryptDecrypt_b64(self):
        """
        Same tests as in test_encryptDecrypt_rsa but with base64 encoding
        """

        encrypted_string = self.public_key.encrypt_base64(self.reference_string)
        msg = "(RSA - B64) Reference string was not encrypted"
        self.assertNotEqual(encrypted_string, self.reference_string, msg)

        decrypted_string = self.private_key.decrypt_base64(encrypted_string)
        msg = "(RSA - B64) Decrypted content does not match reference"
        self.assertEqual(decrypted_string, self.reference_string, msg)


    def test_encryptDecrypt_hex(self):
        """
        Same tests as in test_encryptDecrypt_rsa but with hex encoding
        """

        encrypted_string = self.public_key.encrypt_hex(self.reference_string)
        msg = "(RSA - HEX) Reference string was not encrypted"
        self.assertNotEqual(encrypted_string, self.reference_string, msg)

        decrypted_string = self.private_key.decrypt_hex(encrypted_string)
        msg = "(RSA - HEX) Decrypted content does not match reference"
        self.assertEqual(decrypted_string, self.reference_string, msg)


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))

