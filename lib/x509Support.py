# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import sys

import M2Crypto

from . import defaults


def extract_DN(fname):
    """Extract a Distinguished Name from an X.509 proxy.

    Get the proxy subject: the subject of the first certificate
    starting form the bottom of the chain (PEM format)
    that is not a CA.
    This is necessary to skip the proxies at the beginning and
    get the subject of the user/server certificate.

    Args:
        fname(str): Filename containing the X.509 proxy

    Returns:
        bytes: Proxy subject in oneline format
    """

    with open(fname) as fd:
        data = fd.read()

    while True:
        try:
            data_idx = data.rindex("-----BEGIN CERTIFICATE-----")
            old_data = data[:data_idx]
            data = data[data_idx:]
        except ValueError:
            print("%s not a valid certificate file" % fname)
            sys.exit(3)

        # load certificate from AnyStr. Default format=FORMAT_PEM
        m = M2Crypto.X509.load_cert_string(data)
        if m.check_ca():
            # oops, this is the CA part
            # get the previous in the chain
            data = old_data
        else:
            break  # ok, found it, end the loop

    # M2Crypto.X509.x509.get_subject() returns M2Crypto.X509.x509_Name, .__str__() returns bytes
    # the str() method is returning bytes according to the source code:
    # https://github.com/mcepl/M2Crypto/blob/b8addc7ad9990d1ba3786830ebd74aa8c939849d/src/M2Crypto/X509.py#L343
    #     def __str__(self):
    #         """type here () -> bytes"""
    #         assert m2.x509_name_type_check(self.x509_name), \
    #             "'x509_name' type error"
    #         return m2.x509_name_oneline(self.x509_name)
    # Forcing to return str (unicode string)
    return defaults.force_str(str(m.get_subject()))
