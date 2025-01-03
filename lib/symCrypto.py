# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""symCrypto - This module defines classes to perform symmetric key cryptography (shared or hidden key).

It uses M2Crypto: https://github.com/mcepl/M2Crypto
a wrapper around OpenSSL: https://www.openssl.org/docs/man1.1.1/man3/

Note:
    For convenience and consistency with previous versions of this module, Encryption/Signing functions
    (b64, hex, and .encrypt()) accept bytes-like objects (bytes, bytearray) and also Unicode strings
    utf-8 encoded (defaults.BINARY_ENCODING_CRYPTO).
    B64 and hex Decryption functions, consistent with Python's binascii.a2b_* functions, accept bytes and
    Unicode strings containing only ASCII characters. The .decrypt() function only accepts bytes-like objects
    (such as bytes, bytearray, and other objects that support the buffer protocol).
    All these functions return bytes.

    Key definitions accept AnyStr (str, bytes, bytearray). key_str and iv_str are bytes, key_iv_code and the
    key are a str.
"""

import binascii

import M2Crypto.BIO
import M2Crypto.Rand

from . import defaults


class SymKey:
    """Symmetric key cryptography class.

    This class provides functionalities to perform symmetric key cryptography.
    It is designed to be extended by child classes for specific algorithms.

    Attributes:
        cypher_name (str): The name of the cipher.
        key_len (int): The length of the key.
        iv_len (int): The length of the initialization vector (IV).
        key_str (bytes): The key string (HEX encoded).
        iv_str (bytes): The initialization vector (HEX encoded).

    Notes:
        Many cyphers are available, use `man enc` to list them all, a few of them are:
            'aes_128_cbc'
            'aes_128_ofb
            'aes_256_cbc'
            'aes_256_cfb'
            'bf_cbc'
            'des3'
    """

    def __init__(self, cypher_name, key_len, iv_len, key_str=None, iv_str=None, key_iv_code=None):
        """Initializes a SymKey object.

        Args:
            cypher_name (str): Name of the cipher.
            key_len (int): Length of the key.
            iv_len (int): Length of the initialization vector (IV).
            key_str (str/bytes, optional): HEX encoded key string. Defaults to None.
            iv_str (str/bytes, optional): HEX encoded IV string. Defaults to None.
            key_iv_code (str, optional): Key and IV encoded as a comma-separated string. Defaults to None.
        """
        self.cypher_name = cypher_name
        self.key_len = key_len
        self.iv_len = iv_len
        self.key_str = None
        self.iv_str = None
        self.load(key_str, iv_str, key_iv_code)

    def load(self, key_str=None, iv_str=None, key_iv_code=None):
        """Loads a new key and initialization vector.

        Args:
            key_str (str/bytes, optional): Base64 encoded key string. Defaults to None.
            iv_str (str/bytes, optional): Base64 encoded initialization vector. Defaults to None.
            key_iv_code (str/bytes, optional): Comma-separated string of cipher, key, and IV. Defaults to None.

        Raises:
            ValueError: If both `key_str` and `key_iv_code` are defined, or the lengths of the key/IV are invalid.
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
        """Checks if the key is valid.

        A key is valid if the key string is not empty.

        Returns:
            bool: True if the key is valid, False otherwise.
        """
        return self.key_str is not None

    def get(self):
        """Returns the key and initialization vector.

        Returns:
            tuple: A tuple (key, iv) where both key and IV are bytes.
        """
        return self.key_str, self.iv_str

    def get_code(self):
        """Returns the cipher, key, and IV as a comma-separated string.

        Returns:
            str: The key code in the format "cypher:{cypher_name},key:{key},iv:{iv}".
        """
        return "cypher:{},key:{},iv:{}".format(
            self.cypher_name,
            self.key_str.decode(defaults.BINARY_ENCODING_CRYPTO),
            self.iv_str.decode(defaults.BINARY_ENCODING_CRYPTO),
        )

    def new(self, random_iv=True):
        """Generates a new key and IV.

        Args:
            random_iv (bool): If True, generate a random IV. If False, set IV to zero. Defaults to True.
        """
        self.key_str = binascii.b2a_hex(M2Crypto.Rand.rand_bytes(self.key_len))
        if random_iv:
            self.iv_str = binascii.b2a_hex(M2Crypto.Rand.rand_bytes(self.iv_len))
        else:
            self.iv_str = b"0" * (self.iv_len * 2)

    def encrypt(self, data):
        """Encrypts the given data.

        Args:
            data (AnyStr): The data to encrypt.

        Returns:
            bytes: The encrypted data.

        Raises:
            KeyError: If there is no valid key.
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
        return b.read()

    def encrypt_base64(self, data):
        """Encrypts data and returns the result as a base64-encoded string.

        Args:
            data (AnyStr): The data to encrypt.

        Returns:
            str: The encrypted data as a base64-encoded string.

        Raises:
            KeyError: If there is no valid key.
        """
        return binascii.b2a_base64(self.encrypt(data))

    def encrypt_hex(self, data):
        """Encrypts data and returns the result as a hex-encoded string.

        Args:
            data (AnyStr): The data to encrypt.

        Returns:
            str: The encrypted data as a hex-encoded string.

        Raises:
            KeyError: If there is no valid key.
        """
        return binascii.b2a_hex(self.encrypt(data))

    def decrypt(self, data):
        """Decrypts the given data.

        Args:
            data (bytes): The data to decrypt.

        Returns:
            bytes: The decrypted data.

        Raises:
            KeyError: If there is no valid key.
        """
        if not self.is_valid():
            raise KeyError("No key")
        b = M2Crypto.BIO.MemoryBuffer()
        c = M2Crypto.BIO.CipherStream(b)
        c.set_cipher(self.cypher_name, binascii.a2b_hex(self.key_str), binascii.a2b_hex(self.iv_str), 0)
        c.write(data)
        c.flush()
        c.close()
        return b.read()

    def decrypt_base64(self, data):
        """Decrypts base64-encoded data.

        Args:
            data (AnyStrASCII): Base64 input data. bytes or ASCII encoded Unicode str.

        Returns:
            bytes: decrypted data.
        """
        return self.decrypt(binascii.a2b_base64(data))

    def decrypt_hex(self, data):
        """Decrypts hex-encoded data.

        Args:
            data (AnyStrASCII): HEX input data. bytes or ASCII encoded Unicode str.

        Returns:
            bytes: decrypted data.
        """
        return self.decrypt(binascii.a2b_hex(data))


class MutableSymKey(SymKey):
    """SymKey class that allows changing the cryptography parameters after instantiation."""

    def __init__(self, cypher_name=None, key_len=None, iv_len=None, key_str=None, iv_str=None, key_iv_code=None):
        """Initializes a MutableSymKey object and allows redefinition of cryptographic parameters.

        Args:
            cypher_name (str, optional): The name of the cipher. Defaults to None.
            key_len (int, optional): Length of the key. Defaults to None.
            iv_len (int, optional): Length of the initialization vector (IV). Defaults to None.
            key_str (str/bytes, optional): HEX encoded key string. Defaults to None.
            iv_str (str/bytes, optional): HEX encoded IV string. Defaults to None.
            key_iv_code (str, optional): Key and IV encoded as a comma-separated string. Defaults to None.
        """
        self.redefine(cypher_name, key_len, iv_len, key_str, iv_str, key_iv_code)

    def redefine(self, cypher_name=None, key_len=None, iv_len=None, key_str=None, iv_str=None, key_iv_code=None):
        """Redefines the cryptographic parameters and reloads the key.

        Args:
            cypher_name (str, optional): Name of the cipher. Defaults to None.
            key_len (int, optional): Length of the key. Defaults to None.
            iv_len (int, optional): Length of the initialization vector (IV). Defaults to None.
            key_str (str/bytes, optional): HEX encoded key string. Defaults to None.
            iv_str (str/bytes, optional): HEX encoded IV string. Defaults to None.
            key_iv_code (str, optional): Key and IV encoded as a comma-separated string. Defaults to None.
        """
        self.cypher_name = cypher_name
        self.key_len = key_len
        self.iv_len = iv_len
        self.load(key_str, iv_str, key_iv_code)

    def is_valid(self):
        """Checks if the key and cipher name are valid.

        Redefine, as null crypto name could be used in this class

        Returns:
            bool: True if both the key and cipher name are valid.
        """
        return (self.key_str is not None) and (self.cypher_name is not None)

    def get_wcrypto(self):
        """Gets the cipher name, key, and IV.

        Returns:
            tuple: A tuple containing the cipher name (str), key string (bytes), and IV string (bytes).
        """
        return self.cypher_name, self.key_str, self.iv_str


##########################################################################
# Parametrized symmetric algorithm classes

# Dictionary of crypt_name -> (key_len, iv_len)
cypher_dict = {"aes_128_cbc": (16, 16), "aes_256_cbc": (32, 16), "bf_cbc": (16, 8), "des3": (24, 8), "des_cbc": (8, 8)}


class ParametrizedSymKey(SymKey):
    """Helper class to build different types of Symmetric Keys from a parameter dictionary (`cypher_dict`)."""

    def __init__(self, cypher_name, key_str=None, iv_str=None, key_iv_code=None):
        """Initializes a ParametrizedSymKey based on a cipher name.

        Args:
            cypher_name (str): Name of the cipher.
            key_str (str/bytes, optional): HEX encoded key string. Defaults to None.
            iv_str (str/bytes, optional): HEX encoded IV string. Defaults to None.
            key_iv_code (str, optional): Key and IV encoded as a comma-separated string. Defaults to None.

        Raises:
            KeyError: If the cipher is unsupported.
        """
        if cypher_name not in list(cypher_dict.keys()):
            raise KeyError(f"Unsupported cipher {cypher_name}")
        cypher_params = cypher_dict[cypher_name]
        SymKey.__init__(self, cypher_name, cypher_params[0], cypher_params[1], key_str, iv_str, key_iv_code)


class AutoSymKey(MutableSymKey):
    """Symmetric key class that automatically determines the cipher from the `key_iv_code`."""

    def __init__(self, key_iv_code=None):
        """Initializes an `AutoSymKey` object based on `key_iv_code`.

        Args:
            key_iv_code (str/bytes): Cipher and key information encoded, using BINARY_ENCODING_CRYPTO,
                                     as a comma-separated string.
        """
        self.auto_load(key_iv_code)

    def auto_load(self, key_iv_code=None):
        """Loads a new key and determines the cipher name from `key_iv_code`.

        Args:
            key_iv_code (str/bytes): Cipher and key information encoded using BINARY_ENCODING_CRYPTO,
                                     as a comma-separated string.

        Raises:
            ValueError: If the format of `key_iv_code` is incorrect.
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
# Explicit symmetric algorithm classes


