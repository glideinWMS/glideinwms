from __future__ import print_function
import sys
import os
import M2Crypto

def extract_DN(fname):
    """
    Extract a Distinguished Name from an X.509 proxy.

    @type fname: string
    @param fname: Filename containing the X.509 proxy
    """

    fd = open(fname, "r")
    try:
        data = fd.read()
    finally:
        fd.close()

    while True:
        try:
            data_idx = data.rindex('-----BEGIN CERTIFICATE-----')
            old_data = data[:data_idx]
            data = data[data_idx:]
        except ValueError:
            # need to return without exiting to be able to store condor_tokens
            # and SciTokens in  <credentials > in frontend.xml
            print("%s not a valid certificate file, using filename as DN" % fname)
            return str(os.path.basename(fname))

        m = M2Crypto.X509.load_cert_string(data)
        if m.check_ca():
            # oops, this is the CA part
            # get the previous in the chain
            data = old_data
        else:
            break # ok, found it, end the loop

    return str(m.get_subject())
