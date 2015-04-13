import string
import os.path
import urllib
import cPickle
import copy

from glideinwms.lib import hashCrypto

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Frontend config related classes
#

############################################################
#
# Configuration
#
############################################################

class FrontendConfig:
    def __init__(self):
        # set default values
        # user should modify if needed

        self.frontend_descript_file = "frontend.descript"
        self.group_descript_file = "group.descript"
        self.params_descript_file = "params.cfg"
        self.attrs_descript_file = "attrs.cfg"
        self.signature_descript_file = "signatures.sha1"
        self.signature_type = "sha1"
        self.history_file = "history.pk"

# global configuration of the module
frontendConfig=FrontendConfig()


############################################################
#
# Helper function
#
############################################################
def get_group_dir(base_dir,group_name):
    return os.path.join(base_dir,"group_"+group_name)


############################################################
#
# Generic Class
# You most probably don't want to use these
#
############################################################

# loads a file or URL composed of
#   NAME VAL
# and creates
#   self.data[NAME]=VAL
# It also defines:
#   self.config_file="name of file"
# If validate is defined, also defines
#   self.hash_value
class ConfigFile:
    def __init__(self,config_dir,config_file,convert_function=repr,
                 validate=None): # if defined, must be (hash_algo,value)
        self.config_dir=config_dir
        self.config_file=config_file
        self.data={}
        self.load(os.path.join(config_dir,config_file),convert_function,validate)
        self.derive()

    def open(self,fname):
        if (fname[:5]=="http:") or (fname[:6]=="https:") or (fname[:4]=="ftp:"):
            # one of the supported URLs
            return urllib.urlopen(fname)
        else:
            # local file
            return open(fname,"r")
        

    def validate_func(self,data,validate,fname):
        if validate is not None:
            vhash=hashCrypto.get_hash(validate[0],data)
            self.hash_value=vhash
            if (validate[1] is not None) and (vhash!=validate[1]):
                raise IOError, "Failed validation of '%s'. Hash %s computed to '%s', expected '%s'"%(fname,validate[0],vhash,validate[1])

    def load(self,fname,convert_function,
             validate=None): # if defined, must be (hash_algo,value)
        self.data={}
        fd=self.open(fname)
        try:
            data=fd.read()
            self.validate_func(data,validate,fname)
            lines=data.splitlines()
            del data
            for line in lines:
                if line[0]=="#":
                    continue # comment
                if len(string.strip(line))==0:
                    continue # empty line
                self.split_func(line,convert_function)
        finally:
            fd.close()

    def split_func(self,line,convert_function):
        larr=string.split(line,None,1)
        lname=larr[0]
        if len(larr)==1:
            lval=""
        else:
            lval=larr[1]
        exec("self.data['%s']=%s"%(lname,convert_function(lval)))

    def derive(self):
        return # by default, do nothing
    
    def __str__(self):
        output = '\n'
        for key in self.data.keys():
            output += '%s = %s, (%s)\n' % (key, str(self.data[key]), type(self.data[key]))
        return output

# load from the group subdir
class GroupConfigFile(ConfigFile):
    def __init__(self,base_dir,group_name,config_file,convert_function=repr,
                 validate=None): # if defined, must be (hash_algo,value)
        ConfigFile.__init__(self,get_group_dir(base_dir,group_name),config_file,convert_function,validate)
        self.group_name=group_name

# load both the main and group subdir config file
# and join the results
# Also defines:
#   self.group_hash_value, if group_validate defined
class JoinConfigFile(ConfigFile):
    def __init__(self,base_dir,group_name,config_file,convert_function=repr,
                 main_validate=None,group_validate=None): # if defined, must be (hash_algo,value)
        ConfigFile.__init__(self,base_dir,config_file,convert_function,main_validate)
        self.group_name=group_name
        group_obj=GroupConfigFile(base_dir,group_name,config_file,convert_function,group_validate)
        if group_validate is not None:
            self.group_hash_value=group_obj.hash_value
        #merge by overriding whatever is found in the subdir
        for k in group_obj.data.keys():
            self.data[k]=group_obj.data[k]

