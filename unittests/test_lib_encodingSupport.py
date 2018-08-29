#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/lib/encodingSupport.py

 Author:
   Dennis Box dbox@fnal.gov
"""


from __future__ import absolute_import
from __future__ import print_function
import string
import unittest2 as unittest
import xmlrunner
import hypothesis
import hypothesis.strategies as st


from glideinwms.lib.encodingSupport import encode_data
from glideinwms.lib.encodingSupport import decode_data

# define globally for convenience
ENCODING = ['b16', 'b32', 'b64']
DATA = """This is my data. There are many like it but this is mine.
"""
ENC_16 = "54686973206973206D7920646174612E20546865726520617265206D616E79206C696B65206974206275742074686973206973206D696E652E0A"
ENC_32 = "KRUGS4ZANFZSA3LZEBSGC5DBFYQFI2DFOJSSAYLSMUQG2YLOPEQGY2LLMUQGS5BAMJ2XIIDUNBUXGIDJOMQG22LOMUXAU==="
ENC_64 = "VGhpcyBpcyBteSBkYXRhLiBUaGVyZSBhcmUgbWFueSBsaWtlIGl0IGJ1dCB0aGlzIGlzIG1pbmUuCg=="


class TestEncodeDecodeData(unittest.TestCase):

    def test_encode_data(self):
        self.assertEqual(
            ENC_16,
            encode_data(
                DATA,
                ENCODING[0],
                url_safe=False))
        self.assertEqual(
            ENC_32,
            encode_data(
                DATA,
                ENCODING[1],
                url_safe=False))
        self.assertEqual(
            ENC_64,
            encode_data(
                DATA,
                ENCODING[2],
                url_safe=False))
        self.assertEqual(ENC_16, encode_data(DATA, ENCODING[0], url_safe=True))
        self.assertEqual(ENC_32, encode_data(DATA, ENCODING[1], url_safe=True))
        self.assertEqual(ENC_64, encode_data(DATA, ENCODING[2], url_safe=True))

    def test_decode_data(self):
        self.assertEqual(
            DATA,
            decode_data(
                ENC_16,
                ENCODING[0],
                url_safe=False))
        self.assertEqual(
            DATA,
            decode_data(
                ENC_32,
                ENCODING[1],
                url_safe=False))
        self.assertEqual(
            DATA,
            decode_data(
                ENC_64,
                ENCODING[2],
                url_safe=False))
        self.assertEqual(DATA, decode_data(ENC_16, ENCODING[0], url_safe=True))
        self.assertEqual(DATA, decode_data(ENC_32, ENCODING[1], url_safe=True))
        self.assertEqual(DATA, decode_data(ENC_64, ENCODING[2], url_safe=True))

    @hypothesis.given(st.binary())
    def test_symmetric_binary(self, data):
        for enc in ENCODING:
            for tf in [True, False]:
                self.assertEqual(
                    data,
                    decode_data(
                        encode_data(
                            data,
                            enc,
                            url_safe=tf),
                        enc,
                        url_safe=tf))

    # @skip('doesnt work with unicode, should it?')
    @hypothesis.given(st.text(alphabet=string.printable))
    def test_symmetric_text(self, data):
        for enc in ENCODING:
            for tf in [True, False]:
                self.assertEqual(
                    data,
                    decode_data(
                        encode_data(
                            data,
                            enc,
                            url_safe=tf),
                        enc,
                        url_safe=tf))


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
