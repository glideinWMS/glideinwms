#
# Project:
#   glideinWMS
#
# File Version:
#

import string
import os
import os.path
import shutil

############################################################
#
# Configuration
#
############################################################

class FactoryConfig:
    def __init__(self):
        # set default values
        # user should modify if needed

        self.glidein_descript_file = "glidein.descript"
        self.job_descript_file = "job.descript"
        self.job_attrs_file = "attributes.cfg"
        self.job_params_file = "params.cfg"
        self.frontend_descript_file = "frontend.descript"
        self.signatures_file = "signatures.sha1"

# global configuration of the module
factoryConfig=FactoryConfig()


############################################################
#
# Generic Class
# You most probably don't want to use these
#
############################################################

# loads a file composed of
#   NAME VAL
# and creates
#   self.data[NAME]=VAL
# It also defines:
#   self.config_file="name of file"
class ConfigFile:
    def __init__(self,config_file,convert_function=repr):
        self.config_file=config_file
        self.load(config_file,convert_function)

    def load(self,fname,convert_function):
        self.data={}
        fd=open(fname,"r")
        try:
            lines=fd.readlines()
            for line in lines:
                if line[0]=="#":
                    continue # comment
                if len(string.strip(line))==0:
                    continue # empty line
                larr=string.split(line,None,1)
                lname=larr[0]
                if len(larr)==1:
                    lval=""
                else:
                    lval=larr[1][:-1] #strip newline
                exec("self.data['%s']=%s"%(lname,convert_function(lval)))
        finally:
            fd.close()

    def has_key(self, key_name):
        return self.data.has_key(key_name)
    
    def __str__(self):
        output = '\n'
        for key in self.data.keys():
            output += '%s = %s, (%s)\n' % (key, str(self.data[key]), type(self.data[key]))
        return output

# load from the entry subdir
class EntryConfigFile(ConfigFile):
    def __init__(self,entry_name,config_file,convert_function=repr):
        ConfigFile.__init__(self,os.path.join("entry_"+entry_name,config_file),convert_function)
        self.entry_name=entry_name
        self.config_file_short=config_file

# load both the main and entry subdir config file
# and join the results
class JoinConfigFile(ConfigFile):
    def __init__(self,entry_name,config_file,convert_function=repr):
        ConfigFile.__init__(self,config_file,convert_function)
        self.entry_name=entry_name
        entry_obj=EntryConfigFile(entry_name,config_file,convert_function)
        #merge by overriding whatever is found in the subdir
        for k in entry_obj.data.keys():
            self.data[k]=entry_obj.data[k]

############################################################
#
# Configuration
#
############################################################

class GlideinKey:
    def __init__(self,pub_key_type,key_fname=None,recreate=False):
        self.pub_key_type=pub_key_type
        self.load(key_fname,recreate)

    def load(self,key_fname=None,recreate=False):
        """
        Create the key if required and initialize it
        
        @type key_fname: String
        @param key_fname: Filename of the key
        @type recreate: bool
        @param recreate: Create a new key if True else load existing key. Defaults to False.
          
        """
        
        if self.pub_key_type=='RSA':
            from glideinwms.lib import pubCrypto,symCrypto
            try:
                # pylint: disable=E0611
                #  (hashlib methods are called dynamically)
                from hashlib import md5
                # pylint: enable=E0611
            except ImportError:
                from md5 import md5

            if key_fname==None:
                key_fname='rsa.key'

            self.rsa_key=pubCrypto.RSAKey(key_fname=key_fname)

            if recreate:
                # recreate it
                self.rsa_key.new()
                self.rsa_key.save(key_fname)

            self.pub_rsa_key=self.rsa_key.PubRSAKey()
            self.pub_key_id = md5(string.join((self.pub_key_type,self.pub_rsa_key.get()))).hexdigest()
            self.sym_class=symCrypto.AutoSymKey
        else:
            raise RuntimeError, 'Invalid pub key type value(%s), only RSA supported'%self.pub_key_type

    def get_pub_key_type(self):
        return self.pub_key_type[0:]

    def get_pub_key_value(self):
        if self.pub_key_type=='RSA':
            return self.pub_rsa_key.get()
        else:
            raise RuntimeError, 'Invalid pub key type value(%s), only RSA supported'%self.pub_key_type

    def get_pub_key_id(self):
        return self.pub_key_id[0:]

    # extracts the symkey from encrypted fronted attribute
    # returns a SymKey child object
    def extract_sym_key(self,enc_sym_key):
        if self.pub_key_type=='RSA':
            sym_key_code=self.rsa_key.decrypt_hex(enc_sym_key)
            return self.sym_class(sym_key_code)
        else:
            raise RuntimeError, 'Invalid pub key type value(%s), only RSA supported'%self.pub_key_type

