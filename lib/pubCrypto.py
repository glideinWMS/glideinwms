# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""pubCrypto - This module defines classes to perform public key cryptography.

It uses M2Crypto: https://github.com/mcepl/M2Crypto,
a wrapper around OpenSSL: https://www.openssl.org/docs/man1.1.1/man3/

Note:
    For convenience and consistency with previous versions of this module, Encryption/Signing functions
    (b64, hex, and .encrypt()) accept bytes-like objects (bytes, bytearray) and Unicode strings
    encoded in utf-8 (defaults.BINARY_ENCODING_CRYPTO). B64 and hex Decryption functions, consistent with
    Python's binascii.a2b_* functions, accept bytes and Unicode strings containing only ASCII characters.
    The .decrypt() method only accepts bytes-like objects (such as bytes, bytearray, and other objects that
    support the buffer protocol). All these functions return bytes.

    Keys can be loaded from AnyStr (str, bytes, bytearray). Keys are returned as bytes strings. Key files are binary.
"""

import binascii
import os

import M2Crypto.BIO
import M2Crypto.Err
import M2Crypto.RSA

from . import defaults


def passphrase_callback(v: bool, prompt1: str = "Enter passphrase:", prompt2: str = "Verify passphrase:"):
    """Placeholder for a passphrase callback function.

    Args:
        v (bool): Placeholder argument.
        prompt1 (str): Prompt for entering the passphrase.
        prompt2 (str): Prompt for verifying the passphrase.

    Returns:
        None (Optional return, Passphrase or None)
    """
    # Example callback (uncomment for manual testing)
    # str3 = prompt1 + prompt2
    # return str3  # Optional return
    pass


def _default_callback(*args):
    """Return a dummy passphrase.

    This function is used as a callback for service key processing where no human interaction is present.
    It is used in the :mod:M2Crypto module: to acquire a passphrase for unlocking the key.
        The default is :func:M2Crypto.util.passphrase_callback ::
            def passphrase_callback(v: bool, prompt1: str = 'Enter passphrase:', prompt2: str = 'Verify passphrase:'
                                   ): -> Optional[str]

    Args:
        *args: Variable arguments passed to the callback.

    Returns:
        Optional[str]: Dummy passphrase or None.
    """
    # TODO: according to the M2Crypto spec this function is expected to return a str (unicode)
    #   but doing so fails the unit test (test_factory_glideFactoryConfig.py), leaving the bytes now
    #   maybe the fixture w/ the key should be foxed (fixtures/factory/work-dir/rsa.key/rsa.key.bak)
    # return "default"
    return b"default"


class PubCryptoError(Exception):
    """Custom exception class to mask M2Crypto exceptions.

    This exception is used to ease error handling in modules importing pubCrypto.

    Args:
        msg (str): The error message.
    """

    def __init__(self, msg):
        super().__init__(msg)


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


class PubRSAKey:
    """Class representing the public part of an RSA key."""

    def __init__(
        self, key_str=None, key_fname=None, encryption_padding=M2Crypto.RSA.pkcs1_oaep_padding, sign_algo="sha256"
    ):
        """Initialize a PubRSAKey instance.

        One and only one of the two `key_str` or `key_fname` must be defined (not None)

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
            key_str (str | bytes, optional): Base64 encoded key as a string or bytes.
                                             Must be bytes-like object or ASCII string, like base64 inputs.
            key_fname (str, optional): Path to the key file.
            encryption_padding (int): Padding scheme for encryption. Defaults to `M2Crypto.RSA.pkcs1_oaep_padding`.
            sign_algo (str, optional): Signing algorithm to use. Defaults to 'sha256'.

        Raises:
            M2Crypto.RSA.RSAError: If there is an error loading the key.
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
            raise e from e  # Need to raise a new exception to have the modified values (only raise keeps the original)

    def load(self, key_str=None, key_fname=None):
        """Load an RSA key from a string or file.

        Only one of the two `key_str` or `key_fname` can be defined (not None).
        Load the key into `self.rsa_key`.

        Args:
            key_str (str | bytes, optional): Base64 encoded key as a string or bytes.
            key_fname (str, optional): Path to the key file.

        Raises:
            ValueError: If both key_str and key_fname are defined.
            PubCryptoError: If there is an error loading the key from the string.
            M2Crypto.BIO.BIOError: If there is an error opening the key file.
        """
        if key_str is not None:
            if key_fname is not None:
                raise ValueError("Illegal to define both key_str and key_fname")
            key_str = defaults.force_bytes(key_str)
            try:
                bio = M2Crypto.BIO.MemoryBuffer(key_str)
                self._load_from_bio(bio)
            except M2Crypto.RSA.RSAError as e:
                raise PubCryptoError("M2Crypto.RSA.RSAError: %s" % e) from e
        elif key_fname is not None:
            bio = M2Crypto.BIO.openfile(key_fname)
            if bio is None:
                # File not found or wrong permissions
                raise M2Crypto.BIO.BIOError(M2Crypto.Err.get_error())
            self._load_from_bio(bio)
        else:
            self.rsa_key = None

    # meant to be internal
    def _load_from_bio(self, bio):
        """Load the key into the object from a BIO.

        Protected method, overridden by child classes. Used by `load`.

        Args:
            bio (M2Crypto.BIO.BIO): BIO object to load the key from (file or memory buffer).
        """
        self.rsa_key = M2Crypto.RSA.load_pub_key_bio(bio)
        self.has_private = False

    def save(self, key_fname):
        """Save the RSA key to a file.

        The file is binary and is written using `M2Crypto.BIO`.

        Args:
            key_fname (str): Path to the file where the key should be saved.

        Returns:
            int: status returned by `M2Crypto.m2.rsa_write_pub_key`.

        Raises:
            Exception: If there is an error saving the key, the file is removed.
        """
        bio = M2Crypto.BIO.openfile(key_fname, "wb")
        try:
            return self._save_to_bio(bio)
        except Exception:
            # need to remove the file in case of error
            bio.close()
            del bio
            os.unlink(key_fname)
            raise

    def get(self):
        """Get the RSA key as bytes.

        Returns:
            bytes: The RSA key as bytes.
        """
        bio = M2Crypto.BIO.MemoryBuffer()
        self._save_to_bio(bio)
        return bio.read()

    # meant to be internal
    def _save_to_bio(self, bio):
        """Save the RSA key to a BIO object.

        Protected, overridden by child classes. Used by `save` and `get`.

        Args:
            bio (M2Crypto.BIO.BIO): BIO object to save the key to (file or memory buffer).

        Returns:
            int: Status code returned by `M2Crypto.m2.rsa_write_pub_key`.

        Raises:
            KeyError: If the key is not defined.
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        return self.rsa_key.save_pub_key_bio(bio)

    def encrypt(self, data):
        """Encrypt data using the RSA key.

        Args:
            data (str | bytes): The data to encrypt.
                                bytes-like or str. If unicode, it is encoded using utf-8 before being encrypted.
                                len(data) must be less than len(key).

        Returns:
            bytes: The encrypted data.

        Raises:
            KeyError: If the RSA key is not defined.
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        bdata = defaults.force_bytes(data)
        return self.rsa_key.public_encrypt(bdata, self.encryption_padding)

    def encrypt_base64(self, data):
        """Encrypt data using the RSA key and encode it in base64.

        Args:
            data (str | bytes): The data to encrypt.
                                bytes-like or str. If unicode, it is encoded using utf-8 before being encrypted.
                                len(data) must be less than len(key).

        Returns:
            bytes: The base64-encoded encrypted data.
        """
        return binascii.b2a_base64(self.encrypt(data))

    def encrypt_hex(self, data):
        """Encrypt data and encode it in hexadecimal.

        Args:
            data (str | bytes): The data to encrypt.
                                bytes-like or str. If unicode, it is encoded using utf-8 before being encrypted.
                                len(data) must be less than len(key).

        Returns:
            bytes: The hex-encoded encrypted data.
        """
        return binascii.b2a_hex(self.encrypt(data))

    def verify(self, data, signature):
        """Verify a signature against the data.

        Args:
            data (str | bytes): The data to verify.
                                If unicode, it is encoded using utf-8 before being encrypted.
            signature (bytes): The signature to verify.

        Returns:
            bool: True if the signature is valid, False otherwise.

        Raises:
            KeyError: If the RSA key is not defined.
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        bdata = defaults.force_bytes(data)
        return self.rsa_key.verify(bdata, signature, self.sign_algo)

    def verify_base64(self, data, signature):
        """Verify a base64-encoded signature against the data.

        Args:
            data (str | bytes): The data to verify.
            signature (bytes): The base64-encoded signature to verify.

        Returns:
            bool: True if the signature is valid, False otherwise.
        """
        return self.verify(data, binascii.a2b_base64(signature))

    def verify_hex(self, data, signature):
        """Verify a hex-encoded signature against the data.

        Args:
            data (str | bytes): The data to verify.
            signature (bytes): The hex-encoded signature to verify.

        Returns:
            bool: True if the signature is valid, False otherwise.
        """
        return self.verify(data, binascii.a2b_hex(signature))


class RSAKey(PubRSAKey):
    """Class representing both the public and private parts of an RSA key."""

    def __init__(
        self,
        key_str=None,
        key_fname=None,
        private_cipher="aes_256_cbc",
        private_callback=_default_callback,
        encryption_padding=M2Crypto.RSA.pkcs1_oaep_padding,
        sign_algo="sha256",
    ):
        """Initialize an RSAKey instance.

        Args:
            key_str (str | bytes, optional): Base64 encoded key as a string or bytes.
            key_fname (str, optional): Path to the key file.
            private_cipher (str): Cipher to use for private key encryption. Defaults to 'aes_256_cbc'.
            private_callback (callable): Callback function for the private key passphrase.
            encryption_padding (int): Padding scheme for encryption. Defaults to `M2Crypto.RSA.pkcs1_oaep_padding`.
            sign_algo (str): Signing algorithm to use. Defaults to 'sha256'.
        """
        self.private_cipher = private_cipher
        self.private_callback = private_callback
        super().__init__(key_str, key_fname, encryption_padding, sign_algo)

    def PubRSAKey(self):
        """Return the public part of the RSA key. Downgrade to PubRSAKey.

        Returns:
            PubRSAKey: An instance of PubRSAKey containing only the public part of the RSA key.

        Raises:
            KeyError: If the RSA key is not defined.
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")

        bio = M2Crypto.BIO.MemoryBuffer()
        self.rsa_key.save_pub_key_bio(bio)
        public_key = bio.read()
        return PubRSAKey(key_str=public_key, encryption_padding=self.encryption_padding, sign_algo=self.sign_algo)

    def _load_from_bio(self, bio):
        """Load the RSA key from a BIO object.

        Internal, overrides the parent _load_from_bio. Used by `load`.

        Args:
            bio (M2Crypto.BIO.BIO): BIO object to load the key from.
        """
        self.rsa_key = M2Crypto.RSA.load_key_bio(bio, self.private_callback)
        self.has_private = True

    def _save_to_bio(self, bio):
        """Save the RSA key to a BIO object.

        Protected, overridden by child classes. Used by `save` and `get`.

        Args:
            bio (M2Crypto.BIO.BIO): BIO object to save the key to (file or memory buffer).

        Returns:
            int: Status code returned by M2Crypto.

        Raises:
            KeyError: If the RSA key is not defined.
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        return self.rsa_key.save_key_bio(bio, self.private_cipher, self.private_callback)

    def new(self, key_length=None, exponent=65537):
        """Generate or refresh a new RSA key and store it in the object.

        Args:
            key_length (int, optional): Length of the RSA key in bits. If None, the length of the existing key is used.
            exponent (int, optional): Public exponent value. Defaults to 65537.

        Raises:
            KeyError: If no key length is provided and there is no existing key.
        """
        if key_length is None:
            if self.rsa_key is None:
                raise KeyError("No RSA key and no key length provided")
            key_length = len(self.rsa_key)
        self.rsa_key = M2Crypto.RSA.gen_key(key_length, exponent)

    def decrypt(self, data):
        """Decrypt data using the RSA key.

        Args:
            data (bytes): The data to decrypt.

        Returns:
            bytes: The decrypted data.

        Raises:
            KeyError: If the RSA key is not defined.
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        return self.rsa_key.private_decrypt(data, self.encryption_padding)

    def decrypt_base64(self, data):
        """Decrypt base64-encoded data.

        Args:
            data (bytes): The base64-encoded data to decrypt.

        Returns:
            bytes: The decrypted data.
        """
        return self.decrypt(binascii.a2b_base64(data))

    def decrypt_hex(self, data):
        """Decrypt hex-encoded data.

        Args:
            data (bytes): The hex-encoded data to decrypt.

        Returns:
            bytes: The decrypted data.
        """
        return self.decrypt(binascii.a2b_hex(data))

    def sign(self, data):
        """Sign data using the RSA key. Same as private_encrypt.

        Args:
            data (str | bytes): The data to sign.
                                If unicode, it is encoded using utf-8 before being encrypted.
                                len(data) must be less than len(key).

        Returns:
            bytes: The signed data.

        Raises:
            KeyError: If the RSA key is not defined.
        """
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        bdata = defaults.force_bytes(data)
        return self.rsa_key.sign(bdata, self.sign_algo)

    def sign_base64(self, data):
        """Sign data and encode it in base64.

        Args:
            data (str | bytes): The data to sign.

        Returns:
            bytes: The base64-encoded signed data.
        """
        return binascii.b2a_base64(self.sign(data))

    def sign_hex(self, data):
        """Sign data and encode it in hexadecimal.

        Args:
            data (str | bytes): The data to sign.

        Returns:
            bytes: The hex-encoded signed data.
        """
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
