# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""pubCrypto - This module defines classes to perform public key cryptography

It uses M2Crypto: https://github.com/mcepl/M2Crypto
a wrapper around OpenSSL: https://www.openssl.org/docs/man1.1.1/man3/

NOTE For convenience and consistency w/ previous versions of this module, Encryption/Signing functions
    (b64, hex and .encrypt() ) accept bytes-like objects (bytes, bytearray) and also Unicode strings
    utf-8 encoded (defaults.BINARY_ENCODING_CRYPTO).
    B64 and hex Decryption functions, consistent w/ Python's binascii.a2b_* functions, accept bytes and
    Unicode strings containing only ASCII characters, .decrypt() only accepts bytes-like objects (such as bytes,
    bytearray and other objects that support the buffer protocol).
    All these functions return bytes.

    Keys can be loaded from AnyStr (str, bytes, bytearray). Keys are returned as bytes string. Key files are binary.

"""

import binascii
import os

import M2Crypto

from . import defaults


def passphrase_callback(
    v: bool, prompt1: str = "Enter passphrase:", prompt2: str = "Verify passphrase:"
):
    str3 = prompt1 + prompt2
    pass


def _default_callback(*args):
    """Return a dummy passphrase

    Good for service key processing where human not present.
    Used as a callback in the :mod:M2Crypto module:
        A Python callable object that is invoked to acquire a passphrase with which to unlock the key.
        The default is :func:M2Crypto.util.passphrase_callback ::
            def passphrase_callback(v: bool, prompt1: str = 'Enter passphrase:', prompt2: str = 'Verify passphrase:'
                                   ): -> Optional[str]

    Args:
        *args:

    Returns:
        Optional[str]: str or None

    """
    # TODO: according to the M2Crypto spec this function is expected to return a str (unicode)
    #   but doing so fails the unit test (test_factory_glideFactoryConfig.py), leaving the bytes now
    #   maybe the fixture w/ the key should be foxed (fixtures/factory/work-dir/rsa.key/rsa.key.bak)
    # return "default"
    return b"default"


class PubCryptoError(Exception):
    """Exception masking M2Crypto exceptions,
    to ease error handling in modules importing pubCrypto
    """

    def __init__(self, msg):
        Exception.__init__(self, msg)


######################
#
# Available paddings:
# M2Crypto.RSA.no_padding
# M2Crypto.RSA.pkcs1_padding
# M2Crypto.RSA.sslv23_padding
# M2Crypto.RSA.pkhas1_oaep_padding
#
# Available sign algos:
#  'sha1'
#  'sha224'
#  'sha256',
#  'ripemd160'
#  'md5'
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


##########################################################################
# Public part of the RSA key
class PubRSAKey:
    """Public part of the RSA key"""

    def __init__(
        self,
        key_str=None,
        key_fname=None,
        encryption_padding=M2Crypto.RSA.pkcs1_oaep_padding,
        sign_algo="sha256",
    ):
        """Constructor for RSA public key

        One and only one of the two key_str or key_fname must be defined (not None)

        Available paddings:
            M2Crypto.RSA.no_padding
            M2Crypto.RSA.pkcs1_padding
            M2Crypto.RSA.sslv23_padding
            M2Crypto.RSA.pkhas1_oaep_padding

        Available sign algos:
            'sha1', 'sha224', 'sha256', 'ripemd160', 'md5'

        Available ciphers, too many to list them all, try `man enc` a few of them are:
            'aes_128_cbc'
            'aes_128_ofb
            'aes_256_cbc'
            'aes_256_cfb'
            'bf_cbc'
            'des3'

        Args:
            key_str (str/bytes): string w/ base64 encoded key
                Must be bytes-like object or ASCII string, like base64 inputs
            key_fname (str): key file path
            encryption_padding:
            sign_algo (str): valid signing algorithm (default: 'sha256')
        """
        self.rsa_key = None
        self.has_private = False
        self.encryption_padding = encryption_padding
        self.sign_algo = sign_algo

        try:
            self.load(key_str, key_fname)
        except M2Crypto.RSA.RSAError as e:
            # Put some additional information in the exception object to be printed later on
            # This helps operator understand which file might be corrupted so that they can try to delete it
            e.key_fname = key_fname
            e.cwd = os.getcwd()
            raise
        return

    ###########################################
    # Load key functions

    def load(self, key_str=None, key_fname=None):
        """Load key from a string or a file

        Only one of the two can be defined (not None)
        Load the key into self.rsa_key

        Args:
            key_str (str/bytes): string w/ base64 encoded key
                Must be bytes-like object or ASCII string, like base64 inputs
            key_fname (str): file name

        Raises:
            ValueError: if both key_str and key_fname are defined
        """
        if key_str is not None:
            if key_fname is not None:
                raise ValueError("Illegal to define both key_str and key_fname")
            key_str = defaults.force_bytes(key_str)
            try:
                bio = M2Crypto.BIO.MemoryBuffer(key_str)
                self._load_from_bio(bio)
            except M2Crypto.RSA.RSAError as e:
                raise PubCryptoError("M2Crypto.RSA.RSAError: %s" % e)
        elif key_fname is not None:
            bio = M2Crypto.BIO.openfile(key_fname)
            if bio is None:
                # File not found or wrong permissions
                raise M2Crypto.BIO.BIOError(M2Crypto.Err.get_error())
            self._load_from_bio(bio)
        else:
            self.rsa_key = None
        return

    # meant to be internal
    def _load_from_bio(self, bio):
        """Load the key into the object

        Protected, overridden by child classes. Used by load

        Args:
            bio (M2Crypto.BIO.BIO): BIO to retrieve the key from (file or memory buffer)
        """
        self.rsa_key = M2Crypto.RSA.load_pub_key_bio(bio)
        self.has_private = False
        return

    ###########################################
    # Save key functions

    def save(self, key_fname):
        """Save the key to a file

        The file is binary and is written using M2Crypto.BIO

        Args:
            key_fname (str): file name

        Returns:

        """
        bio = M2Crypto.BIO.openfile(key_fname, "wb")
        try:
            return self._save_to_bio(bio)
        except Exception as e:
            # need to remove the file in case of error
            bio.close()
            del bio
            os.unlink(key_fname)
            raise

    # like save, but return a string
    def get(self):
        """Retrieve the key

        Returns:
            bytes: key

        """
        bio = M2Crypto.BIO.MemoryBuffer()
        self._save_to_bio(bio)
        return bio.read()

    # meant to be internal
    def _save_to_bio(self, bio):
        """Save the key from the object

        Protected, overridden by child classes. Used by save and get

        Args:
            bio (M2Crypto.BIO.BIO): BIO object to save the key to (file or memory buffer)

        Returns:
            int: status returned by M2Crypto.m2.rsa_write_pub_key
        Raises:
            KeyError: if the key is not defined
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")

        return self.rsa_key.save_pub_key_bio(bio)

    ###########################################
    # encrypt/verify data inline

    def encrypt(self, data):
        """Encrypt the data

        Args:
            data (AnyStr): string to encrypt. bytes-like or str. If unicode,
                it is encoded using utf-8 before being encrypted.
                len(data) must be less than len(key)

        Returns:
            bytes: encrypted data
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        bdata = defaults.force_bytes(data)
        return self.rsa_key.public_encrypt(bdata, self.encryption_padding)

    def encrypt_base64(self, data):
        """like encrypt, but base64 encoded"""
        return binascii.b2a_base64(self.encrypt(data))

    def encrypt_hex(self, data):
        """like encrypt, but hex encoded"""
        return binascii.b2a_hex(self.encrypt(data))

    def verify(self, data, signature):
        """Verify that the signature gets you the data

        Args:
            data (AnyStr): string to verify. bytes-like or str. If unicode,
                it is encoded using utf-8 before being encrypted. :
            signature (bytes): signature to use in the verification

        Returns:
            bool: True if the signature gets you the data

        Raises:
            KeyError: if the key is not defined
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        bdata = defaults.force_bytes(data)
        return self.rsa_key.verify(bdata, signature, self.sign_algo)

    def verify_base64(self, data, signature):
        """like verify, but the signature is base64 encoded"""
        return self.verify(data, binascii.a2b_base64(signature))

    def verify_hex(self, data, signature):
        """like verify, but the signature is hex encoded"""
        return self.verify(data, binascii.a2b_hex(signature))


