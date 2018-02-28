#!/usr/bin/env python

#
# Description:
#  This file is specialized in updating a proxy file
#   in privsep mode
#
# All information is passed via the environment;
#  so it has no arguments
#
# Env variables used:
#  HEXDATA - b2a_hex(proxy_data)
#  FNAME   - file name to update
#
# The python-related environment variables must also
#  be properly set
#  PATH, LD_LIBRARY_PATH, PYTHON_PATH
#
# Author:
#  Igor Sfiligoi (Mar 18th, 2010) @UCSD
#

import os
import sys
import binascii
import gzip
import cStringIO
import traceback
import base64
import shutil

class ProxyEnvironmentError(Exception): pass
class CompressionError(Exception): pass

def compress_credential(credential_data):
    try:
        cfile = cStringIO.StringIO()
        f = gzip.GzipFile(fileobj=cfile, mode='wb')
        f.write(credential_data)
        f.close()
        return base64.b64encode(cfile.getvalue())
    except:
        tb = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        msg = "Error compressing credential: \n%s" % tb
        raise CompressionError(msg)

def update_credential(fname, credential_data):
    if not os.path.isfile(fname):
        # new file, create
        fd = os.open(fname, os.O_CREAT|os.O_WRONLY, 0o600)
        try:
            os.write(fd, credential_data)
        finally:
            os.close(fd)
    else:
        # old file exists, check if same content
        fl = open(fname, 'r')
        try:
            old_data = fl.read()
        finally:
            fl.close()

        #  if proxy_data == old_data nothing changed, done else
        if not (credential_data == old_data):
            # proxy changed, neeed to update
            # remove any previous backup file, if it exists
            try:
                os.remove(fname + ".old")
            except:
                pass # just protect

            # create new file
            fd = os.open(fname + ".new", os.O_CREAT|os.O_WRONLY, 0o600)
            try:
                os.write(fd, credential_data)
            finally:
                os.close(fd)

            # copy the old file to a tmp and rename new one to the official name
            try:
                shutil.copy2(fname, fname + ".old")
            except:
                pass # just protect

            os.rename(fname + ".new", fname)

def get_env():
    # Extract data from environment
    # Arguments not used
    if 'HEXDATA' not in os.environ:
        raise ProxyEnvironmentError('HEXDATA env variable not defined.')

    if 'FNAME' not in os.environ:
        raise ProxyEnvironmentError('FNAME env variable not defined.')

    credential_data = binascii.a2b_hex(os.environ['HEXDATA'])
    fname = os.environ['FNAME']

    if 'FNAME_COMPRESSED' in os.environ:
        fname_compressed = os.environ['FNAME_COMPRESSED']
    else:
        fname_compressed = None

    return credential_data, fname, fname_compressed

def main():
    update_code = 0
    try:
        credential_data, fname, fname_compressed = get_env()
        update_credential(fname, credential_data)
        if fname_compressed:
            compressed_credential = compress_credential(credential_data)
            update_credential(fname_compressed, compressed_credential)
    except ProxyEnvironmentError as ex:
        sys.stderr.write(str(ex))
        update_code = 2
    except Exception as ex:
        sys.stderr.write(str(ex))
        update_code = 4

    return update_code

if __name__ == "__main__":
    sys.exit(main())