class SymAES128Key(ParametrizedSymKey):
    """Symmetric key class for AES-128 encryption."""

    def __init__(self, key_str=None, iv_str=None, key_iv_code=None):
        """Initializes a SymAES128Key object.

        Args:
            key_str (str/bytes, optional): HEX encoded key string. Defaults to None.
            iv_str (str/bytes, optional): HEX encoded IV string. Defaults to None.
            key_iv_code (str, optional): Key and IV encoded as a comma-separated string. Defaults to None.
        """
        ParametrizedSymKey.__init__(self, "aes_128_cbc", key_str, iv_str, key_iv_code)


class SymAES256Key(ParametrizedSymKey):
    """Symmetric key class for AES-256 encryption."""

    def __init__(self, key_str=None, iv_str=None, key_iv_code=None):
        """Initializes a SymAES256Key object.

        Args:
            key_str (str/bytes, optional): HEX encoded key string. Defaults to None.
            iv_str (str/bytes, optional): HEX encoded IV string. Defaults to None.
            key_iv_code (str, optional): Key and IV encoded as a comma-separated string. Defaults to None.
        """
        ParametrizedSymKey.__init__(self, "aes_256_cbc", key_str, iv_str, key_iv_code)


class Sym3DESKey(ParametrizedSymKey):
    """Symmetric key class for 3DES encryption."""

    def __init__(self, key_str=None, iv_str=None, key_iv_code=None):
        """Initializes a Sym3DESKey object.

        Args:
            key_str (str/bytes, optional): HEX encoded key string. Defaults to None.
            iv_str (str/bytes, optional): HEX encoded IV string. Defaults to None.
            key_iv_code (str, optional): Key and IV encoded as a comma-separated string. Defaults to None.
        """
        ParametrizedSymKey.__init__(self, "des3", key_str, iv_str, key_iv_code)


# Removed SymBlowfishKey, bf_cbc and SymDESKey, des_cbc, because not supported in openssl3 (EL9)

# Test functions
#
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
