#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glideinFrontendInterface.py,v 1.47.2.3.8.1.4.1 2010/09/02 19:05:32 sfiligoi Exp $
#
# Description:
#   This module implements the functions needed to advertize
#   and get resources from the Collector
#
# Author:
#   Igor Sfiligoi (Sept 15th 2006)
#

import condorExe
import condorMonitor
import os,os.path
import copy
import time
import string
import pubCrypto,symCrypto

############################################################
#
# Configuration
#
############################################################

class FrontendConfig:
    def __init__(self):
        # set default values
        # user should modify if needed

        # The name of the attribute that identifies the glidein
        self.factory_id = "glidefactory"
        self.client_id = "glideclient"
        self.factoryclient_id = "glidefactoryclient"

        # String to prefix for the attributes
        self.glidein_attr_prefix = ""

        # String to prefix for the parameters
        self.glidein_param_prefix = "GlideinParam"
        self.encrypted_param_prefix = "GlideinEncParam"

        # String to prefix for the monitors
        self.glidein_monitor_prefix = "GlideinMonitor"

        # String to prefix for the requests
        self.client_req_prefix = "Req"

        # The name of the signtype
        self.factory_signtype_id = "SupportedSignTypes"


        # Should we use TCP for condor_advertise?
        self.advertise_use_tcp=False

        self.condor_reserved_names=("MyType","TargetType","GlideinMyType","MyAddress",'UpdatesHistory','UpdatesTotal','UpdatesLost','UpdatesSequenced','UpdateSequenceNumber','DaemonStartTime')


# global configuration of the module
frontendConfig=FrontendConfig()

#####################################################
# Exception thrown when multiple executions are used
# Helps handle partial failures

class MultiExeError(condorExe.ExeError):
    def __init__(self,arr): # arr is a list of ExeError exceptions
        self.arr=arr

        # First approximation of implementation, can be improved
        str_arr=[]
        for e in arr:
            str_arr.append('%s'%e)
        
        str=string.join(str_arr,'\\n')
        
        condorExe.ExeError.__init__(self,str)

############################################################
#
# User functions
#
############################################################

# can throw condorExe.ExeError
def findGlideins(factory_pool,factory_identity,
                 signtype,
                 additional_constraint=None,
                 have_proxy=False,
                 get_only_matching=True): # if this is false, return also glideins I cannot use
    global frontendConfig
    
    status_constraint='(GlideinMyType=?="%s")'%frontendConfig.factory_id
    if not ((factory_identity==None) or (factory_identity=='*')): # identity checking can be disabled, if really wanted
        # filter based on AuthenticatedIdentity
        status_constraint+=' && (AuthenticatedIdentity=?="%s")'%factory_identity

    if signtype!=None:
        status_constraint+=' && stringListMember("%s",%s)'%(signtype,frontendConfig.factory_signtype_id)

    if get_only_matching:
        if have_proxy:
            # must support secure message passing and must allow proxies
            status_constraint+='&& (PubKeyType=?="RSA") && (GlideinAllowx509_Proxy=!=False)'
        else:
            # cannot use factories that require a proxy
            status_constraint+='&& (GlideinRequirex509_Proxy=!=True)'

    if additional_constraint!=None:
        status_constraint="%s && (%s)"%(status_constraint,additional_constraint)
    status=condorMonitor.CondorStatus("any",pool_name=factory_pool)
    status.require_integrity(True) #important, especially for proxy passing

    status.load(status_constraint)

    data=status.fetchStored()

    reserved_names=frontendConfig.condor_reserved_names
    for k in reserved_names:
        if data.has_key(k):
            del data[k]

    out={}

    # copy over requests and parameters
    for k in data.keys():
        kel=data[k].copy()

        el={"params":{},"monitor":{}}

        # first remove reserved anmes
        for attr in reserved_names:
            if kel.has_key(attr):
                del kel[attr]

        # then move the parameters and monitoring
        for (prefix,eldata) in ((frontendConfig.glidein_param_prefix,el["params"]),
                              (frontendConfig.glidein_monitor_prefix,el["monitor"])):
            plen=len(prefix)
            for attr in kel.keys():
                if attr[:plen]==prefix:
                    eldata[attr[plen:]]=kel[attr]
                    del kel[attr]

        # what is left are glidein attributes
        el["attrs"]=kel
        
        out[k]=el

    return out

