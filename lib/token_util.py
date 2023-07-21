# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Project:
#   glideinWMS
#
# Description:
#   This is a collection of utility functions for HTCondor IDTOKEN generation


import codecs
import os
import re
import socket
import struct
import sys
import time
import uuid

import jwt

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from glideinwms.lib import defaults, logSupport
from glideinwms.lib.subprocessSupport import iexe_cmd


def token_file_expired(token_file):
    """
    Check validity of token exp and nbf claim.
    Do not check signature, audience, or other claims

    Args:
        token_file(Path or str): a filename containing a jwt (a text file w/ default encoding is expected)

    Returns:
        bool: True if exp in future or absent and nbf in past or absent,
              False otherwise
    """
    expired = True
    try:
        with open(token_file) as tf:
            token_str = tf.read()
        token_str = token_str.strip()
        return token_str_expired(token_str)
    except Exception as e:
        logSupport.log.exception("%s" % e)
    return expired


def token_str_expired(token_str):
    """
    Check validity of token exp and nbf claim.
    Do not check signature, audience, or other claims

    Args:
        token_str(str): string containing a jwt

    Returns:
        bool: True if exp in future or absent and nbf in past or absent,
              False otherwise
    """

    expired = True
    try:
        decoded = jwt.decode(
            token_str.strip(),
            options={"verify_signature": False, "verify_aud": False, "verify_exp": True, "verify_nbf": True},
        )
        expired = False
    except jwt.exceptions.ExpiredSignatureError as e:
        logSupport.log.error("Expired token: %s" % e)
    except Exception as e:
        logSupport.log.exception("Unknown exception decoding token: %s" % e)
        logSupport.log.debug(f"Faulty token: {token_str}")
    return expired


def simple_scramble(in_buf):
    """Undo the simple scramble of HTCondor

    simply XOR with 0xdeadbeef
    Source: https://github.com/CoffeaTeam/coffea-casa/blob/master/charts/coffea-casa/files/hub-extra/auth.py

    Args:
        data(bytearray): binary string to be unscrambled

    Returns:
        bytearray: an HTCondor scrambled binary string
    """
    DEADBEEF = (0xDE, 0xAD, 0xBE, 0xEF)
    out_buf = b""
    for idx in range(len(in_buf)):
        scramble = in_buf[idx] ^ DEADBEEF[idx % 4]  # 4 = len(DEADBEEF)
        out_buf += b"%c" % scramble
    return out_buf


def derive_master_key(password):
    """Derive an encryption/decryption key

    Source: https://github.com/CoffeaTeam/coffea-casa/blob/master/charts/coffea-casa/files/hub-extra/auth.py

    Args:
        password(bytes): an unscrambled HTCondor password (bytes-like: bytes, bytearray, memoryview)

    Returns:
       bytes: an HTCondor encryption/decryption key
    """

    # Key length, salt, and info are fixed as part of the protocol
    # Here the types and meaning from cryptography.hazmat.primitives.kdf.hkdf:
    # HKDF.__init__
    #   Aalgorithm – An instance of HashAlgorithm.
    #   length(int) – key length in bytes
    #   salt(bytes) – To randomize
    #   info(bytes) – Application data
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"htcondor",
        info=b"master jwt",
        backend=default_backend(),
    )
    # HKDF.derive() requires bytes and returns bytes
    return hkdf.derive(password)


def sign_token(identity, issuer, kid, master_key, duration=None, scope=None):
    """Assemble and sign an idtoken

    Args:
        identity(str): who the token was generated for
        issuer(str): idtoken issuer, typically HTCondor Collector
        kid(str): Key ID
        master_key(bytes): encryption key
        duration(int, optional): number of seconds IDTOKEN is valid. Default: infinity
        scope(str, optional): permissions IDTOKEN has. Default: everything

    Returns:
       str: a signed IDTOKEN (jwt token)
    """

    iat = int(time.time())
    payload = {
        "sub": identity,
        "iat": iat,
        "nbf": iat,
        "jti": uuid.uuid4().hex,
        "iss": issuer,
    }
    if duration:
        exp = iat + duration
        payload["exp"] = exp
    if scope:
        payload["scope"] = scope
    # master_key should be `bytes`. `str` could cause value changes if was decoded not using utf-8.
    # The manual (https://pyjwt.readthedocs.io/en/stable/api.html) is incorrect to list `str` only.
    # The source code (https://github.com/jpadilla/pyjwt/blob/72ad55f6d7041ae698dc0790a690804118be50fc/jwt/api_jws.py)
    # shows `AllowedPrivateKeys | str | bytes` and if it is str, then it is encoded w/ utf-8:  value.encode("utf-8")
    encoded = jwt.encode(payload, master_key, algorithm="HS256", headers={"kid": kid})
    return encoded