############################################################
#
# Configuration
#
############################################################

class FrontendDescript(ConfigFile):
    def __init__(self,config_dir):
        global frontendConfig
        ConfigFile.__init__(self,config_dir,frontendConfig.frontend_descript_file,
                            repr) # convert everything in strings
        

class ElementDescript(GroupConfigFile):
    def __init__(self,base_dir,group_name):
        global frontendConfig
        GroupConfigFile.__init__(self,base_dir,group_name,frontendConfig.group_descript_file,
                                 repr) # convert everything in strings

class ParamsDescript(JoinConfigFile):
    def __init__(self,base_dir,group_name):
        global frontendConfig
        JoinConfigFile.__init__(self,base_dir,group_name,frontendConfig.params_descript_file,
                                lambda s:"('%s',%s)"%tuple(s.split(None,1))) # split the array
        self.const_data={}
        self.expr_data={} # original string
        self.expr_objs={}  # compiled object
        for k in self.data.keys():
            type_str,val=self.data[k]
            if type_str=='EXPR':
                self.expr_objs[k]=compile(val,"<string>","eval")
                self.expr_data[k]=val
            elif type_str=='CONST':
                self.const_data[k]=val
            else:
                raise RuntimeError, "Unknown parameter type '%s' for '%s'!"%(type_str,k)

class AttrsDescript(JoinConfigFile):
    def __init__(self,base_dir,group_name):
        global frontendConfig
        JoinConfigFile.__init__(self,base_dir,group_name,frontendConfig.attrs_descript_file,
                                str)  # they are already in python form

# this one is the special frontend work dir signature file
class SignatureDescript(ConfigFile):
    def __init__(self,config_dir):
        global frontendConfig
        ConfigFile.__init__(self,config_dir,frontendConfig.signature_descript_file,
                            None) # Not used, redefining split_func
        self.signature_type=frontendConfig.signature_type

    def split_func(self,line,convert_function):
        larr=string.split(line,None)
        if len(larr)!=3:
            raise RuntimeError, "Invalid line (expected 3 elements, found %i)"%len(larr)
        self.data[larr[2]]=(larr[0],larr[1])

# this one is the generic hash descript file
class BaseSignatureDescript(ConfigFile):
    def __init__(self,config_dir,signature_fname,signature_type,validate=None):
        ConfigFile.__init__(self,config_dir,signature_fname,
                            None, # Not used, redefining split_func
                            validate)
        self.signature_type=signature_type

    def split_func(self,line,convert_function):
        larr=string.split(line,None,1)
        if len(larr)!=2:
            raise RuntimeError, "Invalid line (expected 2 elements, found %i)"%len(larr)
        lval=larr[1]
        self.data[lval]=larr[0]

############################################################
#
# Processed configuration
#
############################################################

