#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module defines classes to perform symmetric key cryptography
#   (shared or hidden key)
#

import M2Crypto
import os,binascii

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

# you probably don't want to use this
# Use the child classes instead
class SymKey:
    def __init__(self,
                 cypher_name,key_len,iv_len,
                 key_str=None,iv_str=None,
                 key_iv_code=None):
        self.cypher_name=cypher_name
        self.key_len=key_len
        self.iv_len=iv_len
        self.load(key_str,iv_str,key_iv_code)
        return

    ###########################################
    # load a new key
    def load(self,
             key_str=None,iv_str=None,
             key_iv_code=None):
        if key_str is not None:
            if key_iv_code is not None:
                raise ValueError,"Illegal to define both key_str and key_iv_code"

            key_str=str(key_str) # just in case it was unicode"
            if len(key_str)!=(self.key_len*2):
                raise ValueError, "Key must be exactly %i long, got %i"%(self.key_len*2,len(key_str))

            if iv_str is None:
                # if key_str defined, one needs the iv_str, too
                # set to default of 0
                iv_str='0'*(self.iv_len*2)
            else:
                if len(iv_str)!=(self.iv_len*2):
                    raise ValueError, "Initialization vector must be exactly %i long, got %i"%(self.iv_len*2,len(iv_str))
                iv_str=str(iv_str) # just in case it was unicode"
        elif key_iv_code is not None:
            key_iv_code=str(key_iv_code) # just in case it was unicode
            ki_arr=key_iv_code.split(',')
            if len(ki_arr)!=3:
                raise ValueError, "Invalid format, comas not found"
            if ki_arr[0]!=('cypher:%s'%self.cypher_name):
                raise ValueError, "Invalid format, not my cypher(%s)"%self.cypher_name
            if ki_arr[1][:4]!='key:':
                raise ValueError, "Invalid format, key not found"
            if ki_arr[2][:3]!='iv:':
                raise ValueError, "Invalid format, iv not found"
            # call itself, but with key and iv decoded
            return self.load(key_str=ki_arr[1][4:],iv_str=ki_arr[2][3:])
        #else keep None
            
        self.key_str=key_str
        self.iv_str=iv_str

    ###########################################
    # get the stored key
    def is_valid(self):
        return (self.key_str is not None)

    def get(self):
        return (self.key_str,self.iv_str)

    def get_code(self):
        return "cypher:%s,key:%s,iv:%s"%(self.cypher_name,self.key_str,self.iv_str)

    ###########################################
    # generate key function
    def new(self, random_iv=True): # if random_iv==False, set iv to 0
        self.key_str=binascii.b2a_hex(M2Crypto.Rand.rand_bytes(self.key_len))
        if random_iv:
            self.iv_str=binascii.b2a_hex(M2Crypto.Rand.rand_bytes(self.iv_len))
        else:
            self.iv_str='0'*(self.iv_len*2)
        return

    ###########################################
    # encrypt data inline

    def encrypt(self,data):
        if not self.is_valid():
            raise KeyError,"No key"
        
        b=M2Crypto.BIO.MemoryBuffer()
        c=M2Crypto.BIO.CipherStream(b)
        c.set_cipher(self.cypher_name,binascii.a2b_hex(self.key_str),binascii.a2b_hex(self.iv_str),1)
        c.write(data)
        c.flush()
        c.close()
        e=b.read()
        
        return e

    # like encrypt, but base64 encoded 
    def encrypt_base64(self,data):
        return binascii.b2a_base64(self.encrypt(data))

    # like encrypt, but hex encoded 
    def encrypt_hex(self,data):
        return binascii.b2a_hex(self.encrypt(data))

    ###########################################
    # decrypt data inline
    def decrypt(self,data):
        if not self.is_valid():
            raise KeyError,"No key"
        
        b=M2Crypto.BIO.MemoryBuffer()
        c=M2Crypto.BIO.CipherStream(b)
        c.set_cipher(self.cypher_name,binascii.a2b_hex(self.key_str),binascii.a2b_hex(self.iv_str),0)
        c.write(data)
        c.flush()
        c.close()
        d=b.read()
        
        return d

    # like decrypt, but base64 encoded 
    def decrypt_base64(self,data):
        return self.decrypt(binascii.a2b_base64(data))

    # like decrypt, but hex encoded 
    def decrypt_hex(self,data):
        return self.decrypt(binascii.a2b_hex(data))

