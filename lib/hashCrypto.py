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


##########################################################################
# Generic hash class    
class Hash:
    def __init__(self,
                 hash_algo):
        self.hash_algo = hash_algo
        return

    def redefine(self,
                 hash_algo):
        self.hash_algo = hash_algo
        return

    ###########################################
    # compute hash inline

    # len(data) must be less than len(key)
    def compute(self, data):
        h = M2Crypto.EVP.MessageDigest(self.hash_algo)
        h.update(data)
        return h.final()

    # like compute, but base64 encoded 
    def compute_base64(self, data):
        return binascii.b2a_base64(self.compute(data))

    # like compute, but hex encoded 
    def compute_hex(self, data):
        return binascii.b2a_hex(self.compute(data))

    ###########################################
    # extract hash from a file

    # len(data) must be less than len(key)
    def extract(self, fname, block_size=1048576):
        h = M2Crypto.EVP.MessageDigest(self.hash_algo)
        fd = open(fname, 'rb')
        try:
            while True:
                data = fd.read(block_size)
                if data == '':
                    break # no more data, stop reading
                h.update(data)               
        finally:
            fd.close()
        return h.final()

    # like extract, but base64 encoded 
    def extract_base64(self, fname, block_size=1048576):
        return binascii.b2a_base64(self.extract(fname, block_size))

    # like extract, but hex encoded 
    def extract_hex(self, fname, block_size=1048576):
        return binascii.b2a_hex(self.extract(fname, block_size))

#########################################

# compute hash inline
def get_hash(hash_algo, data):
    h = Hash(hash_algo)
    return h.compute_hex(data)

# compute hash from file
def extract_hash(hash_algo, fname, block_size=1048576):
    h = Hash(hash_algo)
    return h.extract_hex(fname, block_size)

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
