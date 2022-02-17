# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Project:
#   glideinWMS
#
# File Version:
#

"""hashCrypto - This module defines classes to perform hash based cryptography

It uses M2Crypto: https://github.com/mcepl/M2Crypto
a wrapper around OpenSSL: https://www.openssl.org/docs/man1.1.1/man3/

NOTE get_hash() and extract_hash() both return Unicode utf-8 (defaults.BINARY_ENCODING_CRYPTO) strings and
    get_hash() accepts byte-like objects or utf-8 encoded Unicode strings.
    Same for all the get_XXX or extract_XXX that use those functions.
    Other class methods and functions use bytes for input and output

"""
# TODO: should this module be replaced (or reimplemented) by using Python's hashlib?

import binascii

import M2Crypto

from . import defaults

######################
#
# Available hash algos:
#  'sha1'
#  'sha224'
#  'sha256',
#  'ripemd160'
#  'md5'
#
######################


##########################################################################
# Generic hash class
class Hash:
    """Generic hash class

    Available hash algorithms:
        'sha1'
        'sha224'
        'sha256',
        'ripemd160'
        'md5'
    """
    def __init__(self, hash_algo):
        self.hash_algo = hash_algo
        return

    def redefine(self, hash_algo):
        self.hash_algo = hash_algo
        return

    ###########################################
    # compute hash inline

    def compute(self, data):
        """Compute hash inline

        len(data) must be less than len(key)

        Args:
            data (bytes): data to calculate the hash of

        Returns:
            bytes: digest value as bytes string (OpenSSL final and digest together)
        """
        h = M2Crypto.EVP.MessageDigest(self.hash_algo)
        h.update(data)
        return h.final()

    def compute_base64(self, data):
        """like compute, but base64 encoded"""
        return binascii.b2a_base64(self.compute(data))

    def compute_hex(self, data):
        """like compute, but hex encoded"""
        return binascii.b2a_hex(self.compute(data))

    ###########################################
    # extract hash from a file

    def extract(self, fname, block_size=1048576):
        """Extract hash from a file

        len(data) must be less than len(key)

        Args:
            fname (str): input file path (binary file)
            block_size:

        Returns:
            bytes: digest value as bytes string (OpenSSL final and digest together)
        """
        h = M2Crypto.EVP.MessageDigest(self.hash_algo)
        with open(fname, 'rb') as fd:
            while True:
                data = fd.read(block_size)
                if data == b'':
                    break  # no more data, stop reading
                # should check update return? -1 for Python error, 1 for success, 0 for OpenSSL failure
                h.update(data)
        return h.final()

    def extract_base64(self, fname, block_size=1048576):
        """like extract, but base64 encoded"""
        return binascii.b2a_base64(self.extract(fname, block_size))

    def extract_hex(self, fname, block_size=1048576):
        """like extract, but hex encoded"""
        return binascii.b2a_hex(self.extract(fname, block_size))


#########################################

def get_hash(hash_algo, data):
    """Compute hash inline

    Args:
        hash_algo (str): hash algorithm to use
        data (AnyStr): data of which to calculate the hash

    Returns:
        str: utf-8 encoded hash
    """
    # Check to see if the data is already in bytes
    bdata = defaults.force_bytes(data)

    h = Hash(hash_algo)
    return h.compute_hex(bdata).decode(defaults.BINARY_ENCODING_CRYPTO)


def extract_hash(hash_algo, fname, block_size=1048576):
    """Compute hash from file

    Args:
        hash_algo (str): hash algorithm to use
        fname (str): file path (file will be open in binary mode)
        block_size (int): block size

    Returns:
        str: utf-8 encoded hash
    """
    h = Hash(hash_algo)
    return h.extract_hex(fname, block_size).decode(defaults.BINARY_ENCODING_CRYPTO)


##########################################################################
# Explicit hash algo section

class HashMD5(Hash):
    def __init__(self):
        Hash.__init__(self, 'md5')


def get_md5(data):
    return get_hash('md5', data)


def extract_md5(fname, block_size=1048576):
    return extract_hash('md5', fname, block_size)


class HashSHA1(Hash):
    def __init__(self):
        Hash.__init__(self, 'sha1')


def get_sha1(data):
    return get_hash('sha1', data)


def extract_sha1(fname, block_size=1048576):
    return extract_hash('sha1', fname, block_size)


class HashSHA256(Hash):
    def __init__(self):
        Hash.__init__(self, 'sha256')


def get_sha256(data):
    return get_hash('sha256', data)


def extract_sha256(fname, block_size=1048576):
    return extract_hash('sha256', fname, block_size)
