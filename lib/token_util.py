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
from glideinwms.lib.subprocessSupport import iexe_cmd
from . import logSupport

"""
2/3 compatibility helpers
Inspired by http://python3porting.com/problems.html#nicer-solutions
"""

if sys.version_info[0] < 3:
    def byt(x):
        return x
else:
    import codecs
    def byt(x):
        return codecs.latin_1_encode(x)[0]

def un_byt(data):
    if not isinstance(data,str):
        data = data.decode()
    return data.strip()



def simple_scramble(data):
    """
    Undo the simple scramble of HTCondor - simply
    XOR with 0xdeadbeef

    Source: https://github.com/CoffeaTeam/jhub/blob/master/charts/coffea-casa-jhub/files/hub/auth.py#L196-L235
    """
    outb = byt('')
    deadbeef = [0xde, 0xad, 0xbe, 0xef]
    ldata = len(data)
    lbeef = len(deadbeef)
    for i in range(ldata):
        if sys.version_info[0] == 2:
            datum = struct.unpack('B',data[i])[0]
        else:
            datum = data[i]
        rslt = datum ^ deadbeef[i % lbeef]
        b1 = struct.pack('H',rslt)[0]
        outb += byt('%c'%b1)
    return outb

def derive_master_key(password):
    """
    derive an encryption/decryption key
    Parameters:
        @password: an unscrambled HTCondor password

    Source: https://github.com/CoffeaTeam/jhub/blob/master/charts/coffea-casa-jhub/files/hub/auth.py#L196-L235
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
    """
    Assemble and sign an idtoken
    Parameters:
        @identity:  who the token was generated for
        @issuer: idtoken issuer, typically HTCondor Collector
        @kid: Key ID
        @master_key: encryption key
        @duration: number of seconds IDTOKEN is valid. Default: infinity
        @scope: permissions IDTOKEN has. Default: everything
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
    encoded = jwt.encode(payload, master_key, algorithm='HS256', headers={'kid':kid})
    return encoded


def create_and_sign_token(pwd_file, issuer=None, identity=None, kid=None, duration=None, scope=None):
    """
    Create an HTCondor IDTOKEN
    
    Parameters:
        @pwd_file: file containing an HTCondor password
        @issuer: default is HTCondor Collector, $HOSTNAME:9618
        @identity: owner of IDTOKEN, default is $USERNAME@$HOSTNAME
        @kid:  Key id, hint of signature used.  Default is file name of passwordi
        @duration: number of seconds IDTOKEN is valid.  Default is infinity
        @scope: permissions IDTOKEN will have.  Default is everything,  
                other examples would be condor:/READ condor:/WRITE condor:/ADVERTISE_STARTD
    """
    if not kid:
        kid = os.path.basename(pwd_file)
    if not issuer:
        # split() has been added because condor is only considering the first part. Here is Brian B. comment:
        # "any comma, space, or tab character in the trust domain is treated as a separator.  Hence, for purpose of finding the token,
        # TRUST_DOMAIN=vocms0803.cern.ch:9618,cmssrv623.fnal.gov:9618
        # TRUST_DOMAIN=vocms0803.cern.ch:9618
        # TRUST_DOMAIN=vocms0803.cern.ch:9618,Some Random Text
        # are all considered the same - vocms0803.cern.ch:9618."

        issuer = iexe_cmd("condor_config_val TRUST_DOMAIN").strip().split(',')[0]
    if not identity:
        identity = "%s@%s" % (os.getlogin(), socket.gethostname())

    with open(pwd_file,'rb') as fd:
        data=fd.read()
    master_key = derive_master_key(simple_scramble(data))
    return sign_token(identity, issuer, kid, master_key, duration, scope)



# to test: need htcondor password file (for example el7_osg34)
# python token_util.py el7_osg34 $HOSTNAME:9618 vofrontend_service@$HOSTNAME

# will output condor IDTOKEN to stdout - use condor_ping to verify/validate
if __name__ == '__main__':
    kid = sys.argv[1]
    issuer = sys.argv[2]
    identity = sys.argv[3]
    with open(kid,'rb') as fd:
        data=fd.read()
    obfusicated = simple_scramble(data)
    master_key = derive_master_key(obfusicated)
    scope = "condor:/READ condor:/WRITE condor:/ADVERTISE_STARTD condor:/ADVERTISE_SCHEDD condor:/ADVERTISE_MASTER"
    idtoken = sign_token(identity, issuer, kid, master_key, scope=scope)
    print(un_byt(idtoken))
