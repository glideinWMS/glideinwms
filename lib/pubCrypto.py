#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module defines classes to perform public key cryptography
#

import M2Crypto
import os
import binascii

# use a dummy passwd
# good for service key processing where human not present
def default_callback(*args):
    return "default"

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
    def __init__(self,
                 key_str=None,key_fname=None,
                 encryption_padding=M2Crypto.RSA.pkcs1_oaep_padding,
                 sign_algo='sha256'):
        self.rsa_key=None
        self.has_private=False
        self.encryption_padding=encryption_padding
        self.sign_algo=sign_algo

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

    def load(self,
             key_str=None,key_fname=None):
        if key_str is not None:
            if key_fname is not None:
                raise ValueError("Illegal to define both key_str and key_fname")
            bio = M2Crypto.BIO.MemoryBuffer(key_str)
            self.load_from_bio(bio)
        elif key_fname is not None:
            bio = M2Crypto.BIO.openfile(key_fname)
            self.load_from_bio(bio)
        else:
            self.rsa_key=None
        return

    # meant to be internal
    def load_from_bio(self, bio):
        self.rsa_key=M2Crypto.RSA.load_pub_key_bio(bio)
        self.has_private=False
        return

    ###########################################
    # Save key functions

    def save(self, key_fname):
        bio = M2Crypto.BIO.openfile(key_fname, 'wb')
        try:
            return self.save_to_bio(bio)
        except:
            # need to remove the file in case of error
            bio.close()
            del bio
            os.unlink(key_fname)
            raise

    # like save, but return a string
    def get(self):
        bio = M2Crypto.BIO.MemoryBuffer()
        self.save_to_bio(bio)
        return bio.read()

    # meant to be internal
    def save_to_bio(self, bio):
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        
        return self.rsa_key.save_pub_key_bio(bio)

    ###########################################
    # encrypt/verify data inline

    # len(data) must be less than len(key)
    def encrypt(self, data):
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        
        return self.rsa_key.public_encrypt(data, self.encryption_padding)

    # like encrypt, but base64 encoded 
    def encrypt_base64(self, data):
        return binascii.b2a_base64(self.encrypt(data))

    # like encrypt, but hex encoded 
    def encrypt_hex(self, data):
        return binascii.b2a_hex(self.encrypt(data))

    # verify that the signature gets you the data
    # return a Bool
    def verify(self, data, signature):
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        
        return self.rsa_key.verify(data, signature, self.sign_algo)

    # like verify, but the signature is base64 encoded
    def verify_base64(self, data, signature):
        return self.verify(data, binascii.a2b_base64(signature))

    # like verify, but the signature is hex encoded
    def verify_hex(self, data, signature):
        return self.verify(data, binascii.a2b_hex(signature))


##########################################################################
# Public and private part of the RSA key    
class RSAKey(PubRSAKey):
    def __init__(self,
                 key_str=None,key_fname=None,
                 private_cipher='aes_256_cbc',
                 private_callback=default_callback,
                 encryption_padding=M2Crypto.RSA.pkcs1_oaep_padding,
                 sign_algo='sha256'):
        self.private_cipher=private_cipher
        self.private_callback=private_callback
        PubRSAKey.__init__(self, key_str, key_fname, encryption_padding, sign_algo)
        return

    ###########################################
    # Downgrade to PubRSAKey
    def PubRSAKey(self):
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        
        bio = M2Crypto.BIO.MemoryBuffer()
        self.rsa_key.save_pub_key_bio(bio)
        public_key=bio.read()
        return PubRSAKey(key_str=public_key, encryption_padding=self.encryption_padding, sign_algo=self.sign_algo)

    ###########################################
    # Load key functions

    # meant to be internal
    # load uses it
    def load_from_bio(self, bio):
        self.rsa_key=M2Crypto.RSA.load_key_bio(bio, self.private_callback)
        self.has_private=True
        return

    ###########################################
    # Save key functions

    # meant to be internal
    # save and get use it
    def save_to_bio(self, bio):
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        
        return self.rsa_key.save_key_bio(bio, self.private_cipher, self.private_callback)

    ###########################################
    # generate key function
    # if no key_length provided, use the length of the existing one
    def new(self,key_length=None,exponent=65537):
        if key_length is None:
            if self.rsa_key is None:
                raise KeyError("No RSA key and no key length provided")
            key_length=len(self.rsa_key)
        self.rsa_key= M2Crypto.RSA.gen_key(key_length, exponent)
        return
        
    ###########################################
    # sign/decrypt data inline

    def decrypt(self, data):
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        
        return self.rsa_key.private_decrypt(data, self.encryption_padding)

    # like decrypt, but base64 encoded 
    def decrypt_base64(self, data):
        return self.decrypt(binascii.a2b_base64(data))

    # like decrypt, but hex encoded 
    def decrypt_hex(self, data):
        return self.decrypt(binascii.a2b_hex(data))

    # synonim with private_encrypt
    def sign(self, data):
        if self.rsa_key is None:
            raise KeyError("No RSA key")
        
        return self.rsa_key.sign(data, self.sign_algo)

    # like sign, but base64 encoded 
    def sign_base64(self, data):
        return binascii.b2a_base64(self.sign(data))

    # like sign, but hex encoded 
    def sign_hex(self, data):
        return binascii.b2a_hex(self.sign(data))

#def generate():
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
#def debug_print(description, text):
#    print "<%s>\n%s\n</%s>\n" % (description,text,description)
#
#def test():
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
