import string
import os.path

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
    def __init__(self,pub_key_type):
        self.pub_key_type=pub_key_type
        self.load()

    def load(self):
        if self.pub_key_type=='RSA':
            import pubCrypto,symCrypto,md5
            self.rsa_key=pubCrypto.RSAKey(key_fname='rsa.key')
            self.pub_rsa_key=self.rsa_key.PubRSAKey()
            self.pub_key_id=md5.new(string.join((self.pub_key_type,self.pub_rsa_key.get()))).hexdigest()
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

    # returns a SymKey child object
    def extract_sym_key(self,enc_sym_key):
        if self.pub_key_type=='RSA':
            sym_key_code=self.rsa_key.decrypt_hex(data)
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

    # define PubKeyObj
    def load_pub_key(self):
        if self.data['PubKeyType']!=None:
            self.data['PubKeyObj']=GlideinKey(self.data['PubKeyType'])
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



###########################################################
#
# CVS info
#
# $Id: glideFactoryConfig.py,v 1.15 2008/09/15 17:11:21 sfiligoi Exp $
#
# Log:
#  $Log: glideFactoryConfig.py,v $
#  Revision 1.15  2008/09/15 17:11:21  sfiligoi
#  Add decoding of encrypted params
#
#  Revision 1.14  2008/09/15 16:40:41  sfiligoi
#  Better encapsulation
#
#  Revision 1.13  2008/09/15 16:04:34  sfiligoi
#  Make sending PubKeyType optional
#
#  Revision 1.12  2008/09/05 21:07:19  sfiligoi
#  Fix typo
#
#  Revision 1.11  2008/08/19 21:53:02  sfiligoi
#  Add PubKeyID
#
#  Revision 1.10  2008/08/19 18:03:17  sfiligoi
#  Make loading of pub key optional
#
#  Revision 1.9  2008/08/19 15:10:56  sfiligoi
#  Use PubKey
#
#  Revision 1.8  2007/05/18 19:10:57  sfiligoi
#  Add CVS tags
#
#
###########################################################
