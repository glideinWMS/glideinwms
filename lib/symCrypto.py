# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""symCrypto - This module defines classes to perform symmetric key cryptography (shared or hidden key)

It uses M2Crypto: https://github.com/mcepl/M2Crypto
a wrapper around OpenSSL: https://www.openssl.org/docs/man1.1.1/man3/

NOTE For convenience and consistency w/ previous versions of this module, Encryption/Signing functions
    (b64, hex and .encrypt() ) accept bytes-like objects (bytes, bytearray) and also Unicode strings
    utf-8 encoded (defaults.BINARY_ENCODING_CRYPTO).
    B64 and hex Decryption functions, consistent w/ Python's binascii.a2b_* functions, accept bytes and
    Unicode strings containing only ASCII characters, .decrypt() only accepts bytes-like objects (such as bytes,
    bytearray and other objects that support the buffer protocol).
    All these functions return bytes.

    Key definitions accept AnyStr (str, bytes, bytearray), key_str are iv_str bytes, key_iv_code is a str,
    so is the key

"""

import binascii

import M2Crypto.BIO
import M2Crypto.Rand

from . import defaults

######################
#
# Available ciphers:
#  too many to list them all
#     try 'man enc'
#  a few of them are
#   'aes_128_cbc'
#   'aes_128_ofb
#   'aes_256_cbc'
#   'aes_256_cfb'
#   'bf_cbc'
#   'des3'
#
######################


class SymKey:
    """Symmetric keys cryptography

    You probably don't want to use this, use the child classes instead

    self.key_str and self.iv_str are bytes (strings) with HEX encoded data

    Available ciphers, too many to list them all, try `man enc`, a few of them are:
        'aes_128_cbc'
        'aes_128_ofb
        'aes_256_cbc'
        'aes_256_cfb'
        'bf_cbc'
        'des3'
    """

    def __init__(self, cypher_name, key_len, iv_len, key_str=None, iv_str=None, key_iv_code=None):
        """Constructor

        Args:
            cypher_name:
            key_len:
            iv_len:
            key_str:
            iv_str:
            key_iv_code:
        """
        self.cypher_name = cypher_name
        self.key_len = key_len
        self.iv_len = iv_len
        self.key_str = None
        self.iv_str = None
        self.ket_str = None
        self.load(key_str, iv_str, key_iv_code)
        return

    ###########################################
    # load a new key
    def load(self, key_str=None, iv_str=None, key_iv_code=None):
        """Load a new key from text (str/bytes)

        Args:
            key_str (str/bytes): string w/ base64 encoded key
                Must be bytes-like object or ASCII string, like base64 inputs
            iv_str (str/bytes): initialization vector
            key_iv_code (str/bytes): comma separated text with cypher, key, iv

        Returns:

        """
        if key_str is not None:
            if key_iv_code is not None:
                raise ValueError("Illegal to define both key_str and key_iv_code")
            # just in case it was unicode"
            key_str = defaults.force_bytes(key_str)
            if len(key_str) != (self.key_len * 2):
                raise ValueError("Key must be exactly %i long, got %i" % (self.key_len * 2, len(key_str)))

            if iv_str is None:
                # if key_str defined, one needs the iv_str, too
                # set to default of 0
                iv_str = b"0" * (self.iv_len * 2)
            else:
                if len(iv_str) != (self.iv_len * 2):
                    raise ValueError(
                        "Initialization vector must be exactly %i long, got %i" % (self.iv_len * 2, len(iv_str))
                    )
                # just in case it was unicode"
                iv_str = defaults.force_bytes(iv_str)
        elif key_iv_code is not None:
            # just in case it was unicode"
            key_iv_code = defaults.force_bytes(key_iv_code)
            ki_arr = key_iv_code.split(b",")
            if len(ki_arr) != 3:
                raise ValueError("Invalid format, commas not found")
            if ki_arr[0] != (b"cypher:%b" % self.cypher_name.encode(defaults.BINARY_ENCODING_CRYPTO)):
                raise ValueError("Invalid format, not my cypher(%s)" % self.cypher_name)
            if ki_arr[1][:4] != b"key:":
                raise ValueError("Invalid format, key not found")
            if ki_arr[2][:3] != b"iv:":
                raise ValueError("Invalid format, iv not found")
            # call itself, but with key and iv decoded, to run the checks on key and iv
            return self.load(key_str=ki_arr[1][4:], iv_str=ki_arr[2][3:])
        # else keep None

        self.key_str = key_str
        self.iv_str = iv_str

    def is_valid(self):
        """Return true if the key is valid

        Returns:
            bool: True if the key string is not None

        """
        return self.key_str is not None

    def get(self):
        """Get the key and initialization vector

        Returns:
            tuple: (key, iv) tuple wehere both key and iv are bytes

        """
        return (self.key_str, self.iv_str)

    def get_code(self):
        """Return the key code: cypher, key, iv, as a comma separated string

        Returns:
            str: key description in the string

        """
        return "cypher:{},key:{},iv:{}".format(
            self.cypher_name,
            self.key_str.decode(defaults.BINARY_ENCODING_CRYPTO),
            self.iv_str.decode(defaults.BINARY_ENCODING_CRYPTO),
        )

    def new(self, random_iv=True):
        """Generate a new key

        Set self.key_str and self.iv_str

        Args:
            random_iv (bool): if False, set iv to 0
        """
        self.key_str = binascii.b2a_hex(M2Crypto.Rand.rand_bytes(self.key_len))
        if random_iv:
            self.iv_str = binascii.b2a_hex(M2Crypto.Rand.rand_bytes(self.iv_len))
        else:
            self.iv_str = b"0" * (self.iv_len * 2)
        return

    def encrypt(self, data):
        """Encrypt data inline

        Args:
            data (AnyStr): data to encrypt

        Returns:
            bytes: encrypted data

        Raises:
            KeyError: if there is no valid crypto key
        """
        if not self.is_valid():
            raise KeyError("No key")
        bdata = defaults.force_bytes(data)
        b = M2Crypto.BIO.MemoryBuffer()
        c = M2Crypto.BIO.CipherStream(b)
        c.set_cipher(self.cypher_name, binascii.a2b_hex(self.key_str), binascii.a2b_hex(self.iv_str), 1)
        c.write(bdata)
        c.flush()
        c.close()
        e = b.read()
        return e

    def encrypt_base64(self, data):
        """like encrypt, but the result is base64 encoded"""
        return binascii.b2a_base64(self.encrypt(data))

    def encrypt_hex(self, data):
        """like encrypt, but the result is hex encoded"""
        return binascii.b2a_hex(self.encrypt(data))

    def decrypt(self, data):
        """Decrypt data inline

        Args:
            data (bytes): data to decrypt

        Returns:
            bytes: decrypted data

        Raises:
            KeyError: if there is no valid crypto key
        """
        if not self.is_valid():
            raise KeyError("No key")
        b = M2Crypto.BIO.MemoryBuffer()
        c = M2Crypto.BIO.CipherStream(b)
        c.set_cipher(self.cypher_name, binascii.a2b_hex(self.key_str), binascii.a2b_hex(self.iv_str), 0)
        c.write(data)
        c.flush()
        c.close()
        d = b.read()
        return d

    def decrypt_base64(self, data):
        """like decrypt, but the input is base64 encoded

        Args:
            data (AnyStrASCII): Base64 input data. bytes or ASCII encoded Unicode str

        Returns:
            bytes: decrypted data
        """
        return self.decrypt(binascii.a2b_base64(data))

    def decrypt_hex(self, data):
        """like decrypt, but the input is hex encoded

        Args:
            data (AnyStrASCII): HEX input data. bytes or ASCII encoded Unicode str

        Returns:
            bytes: decrypted data
        """
        return self.decrypt(binascii.a2b_hex(data))


class MutableSymKey(SymKey):
    """SymKey class, allows to change the crypto after instantiation"""

    def __init__(self, cypher_name=None, key_len=None, iv_len=None, key_str=None, iv_str=None, key_iv_code=None):
        self.redefine(cypher_name, key_len, iv_len, key_str, iv_str, key_iv_code)

    def redefine(self, cypher_name=None, key_len=None, iv_len=None, key_str=None, iv_str=None, key_iv_code=None):
        """Load a new crypto type and a new key

        Args:
            cypher_name:
            key_len:
            iv_len:
            key_str:
            iv_str:
            key_iv_code:

        Returns:

        """
        self.cypher_name = cypher_name
        self.key_len = key_len
        self.iv_len = iv_len
        self.load(key_str, iv_str, key_iv_code)
        return

    def is_valid(self):
        """Return true if the key is valid.

        Redefine, as null crypto name could be used in this class

        Returns:
             bool: True if both the key string and cypher name are not None

        """
        return (self.key_str is not None) and (self.cypher_name is not None)

    def get_wcrypto(self):
        """Get the stored key and the crypto name

        Returns:
            str: cypher name
            bytes: key string
            bytes: iv string

        """
        return (self.cypher_name, self.key_str, self.iv_str)


##########################################################################
# Parametrized sym algo classes

# dict of crypt_name -> (key_len, iv_len)
cypher_dict = {"aes_128_cbc": (16, 16), "aes_256_cbc": (32, 16), "bf_cbc": (16, 8), "des3": (24, 8), "des_cbc": (8, 8)}


class ParametrizedSymKey(SymKey):
    """Helper class to build different types of Symmetric Keys from a parameter dictionary (cypher_dict)."""

    def __init__(self, cypher_name, key_str=None, iv_str=None, key_iv_code=None):
        if cypher_name not in list(cypher_dict.keys()):
            raise KeyError("Unsupported cypher %s" % cypher_name)
        cypher_params = cypher_dict[cypher_name]
        SymKey.__init__(self, cypher_name, cypher_params[0], cypher_params[1], key_str, iv_str, key_iv_code)


class AutoSymKey(MutableSymKey):
    """Symmetric Keys from code strings. Get cypher name from key_iv_code"""

    def __init__(self, key_iv_code=None):
        """Constructor

        Args:
            key_iv_code (AnyStr): cypher byte string. str is encoded using BINARY_ENCODING_CRYPTO
        """
        self.auto_load(key_iv_code)

    def auto_load(self, key_iv_code=None):
        """Load a new key_iv_key and extract the cypher

        Args:
            key_iv_code (AnyStr): cypher byte string. str is encoded using BINARY_ENCODING_CRYPTO

        Raises:
            ValueError: if the format of the code is incorrect

        """
        if key_iv_code is None:
            self.cypher_name = None
            self.key_str = None
        else:
            key_iv_code = defaults.force_bytes(key_iv_code)  # just in case it was unicode"
            ki_arr = key_iv_code.split(b",")
            if len(ki_arr) != 3:
                raise ValueError("Invalid format, commas not found")
            if ki_arr[0][:7] != b"cypher:":
                raise ValueError("Invalid format, cypher not found")
            cypher_name = ki_arr[0][7:].decode(defaults.BINARY_ENCODING_CRYPTO)
            if ki_arr[1][:4] != b"key:":
                raise ValueError("Invalid format, key not found")
            key_str = ki_arr[1][4:]
            if ki_arr[2][:3] != b"iv:":
                raise ValueError("Invalid format, iv not found")
            iv_str = ki_arr[2][3:]
            cypher_params = cypher_dict[cypher_name]
            self.redefine(cypher_name, cypher_params[0], cypher_params[1], key_str, iv_str)


##########################################################################
# Explicit sym algo classes


class SymAES128Key(ParametrizedSymKey):
    def __init__(self, key_str=None, iv_str=None, key_iv_code=None):
        ParametrizedSymKey.__init__(self, "aes_128_cbc", key_str, iv_str, key_iv_code)


class SymAES256Key(ParametrizedSymKey):
    def __init__(self, key_str=None, iv_str=None, key_iv_code=None):
        ParametrizedSymKey.__init__(self, "aes_256_cbc", key_str, iv_str, key_iv_code)


class Sym3DESKey(ParametrizedSymKey):
    def __init__(self, key_str=None, iv_str=None, key_iv_code=None):
        ParametrizedSymKey.__init__(self, "des3", key_str, iv_str, key_iv_code)


# Removed SymBlowfishKey, bf_cbc and SymDESKey, des_cbc, because not supported in openssl3 (EL9)

# def debug_print(description, text):
#    print "<%s>\n%s\n</%s>\n" % (description,text,description)
#
# def test():
#    plaintext = "5105105105105100"
#
#    sk=SymAES256Key()
#    sk.new()
#
#    key_iv_code=sk.get_code()
#
#    encrypted = sk.encrypt_hex(plaintext)
#
#    sk2=AutoSymKey(key_iv_code=key_iv_code)
#    decrypted = sk2.decrypt_hex(encrypted)
#
#    assert plaintext == decrypted
#
#    debug_print("key_id", key_iv_code)
#    debug_print("plain text", plaintext)
#    debug_print("cipher text", encrypted)
#    debug_print("decrypted text", decrypted)