def findGlideinClientMonitoring(factory_pool,my_name,
                                additional_constraint=None):
    global frontendConfig
    
    status_constraint='(GlideinMyType=?="%s")'%frontendConfig.factoryclient_id
    if my_name!=None:
        status_constraint='%s && (ReqClientName=?="%s")'%my_name
    if additional_constraint!=None:
        status_constraint="%s && (%s)"%(status_constraint,additional_constraint)
    status=condorMonitor.CondorStatus("any",pool_name=factory_pool)
    status.load(status_constraint)

    data=status.fetchStored()

    reserved_names=frontendConfig.condor_reserved_names
    for k in reserved_names:
        if data.has_key(k):
            del data[k]

    out={}

    # copy over requests and parameters
    for k in data.keys():
        kel=data[k].copy()

        el={"params":{},"monitor":{}}

        # first remove reserved anmes
        for attr in reserved_names:
            if kel.has_key(attr):
                del kel[attr]

        # then move the parameters and monitoring
        for (prefix,eldata) in ((frontendConfig.glidein_param_prefix,el["params"]),
                              (frontendConfig.glidein_monitor_prefix,el["monitor"])):
            plen=len(prefix)
            for attr in kel.keys():
                if attr[:plen]==prefix:
                    eldata[attr[plen:]]=kel[attr]
                    del kel[attr]

        # what is left are glidein attributes
        el["attrs"]=kel
        
        out[k]=el

    return out

############################################
class FrontendDescriptNoGroup:
    def __init__(self,
                 my_name,frontend_name,
                 web_url, main_descript,
                 signtype, main_sign,
                 x509_proxies_data=None):
        self.my_name=my_name
        self.frontend_name=frontend_name
        self.web_url=web_url
        self.main_descript=main_descript
        self.signtype=signtype
        self.main_sign=main_sign
        self.x509_proxies_data=x509_proxies_data

    # returns a boolean
    def need_encryption(self):
        return self.x509_proxies_data!=None

    # return a list of strings
    def get_id_attrs(self):
        return ('ClientName = "%s"'%self.my_name,
                'FrontendName = "%s"'%self.frontend_name)

    def get_web_attrs(self):
        return ('WebURL = "%s"'%self.web_url,
                'WebSignType = "%s"'%self.signtype,
                'WebDescriptFile = "%s"'%self.main_descript,
                'WebDescriptSign = "%s"'%self.main_sign)

class FrontendDescript(FrontendDescriptNoGroup):
    def __init__(self,
                 my_name,frontend_name,group_name,
                 web_url, main_descript, group_descript,
                 signtype, main_sign, group_sign,
                 x509_proxies_data=None):
        FrontendDescriptNoGroup.__init__(self,my_name,frontend_name,
                                         web_url, main_descript,
                                         signtype, main_sign,
                                         x509_proxies_data)
        self.group_name=group_name
        self.group_descript=group_descript
        self.group_sign=group_sign

    # return a list of strings
    def get_id_attrs(self):
        return (FrontendDescriptNoGroup.get_id_attrs(self)+
                ('GroupName = "%s"\n'%self.group_name,))

    def get_web_attrs(self):
        return (FrontendDescriptNoGroup.get_web_attrs(self)+
                ('WebGroupURL = "%s"'%os.path.join(self.web_url,"group_%s"%self.group_name),
                 'WebGroupDescriptFile = "%s"'%self.group_descript,
                 'WebGroupDescriptSign = "%s"'%self.group_sign))

class FactoryKeys4Advertize:
    def __init__(self,
                 classad_identity,
                 factory_pub_key_id,factory_pub_key,
                 glidein_symKey=None): # if a symkey is not provided, or is not initialized, one will be generated
        self.classad_identity=classad_identity
        self.factory_pub_key_id=factory_pub_key_id
        self.factory_pub_key=factory_pub_key

        if glidein_symKey==None:
            glidein_symKey=symCrypto.SymAES256Key()
        if not glidein_symKey.is_valid():
            glidein_symKey=copy.deepcopy(glidein_symKey)
            glidein_symKey.new()
        self.glidein_symKey=glidein_symKey

    # returns a list of strings
    def get_key_attrs(self):
        glidein_symKey_str=self.glidein_symKey.get_code()
        
        return ('ReqPubKeyID = "%s"\n'%self.factory_pub_key_id,
                'ReqEncKeyCode = "%s"\n'%self.factory_pub_key.encrypt_hex(glidein_symKey_str),
                # this attribute will be checked against the AuthenticatedIdentity
                # this will prevent replay attacks, as only who knows the symkey can change this field
                # no other changes needed, as Condor provides integrity of the whole classAd
                'ReqEncIdentity = "%s"\n'%self.encrypt_hex(self.classad_identity))
    
    def encrypt_hex(self,str):
        return self.glidein_symKey.encrypt_hex(str)