class GlideinDescript(ConfigFile):
    def __init__(self):
        global factoryConfig
        ConfigFile.__init__(self,factoryConfig.glidein_descript_file,
                            repr) # convert everything in strings
        if self.data['PubKeyType']=='None':
            self.data['PubKeyType']=None
        self.default_rsakey_fname = 'rsa.key'
        self.backup_rsakey_fname = 'rsa.key.bak'


    def backup_and_load_old_key(self):
        """
        Backup existing key and load the key object
        """
 
        if self.data['PubKeyType'] != None:
            self.backup_rsa_key()
        self.load_old_rsa_key()
                
    def backup_rsa_key(self):
        """
        Backup existing rsa key.
        """
        
        if self.data['PubKeyType'] == 'RSA':
            try:
                shutil.copy(self.default_rsakey_fname, self.backup_rsakey_fname)
                self.data['OldPubKeyType'] = self.data['PubKeyType']
                return
            except:
                # In case of failure, the requests from frontend get
                # delayed. So it is not critical enough to fail.
                pass
            
        self.data['OldPubKeyType'] = None
        self.data['OldPubKeyObj'] = None
        return

    def load_old_rsa_key(self):
        """
        Load the old key object.
        """

        # Assume that old key if exists is of same type
        self.data['OldPubKeyType'] = self.data['PubKeyType']
        self.data['OldPubKeyObj'] = None

        if self.data['OldPubKeyType'] != None:
            try:
                self.data['OldPubKeyObj'] = GlideinKey(self.data['OldPubKeyType'],
                                                       key_fname=self.backup_rsakey_fname)
            except:
                self.data['OldPubKeyType'] = None
                self.data['OldPubKeyObj'] = None
        return

    def remove_old_key(self):
        try:
            os.remove(self.backup_rsakey_fname)
        except:
            self.data['OldPubKeyType'] = None
            self.data['OldPubKeyObj'] = None
            raise
        self.data['OldPubKeyType'] = None
        self.data['OldPubKeyObj'] = None
        return
    
    def load_pub_key(self,recreate=False):
        """
        Load the key object. Create the key if required
        
        @type recreate: bool
        @param recreate: Create a new key overwriting the old one. Defaults to False
        """
        
        if self.data['PubKeyType']!=None:
            self.data['PubKeyObj']=GlideinKey(self.data['PubKeyType'], 
                                              key_fname=self.default_rsakey_fname,
                                              recreate=recreate)
        else:
            self.data['PubKeyObj']=None
        return

class JobDescript(EntryConfigFile):
    def __init__(self,entry_name):
        global factoryConfig
        EntryConfigFile.__init__(self,entry_name,factoryConfig.job_descript_file,
                                 repr) # convert everything in strings

class JobAttributes(JoinConfigFile):
    def __init__(self,entry_name):
        global factoryConfig
        JoinConfigFile.__init__(self,entry_name,factoryConfig.job_attrs_file,
                                lambda s:s) # values are in python format

class JobParams(JoinConfigFile):
    def __init__(self,entry_name):
        global factoryConfig
        JoinConfigFile.__init__(self,entry_name,factoryConfig.job_params_file,
                                lambda s:s) # values are in python format


class FrontendDescript(ConfigFile):
    """
    Contains the security identity and username mappings for the Frontends that are authorized to
    use this factory.

    Contains dictionary of dictionaries:
    obj.data[frontend]['ident']=identity
    obj.data[frontend]['usermap'][sec_class]=username
    """
    def __init__(self):
        global factoryConfig
        ConfigFile.__init__(self, factoryConfig.frontend_descript_file,
                            lambda s:s) # values are in python format

    def get_identity(self, frontend):
        """
        Gets the identity for the given frontend.  If the Frontend is unknown, returns None.

        @type frontend: string
        @param frontend: frontend name

        @return identity
        """
        if self.data.has_key(frontend):
            fe = self.data[frontend]
            return fe['ident']
        else:
            return None

    def get_username(self, frontend, sec_class):
        """
        Gets the security name mapping for the given frontend and security class.  If not found or not authorized, returns None.

        @type frontend: string
        @param frontend: frontend name
        @type sec_class: string
        @param sec_class: security class name

        @return: security name
        """
        if self.data.has_key(frontend):
            fe = self.data[frontend]['usermap']
            if fe.has_key(sec_class):
                return fe[sec_class]

        return None

    def get_all_usernames(self):
        """
        Gets all the usernames assigned to all the frontends.

        @return: list of usernames
        """
        usernames = {}
        for frontend in self.data.keys():
            fe = self.data[frontend]['usermap']
            for sec_class in fe.keys():
                username = fe[sec_class]
                usernames[username] = True
        return usernames.keys()
    
    def get_all_frontend_sec_classes(self):
        """
        Get a list of all frontend:sec_class
        """
        frontend_sec_classes = []
        for fe_name in self.data.keys():
            fe = self.data[fe_name]['usermap']
            for sec_class in fe.keys():
                frontend_sec_classes.append("%s:%s" % (fe_name, sec_class))
        return frontend_sec_classes
    
    def get_frontend_name(self, identity):
        """
        Get the frontend:sec_class mapping for the given identity
        """
        for fe_name in self.data.keys():
            if self.data[fe_name]['ident'] == identity:
                return fe_name
        
            

# Signatures File
## File: signatures.sha1
##
#6e3565a9a0f39e0641d7e3e777b8f22d7ebc8b0f  description.a92arS.cfg  entry_AmazonEC2
#51b01a3c38589a41fb7a44936e12b31fe506ec7b  description.a92aqM.cfg  main
class SignatureFile(ConfigFile):
    def __init__(self):
        global factoryConfig
        ConfigFile.__init__(self, factoryConfig.signatures_file, lambda s:s) # values are in python format

    def load(self, fname, convert_function):
        """ Load the signatures.sha1 file into the class as a dictionary.  The
        convert_function is completely ignored here.  The line format is different
        from all the other class in that there are three values with the key being
        the last value.  The internal dictionary has the following structure:
            where:
                line[0] is the sign for the line
                line[1] is the descript file for the line
                line[2] is the key for the line

            for each line:
                line[2]_sign = line[0]
                line[2]_descript = line[1]

        """
        self.data = {}
        fd = open(fname,"r")
        try:
            lines = fd.readlines()
            for line in lines:
                if line[0] == "#":
                    continue # comment
                if len(string.strip(line)) == 0:
                    continue # empty line
                larr = string.split(line, None)
                lsign = larr[0]
                ldescript = larr[1]
                lname = larr[2]
                self.data["%s_sign" % str(lname)] = str(lsign)
                self.data["%s_descript" % str(lname)] = str(ldescript)
        finally:
            fd.close()
