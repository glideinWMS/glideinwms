# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""hashCrypto - This module defines classes to perform hash based cryptography.

It uses M2Crypto: https://github.com/mcepl/M2Crypto
a wrapper around OpenSSL: https://www.openssl.org/docs/man1.1.1/man3/

NOTE: get_hash() and extract_hash() both return Unicode utf-8 (defaults.BINARY_ENCODING_CRYPTO) strings and
get_hash() accepts byte-like objects or utf-8 encoded Unicode strings.
Same for all the get_XXX or extract_XXX that use those functions.
Other class methods and functions use bytes for input and output.
"""
# TODO: should this module be replaced (or reimplemented) by using Python's hashlib?

import binascii

import M2Crypto.EVP

from . import defaults

######################
# Available hash algorithms:
#  'sha1'
#  'sha224'
#  'sha256',
#  'ripemd160'
#  'md5'
######################


class Hash:
    """Generic hash class.

    Available hash algorithms:
        'sha1'
        'sha224'
        'sha256'
        'ripemd160'
        'md5'
    """

    def __init__(self, hash_algo):
        """Initializes the Hash object with the specified algorithm.

        Args:
            hash_algo (str): The hash algorithm to use.
        """
        self.hash_algo = hash_algo

    def redefine(self, hash_algo):
        """Redefines the hash algorithm.

        Args:
            hash_algo (str): The new hash algorithm to use.
        """
        self.hash_algo = hash_algo

    def compute(self, data):
        """Compute hash inline.

        Args:
            data (bytes): Data to calculate the hash of.

        Returns:
            bytes: Digest value as bytes string (OpenSSL final and digest together).
        """
        h = M2Crypto.EVP.MessageDigest(self.hash_algo)
        h.update(data)
        return h.final()

    def compute_base64(self, data):
        """Computes hash inline and returns base64 encoded result.

        Args:
            data (bytes): Data to calculate the hash of.

        Returns:
            bytes: Base64 encoded digest value.
        """
        return binascii.b2a_base64(self.compute(data))

    def compute_hex(self, data):
        """Computes hash inline and returns hex encoded result.

        Args:
            data (bytes): Data to calculate the hash of.

        Returns:
            bytes: Hex encoded digest value.
        """
        return binascii.b2a_hex(self.compute(data))

    def extract(self, fname, block_size=1048576):
        """Extracts hash from a file.

        Args:
            fname (str): Input file path (binary file).
            block_size (int): Block size for reading the file.

        Returns:
            bytes: Digest value as bytes string (OpenSSL final and digest together).
        """
        h = M2Crypto.EVP.MessageDigest(self.hash_algo)
        with open(fname, "rb") as fd:
            while True:
                data = fd.read(block_size)
                if data == b"":
                    break  # No more data, stop reading
                # Should check update return? -1 for Python error, 1 for success, 0 for OpenSSL failure
                h.update(data)
        return h.final()

    def extract_base64(self, fname, block_size=1048576):
        """Extracts hash from a file and returns base64 encoded result.

        Args:
            fname (str): Input file path (binary file).
            block_size (int): Block size for reading the file.

        Returns:
            bytes: Base64 encoded digest value.
        """
        return binascii.b2a_base64(self.extract(fname, block_size))

    def extract_hex(self, fname, block_size=1048576):
        """Extracts hash from a file and returns hex encoded result.

        Args:
            fname (str): Input file path (binary file).
            block_size (int): Block size for reading the file.

        Returns:
            bytes: Hex encoded digest value.
        """
        return binascii.b2a_hex(self.extract(fname, block_size))


def get_hash(hash_algo, data):
    """Compute hash inline.

    Convert `data` to bytes if needed and calculate the desired hash.

    Args:
        hash_algo (str): Hash algorithm to use.
        data (AnyStr): Data of which to calculate the hash.

    Returns:
        str: utf-8 encoded hash.
    """
    bdata = defaults.force_bytes(data)
    h = Hash(hash_algo)
    return h.compute_hex(bdata).decode(defaults.BINARY_ENCODING_CRYPTO)


def extract_hash(hash_algo, fname, block_size=1048576):
    """Compute hash from file.

    Args:
        hash_algo (str): Hash algorithm to use.
        fname (str): File path (file will be open in binary mode).
        block_size (int): Block size.

    Returns:
        str: utf-8 encoded hash.
    """
    h = Hash(hash_algo)
    return h.extract_hex(fname, block_size).decode(defaults.BINARY_ENCODING_CRYPTO)


##########################################################################
# Explicit hash algorithms section


class HashMD5(Hash):
    """MD5 hash class."""

    def __init__(self):
        """Initializes the MD5 hash class."""
        super().__init__("md5")


def get_md5(data):
    """Compute MD5 hash inline.

    Args:
        data (AnyStr): Data of which to calculate the hash.

    Returns:
        str: utf-8 encoded MD5 hash.
    """
    return get_hash("md5", data)


def extract_md5(fname, block_size=1048576):
    """Compute MD5 hash from file.

    Args:
        fname (str): File path (file will be open in binary mode).
        block_size (int): Block size.

    Returns:
        str: utf-8 encoded MD5 hash.
    """
    return extract_hash("md5", fname, block_size)


class HashSHA1(Hash):
    """SHA1 hash class."""

    def __init__(self):
        """Initializes the SHA1 hash class."""
        super().__init__("sha1")


def get_sha1(data):
    """Compute SHA1 hash inline.

    Args:
        data (AnyStr): Data of which to calculate the hash.

    Returns:
        str: utf-8 encoded SHA1 hash.
    """
    return get_hash("sha1", data)


def extract_sha1(fname, block_size=1048576):
    """Compute SHA1 hash from file.

    Args:
        fname (str): File path (file will be open in binary mode).
        block_size (int): Block size.

    Returns:
        str: utf-8 encoded SHA1 hash.
    """
    return extract_hash("sha1", fname, block_size)


class HashSHA256(Hash):
    """SHA256 hash class."""

    def __init__(self):
        """Initializes the SHA256 hash class."""
        super().__init__("sha256")


def get_sha256(data):
    """Compute SHA256 hash inline.

    Args:
        data (AnyStr): Data of which to calculate the hash.

    Returns:
        str: utf-8 encoded SHA256 hash.
    """
    return get_hash("sha256", data)


def extract_sha256(fname, block_size=1048576):
    """Compute SHA256 hash from file.

    Args:
        fname (str): File path (file will be open in binary mode).
        block_size (int): Block size.

    Returns:
        str: utf-8 encoded SHA256 hash.
    """
    return extract_hash("sha256", fname, block_size)
