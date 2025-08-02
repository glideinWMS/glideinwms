#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This file is specialized in updating a proxy file

All information is passed via the environment;
  so it has no arguments

Env variables used:
  HEXDATA - b2a_hex(proxy_data)
  FNAME   - file name to update

The python-related environment variables must also
  be properly set
  PATH, LD_LIBRARY_PATH, PYTHON_PATH
"""

import base64
import binascii
import gzip
import io
import os
import shutil
import sys
import traceback


class ProxyEnvironmentError(Exception):
    pass


class CompressionError(Exception):
    pass


def compress_credential(credential_data):
    try:
        cfile = io.StringIO()
        f = gzip.GzipFile(fileobj=cfile, mode="wb")
        f.write(credential_data)
        f.close()
        return base64.b64encode(cfile.getvalue())
    except Exception:
        tb = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        msg = "Error compressing credential: \n%s" % tb
        raise CompressionError(msg)


def update_credential(fname, credential_data):
    if not os.path.isfile(fname):
        # new file, create
        fd = os.open(fname, os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(fd, credential_data)
        finally:
            os.close(fd)
    else:
        # old file exists, check if same content
        with open(fname) as fl:
            old_data = fl.read()

        #  if proxy_data == old_data nothing changed, done else
        if not (credential_data == old_data):
            # proxy changed, need to update
            # remove any previous backup file, if it exists
            try:
                os.remove(fname + ".old")
            except Exception:
                pass  # just protect

            # create new file
            fd = os.open(fname + ".new", os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                os.write(fd, credential_data)
            finally:
                os.close(fd)

            # copy the old file to a tmp and rename new one to the official name
            try:
                shutil.copy2(fname, fname + ".old")
            except Exception:
                pass  # just protect

            os.rename(fname + ".new", fname)


def get_env():
    # Extract data from environment
    # Arguments not used
    if "HEXDATA" not in os.environ:
        raise ProxyEnvironmentError("HEXDATA env variable not defined.")

    if "FNAME" not in os.environ:
        raise ProxyEnvironmentError("FNAME env variable not defined.")

    credential_data = binascii.a2b_hex(os.environ["HEXDATA"])
    fname = os.environ["FNAME"]

    if "FNAME_COMPRESSED" in os.environ:
        fname_compressed = os.environ["FNAME_COMPRESSED"]
    else:
        fname_compressed = None

    if "IDTOKENS_FILE" in os.environ:
        idtokens_file = os.environ["IDTOKENS_FILE"]
    else:
        idtokens_file = None

    return credential_data, fname, fname_compressed, idtokens_file


def main():
    update_code = 0
    try:
        credential_data, fname, fname_compressed, idtokens_file = get_env()
        update_credential(fname, credential_data)
        if fname_compressed:
            idtoken_data = ""
            if idtokens_file:
                with open(idtokens_file) as idtf:
                    for line in idtf.readlines():
                        idtoken_data += line
            compressed_credential = compress_credential(credential_data)
            update_credential(fname_compressed, f"{idtoken_data}####glidein_credentials={compressed_credential}")
            # in branch_v3_2 after migration_3_1 WAS: update_credential(fname_compressed, compressed_credential)
    except ProxyEnvironmentError as ex:
        sys.stderr.write(str(ex))
        update_code = 2
    except Exception as ex:
        sys.stderr.write(str(ex))
        update_code = 4

    return update_code


if __name__ == "__main__":
    sys.exit(main())