# class for creating FactoryKeys4Advertize objects
# will reuse the symkey as much as possible
class Key4AdvertizeBuilder:
    def __init__(self):
        self.keys_cache={} # will contain a tuple of (key_obj,creation_time, last_access_time)

    def get_key_obj(self,
                    classad_identity,
                    factory_pub_key_id,factory_pub_key,
                    glidein_symKey=None): # will use one, if provided, but better to leave it blank and let the Builder create one
        # whoever can decrypt the pub key can anyhow get the symkey
        cache_id=factory_pub_key.get()

        if glidein_symKey!=None:
            # when a key is explicitly given, cannot reuse a cached one
            key_obj=FactoryKeys4Advertize(classad_identity,
                                        factory_pub_key_id,factory_pub_key,
                                          glidein_symKey)
            # but I can use it for others
            if not self.keys_cache.has_key(cache_id):
                now=time.time()
                self.keys_cache[cache_id]=[key_obj,now,now]
            return key_obj
        else:
            if self.keys_cache.has_key(cache_id):
                self.keys_cache[cache_id][2]=time.time()
                return  self.keys_cache[cache_id][0]
            else:
                key_obj=FactoryKeys4Advertize(classad_identity,
                                              factory_pub_key_id,factory_pub_key,
                                             glidein_symKey=None)
                now=time.time()
                self.keys_cache[cache_id]=[key_obj,now,now]
                return key_obj

    # clear the cache
    def clear(self,
              created_after=None,   # if not None, only clear entries older than this
              accessed_after=None): # if not None, only clear entries not accessed recently
        if (created_after==None) and (accessed_after==None):
            # just delete everything
            self.keys_cache={}
            return
        
        for cache_id in self.keys_cache.keys():
            # if at least one criteria is not satisfied, delete the entry
            delete_entry=False
            
            if created_after!=None:
                delete_entry = delete_entry or (self.keys_cache[cache_id][1]<created_after)

            if accessed_after!=None:
                delete_entry = delete_entry or (self.keys_cache[cache_id][2]<accessed_after)

            if delete_entry:
                del self.keys_cache[cache_id]

#######################################
# INTERNAL, do not use directly

class AdvertizeParams:
    def __init__(self,
                 request_name,glidein_name,
                 min_nr_glideins,max_run_glideins,
                 glidein_params={},glidein_monitors={},
                 glidein_params_to_encrypt=None,  # params_to_encrypt needs key_obj
                 security_name=None):             # needs key_obj
        self.request_name=request_name
        self.glidein_name=glidein_name
        self.min_nr_glideins=min_nr_glideins
        self.max_run_glideins=max_run_glideins
        self.glidein_params=glidein_params
        self.glidein_monitors=glidein_monitors
        self.glidein_params_to_encrypt=glidein_params_to_encrypt
        self.security_name=security_name