# allows to change the crypto after instantiation
class MutableSymKey(SymKey):
    def __init__(self,
                 cypher_name=None,key_len=None,iv_len=None,
                 key_str=None,iv_str=None,
                 key_iv_code=None):
        self.redefine(cypher_name,key_len,iv_len,
                      key_str,iv_str,key_iv_code)

    ###########################################
    # load a new crypto type and a new key
    def redefine(self,
                 cypher_name=None,key_len=None,iv_len=None,
                 key_str=None,iv_str=None,
                 key_iv_code=None):
        self.cypher_name=cypher_name
        self.key_len=key_len
        self.iv_len=iv_len
        self.load(key_str,iv_str,key_iv_code)
        return

    ###########################################
    # get the stored key and the crypto name

    # redefine, as null crypto name could be used in this class
    def is_valid(self):
        return (self.key_str is not None) and (self.cypher_name is not None)

    def get_wcrypto(self):
        return (self.cypher_name,self.key_str,self.iv_str)


##########################################################################
# Parametrized sym algo classes

# dict of crypt_name -> (key_len,iv_len)
cypher_dict={'aes_128_cbc':(16,16),
             'aes_256_cbc':(32,16),
             'bf_cbc':(16,8),
             'des3':(24,8),
             'des_cbc':(8,8)}

class ParametryzedSymKey(SymKey):
    def __init__(self,cypher_name,
                 key_str=None,iv_str=None,
                 key_iv_code=None):
        if not (cypher_name in cypher_dict.keys()):
            raise KeyError,"Unsupported cypher %s"%cypher_name
        cypher_params=cypher_dict[cypher_name]
        SymKey.__init__(self,cypher_name,cypher_params[0],cypher_params[1],key_str,iv_str,key_iv_code)
        
# get cypher name from key_iv_code
class AutoSymKey(MutableSymKey):
    def __init__(self,
                 key_iv_code=None):
        self.auto_load(key_iv_code)

    ###############################################
    # load a new key_iv_key and extract the cypther
    def auto_load(self,key_iv_code=None):
        if key_iv_code is None:
            self.cypher_name=None
            self.key_str=None
        else:
            key_iv_code=str(key_iv_code) # just in case it was unicode
            ki_arr=key_iv_code.split(',')
            if len(ki_arr)!=3:
                raise ValueError, "Invalid format, comas not found"
            if ki_arr[0][:7]!='cypher:':
                raise ValueError, "Invalid format, cypher not found"
            cypher_name=ki_arr[0][7:]
            if ki_arr[1][:4]!='key:':
                raise ValueError, "Invalid format, key not found"
            key_str=ki_arr[1][4:]
            if ki_arr[2][:3]!='iv:':
                raise ValueError, "Invalid format, iv not found"
            iv_str=ki_arr[2][3:]


            cypher_params=cypher_dict[cypher_name]
            self.redefine(cypher_name,cypher_params[0],cypher_params[1],key_str,iv_str)
        
        
##########################################################################
# Explicit sym algo classes

class SymAES128Key(ParametryzedSymKey):
    def __init__(self,
                 key_str=None,iv_str=None,
                 key_iv_code=None):
        ParametryzedSymKey.__init__(self,'aes_128_cbc',key_str,iv_str,key_iv_code)

class SymAES256Key(ParametryzedSymKey):
    def __init__(self,
                 key_str=None,iv_str=None,
                 key_iv_code=None):
        ParametryzedSymKey.__init__(self,'aes_256_cbc',key_str,iv_str,key_iv_code)

class SymBlowfishKey(ParametryzedSymKey):
    def __init__(self,
                 key_str=None,iv_str=None,
                 key_iv_code=None):
        ParametryzedSymKey.__init__(self,'bf_cbc',key_str,iv_str,key_iv_code)

class Sym3DESKey(ParametryzedSymKey):
    def __init__(self,
                 key_str=None,iv_str=None,
                 key_iv_code=None):
        ParametryzedSymKey.__init__(self,'des3',key_str,iv_str,key_iv_code)

class SymDESKey(ParametryzedSymKey):
    def __init__(self,
                 key_str=None,iv_str=None,
                 key_iv_code=None):
        ParametryzedSymKey.__init__(self,'des_cbc',key_str,iv_str,key_iv_code)


#def debug_print(description, text):
#    print "<%s>\n%s\n</%s>\n" % (description,text,description)
#
#def test():
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

