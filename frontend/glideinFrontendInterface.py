#
# Project:
#   glideinWMS
#
# File Version: 
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
import condorManager
import os,os.path
import copy
import time
import string
import pubCrypto,symCrypto
from sets import Set

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

        #Default the glideinWMS version string
        self.glideinwms_version = "glideinWMS UNKNOWN"

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
        # Should we use the new -multiple for condor_advertise?
        self.advertise_use_multi=False

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
# Global Variables
#
############################################################

# Advertize counter for glideclient
advertizeGCCounter = {}

# Advertize counter for glideresource
advertizeGRCounter = {}

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
                 web_url, monitoring_web_url, main_descript,
                 signtype, main_sign,
                 x509_proxies_data=None):
        self.my_name=my_name
        self.frontend_name=frontend_name
        self.web_url=web_url
        self.monitoring_web_url=monitoring_web_url
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
                 web_url, monitoring_web_url, main_descript, group_descript,
                 signtype, main_sign, group_sign,
                 x509_proxies_data=None):
        FrontendDescriptNoGroup.__init__(self,my_name,frontend_name,
                                         web_url, monitoring_web_url, main_descript,
                                         signtype, main_sign,
                                         x509_proxies_data)
        self.group_name=group_name
        self.group_descript=group_descript
        self.group_sign=group_sign

    # return a list of strings
    def get_id_attrs(self):
        return (FrontendDescriptNoGroup.get_id_attrs(self)+
                ('GroupName = "%s"'%self.group_name,))

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
        
        return ('ReqPubKeyID = "%s"'%self.factory_pub_key_id,
                'ReqEncKeyCode = "%s"'%self.factory_pub_key.encrypt_hex(glidein_symKey_str),
                # this attribute will be checked against the AuthenticatedIdentity
                # this will prevent replay attacks, as only who knows the symkey can change this field
                # no other changes needed, as Condor provides integrity of the whole classAd
                'ReqEncIdentity = "%s"'%self.encrypt_hex(self.classad_identity))
    
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
                 security_name=None,              # needs key_obj
                 remove_excess_str=None):
        self.request_name=request_name
        self.glidein_name=glidein_name
        self.min_nr_glideins=min_nr_glideins
        self.max_run_glideins=max_run_glideins
        if remove_excess_str==None:
            remove_excess_str="NO"
        elif not (remove_excess_str in ("NO","WAIT","IDLE","ALL","UNREG")):
            raise RuntimeError, 'Invalid remove_excess_str(%s), valid values are "NO","WAIT","IDLE","ALL","UNREG"'%remove_excess_str
        self.remove_excess_str=remove_excess_str
        self.glidein_params=glidein_params
        self.glidein_monitors=glidein_monitors
        self.glidein_params_to_encrypt=glidein_params_to_encrypt
        self.security_name=security_name

def createAdvertizeWorkFile(fname, descript_obj, params_obj,
                            key_obj=None, do_append=False):

    """
    Create file needed by advertize Work

    @type fname: string
    @param fname: Filename for the classad

    @type descript_obj: FrontendDescriptNoGroup (or child)
    @param descript_obj: Description object

    @type params_obj: AdvertizeParams
    @param params_obj: Params object

    @type key_obj: FactoryKeys4Advertize
    @param key_obj: Factory Keys to advertize object

    @type do_append: bool
    @param do_append: True in case of multiclassad file else False
    """

    global frontendConfig
    global advertizeGCCounter

    if do_append:
        open_type="a"
    else:
        open_type="w"

    fd=file(fname,open_type)
    try:
        try:
            classad_name="%s@%s"%(params_obj.request_name,descript_obj.my_name)

            fd.write('MyType = "%s"\n'%frontendConfig.client_id)
            fd.write('GlideinMyType = "%s"\n'%frontendConfig.client_id)
            fd.write('GlideinWMSVersion = "%s"\n'%frontendConfig.glideinwms_version)
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
            fd.write('ReqRemoveExcess = "%s"\n'%params_obj.remove_excess_str)
            fd.write('WebMonitoringURL = "%s"\n'%descript_obj.monitoring_web_url)

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

            # Update Sequence number information
            if advertizeGCCounter.has_key(classad_name):
                advertizeGCCounter[classad_name] += 1
            else:
                advertizeGCCounter[classad_name] = 0
            fd.write('UpdateSequenceNumber = %s\n' % advertizeGCCounter[classad_name])
            # add a final empty line... useful when appending
            fd.write('\n')
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
                          remove_file=True,
                          is_multi=False):
    try:
        exe_condor_advertise(fname,"UPDATE_MASTER_AD",factory_pool,is_multi=is_multi)
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
                            descript_obj,params_obj,key_obj,
                            do_append=False)
    advertizeWorkFromFile(factory_pool, tmpnam, remove_file)

