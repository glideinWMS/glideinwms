#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import string
import xmlrunner
import hypothesis
import hypothesis.strategies as st


# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.lib.encodingSupport import encode_data 
from glideinwms.lib.encodingSupport import decode_data 

encoding = ['b16', 'b32', 'b64']
data = """This is my data. There are many like it but this is mine.
"""
enc_16="54686973206973206D7920646174612E20546865726520617265206D616E79206C696B65206974206275742074686973206973206D696E652E0A"
enc_32="KRUGS4ZANFZSA3LZEBSGC5DBFYQFI2DFOJSSAYLSMUQG2YLOPEQGY2LLMUQGS5BAMJ2XIIDUNBUXGIDJOMQG22LOMUXAU==="
enc_64="VGhpcyBpcyBteSBkYXRhLiBUaGVyZSBhcmUgbWFueSBsaWtlIGl0IGJ1dCB0aGlzIGlzIG1pbmUuCg=="


class TestEncodeDecodeData(unittest.TestCase):

    def test_encode_data(self):
        self.assertEqual(enc_16, encode_data(data, encoding[0], url_safe=False))
        self.assertEqual(enc_32, encode_data(data, encoding[1], url_safe=False))
        self.assertEqual(enc_64, encode_data(data, encoding[2], url_safe=False))
        self.assertEqual(enc_16, encode_data(data, encoding[0], url_safe=True))
        self.assertEqual(enc_32, encode_data(data, encoding[1], url_safe=True))
        self.assertEqual(enc_64, encode_data(data, encoding[2], url_safe=True))

    def test_decode_data(self):
        self.assertEqual(data, decode_data(enc_16, encoding[0], url_safe=False))
        self.assertEqual(data, decode_data(enc_32, encoding[1], url_safe=False))
        self.assertEqual(data, decode_data(enc_64, encoding[2], url_safe=False))
        self.assertEqual(data, decode_data(enc_16, encoding[0], url_safe=True))
        self.assertEqual(data, decode_data(enc_32, encoding[1], url_safe=True))
        self.assertEqual(data, decode_data(enc_64, encoding[2], url_safe=True))

    @hypothesis.given(st.binary())
    def test_symmetric_binary(self, data):
        for enc in encoding:
            for tf in [ True, False ]:
                self.assertEqual(data, decode_data(encode_data(data, enc, url_safe=tf), enc, url_safe=tf))

    #@skip('doesnt work with unicode, should it?')
    @hypothesis.given(st.text(alphabet=string.printable))
    def test_symmetric_text(self, data):
        for enc in encoding:
            for tf in [ True, False ]:
                self.assertEqual(data, decode_data(encode_data(data, enc, url_safe=tf), enc, url_safe=tf))


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