# Create file needed by advertize Work
def createAdvertizeWorkFile(fname,
                            descript_obj,            # must be of type FrontendDescriptNoGroup (or child)
                            params_obj,              # must be of type AdvertizeParams
                            key_obj=None):           # must be of type FactoryKeys4Advertize
    global frontendConfig

    fd=file(fname,"w")
    try:
        try:
            classad_name="%s@%s"%(params_obj.request_name,descript_obj.my_name)
            
            fd.write('MyType = "%s"\n'%frontendConfig.client_id)
            fd.write('GlideinMyType = "%s"\n'%frontendConfig.client_id)
            fd.write('Name = "%s"\n'%classad_name)
            fd.write(string.join(descript_obj.get_id_attrs(),'\n')+"\n")
            fd.write('ReqName = "%s"\n'%params_obj.request_name)
            fd.write('ReqGlidein = "%s"\n'%params_obj.glidein_name)

            fd.write(string.join(descript_obj.get_web_attrs(),'\n')+"\n")

            encrypted_params={} # none by default
            if key_obj!=None:
                fd.write(string.join(key_obj.get_key_attrs(),'\n')+"\n")

                glidein_params_to_encrypt=params_obj.glidein_params_to_encrypt
                if glidein_params_to_encrypt==None:
                    glidein_params_to_encrypt={}
                else:
                    glidein_params_to_encrypt=copy.deepcopy(glidein_params_to_encrypt)
                if params_obj.security_name!=None:
                    glidein_params_to_encrypt['SecurityName']=params_obj.security_name
                
                if descript_obj.x509_proxies_data!=None:
                    nr_proxies=len(descript_obj.x509_proxies_data)
                    glidein_params_to_encrypt['nr_x509_proxies']="%s"%nr_proxies
                    for i in range(nr_proxies):
                        x509_proxies_data_el=descript_obj.x509_proxies_data[i]
                        x509_proxy_idx=x509_proxies_data_el[0]
                        x509_proxy_data=x509_proxies_data_el[1]
                        glidein_params_to_encrypt['x509_proxy_%i_identifier'%i]="%s"%x509_proxy_idx
                        glidein_params_to_encrypt['x509_proxy_%i'%i]=x509_proxy_data
                        if len(x509_proxies_data_el)>2: # for backwards compatibility
                            x509_proxy_security_class=x509_proxies_data_el[2]
                            glidein_params_to_encrypt['x509_proxy_%i_security_class'%i]=str("%s"%x509_proxy_security_class)

                for attr in glidein_params_to_encrypt.keys():
                    encrypted_params[attr]=key_obj.encrypt_hex(glidein_params_to_encrypt["%s"%attr])
                        
            fd.write('ReqIdleGlideins = %i\n'%params_obj.min_nr_glideins)
            fd.write('ReqMaxRunningGlideins = %i\n'%params_obj.max_run_glideins)

            # write out both the params and monitors
            for (prefix,data) in ((frontendConfig.glidein_param_prefix,params_obj.glidein_params),
                                  (frontendConfig.glidein_monitor_prefix,params_obj.glidein_monitors),
                                  (frontendConfig.encrypted_param_prefix,encrypted_params)):
                for attr in data.keys():
                    el=data[attr]
                    if type(el)==type(1):
                        # don't quote ints
                        fd.write('%s%s = %s\n'%(prefix,attr,el))
                    else:
                        escaped_el=string.replace(string.replace(str(el),'"','\\"'),'\n','\\n')
                        fd.write('%s%s = "%s"\n'%(prefix,attr,escaped_el))
        finally:
            fd.close()
    except:
        # remove file in case of problems
        os.remove(fname)
        raise

# Given a file, advertize
# Can throw a CondorExe/ExeError exception
def advertizeWorkFromFile(factory_pool,
                          fname,
                          remove_file=True):
    try:
        exe_condor_advertise(fname,"UPDATE_MASTER_AD",factory_pool)
    finally:
        if remove_file:
            os.remove(fname)

# do the advertizing from start to end
# Can throw a CondorExe/ExeError exception
def advertizeWorkOnce(factory_pool,
                      tmpnam,                  # what fname should should i use
                      descript_obj,            # must be of type FrontendDescriptNoGroup (or child)
                      params_obj,              # must be of type AdvertizeParams
                      key_obj=None,            # must be of type FactoryKeys4Advertize
                      remove_file=True):
    createAdvertizeWorkFile(tmpnam,
                            descript_obj,params_obj,key_obj)
    advertizeWorkFromFile(factory_pool, tmpnam, remove_file)

# As above, but combine many together
# can throw a MultiExeError exception
def advertizeWorkMulti(factory_pool,
                       tmpnam,                 # what fname should should I use
                       descript_obj,           # must be of type FrontendDescriptNoGroup (or child)
                       paramkey_list):         # list of tuple (params_obj,key_obj)
    error_arr=[]
    for el in paramkey_list:
        params_obj,key_obj=el
        createAdvertizeWorkFile(tmpnam,
                                descript_obj,params_obj,key_obj)
        try:
            advertizeWorkFromFile(factory_pool, tmpnam, remove_file=True)
        except condorExe.ExeError, e:
            error_arr.append(e)
    if len(error_arr)>0:
        raise MultiExeError, error_arr

# END INTERNAL
########################################