# not everything is merged
# the old element can still be accessed
class ElementMergedDescript:
    def __init__(self,base_dir,group_name):
        self.frontend_data=FrontendDescript(base_dir).data
        if not (group_name in string.split(self.frontend_data['Groups'],',')):
            raise RuntimeError, "Group '%s' not supported: %s"%(group_name,self.frontend_data['Groups'])
        
        self.element_data=ElementDescript(base_dir,group_name).data
        self.group_name=group_name

        self.merge()

    #################
    # Private
    def merge(self):
        self.merged_data={}

        for t in ('JobSchedds',):
            self.merged_data[t]=self.split_list(self.frontend_data[t])+self.split_list(self.element_data[t])
            if len(self.merged_data[t])==0:
                raise RuntimeError,"Found empty %s!"%t
        for t in ('FactoryCollectors',):
            self.merged_data[t]=eval(self.frontend_data[t])+eval(self.element_data[t])
            if len(self.merged_data[t])==0:
                raise RuntimeError,"Found empty %s!"%t
        for t in ('FactoryQueryExpr','JobQueryExpr'):
            self.merged_data[t]="(%s) && (%s)"%(self.frontend_data[t],self.element_data[t])
        for t in ('JobMatchAttrs',):
            attributes=[]
            names=[]
            for el in eval(self.frontend_data[t])+eval(self.element_data[t]):
                el_name=el[0]
                if not (el_name in names):
                    attributes.append(el)
                    names.append(el_name)
            self.merged_data[t]=attributes
        for t in ('MatchExpr',):
            self.merged_data[t]="(%s) and (%s)"%(self.frontend_data[t],self.element_data[t])
            self.merged_data[t+'CompiledObj']=compile(self.merged_data[t],"<string>","eval")

        self.merged_data['ProxySelectionPlugin']='ProxyAll' #default
        for t in ('ProxySelectionPlugin','SecurityName'):
            for data in (self.frontend_data,self.element_data):
                if data.has_key(t):
                    self.merged_data[t]=data[t]

        proxies=[]
        for data in (self.frontend_data,self.element_data):
            if data.has_key('Proxies'):
                proxies+=eval(data['Proxies'])
        self.merged_data['Proxies']=proxies

        proxy_descript_attrs=['ProxySecurityClasses','ProxyTrustDomains',
            'ProxyTypes','ProxyKeyFiles','ProxyPilotFiles','ProxyVMIds',
            'ProxyVMTypes','ProxyCreationScripts','ProxyUpdateFrequency']

        for attr in proxy_descript_attrs:
            proxy_descript_data={}
            for data in (self.frontend_data,self.element_data):
                if data.has_key(attr):
                    dprs=eval(data[attr])
                    for k in dprs.keys():
                        proxy_descript_data[k]=dprs[k]
            self.merged_data[attr]=proxy_descript_data
        
        return

    def split_list(self,val):
        if val=='None':
            return []
        elif val=='':
            return []
        else:
            return string.split(val,',')
        
class GroupSignatureDescript:
    def __init__(self,base_dir,group_name):
        self.group_name=group_name
        
        sd=SignatureDescript(base_dir)
        self.signature_data=sd.data
        self.signature_type=sd.signature_type

        fd=sd.data['main']
        self.frontend_descript_fname=fd[1]
        self.frontend_descript_signature=fd[0]

        gd=sd.data['group_%s'%group_name]
        self.group_descript_fname=gd[1]
        self.group_descript_signature=gd[0]

class StageFiles:
    def __init__(self,base_URL,descript_fname,validate_algo,signature_hash):
        self.base_URL=base_URL
        self.validate_algo=validate_algo
        self.stage_descript=ConfigFile(base_URL, descript_fname, repr,
                                       (validate_algo,None)) # just get the hash value... will validate later

        self.signature_descript=BaseSignatureDescript(base_URL,self.stage_descript.data['signature'],validate_algo,(validate_algo,signature_hash))
        
        if self.stage_descript.hash_value!=self.signature_descript.data[descript_fname]:
            raise IOError, "Descript file %s signature invalid, expected'%s' got '%s'"%(descript_fname,self.signature_descript.data[descript_fname],self.stage_descript.hash_value)

    def get_stage_file(self,fname,repr):
        return ConfigFile(self.base_URL,fname,repr,
                          (self.validate_algo,self.signature_descript.data[fname]))

    def get_file_list(self,list_type): # example list_type == 'preentry_file_list'
        if not self.stage_descript.data.has_key(list_type):
            raise KeyError,"Unknown list type '%s'; valid typtes are %s"%(list_type,self.stage_descript.data.keys())

        list_fname=self.stage_descript.data[list_type]
        return self.get_stage_file(self.stage_descript.data[list_type],
                                   lambda x:string.split(x,None,4))