# As above, but combine many together
# can throw a MultiExeError exception
def advertizeWorkMulti(factory_pool,
                       tmpnam,                 # what fname should should I use
                       descript_obj,           # must be of type FrontendDescriptNoGroup (or child)
                       paramkey_list):         # list of tuple (params_obj,key_obj)
    if frontendConfig.advertise_use_multi:
        return advertizeWorkMulti_multi(factory_pool,tmpnam,descript_obj,paramkey_list)
    else:
        return advertizeWorkMulti_iterate(factory_pool,tmpnam,descript_obj,paramkey_list)

# INTERNAL2
def advertizeWorkMulti_iterate(factory_pool,
                               tmpnam,
                               descript_obj,
                               paramkey_list):
    error_arr=[]
    for el in paramkey_list:
        params_obj,key_obj=el
        createAdvertizeWorkFile(tmpnam,
                                descript_obj,params_obj,key_obj,
                                do_append=False)
        try:
            advertizeWorkFromFile(factory_pool, tmpnam, remove_file=True)
        except condorExe.ExeError, e:
            error_arr.append(e)
    if len(error_arr)>0:
        raise MultiExeError, error_arr

# INTERNAL2
def advertizeWorkMulti_multi(factory_pool,
                             tmpnam,
                             descript_obj,
                             paramkey_list):
    ap=False
    for el in paramkey_list:
        params_obj,key_obj=el
        createAdvertizeWorkFile(tmpnam,
                                descript_obj,params_obj,key_obj,
                                do_append=ap)
        ap=True # Append from here on
    
    if ap: # if true, there is at least one el -> file has been created
        try:
            advertizeWorkFromFile(factory_pool, tmpnam, remove_file=True,is_multi=True)
        except condorExe.ExeError, e:
            # the parent expects a MultiError
            raise MultiExeError,[e]


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
                  security_name=None,               # needs key_obj
                  remove_excess_str=None):
    params_obj=AdvertizeParams(request_name,glidein_name,
                               min_nr_glideins,max_run_glideins,
                               glidein_params,glidein_monitors,
                               glidein_params_to_encrypt,security_name,
                               remove_excess_str)

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
            security_name=None,               # needs key_obj
            remove_excess_str=None):
        params_obj=AdvertizeParams(request_name,glidein_name,
                                   min_nr_glideins,max_run_glideins,
                                   glidein_params,glidein_monitors,
                                   glidein_params_to_encrypt,security_name,
                                   remove_excess_str)
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


###############################################################################
# Code to advertise resource classads to the User Pool
###############################################################################

