##########################################
#
# This module defines classes to perform
# hash based cryptography
#
##########################################

import M2Crypto
import os,binascii

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
        self.redefine(hash_algo)
        return

    def redefine(self,
                 hash_algo):
        self.hash_also=hash_algo
        return

    ###########################################
    # compute hash inline

    # len(data) must be less than len(key)
    def compute(self,data):
        h=M2Crypto.EVP.MessageDigest(self.hash_algo)
        h.update(data)
        return h.final()

    # like compute, but base64 encoded 
    def compute_base64(self,data):
        return binascii.b2a_base64(self.compute(data))

    # like compute, but hex encoded 
    def compute_hex(self,data):
        return binascii.b2a_hex(self.compute(data))

#########################################

# compute hash inline
def get_hash(hash_algo,data):
    h=Hash(hash_algo)
    return h.compute_hex(data)

# compute hash from file
def extract_hash(hash_algo,fname,block_size=1000000):
    h=Hash(hash_algo)
    fd=open(fname,'rb')
    try:
        while 1:
            data=fd.read(block_size)
            if data=='':
                break # no more data, stop reading
            h.update(data)               
    finally:
        fd.close()
    return h.compute_hex(data)

##########################################################################
# Explicit hash algo section

class HashMD5(Hash):
    def __init__(self):
        Hash.__init__(self,'md5')

def get_md5(data):
    return get_hash('md5',data)

def extract_md5(fname):
    return extract_hash('md5',fname)

class HashSHA1(Hash):
    def __init__(self):
        Hash.__init__(self,'sha1')

def get_sha1(data):
    return get_hash('sha1',data)

def extract_sha1(fname):
    return extract_hash('sha1',fname)

class HashSHA256(Hash):
    def __init__(self):
        Hash.__init__(self,'sha256')

def get_sha256(data):
    return get_hash('sha256',data)

def extract_sha256(fname):
    return extract_hash('sha256',fname)