##########################################################################
# Public and private part of the RSA key
class RSAKey(PubRSAKey):
    """Public and private part of the RSA key"""

    def __init__(
        self,
        key_str=None,
        key_fname=None,
        private_cipher="aes_256_cbc",
        private_callback=_default_callback,
        encryption_padding=M2Crypto.RSA.pkcs1_oaep_padding,
        sign_algo="sha256",
    ):
        self.private_cipher = private_cipher
        self.private_callback = private_callback
        PubRSAKey.__init__(self, key_str, key_fname, encryption_padding, sign_algo)
        return

    ###########################################
    # Downgrade to PubRSAKey
    def PubRSAKey(self):
        """Return the public part only. Downgrade to PubRSAKey

        Returns:
            PubRSAKey: an object w/ only the public part of the key

        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")

        bio = M2Crypto.BIO.MemoryBuffer()
        self.rsa_key.save_pub_key_bio(bio)
        public_key = bio.read()
        return PubRSAKey(
            key_str=public_key,
            encryption_padding=self.encryption_padding,
            sign_algo=self.sign_algo,
        )

    ###########################################
    # Load key functions

    def _load_from_bio(self, bio):
        """Load the key into the object

        Internal, overrides the parent _load_from_bio. Used by load

        Args:
            bio (M2Crypto.BIO.BIO):
        """
        self.rsa_key = M2Crypto.RSA.load_key_bio(bio, self.private_callback)
        self.has_private = True
        return

    ###########################################
    # Save key functions

    def _save_to_bio(self, bio):
        """Save the key from the object

        Protected, overridden by child classes. Used by save and get

        Args:
            bio (M2Crypto.BIO.BIO): BIO to save the key into (file or memory buffer)

        Returns:

        Raises:
            KeyError: if the key is not defined
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        return self.rsa_key.save_key_bio(
            bio, self.private_cipher, self.private_callback
        )

    ###########################################
    # generate key function
    def new(self, key_length=None, exponent=65537):
        """Refresh/Generate a new key and store it in the object

        Args:
            key_length (int/None): if no key_length provided, use the length of the existing one
            exponent (int): exponent
        """
        if key_length is None:
            if self.rsa_key is None:
                raise KeyError("No RSA key and no key length provided")
            key_length = len(self.rsa_key)
        self.rsa_key = M2Crypto.RSA.gen_key(key_length, exponent)
        return

    ###########################################

    def decrypt(self, data):
        """Decrypt data inline

        Args:
            data (bytes): data to decrypt

        Returns:
            bytes: decrypted string

        Raises:
            KeyError: if the key is not defined
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        return self.rsa_key.private_decrypt(data, self.encryption_padding)

    def decrypt_base64(self, data):
        """like decrypt, but base64 encoded"""
        return self.decrypt(binascii.a2b_base64(data))

    def decrypt_hex(self, data):
        """like decrypt, but hex encoded"""
        return self.decrypt(binascii.a2b_hex(data))

    def sign(self, data):
        """Sign data inline. Same as private_encrypt

        Args:
            data (AnyStr): string to encrypt. If unicode, it is encoded using utf-8 before being encrypted.
                len(data) must be less than len(key)

        Returns:
            bytes: encrypted data
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        bdata = defaults.force_bytes(data)
        return self.rsa_key.sign(bdata, self.sign_algo)

    def sign_base64(self, data):
        """like sign, but base64 encoded"""
        return binascii.b2a_base64(self.sign(data))

    def sign_hex(self, data):
        """like sign, but hex encoded"""
        return binascii.b2a_hex(self.sign(data))


# def generate():
#    privkey_file = "priv.pem"
#    pubkey_file = "pub.pem"
#    key_length = 1024
#    cr=RSAKey()
#    cr.new(key_length)
#    cr_pub=cr.PubRSAKey()
#
#    cr.save(privkey_file)
#    cr_pub.save(pubkey_file)
#
# def debug_print(description, text):
#    print "<%s>\n%s\n</%s>\n" % (description,text,description)
#
# def test():
#    privkey_file = "priv.pem"
#    pubkey_file = "pub.pem"
#    key_length = 1024
#    cr=RSAKey(key_fname=privkey_file)
#    cr_pub=cr.PubRSAKey()
#
#    plaintext = "5105105105105100"
#    encrypted = cr_pub.encrypt_base64(plaintext)
#    decrypted = cr.decrypt_base64(encrypted)
#    signed = cr.sign_base64(plaintext)
#
#    assert cr_pub.verify_base64(plaintext,signed)
#
#    assert plaintext == decrypted
#
#    debug_print("plain text", plaintext)
#    debug_print("cipher text", encrypted)
#    debug_print("signed text", signed)
#    debug_print("decrypted text", decrypted)
