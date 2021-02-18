#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This is a collection of utility functions for HTCondor IDTOKEN generation
#
# Author:
#   Dennis Box (credit given in comments where source borrowed)
#
import os
import socket
import time
import uuid
import struct
import sys
import jwt

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

"""
2/3 compatibility helpers
Inspired by http://python3porting.com/problems.html#nicer-solutions

byt(): encode a byte into (byte str) for python2 or 3
un_byt(): decode a (byte str) into string for python2 or 3
"""

if sys.version_info[0] < 3:
    def byt(x):
        return x
else:
    import codecs

    def byt(x):
        return codecs.latin_1_encode(x)[0]


def un_byt(data):
    if not isinstance(data, str):
        data = data.decode()
    return data.strip()


def simple_scramble(data):
    """Undo the simple scramble of HTCondor

       The scrambled password has been XOR'ed  with 0xdeadbeef
       to prevent it from being easily readable if it accidentally
       gets printed out.
       NB if an unscrambled password is passed in you get the scrambled
       one back out.
       Source: https://github.com/CoffeaTeam/jhub/blob/master/charts/coffea-casa-jhub/files/hub/auth.py#L196-L235

       Args:
          data: (byte string) an HTCondor password of the type found in
                /etc/condor/passwords.d
       Returns:
          (byte string) containing the unscrambled password.

    """
    outb = byt('')
    deadbeef = [0xde, 0xad, 0xbe, 0xef]
    ldata = len(data)
    lbeef = len(deadbeef)
    for i in range(ldata):
        if sys.version_info[0] == 2:
            datum = struct.unpack('B', data[i])[0]
        else:
            datum = data[i]
        rslt = datum ^ deadbeef[i % lbeef]
        b1 = struct.pack('H', rslt)[0]
        outb += byt('%c' % b1)
    return outb


def derive_master_key(password):
    """Derive an HTCondor encryption/decryption master key
       Source: https://github.com/CoffeaTeam/jhub/blob/master/charts/coffea-casa-jhub/files/hub/auth.py#L196-L235

        Args:
            password (byte str): an unscrambled HTCondor password

        Returns:
            (byte str):  master key for HTCondor IDToken generation
    """

    # Key length, salt, and info fixed as part of protocol
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=byt("htcondor"),
        info=byt("master jwt"),
        backend=default_backend())
    return hkdf.derive(password)


def sign_token(identity, issuer, kid, master_key, duration=None, scope=None):
    """Assemble and sign an idtoken

       Args:
           identity (str):  who the token was generated for
           issuer (str): idtoken issuer, typically HTCondor Collector and port, i.e collector.fnal.gov:9618
           kid (str): Key ID
           master_key (byte str): encryption key
           duration (int): number of seconds IDTOKEN is valid. Default: infinity
           scope (str): permissions IDTOKEN has. Default: everything

       Returns:
           str: an HTCondor IDToken in jwt format
    """

    iat = int(time.time())

    payload = {'sub': identity,
               'iat': iat,
               'nbf': iat,
               'jti': uuid.uuid4().hex,
               'iss': issuer,
               }
    if duration:
        exp = iat + duration
        payload['exp'] = exp
    if scope:
        payload['scope'] = scope
    encoded = jwt.encode(
        payload,
        master_key,
        algorithm='HS256',
        headers={
            'kid': kid})
    return un_byt(encoded)


def create_and_sign_token(pwd_file, issuer=None,
                          identity=None, kid=None, duration=None, scope=None):
    """ Create an HTCondor IDTOKEN

        A wrapper function for sign_token with helpful defaults

        Args:
            pwd_file (str): name of file containing an HTCondor password
            issuer (str): default is HTCondor Collector, $HOSTNAME:9618
            identity (str): claimed identity ofIDTOKEN, default is $USERNAME@$HOSTNAME
            kid (str):  Key id, hint of signature used.  Default is pwd_file
            duration (int): number of seconds IDTOKEN is valid.  Default is infinity
            scope (str): permissions IDTOKEN will have.  Default is everything,
                         another example would be
                         condor:/READ condor:/WRITE condor:/ADVERTISE_STARTD

        Returns:
            str: an HTCondor IDToken in jwt format
    """
    if not kid:
        kid = os.path.basename(pwd_file)
    if not issuer:
        issuer = "%s:9618" % socket.gethostname()
    if not identity:
        identity = "%s@%s" % (os.getlogin(), socket.gethostname())

    with open(pwd_file, 'rb') as fd:
        data = fd.read()
    master_key = derive_master_key(simple_scramble(data))
    return sign_token(identity, issuer, kid, master_key, duration, scope)


NO_FILE = 0

def age_of(file_name):
    """age of file

       useful for testing when tokens need refreshing

       Args:
           file_name(str):  name of file

       Returns:
           seconds since last modified time of file in secods if file exists
           0 if file does not exist
    """

    if os.path.exists(file_name):
        age = time.time() - os.stat(file_name).st_mtime
    else:
        age = NO_FILE
    return age


# to test: need htcondor password file (example: /etc/condor/passwords.d/el7_osg34 )
# python token_util.py /etc/condor/passwords.d/el7_osg34 $HOSTNAME:9618 vofrontend_service@$HOSTNAME
# will output condor IDTOKEN to stdout - use condor_ping to verify/validate
if __name__ == '__main__':
    kid = os.path.basename(sys.argv[1])
    issuer = sys.argv[2]
    identity = sys.argv[3]
    with open(sys.argv[1], 'rb') as fd:
        data = fd.read()
    obfusicated = simple_scramble(data)
    master_key = derive_master_key(obfusicated)
    scope = "condor:/READ condor:/WRITE condor:/ADVERTISE_STARTD condor:/ADVERTISE_SCHEDD condor:/ADVERTISE_MASTER"
    idtoken = sign_token(identity, issuer, kid, master_key, scope=scope)
    print(idtoken)