# glidein_params is a dictionary of values to publish
#  like {"GLIDEIN_Collector":"myname.myplace.us","MinDisk":200000}
# similar for glidein_monitors
# Can throw condorExe.ExeError
def advertizeWork(factory_pool,
                  descript_obj,               # must be of type FrontendDescriptNoGroup (or child)
                  request_name,glidein_name,
                  min_nr_glideins,max_run_glideins,
                  glidein_params={},glidein_monitors={},
                  key_obj=None,                     # must be of type FactoryKeys4Advertize
                  glidein_params_to_encrypt=None,   # params_to_encrypt needs key_obj
                  security_name=None):              # needs key_obj
    params_obj=AdvertizeParams(request_name,glidein_name,
                               min_nr_glideins,max_run_glideins,
                               glidein_params,glidein_monitors,
                               glidein_params_to_encrypt,security_name)

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_aw_%li_%li"%(short_time,os.getpid())
    advertizeWorkOnce(factory_pool,tmpnam,descript_obj,params_obj,key_obj,remove_file=True)


class MultiAdvertizeWork:
    def __init__(self,
                 descript_obj):        # must be of type FrontendDescriptNoGroup (or child)
        self.descript_obj=descript_obj
        self.factory_queue={}          # will have a queue x factory, each element is list of tuples (params_obj, key_obj)

    # add a request to the list
    def add(self,
            factory_pool,
            request_name,glidein_name,
            min_nr_glideins,max_run_glideins,
            glidein_params={},glidein_monitors={},
            key_obj=None,                     # must be of type FactoryKeys4Advertize
            glidein_params_to_encrypt=None,   # params_to_encrypt needs key_obj
            security_name=None):              # needs key_obj
        params_obj=AdvertizeParams(request_name,glidein_name,
                                   min_nr_glideins,max_run_glideins,
                                   glidein_params,glidein_monitors,
                                   glidein_params_to_encrypt,security_name)
        if not self.factory_queue.has_key(factory_pool):
            self.factory_queue[factory_pool]=[]
        self.factory_queue[factory_pool].append((params_obj,key_obj))

    # retirn the queue depth
    def get_queue_len(self):
        count=0
        for factory_pool in self.factory_queue.keys():
            count+=len(self.factory_queue[factory_pool])
        return count

    # do the actual advertizing
    # can throw MultiExeError
    def do_advertize(self):
        error_arr=[]

        # get a 9 digit number that will stay 9 digit for the next 25 years
        short_time = time.time()-1.05e9
        idx=0
        for factory_pool in self.factory_queue.keys():
            idx=idx+1
            tmpnam="/tmp/gfi_aw_%li_%li_%li"%(short_time,os.getpid(),idx)
            
            # this should be done in parallel, but keep it serial for now
            try:
                advertizeWorkMulti(factory_pool,tmpnam,self.descript_obj,self.factory_queue[factory_pool])
            except MultiExeError, e:
                error_arr= error_arr + e.arr
        self.factory_queue={} # clean queue
        
        if len(error_arr)>0:
            raise MultiExeError, error_arr


# Remove ClassAd from Collector
def deadvertizeWork(factory_pool,
                    my_name,request_name):
    global frontendConfig

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_aw_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n'%frontendConfig.client_id)
            fd.write('Requirements = Name == "%s@%s"\n'%(request_name,my_name))
        finally:
            fd.close()

        exe_condor_advertise(tmpnam,"INVALIDATE_MASTER_ADS",factory_pool)
    finally:
        os.remove(tmpnam)

# Remove ClassAd from Collector
def deadvertizeAllWork(factory_pool,
                       my_name):
    global frontendConfig

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_aw_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n'%frontendConfig.client_id)
            fd.write('Requirements = ClientName == "%s"\n'%my_name)
        finally:
            fd.close()

        exe_condor_advertise(tmpnam,"INVALIDATE_MASTER_ADS",factory_pool)
    finally:
        os.remove(tmpnam)

############################################################
#
# I N T E R N A L - Do not use
#
############################################################

def pool2str(pool_name):
    if pool_name==None:
        return ""
    else:
        return "-pool %s "%pool_name

def usetcp2str(use_tcp):
    if use_tcp:
        return ""
    else:
        return "-tcp "


def exe_condor_advertise(fname,command,
                         factory_pool):
    return condorExe.exe_cmd("../sbin/condor_advertise","%s%s %s%s"%(usetcp2str(frontendConfig.advertise_use_tcp),command,pool2str(factory_pool),fname))
    