class Classad:
    """
    Base class describing a classad.
    """
    
    def __init__(self, type, advertiseCmd, invalidateCmd):
        """
        Constructor

        @type type: string 
        @param type: Type of the classad
        @type advertiseCmd: string 
        @param advertiseCmd: Condor update-command to advertise this classad 
        @type invalidateCmd: string 
        @param invalidateCmd: Condor update-command to invalidate this classad 
        """
        
        global frontendConfig

        self.adType = type
        self.adAdvertiseCmd = advertiseCmd
        self.adInvalidateCmd = invalidateCmd
        
        self.adParams = {}
        self.adParams['MyType'] = self.adType
        self.adParams['GlideinMyType'] = self.adType
        self.adParams['GlideinWMSVersion'] = frontendConfig.glideinwms_version

    def __str__(self):
        """
        String representation of the classad.
        """
        
        ad = ""
        for param in self.adParams.keys():
            if isinstance(self.adParams[param], str):
                escaped_str=self.adParams[param].replace("\"","\\\"")
                ad += '%s = "%s"\n' % (param, escaped_str)
            elif isinstance(self.adParams[param], unicode):
                escaped_str=self.adParams[param].replace("\"","\\\"")
                ad += '%s = "%s"\n' % (param, escaped_str)
            else:
                ad += '%s = %s\n' % (param, self.adParams[param])  
        return ad


class ResourceClassad(Classad):
    """
    This class describes the resource classad. Frontend advertises the 
    resource classad to the user pool as an UPDATE_AD_GENERIC type classad
    """
    
    def __init__(self, factory_ref, frontend_ref):
        """
        Class Constructor

        @type factory_ref: string 
        @param factory_ref: Name of the resource in the glidefactory classad
        @type frontend_ref: string 
        @param type: Name of the resource in the glideclient classad
        """

        global advertizeGRCounter

        Classad.__init__(self, 'glideresource', 'UPDATE_AD_GENERIC',
                         'INVALIDATE_ADS_GENERIC')
        
        self.adParams['GlideFactoryName'] = "%s" % factory_ref
        self.adParams['GlideClientName'] = "%s" % frontend_ref
        self.adParams['Name'] = "%s@%s" % (factory_ref, frontend_ref)
        self.adParams['GLIDEIN_In_Downtime'] = 'False'

        if advertizeGRCounter.has_key(self.adParams['Name']):
            advertizeGRCounter[self.adParams['Name']] += 1
        else:       
            advertizeGRCounter[self.adParams['Name']] = 0
        self.adParams['UpdateSequenceNumber'] = advertizeGRCounter[self.adParams['Name']]


    def setInDownTime(self, downtime):
        """
        Set the downtime flag for the resource in the classad

        @type downtime: bool
        @param downtime: True if the entry is in down time.
        """
        self.adParams['GLIDEIN_In_Downtime'] = str(downtime)


    def setGlideClientMonitorInfo(self, monitorInfo):
        """
        Set the GlideClientMonitor* for the resource in the classad
        
        @type monitorInfo: list 
        @param monitorInfo: GlideClientMonitor information.
        """
        if len(monitorInfo) == 13:
            self.adParams['GlideClientMonitorJobsIdle'] = monitorInfo[0]
            self.adParams['GlideClientMonitorJobsIdleMatching'] = monitorInfo[1]
            self.adParams['GlideClientMonitorJobsIdleEffective'] = monitorInfo[2]
            self.adParams['GlideClientMonitorJobsIdleOld'] = monitorInfo[3]
            self.adParams['GlideClientMonitorJobsIdleUnique'] = monitorInfo[4]
            self.adParams['GlideClientMonitorJobsRunning'] = monitorInfo[5]
            self.adParams['GlideClientMonitorJobsRunningHere'] = monitorInfo[6]
            self.adParams['GlideClientMonitorJobsRunningMax'] = monitorInfo[7]
            self.adParams['GlideClientMonitorGlideinsTotal'] = monitorInfo[8]
            self.adParams['GlideClientMonitorGlideinsIdle'] = monitorInfo[9]
            self.adParams['GlideClientMonitorGlideinsRunning'] = monitorInfo[10]
            self.adParams['GlideClientMonitorGlideinsRequestIdle'] = monitorInfo[11]
            self.adParams['GlideClientMonitorGlideinsRequestMaxRun'] = monitorInfo[12]
        else:
            raise RuntimeError, 'Glide client monitoring structure changed. Resource ad may have incorrect GlideClientMonitor values'
    

    def setEntryInfo(self, info):
        """
        Set the useful entry specific info for the resource in the classad

        @type info: dict 
        @param info: Useful info from the glidefactory classad  
        """
        
        eliminate_attrs = Set([
                 'CurrentTime', 'USE_CCB', 'PubKeyValue', 'PubKeyType',
                 'AuthenticatedIdentity', 'GlideinName', 'FactoryName', 
                 'EntryName', 'GlideinWMSVersion', 'PubKeyObj', 
                 'LastHeardFrom', 'PubKeyID', 'SupportedSignTypes',
                 'GLIDEIN_In_Downtime'
                ])
        available_attrs = Set(info.keys())
        publish_attrs = available_attrs - eliminate_attrs
        for attr in publish_attrs:
            self.adParams[attr] = info[attr]

    
    def setGlideFactoryMonitorInfo(self, info):
        """
        Set the GlideinFactoryMonitor* for the resource in the classad

        @type info: string 
        @param info: Useful information from the glidefactoryclient classad
        """
        
        # Required keys do not start with TotalClientMonitor but only
        # start with Total. Substitute Total with GlideFactoryMonitor
        # and put it in the classad
        
        for key in info.keys():
            if not key.startswith('TotalClientMonitor'):
                if key.startswith('Total'):
                    ad_key = key.replace('Total', 'GlideFactoryMonitor', 1)
                    self.adParams[ad_key] = info[key]
    
    