def create_and_sign_token(pwd_file, issuer=None, identity=None, kid=None, duration=None, scope=None):
    """Create an HTCSS IDTOKEN

    This should be compatible with the HTCSS code to create tokens.

    Args:
        pwd_file: (str) file containing an HTCondor password
        issuer: (str, optional) default is HTCondor TRUST_DOMAIN
        identity: (str, optional) identity claim, default is $USERNAME@$HOSTNAME
        kid:  (str, optional) Key id, hint of signature used.
                              Default is file name of password
        duration: (int, optional) number of seconds IDTOKEN is valid.
                                  Default is infinity
        scope: (str, optional) permissions IDTOKEN will have.
                               Default is everything,
                    example: condor:/READ condor:/WRITE condor:/ADVERTISE_STARTD

    Returns:
        str: a signed HTCondor IDTOKEN
    """
    if not kid:
        kid = os.path.basename(pwd_file)
    if not issuer:
        # As of Oct 2022
        # TRUST_DOMAIN is an opaque string to be taken as it is (Brian B.), but for tokens only the first collector
        # is considered in the TRUST_DOMAIN (TJ, generate_token HTCSS code):
        # 	std::string issuer;
        # 	if (!param(issuer, "TRUST_DOMAIN")) {
        # 		if (err) err->push("PASSWD", 1, "Issuer namespace is not set");
        # 		return false;
        # 	}
        # 	issuer = issuer.substr(0, issuer.find_first_of(", \t"));
        # And Brian B. comment: "any comma, space, or tab character in the trust domain is treated as a separator.
        # Hence, for purpose of finding the token,
        # TRUST_DOMAIN=vocms0803.cern.ch:9618,cmssrv623.fnal.gov:9618
        # TRUST_DOMAIN=vocms0803.cern.ch:9618
        # TRUST_DOMAIN=vocms0803.cern.ch:9618,Some Random Text
        # are all considered the same - vocms0803.cern.ch:9618."
        full_issuer = iexe_cmd("condor_config_val TRUST_DOMAIN").strip()  # Remove trailing spaces and newline
        if not full_issuer:
            logSupport.log.warning(
                "Unable to retrieve TRUST_DOMAIN and no issuer provided: token will have empty 'iss'"
            )
        else:
            # To set the issuer TRUST_DOMAIN is split no matter whether coming from COLLECTOR_HOST or not
            # Using the same splitting as creation/web_base/setup_x509.sh
            # is_default_trust_domain = "# at: <Default>" in iexe_cmd("condor_config_val -v TRUST_DOMAIN")
            split_issuers = re.split(" |,|\t", full_issuer)  # get only the first collector
            # re.split(r":|\?", split_issuers[0]) would remove also synful string and port (to have the same tring for secondary collectors, but not needed)
            issuer = split_issuers[0]
    if not identity:
        identity = f"{os.getlogin()}@{socket.gethostname()}"
    with open(pwd_file, "rb") as fd:
        data = fd.read()
    password = simple_scramble(data)
    # The POOL password requires a special handling
    # Done in https://github.com/CoffeaTeam/coffea-casa/blob/master/charts/coffea-casa/files/hub-extra/auth.py#L252
    if kid == "POOL":
        password += password
    master_key = derive_master_key(password)
    return sign_token(identity, issuer, kid, master_key, duration, scope)


# To test you need htcondor password file
# python3 token_util.py <condor_password_file_path> $HOSTNAME:9618 vofrontend_service@$HOSTNAME
# will output condor IDTOKEN to stdout - use condor_ping to the server to verify/validate
if __name__ == "__main__":
    kid = sys.argv[1]
    issuer = sys.argv[2]
    identity = sys.argv[3]
    with open(kid, "rb") as fd:
        data = fd.read()
    obfusicated = simple_scramble(data)
    master_key = derive_master_key(obfusicated)
    scope = "condor:/READ condor:/WRITE condor:/ADVERTISE_STARTD condor:/ADVERTISE_SCHEDD condor:/ADVERTISE_MASTER"
    idtoken = sign_token(identity, issuer, kid, master_key, scope=scope)
    # idtoken is str
    print(idtoken)
