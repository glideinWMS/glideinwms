# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module defines classes to perform hash based cryptography
#

import M2Crypto
import binascii
import os

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


class Hash:
    """
    Generic hash class
    """

    def __init__(self, hash_algo):
        self.hash_algo = hash_algo
        return


    def redefine(self, hash_algo):
        self.hash_algo = hash_algo
        return


    def compute(self, data):
        """
        Compute hash of data inline based on the hashing algorithm
        len(data) must be less than len(key)
        """
        h = M2Crypto.EVP.MessageDigest(self.hash_algo)
        h.update(data)
        return h.final()


    def compute_base64(self, data):
        """
        Compute base64 encoding for data inline
        """
        h = M2Crypto.EVP.MessageDigest(self.hash_algo)
        return binascii.b2a_base64(self.compute(data))


    def compute_hex(self, data):
        """
        Compute hex encoding for data inline
        """
        return binascii.b2a_hex(self.compute(data))


    def extract(self, fname, block_size=1048576):
        """
        Extract hash from a file
        len(data) must be less than len(key)
        """
        h = M2Crypto.EVP.MessageDigest(self.hash_algo)
        with open(fname, 'rb') as fd:
            while 1:
                data = fd.read(block_size)
                if data == '':
                    break # no more data, stop reading
                h.update(data)
        return h.final()


    def extract_base64(self, fname, block_size=1048576):
        """
        Extract base64 hash from a file
        """
        return binascii.b2a_base64(self.extract(fname, block_size))


    def extract_hex(self, fname, block_size=1048576):
        """
        Extract hex from a file
        """
        return binascii.b2a_hex(self.extract(fname, block_size))


class HashMD5(Hash):
    def __init__(self):
        Hash.__init__(self, 'md5')


class HashSHA1(Hash):
    def __init__(self):
        Hash.__init__(self, 'sha1')


class HashSHA256(Hash):
    def __init__(self):
        Hash.__init__(self, 'sha256')


##########################################################################
# Explicit hash algo section
##########################################################################

def get_hash(hash_algo, data):
    """
    Compute hash inline for a given hashing algorithm
    """
    h = Hash(hash_algo)
    return h.compute_hex(data)

def extract_hash(hash_algo, fname, block_size=1048576):
    """
    Extract hash from a file using given hashing algorithm
    """
    h = Hash(hash_algo)
    return h.extract_hex(fname, block_size)

def get_md5(data):
    return get_hash('md5', data)

def extract_md5(fname, block_size=1048576):
    return extract_hash('md5', fname, block_size)

def get_sha1(data):
    return get_hash('sha1', data)

def extract_sha1(fname, block_size=1048576):
    return extract_hash('sha1', fname, block_size)

def get_sha256(data):
    return get_hash('sha256', data)

def extract_sha256(fname, block_size=1048576):
    return extract_hash('sha256', fname, block_size)