class ResourceClassadAdvertiser:
    """
    Class to handle the advertisement of resource classads to the user pool
    """


    def __init__(self, pool=None, multi_support=False):
        """
        Constructor

        @type pool: string 
        @param pool: Collector address
        @type multi_support: bool 
        @param multi_support: True if the installation support advertising multiple classads with one condor_advertise command. Defaults to False.
        """
        
        # Dictionary of classad objects
        self.classads = {}
        self.pool = pool
        self.multiAdvertiseSupport = multi_support
        self.adType = 'glideresource'
        self.adAdvertiseCmd = 'UPDATE_AD_GENERIC'
        self.adInvalidateCmd = 'INVALIDATE_ADS_GENERIC'
        self.multiClassadDelimiter = '\n'


    def addClassad(self, name, ad_obj):
        """
        Adds the classad to the classad dictionary
        
        @type name: string 
        @param name: Name of the classad
        @type ad_obj: ClassAd
        @param ad_obj: Actual classad object
        """

        self.classads[name] = ad_obj
    

    def classadToFile(self, ad):
        """
        Write classad to the file and return the filename
        
        @type ad: string 
        @param ad: Name of the classad
        
        @rtype: string
        @return: Name of the file
        """
        
        # get a 9 digit number that will stay 9 digit for next 25 years
        short_time = time.time() - 1.05e9
        fname = "/tmp/gfi_ar_%li_%li" % (short_time, os.getpid())
        try:
            fd = file(fname, "w")
        except:
            return ""
        
        try:
            fd.write("%s" % self.classads[ad])
        finally:
            fd.close()
        
        return fname


    def classadsToFile(self, ads):
        """
        Write multiple classads to a file and return the filename. 
        Use only when multi advertise is supported by condor.
        
        @type ads: list
        @param ads: Classad names
        
        @rtype: string
        @return: Filename containing all the classads to advertise
        """
        
        # get a 9 digit number that will stay 9 digit for next 25 years
        short_time = time.time() - 1.05e9
        fname = "/tmp/gfi_ar_%li_%li" % (short_time, os.getpid())
        
        try:
            fd = file(fname, "w")
        except:
            return ""
        
        try:
            for ad in ads:
                fd.write('%s' % self.classads[ad])
                # Append an empty line for advertising multiple classads
                fd.write(self.multiClassadDelimiter)
        finally:
            fd.close()
        
        return fname


    def doAdvertise(self, fname):
        """
        Do the actual advertisement of classad(s) in the file

        @type fname: string
        @param fname: File name containing classad(s)
        """

        if (fname) and (fname != ""):
            try:
                exe_condor_advertise(fname, self.adAdvertiseCmd,
                                     self.pool,
                                     is_multi=self.multiAdvertiseSupport)
            finally:
                os.remove(fname)
        else:
            raise RuntimeError, 'Failed advertising %s classads' % self.adType

    def advertiseClassads(self, ads=None):
        """
        Advertise multiple classads to the pool

        @type ads: list
        @param ads: classad names to advertise
        """

        if (ads == None) or (len(ads) == 0) :
            return

        if self.multiAdvertiseSupport:
            fname = self.classadsToFile(ads)
            self.doAdvertise(fname)
        else:
            for ad in ads:
                self.advertiseClassad(ad)

    
    def advertiseClassad(self, ad):
        """
        Advertise the classad to the pool
        
        @type ad: string 
        @param ad: Name of the classad
        """

        fname = self.classadToFile(ad)
        self.doAdvertise(fname)
    
    
    def advertiseAllClassads(self):
        """
        Advertise all the known classads to the pool
        """
        
        self.advertiseClassads(self.classads.keys())
    
    
    def invalidateClassad(self, ad):
        """
        Invalidate the classad from the pool
        
        @type type: string 
        @param type: Name of the classad
        """

        global frontendConfig
    
        # get a 9 digit number that will stay 9 digit for next 25 years
        short_time = time.time() - 1.05e9
        tmpnam = "/tmp/gfi_ar_%li_%li" % (short_time, os.getpid())
        fd = file(tmpnam,"w")
        try:
            try:
                fd.write('MyType = "Query"\n')
                fd.write('TargetType = "%s"\n' % self.classads[ad].adType)
                fd.write('Requirements = Name == "%s"\n' % ad)
            finally:
                fd.close()
    
            exe_condor_advertise(tmpnam, self.classads[ad].adInvalidateCmd, 
                                 self.pool,
                                 is_multi=self.multiAdvertiseSupport)
        finally:
            os.remove(tmpnam)

    
    def invalidateAllClassads(self):
        """
        Invalidate all the known classads
        """

        for ad in self.classads.keys():
            self.invalidateClassad(ad)


    def invalidateConstrainedClassads(self, constraint):
        """
        Invalidate classads from the pool matching the given constraints
        
        @type type: string 
        @param type: Condor constraints for filtering the classads
        """

        global frontendConfig
    
        # get a 9 digit number that will stay 9 digit for next 25 years
        short_time = time.time() - 1.05e9
        tmpnam = "/tmp/gfi_ar_%li_%li" % (short_time, os.getpid())
        fd = file(tmpnam,"w")
        try:
            try:
                fd.write('MyType = "Query"\n')
                fd.write('TargetType = "%s"\n' % self.adType)
                fd.write('Requirements = %s' % constraint)
            finally:
                fd.close()
    
            exe_condor_advertise(tmpnam, self.adInvalidateCmd, 
                                 self.pool,
                                 is_multi=self.multiAdvertiseSupport)
        finally:
            os.remove(tmpnam)

        
    def getAllClassads(self):
        """
        Return all the known classads
        
        @rtype: string
        @return: All the known classads delimited by empty line 
        """

        ads = ""
        
        for ad in self.classads.keys():
            ads = "%s%s\n" % (ads, self.classads[ad]) 
        return ads

############################################################
#
# I N T E R N A L - Do not use
#
############################################################

def exe_condor_advertise(fname,command, pool, is_multi=False):
    return condorManager.condorAdvertise(fname, command, 
                                         frontendConfig.advertise_use_tcp,
                                         is_multi, pool)
