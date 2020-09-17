
import sys
import M2Crypto
from . import defaults


def extract_DN(fname):
    """
    Extract a Distinguished Name from an X.509 proxy.

    @type fname: string
    @param fname: Filename containing the X.509 proxy
    """

    with open(fname, "r") as fd:
        data = fd.read()

    while True:
        try:
            data_idx = data.rindex('-----BEGIN CERTIFICATE-----')
            old_data = data[:data_idx]
            data = data[data_idx:]
        except ValueError:
            print("%s not a valid certificate file" % fname)
            sys.exit(3)

        m = M2Crypto.X509.load_cert_string(data)
        if m.check_ca():
            # oops, this is the CA part
            # get the previous in the chain
            data = old_data
        else:
            break  # ok, found it, end the loop

    # M2Crypto.X509.x509.get_subject() returns M2Crypto.X509.x509_Name, .__str__() returns bytes
    #return str(m.get_subject()).decode(defaults.BINARY_ENCODING_CRYPTO)
    #return m.get_subject().__str__().decode(defaults.BINARY_ENCODING_CRYPTO)
    # leaving it as it was even if the str() method is returning bytes according to the documentation
    return str(m.get_subject())