# this class knows how to interpret some of the files in the Stage area
class ExtStageFiles(StageFiles):
    def __init__(self,base_URL,descript_fname,validate_algo,signature_hash):
        StageFiles.__init__(self,base_URL,descript_fname,validate_algo,signature_hash)
        self.preentry_file_list=None

    def get_constants(self):
        self.load_preentry_file_list()
        return self.get_stage_file(self.preentry_file_list.data['constants.cfg'][0],repr)

    def get_condor_vars(self):
        self.load_preentry_file_list()
        return self.get_stage_file(self.preentry_file_list.data['condor_vars.lst'][0],lambda x:string.split(x,None,6))

    # internal
    def load_preentry_file_list(self):
        if self.preentry_file_list is None:
            self.preentry_file_list=self.get_file_list('preentry_file_list')
        # else, nothing to do

# this class knows how to interpret some of the files in the Stage area
# Will parrpopriately merge the main and the group ones
class MergeStageFiles:
    def __init__(self,base_URL,validate_algo,
                 main_descript_fname,main_signature_hash,
                 group_name,group_descript_fname,group_signature_hash):
        self.group_name=group_name
        self.main_stage=ExtStageFiles(base_URL,main_descript_fname,validate_algo,main_signature_hash)
        self.group_stage=ExtStageFiles(get_group_dir(base_URL,group_name),group_descript_fname,validate_algo,group_signature_hash)

    def get_constants(self):
        main_consts=self.main_stage.get_constants()
        group_consts=self.group_stage.get_constants()
        # group constants override the main ones
        for k in group_consts.data.keys():
            main_consts.data[k]=group_consts.data[k]
        main_consts.group_name=self.group_name
        main_consts.group_hash_value=group_consts.hash_value

        return main_consts
    
    def get_condor_vars(self):
        main_cv=self.main_stage.get_condor_vars()
        group_cv=self.group_stage.get_condor_vars()
        # group condor_vars override the main ones
        for k in group_cv.data.keys():
            main_cv.data[k]=group_cv.data[k]
        main_cv.group_name=self.group_name
        main_cv.group_hash_value=group_cv.hash_value

        return main_cv

############################################################
#
# The FrontendGroups may want to preserve some state between
# iterations/invocations. The HistoryFile class provides
# the needed support for this.
#
# There is no fixed schema in the class itself;
# the FrontedGroup is free to store any arbitrary dictionary
# in it.
#
############################################################

class HistoryFile:
    def __init__(self, base_dir, group_name, load_on_init = True,
                 default_factory=None):
        """
        The default_factory semantics is the same as the one in collections.defaultdict
        """
        self.base_dir = base_dir
        self.group_name = group_name
        self.fname = os.path.join(get_group_dir(base_dir, group_name), frontendConfig.history_file)
        self.default_factory = default_factory

        # cannot use collections.defaultdict directly
        # since it is only supported starting python 2.5
        self.data = {}

        if load_on_init:
            self.load()

    def load(self, raise_on_error = False):
        try:
            fd = open(self.fname,'r')
            try:
                data = cPickle.load(fd)
            finally:
                fd.close()
        except:
            if raise_on_error:
                raise
            else:
                # default to empty history on error
                data = {}

        if type(data) != type({}):
            if raise_on_error:
                raise TypeError, "History object not a dictionary: %s" % str(type(data))
            else:
                # default to empty history on error
                data = {}

        self.data = data

    def save(self, raise_on_error = False):
        try:
            # there is no concurrency, so does not need to be done atomically
            fd = open(self.fname, 'w')
            try:
                cPickle.dump(self.data, fd, cPickle.HIGHEST_PROTOCOL)
            finally:
                fd.close()
        except:
            if raise_on_error:
                raise
            #else, just ignore

    def has_key(self, keyid):
        return self.data.has_key(keyid)

    def __contains__(self, keyid):
        return (keyid in self.data)

    def __getitem__(self, keyid):
        try:
            return self.data[keyid]
        except KeyError,e:
            if self.default_factory is None:
                raise # no default initialization, just fail
            # i have the initialization function, use it
            self.data[keyid] = self.default_factory()
            return self.data[keyid]

    def __setitem__(self, keyid, val):
        self.data[keyid] = val

    def __delitem__(self, keyid):
        del self.data[keyid]

    def empty(self):
        self.data = {}

    def get(self, keyid, defaultval=None):
        return self.data.get(keyid, defaultval)
