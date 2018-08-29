#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/lib/encodingSupport.py

 Author:
   tiradani <tiradani>
"""


from __future__ import absolute_import
import tempfile
import unittest2 as unittest
import xmlrunner


from glideinwms.lib import encodingSupport


class TestEncodingSupport(unittest.TestCase):
    """
    Test the encoding support module by encoding a reference string, decoding
    the encoded output and comparing the decoded string with the reference string
    """

    def setUp(self):
        """
        Create the reference string - quote from http://www.lipsum.com/

        Translation: "There is no one who loves pain itself, who seeks after it
                      and wants to have it, simply because it is pain..."
        """
        self.reference_string = "Neque porro quisquam est qui dolorem ipsum "\
                                "quia dolor sit amet, consectetur, adipisci "\
                                "velit..."

    def test_encodeDecode_b64(self):
        """
        1. Encode the reference string using base 64 encoding.
        2. Check to ensure that the encoded string does not match the reference
           string (i.e. that it has actually been encoded).  Fail if strings match.
        3. Decode the string using base 64 encoding
        4. Compare decoded string with the reference string.  Fail if strings
           do not match.

        Do this with url_safe = True once and once with url_safe = False
        """
        encoded_string = encodingSupport.encode_data(self.reference_string,
                                                     encoding="b64", url_safe=True)
        msg = "(B64 - url_safe == True) Reference string was not encoded."
        self.assertNotEqual(encoded_string, self.reference_string, msg)

        decoded_string = encodingSupport.decode_data(encoded_string,
                                                     encoding="b64", url_safe=True)
        msg = "(B64 - url_safe == True) Decoded string does not match reference string"
        self.assertEqual(decoded_string, self.reference_string, msg)

        encoded_string = encodingSupport.encode_data(self.reference_string,
                                                     encoding="b64", url_safe=False)
        msg = "(B64 - url_safe == False) Reference string was not encoded."
        self.assertNotEqual(encoded_string, self.reference_string, msg)

        decoded_string = encodingSupport.decode_data(encoded_string,
                                                     encoding="b64", url_safe=False)
        msg = "(B64 - url_safe == False) Decoded string does not match reference string"
        self.assertEqual(decoded_string, self.reference_string, msg)

    def test_encodeDecode_b32(self):
        """
        1. Encode the reference string using base 32 encoding.
        2. Check to ensure that the encoded string does not match the reference
           string (i.e. that it has actually been encoded).  Fail if strings match.
        3. Decode the string using base 32 encoding
        4. Compare decoded string with the reference string.  Fail if strings
           do not match.
        """
        encoded_string = encodingSupport.encode_data(self.reference_string,
                                                     encoding="b32")
        msg = "(B32) Reference string was not encoded."
        self.assertNotEqual(encoded_string, self.reference_string, msg)

        decoded_string = encodingSupport.decode_data(
            encoded_string, encoding="b32")
        msg = "(B32) Decoded string does not match reference string"
        self.assertEqual(decoded_string, self.reference_string, msg)

    def test_encodeDecode_b16(self):
        """
        1. Encode the reference string using base 16 encoding.
        2. Check to ensure that the encoded string does not match the reference
           string (i.e. that it has actually been encoded).  Fail if strings match.
        3. Decode the string using base 16 encoding
        4. Compare decoded string with the reference string.  Fail if strings
           do not match.
        """
        encoded_string = encodingSupport.encode_data(self.reference_string,
                                                     encoding="b16")
        msg = "(B16) Reference string was not encoded."
        self.assertNotEqual(encoded_string, self.reference_string, msg)

        decoded_string = encodingSupport.decode_data(
            encoded_string, encoding="b16")
        msg = "(B16) Decoded string does not match reference string"
        self.assertEqual(decoded_string, self.reference_string, msg)

    def test_encodeException(self):
        """
        Pass an invalid option to the encode function to ensure that an exception
        is raised.
        """
        kwds = {"encoding": "b21", "url_safe": True}
        args = (self.reference_string,)
        self.assertRaises(encodingSupport.EncodingTypeError,
                          encodingSupport.encode_data, *args, **kwds)

    def test_decodeException(self):
        """
        Pass an invalid option to the decode function to ensure that an exception
        is raised.
        """
        kwds = {"encoding": "b21", "url_safe": True}
        args = (self.reference_string,)
        self.assertRaises(encodingSupport.EncodingTypeError,
                          encodingSupport.decode_data, *args, **kwds)


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
