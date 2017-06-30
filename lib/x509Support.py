import sys
import M2Crypto

def extract_DN(fname):
    """
    Extract a Distinguished Name from an X.509 proxy.

    @type fname: string
    @param fname: Filename containing the X.509 proxy
    """

    fd = open(fname,"r")
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
            print "%s not a valid certificate file" % fname
            sys.exit(3)

        m = M2Crypto.X509.load_cert_string(data)
        if m.check_ca():
            # oops, this is the CA part
            # get the previous in the chain
            data = old_data
        else:
            break # ok, found it, end the loop

    return str(m.get_subject())
