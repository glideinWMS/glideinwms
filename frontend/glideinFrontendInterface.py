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

import os
import sys
import copy
import calendar
import time
import string
import re

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../lib"))

from glideinwms.lib import pubCrypto,symCrypto
from glideinwms.lib import condorExe
from glideinwms.lib import condorMonitor
from glideinwms.lib import condorManager
from glideinwms.lib import classadSupport
from glideinwms.lib import logSupport

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
        self.factory_global = "glidefactoryglobal"
        self.client_id = "glideclient"
        self.client_global = "glideclientglobal"
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
        self.advertise_use_tcp = False
        # Should we use the new -multiple for condor_advertise?
        self.advertise_use_multi = False

        self.condor_reserved_names = ("MyType", "TargetType", "GlideinMyType", "MyAddress", 'UpdatesHistory', 'UpdatesTotal', 'UpdatesLost', 'UpdatesSequenced', 'UpdateSequenceNumber', 'DaemonStartTime')


# global configuration of the module
frontendConfig = FrontendConfig()

#####################################################
# Exception thrown when multiple executions are used
# Helps handle partial failures

class MultiExeError(condorExe.ExeError):
    def __init__(self, arr): # arr is a list of ExeError exceptions
        self.arr = arr

        # First approximation of implementation, can be improved
        str_arr = []
        for e in arr:
            str_arr.append('%s' % e)

        str = string.join(str_arr, '\\n')

        condorExe.ExeError.__init__(self, str)

############################################################
#
# Global Variables
#
############################################################

# Advertize counter for glideclient
advertizeGCCounter = {}

# Advertize counter for glideclientglobal
advertizeGCGounter = {}

# Advertize counter for glideresource
advertizeGRCounter = {}

# Advertize counter for glidefrontendmonitor
advertizeGFMCounter = {}

############################################################
#
# User functions
#
############################################################
def findGlobals(pool_name, auth_identity, classad_type,
                additional_constraint=None): 
    """
    Query the given pool to find the globals classad.
    Can be used to query glidefactoryglobal and glidefrontendglobal classads.
    """

    status_constraint = '(GlideinMyType=?="%s")' % classad_type

    # identity checking can be disabled, if really wanted
    if not ((auth_identity is None) or (auth_identity=='*')):
        # filter based on AuthenticatedIdentity
        status_constraint += ' && (AuthenticatedIdentity=?="%s")' % auth_identity

    if additional_constraint is not None:
        status_constraint = '%s && (%s)' % (status_constraint,
                                            additional_constraint)

    status = condorMonitor.CondorStatus('any', pool_name=pool_name)
    #important, especially for proxy passing
    status.require_integrity(True)
    status.load(status_constraint)
    data = status.fetchStored()

    return format_condor_dict(data)
    

def findMasterFrontendClassads(pool_name, frontend_name):
    """
    Query the given pool to find master frontend classads
    """

    status_constraint = '(GlideinMyType=?="%s")||(GlideinMyType=?="%s")' % ('glideclientglobal', 'glideclient')
    frontend_constraint = '(FrontendName=?="%s")&&(FrontendHAMode=!="slave")' % frontend_name

    status = condorMonitor.CondorStatus('any', pool_name=pool_name)
    #important, especially for proxy passing
    status.require_integrity(True)
    status.load('(%s)&&(%s)' % (status_constraint, frontend_constraint))
    data = status.fetchStored()

    return format_condor_dict(data)


# can throw condorExe.ExeError
def findGlideins(factory_pool, factory_identity,
                 signtype, additional_constraint=None):
    global frontendConfig

    status_constraint = '(GlideinMyType=?="%s")' % frontendConfig.factory_id

    # identity checking can be disabled, if really wanted
    if not ((factory_identity is None) or (factory_identity == '*')):
        # filter based on AuthenticatedIdentity
        status_constraint += ' && (AuthenticatedIdentity=?="%s")' % factory_identity

    if signtype is not None:
        status_constraint += ' && stringListMember("%s",%s)' % (signtype, frontendConfig.factory_signtype_id)

    # Note that Require and Allow x509_Proxy has been replaced by credential
    # type and trust domain

    if additional_constraint is not None:
        status_constraint += ' && (%s)' % additional_constraint

    status = condorMonitor.CondorStatus("any", pool_name=factory_pool)
    status.require_integrity(True) #important, especially for proxy passing
    status.load(status_constraint)

    data = status.fetchStored()
    return format_condor_dict(data)


def findGlideinClientMonitoring(factory_pool, factory_identity,
                                my_name, additional_constraint=None):
    global frontendConfig

    status_constraint = '(GlideinMyType=?="%s")' % frontendConfig.factoryclient_id

    # identity checking can be disabled, if really wanted
    if not ((factory_identity is None) or (factory_identity == '*')):
        # filter based on AuthenticatedIdentity
        status_constraint += ' && (AuthenticatedIdentity=?="%s")' % factory_identity

    if my_name is not None:
        status_constraint += ' && (ReqClientName=?="%s")' % my_name

    if additional_constraint is not None:
        status_constraint += ' && (%s)' % additional_constraint
    status = condorMonitor.CondorStatus("any", pool_name=factory_pool)
    status.load(status_constraint)

    data = status.fetchStored()
    return format_condor_dict(data)


def format_condor_dict(data):
    """
    Formats the data from the condor call.
    """

    reserved_names = frontendConfig.condor_reserved_names
    for k in reserved_names:
        if data.has_key(k):
            del data[k]

    out = {}

    for k in data.keys():
        kel = data[k].copy()

        el = {"params":{}, "monitor":{}}

        # first remove reserved anmes
        for attr in reserved_names:
            if kel.has_key(attr):
                del kel[attr]

        # then move the parameters and monitoring
        for (prefix, eldata) in ((frontendConfig.glidein_param_prefix, el["params"]),
                              (frontendConfig.glidein_monitor_prefix, el["monitor"])):
            plen = len(prefix)
            for attr in kel.keys():
                if attr[:plen] == prefix:
                    eldata[attr[plen:]] = kel[attr]
                    del kel[attr]

        # what is left are glidein attributes
        el["attrs"] = kel

        out[k] = el

    return out

############################################

# TODO: PM
# At some point we should change this class to watch for credential file 
# updates and cache the contents/info between updates. This should further 
# reduce calls to openssl and maintain consistency of credential info
# between cycles. If the file does not change the info in it remains same.
# This also means that the credential objects should be created much before
# and not for every iteration.

class Credential:
    def __init__(self, proxy_id, proxy_fname, elementDescript):
        self.req_idle=0
        self.req_max_run=0
        self.advertize=False

        proxy_security_classes=elementDescript.merged_data['ProxySecurityClasses']
        proxy_trust_domains=elementDescript.merged_data['ProxyTrustDomains']
        proxy_types=elementDescript.merged_data['ProxyTypes']
        proxy_keyfiles=elementDescript.merged_data['ProxyKeyFiles']
        proxy_pilotfiles=elementDescript.merged_data['ProxyPilotFiles']
        proxy_vm_ids = elementDescript.merged_data['ProxyVMIds']
        proxy_vm_types = elementDescript.merged_data['ProxyVMTypes']
        proxy_creation_scripts = elementDescript.merged_data['ProxyCreationScripts']
        proxy_update_frequency = elementDescript.merged_data['ProxyUpdateFrequency']
        proxy_vmid_fname=elementDescript.merged_data['ProxyVMIdFname']
        proxy_vmtype_fname=elementDescript.merged_data['ProxyVMTypeFname']

        self.proxy_id = proxy_id
        self.filename = proxy_fname
        self.type = proxy_types.get(proxy_fname, "Unknown")
        self.security_class = proxy_security_classes.get(proxy_fname, proxy_id)
        self.trust_domain = proxy_trust_domains.get(proxy_fname, "None")
        self.update_frequency = int(proxy_update_frequency.get(proxy_fname, -1))

        # Following items can be None
        self.vm_id_fname   = proxy_vmid_fname.get(proxy_fname)
        self.vm_type_fname = proxy_vmtype_fname.get(proxy_fname)
        self.vm_id = proxy_vm_ids.get(proxy_fname)
        self.vm_type = proxy_vm_types.get(proxy_fname)
        self.creation_script = proxy_creation_scripts.get(proxy_fname)
        self.key_fname = proxy_keyfiles.get(proxy_fname)
        self.pilot_fname = proxy_pilotfiles.get(proxy_fname)

        # Will be initialized when getId() is called
        self._id = None


    def getId(self, recreate=False):
        """
        Generate the Credential id if we do not have one already
        Since the Id is dependent on the credential content for proxies
        recreate them if asked to do so
        """

        if (not self._id) or recreate:
            # Create the credential id
            self.create()
            self._id = self.file_id(self.getIdFilename())
        return self._id
   

    def getIdFilename(self):
        """
        Get credential file used to generate the credential id
        """

        # This checks seem hacky. Ideally checking against the credetnial type
        # to get the filename is right thing to do

        cred_file = None
        if self.filename:
            cred_file = self.filename
        elif self.key_fname:
            cred_file = self.key_fname
        elif self.pilot_fname:
            cred_file = self.pilot_fname
        return cred_file


    def create(self):
        """
        Generate the credential
        """

        if self.creation_script:
            logSupport.log.debug("Creating credential using %s" % (self.creation_script))
            try:
                condorExe.iexe_cmd(self.creation_script)
            except:
                logSupport.log.exception("Creating credential using %s failed" % (self.creation_script))
                self.advertize = False

            # Recreating the credential can result in ID change
            self._id = self.file_id(self.getIdFilename())


    def createIfNotExist(self):
        """
        Generate the credential if it does not exists.
        """

        if self.filename and (not os.path.exists(self.filename)):
            logSupport.log.debug("Credential %s does not exist." % (self.filename))
            self.create()


    def getString(self, cred_file=None):
        """
        Based on the type of credentials read appropriate files and return
        the credentials to advertise as a string. The output should be
        encrypted by the caller as required.
        """

        cred_data = ''
        if not cred_file:
            # If not file specified, assume the file used to generate Id
            cred_file = self.getIdFilename()
        try:
            data_fd = open(cred_file)
            cred_data = data_fd.read()
            data_fd.close()
        except:
            # This credential should not be advertised
            self.advertize = False
            logSupport.log.exception("Failed to read credential %s: " % cred_file)
        return cred_data


    # PM: Why are the usage details part of Credential Class?
    #     This is overloading the purpose of Credential Class
    def add_usage_details(self,req_idle=0,req_max_run=0):
        self.req_idle=req_idle
        self.req_max_run=req_max_run
        

    def get_usage_details(self):
        return (self.req_idle,self.req_max_run)
    

    def file_id(self,filename,ignoredn=False):
        if (("grid_proxy" in self.type) and not ignoredn):
            dn_list = condorExe.iexe_cmd("openssl x509 -subject -in %s -noout" % (filename))
            dn = dn_list[0]
            hash_str=filename+dn
        else:
            hash_str=filename
        #logSupport.log.debug("Using hash_str=%s (%d)"%(hash_str,abs(hash(hash_str))%1000000))
        return str(abs(hash(hash_str))%1000000)


    def time_left(self):
        """
        Returns the time left if a grid proxy
        If missing, returns 0
        If not a grid proxy or other unidentified error, return -1
        """
        if (not os.path.exists(self.filename)):
            return 0

        if ("grid_proxy" in self.type) or ("cert_pair" in self.type):
            time_list=condorExe.iexe_cmd("openssl x509 -in %s -noout -enddate" % self.filename)
            if "notAfter=" in time_list[0]:
                time_str=time_list[0].split("=")[1].strip()
                timeleft=calendar.timegm(time.strptime(time_str,"%b %d %H:%M:%S %Y %Z"))-int(time.time())
            return timeleft
        else:
            return -1


    def renew(self):
        """
        Renews credential if time_left()<update_frequency
        Only works if type is grid_proxy or creation_script is provided
        """
        remaining=self.time_left()
        if ( (remaining !=-1) and (self.update_frequency!=-1) and 
             (remaining<self.update_frequency) ): 
            self.create()


    def __str__(self):
        output = ""
        output += "id = %s\n" % self.getId()
        output += "proxy_id = %s\n" % self.proxy_id
        output += "req_idle = %s\n" % self.req_idle
        output += "req_max_run = %s\n" % self.req_max_run
        output += "filename = %s\n" % self.filename
        output += "type = %s\n" % self.type
        output += "security_class = %s\n" % self.security_class
        output += "trust_domain = %s\n" % self.trust_domain
        #output += "proxy_data = %s\n" % self.getString(cred_file=self.filename)
        try:
            output += "key_fname = %s\n" % self.key_fname
            #output += "key_data = %s\n" % self.getString(cred_file=self.key_fname)
            #output += "key_data = %s\n" % self.key_data
            output += "pilot_fname = %s\n" % self.pilot_fname
            #output += "pilot_data = %s\n" % self.getString(cred_file=self.pilot_fname)
        except:
            pass
        output += "vm_id = %s\n" % self.vm_id
        output += "vm_type = %s\n" % self.vm_type        
        
        return output

# PM: Credential.getId() should be much faster way of geting the Id
#     Maybe CredentialCache is now obsolete? Can we get rid of it?

class CredentialCache:
    def __init__(self):
        self.file_id_cache={}

    def file_id(self,credential_el,filename):
        k=(credential_el.type,filename)
        if not (k in self.file_id_cache):
            self.file_id_cache[k] = credential_el.file_id(filename)
        return self.file_id_cache[k]

class FrontendDescript:
    def __init__(self,
                 my_name,frontend_name,group_name,
                 web_url, main_descript, group_descript,
                 signtype, main_sign, group_sign,
                 x509_proxies_plugin=None, ha_mode='master'):
        self.my_name=my_name
        self.frontend_name=frontend_name
        self.web_url=web_url
        self.monitoring_web_url=web_url.replace("stage","monitor")
        self.main_descript=main_descript
        self.signtype=signtype
        self.main_sign=main_sign
        self.x509_proxies_plugin=x509_proxies_plugin
        self.group_name=group_name
        self.group_descript=group_descript
        self.group_sign=group_sign
        self.ha_mode=ha_mode

    # Accessor method for monitoring web url
    def add_monitoring_url(self, monitoring_web_url):
        self.monitoring_web_url=monitoring_web_url 

    def need_encryption(self):
        return self.x509_proxies_plugin is not None

    # return a list of strings
    def get_id_attrs(self):
        return ('ClientName = "%s"'%self.my_name,
                'FrontendName = "%s"'%self.frontend_name,
                'FrontendHAMode = "%s"'%self.ha_mode,
                'GroupName = "%s"'%self.group_name)

    def get_web_attrs(self):
        return ('WebURL = "%s"'%self.web_url,
                'WebSignType = "%s"'%self.signtype,
                'WebDescriptFile = "%s"'%self.main_descript,
                'WebDescriptSign = "%s"'%self.main_sign,
                'WebGroupURL = "%s"'%os.path.join(self.web_url,"group_%s"%self.group_name),
                'WebGroupDescriptFile = "%s"'%self.group_descript,
                'WebGroupDescriptSign = "%s"'%self.group_sign)


class FactoryKeys4Advertize:
    def __init__(self,
                 classad_identity,
                 factory_pub_key_id, factory_pub_key,
                 glidein_symKey=None): # if a symkey is not provided, or is not initialized, one will be generated
        self.classad_identity = classad_identity
        self.factory_pub_key_id = factory_pub_key_id
        self.factory_pub_key = factory_pub_key

        if glidein_symKey is None:
            glidein_symKey = symCrypto.SymAES256Key()
        if not glidein_symKey.is_valid():
            glidein_symKey = copy.deepcopy(glidein_symKey)
            glidein_symKey.new()
        self.glidein_symKey = glidein_symKey

    # returns a list of strings
    def get_key_attrs(self):
        glidein_symKey_str = self.glidein_symKey.get_code()
        return ('ReqPubKeyID = "%s"' % self.factory_pub_key_id,
                'ReqEncKeyCode = "%s"' % self.factory_pub_key.encrypt_hex(glidein_symKey_str),
                # this attribute will be checked against the AuthenticatedIdentity
                # this will prevent replay attacks, as only who knows the symkey can change this field
                # no other changes needed, as Condor provides integrity of the whole classAd
                'ReqEncIdentity = "%s"' % self.encrypt_hex(str(self.classad_identity)))

    def encrypt_hex(self, str):
        return self.glidein_symKey.encrypt_hex(str)

# class for creating FactoryKeys4Advertize objects
# will reuse the symkey as much as possible
class Key4AdvertizeBuilder:
    def __init__(self):
        self.keys_cache = {} # will contain a tuple of (key_obj,creation_time, last_access_time)

    def get_key_obj(self,
                    classad_identity,
                    factory_pub_key_id, factory_pub_key,
                    glidein_symKey=None): # will use one, if provided, but better to leave it blank and let the Builder create one
        # whoever can decrypt the pub key can anyhow get the symkey
        cache_id = factory_pub_key.get()

        if glidein_symKey is not None:
            # when a key is explicitly given, cannot reuse a cached one
            key_obj = FactoryKeys4Advertize(classad_identity,
                                        factory_pub_key_id, factory_pub_key,
                                          glidein_symKey)
            # but I can use it for others
            if not self.keys_cache.has_key(cache_id):
                now = time.time()
                self.keys_cache[cache_id] = [key_obj, now, now]
            return key_obj
        else:
            if self.keys_cache.has_key(cache_id):
                self.keys_cache[cache_id][2] = time.time()
                return  self.keys_cache[cache_id][0]
            else:
                key_obj = FactoryKeys4Advertize(classad_identity,
                                              factory_pub_key_id, factory_pub_key,
                                             glidein_symKey=None)
                now = time.time()
                self.keys_cache[cache_id] = [key_obj, now, now]
                return key_obj

    # clear the cache
    def clear(self,
              created_after=None, # if not None, only clear entries older than this
              accessed_after=None): # if not None, only clear entries not accessed recently
        if (created_after is None) and (accessed_after is None):
            # just delete everything
            self.keys_cache = {}
            return

        for cache_id in self.keys_cache.keys():
            # if at least one criteria is not satisfied, delete the entry
            delete_entry = False

            if created_after is not None:
                delete_entry = delete_entry or (self.keys_cache[cache_id][1] < created_after)

            if accessed_after is not None:
                delete_entry = delete_entry or (self.keys_cache[cache_id][2] < accessed_after)

            if delete_entry:
                del self.keys_cache[cache_id]

#######################################
# INTERNAL, do not use directly

class AdvertizeParams:
    def __init__(self,
                 request_name, glidein_name,
                 min_nr_glideins, max_run_glideins,
                 glidein_params={}, glidein_monitors={},
                 glidein_monitors_per_cred={},
                 glidein_params_to_encrypt=None,  # params_to_encrypt needs key_obj
                 security_name=None,  # needs key_obj
                 remove_excess_str=None):
        self.request_name = request_name
        self.glidein_name = glidein_name
        self.min_nr_glideins = min_nr_glideins
        self.max_run_glideins = max_run_glideins
        if remove_excess_str is None:
            remove_excess_str = "NO"
        elif not (remove_excess_str in ("NO", "WAIT", "IDLE", "ALL", "UNREG")):
            raise RuntimeError, 'Invalid remove_excess_str(%s), valid values are "NO","WAIT","IDLE","ALL","UNREG"' % remove_excess_str
        self.remove_excess_str = remove_excess_str
        self.glidein_params = glidein_params
        self.glidein_monitors = glidein_monitors
        self.glidein_monitors_per_cred = glidein_monitors_per_cred
        self.glidein_params_to_encrypt = glidein_params_to_encrypt
        self.security_name = security_name

    def __str__(self):
        output = "\nAdvertizeParams\n"        
        output += "request_name = %s\n" % self.request_name
        output += "glidein_name = %s\n" % self.glidein_name
        output += "min_nr_glideins = %s\n" % self.min_nr_glideins
        output += "max_run_glideins = %s\n" % self.max_run_glideins
        output += "remove_excess_str = %s\n" % self.remove_excess_str
        output += "glidein_params = %s\n" % self.glidein_params
        output += "glidein_monitors = %s\n" % self.glidein_monitors
        output += "glidein_monitors_per_cred = %s\n" % self.glidein_monitors_per_cred
        output += "glidein_params_to_encrypt = %s\n" % self.glidein_params_to_encrypt
        output += "security_name = %s\n" % self.security_name
        
        return output

# Given a file, advertize
# Can throw a CondorExe/ExeError exception
def advertizeWorkFromFile(factory_pool,
                          fname,
                          remove_file=True,
                          is_multi=False):
    try:
        exe_condor_advertise(fname, "UPDATE_MASTER_AD", factory_pool, is_multi=is_multi)
    finally:
        if remove_file:
            os.remove(fname)



# END INTERNAL
########################################


class MultiAdvertizeWork:
    def __init__(self,
                 descript_obj):        # must be of type FrontendDescript
        self.descript_obj = descript_obj
        self.factory_queue = {}          # will have a queue x factory, each element is list of tuples (params_obj, key_obj)
        self.global_pool = []
        self.global_key = {}
        self.global_params = {}
        self.factory_constraint = {}

        # set a few defaults
        self.unique_id = 1
        self.adname = None
        self.x509_proxies_data = []
        self.ha_mode = 'master'

    # add a request to the list
    def add(self,
            factory_pool,
            request_name, glidein_name,
            min_nr_glideins, max_run_glideins,
            glidein_params={}, glidein_monitors={},
            glidein_monitors_per_cred={},
            key_obj=None,                     # must be of type FactoryKeys4Advertize
            glidein_params_to_encrypt=None,   # params_to_encrypt needs key_obj
            security_name=None,               # needs key_obj
            remove_excess_str=None,
            trust_domain="Any",
            auth_method="Any",
            ha_mode='master'):

        params_obj=AdvertizeParams(request_name, glidein_name,
                                   min_nr_glideins, max_run_glideins,
                                   glidein_params, glidein_monitors,
                                   glidein_monitors_per_cred,
                                   glidein_params_to_encrypt, security_name,
                                   remove_excess_str)

        if not self.factory_queue.has_key(factory_pool):
            self.factory_queue[factory_pool] = []
        self.factory_queue[factory_pool].append((params_obj, key_obj))
        self.factory_constraint[params_obj.request_name]=(trust_domain, auth_method)
        self.ha_mode = ha_mode


    def add_global(self,factory_pool,request_name,security_name,key_obj):
        self.global_pool.append(factory_pool)
        self.global_key[factory_pool]=key_obj
        self.global_params[factory_pool]=(request_name,security_name)


    # return the queue depth
    def get_queue_len(self):
        count = 0
        #for factory_pool in self.factory_queue:
        for factory_pool in self.factory_queue.keys():
            count += len(self.factory_queue[factory_pool])
        return count


    def renew_and_load_credentials(self):
            """
            Get the list of proxies,
            invoke the renew scripts if any,
            and read the credentials in memory.
            Modifies the self.x509_proxies_data variable.
            """
            self.x509_proxies_data=[]
            if self.descript_obj.x509_proxies_plugin is not None:
                self.x509_proxies_data=self.descript_obj.x509_proxies_plugin.get_credentials()
                nr_credentials=len(self.x509_proxies_data)
            else:
                nr_credentials=0

            nr_good_credentials=nr_credentials
            for i in range(nr_credentials):
                cred_el=self.x509_proxies_data[i]
                cred_el.advertize=True
                cred_el.renew()
                cred_el.createIfNotExist()

                cred_el.loaded_data=[]
                for cred_file in (cred_el.filename, cred_el.key_fname, cred_el.pilot_fname):
                    if cred_file:
                        cred_data = cred_el.getString(cred_file)
                        if cred_data:
                            cred_el.loaded_data.append((cred_file, cred_data))
                        else:
                            # We encountered error with this credential
                            # Move onto next credential
                            break

            return nr_credentials

    def initialize_advertize_batch(self, adname_prefix='gfi_ad_batch'):
        """
        Initialize the variables that are used for batch avertizement
        Returns the adname to pass to do*advertize methods
        (will have to set reset_unique_id=False there, too)
        """
        self.unique_id=1
        return classadSupport.generate_classad_filename(prefix=adname_prefix)

    def do_advertize_batch(self, filename_dict, remove_files=True):
        """
        Advertize the classad files in the dictionary provided
         The keys are the factory names, while the elements are lists of files
        Safe to run in parallel, guaranteed to not modify the self object state.
        """
        for factory_pool in filename_dict:
            self.do_advertize_batch_one(factory_pool, filename_dict[factory_pool], remove_files)

    def do_advertize_batch_one(self, factory_pool, filename_arr, remove_files=True):
        """
        Advertize to a factory the clasad files provided
        Safe to run in parallel, guaranteed to not modify the self object state.
        """
        # Advertize all the files 
        for filename in filename_arr:
            try:
                advertizeWorkFromFile(factory_pool, filename, remove_file=remove_files, is_multi=frontendConfig.advertise_use_multi)
            except condorExe.ExeError:
                logSupport.log.exception("Advertising failed for factory pool %s: " % factory_pool)

    def get_advertize_factory_list(self):
        return tuple(set(self.global_pool).union(set(self.factory_queue.keys())))
            
    def do_global_advertize(self, adname=None, create_files_only=False, reset_unique_id=True):
        """
        Advertize globals with credentials
        Returns a dictionary of files that still need to be advertised.
          The key is the factory pool, while the element is a list of file names
        Expects that the credentials have been already loaded.
        """
        unpublished_files={}
        if reset_unique_id:
            self.unique_id=1
        for factory_pool in self.global_pool:
            self.unique_id+=1 # make sure ads for different factories don't end in the same file
            unpublished_files[factory_pool]=self.do_global_advertize_one(factory_pool, adname, create_files_only, False)
        return unpublished_files

    def do_global_advertize_one(self, factory_pool, adname=None, create_files_only=False, reset_unique_id=True):
        """
        Advertize globals with credentials to one factory
        Returns the list of files that still need to be advertised.
        Expects that the credentials have been already loaded.
        """
        if not (factory_pool in self.global_pool):
            # nothing to be done, prevent failure
            return []

        if adname is None:
            tmpname=classadSupport.generate_classad_filename(prefix='gfi_ad_gcg')
        else:
            tmpname=adname 

        if reset_unique_id:
            self.unique_id=1
        self.adname=tmpname
        filename_arr = self.createGlobalAdvertizeWorkFile(factory_pool)
        if create_files_only:
            return filename_arr
        
        # Else, advertize all the files (if multi, should only be one) 
        for filename in filename_arr:
            try:
                advertizeWorkFromFile(factory_pool, filename, remove_file=True, is_multi=frontendConfig.advertise_use_multi)
            except condorExe.ExeError:
                logSupport.log.exception("Advertising globals failed for factory pool %s: " % factory_pool)
        return [] # no files left to be advertised
    
    def createGlobalAdvertizeWorkFile(self, factory_pool):
            """
            Create the advertize file for globals with credentials
            Expects the object variables
             adname and x509_proxies_data
            to be set.
            """
            # the different indentation is due to code refactoring
            # this way the diff was minimized
            global advertizeGCGounter

            tmpname=self.adname
            glidein_params_to_encrypt={}
            fd=file(tmpname,"a")
            nr_credentials=len(self.x509_proxies_data)
            if nr_credentials>0:
                glidein_params_to_encrypt['NumberOfCredentials']="%s"%nr_credentials

            request_name="Global"
            if (factory_pool in self.global_params):
                request_name,security_name=self.global_params[factory_pool]
                glidein_params_to_encrypt['SecurityName']=security_name
            classad_name="%s@%s"%(request_name,self.descript_obj.my_name)
            fd.write('MyType = "%s"\n'%frontendConfig.client_global)
            fd.write('GlideinMyType = "%s"\n'%frontendConfig.client_global)
            fd.write('GlideinWMSVersion = "%s"\n'%frontendConfig.glideinwms_version)
            fd.write('Name = "%s"\n'%classad_name)
            fd.write('FrontendName = "%s"\n'%self.descript_obj.frontend_name)
            fd.write('FrontendHAMode = "%s"\n'%self.ha_mode)
            fd.write('GroupName = "%s"\n'%self.descript_obj.group_name)
            fd.write('ClientName = "%s"\n'%self.descript_obj.my_name)
            for i in range(nr_credentials):
                cred_el=self.x509_proxies_data[i]
                if cred_el.advertize==False:
                    continue # we already determined it cannot be used
                for ld_el in cred_el.loaded_data:
                    ld_fname,ld_data=ld_el
                    glidein_params_to_encrypt[cred_el.file_id(ld_fname)]=ld_data
                    if (hasattr(cred_el,'security_class')):
                        # Convert the sec class to a string so the Factory can interpret the value correctly
                        glidein_params_to_encrypt["SecurityClass"+cred_el.file_id(ld_fname)]=str(cred_el.security_class)

            if (factory_pool in self.global_key):
                key_obj=self.global_key[factory_pool]
            if key_obj is not None:
                fd.write(string.join(key_obj.get_key_attrs(),'\n')+"\n")
                for attr in glidein_params_to_encrypt.keys():
                    el = key_obj.encrypt_hex(glidein_params_to_encrypt[attr])
                    escaped_el = string.replace(string.replace(str(el), '"', '\\"'), '\n', '\\n')
                    fd.write('%s%s = "%s"\n' % (frontendConfig.encrypted_param_prefix, attr, escaped_el))

            # Update Sequence number information
            if advertizeGCGounter.has_key(classad_name):
                advertizeGCGounter[classad_name] += 1
            else:
                advertizeGCGounter[classad_name] = 0
            fd.write('UpdateSequenceNumber = %s\n' % advertizeGCGounter[classad_name]) 
 
            # add a final empty line... useful when appending
            fd.write('\n')
            fd.close()

            return [tmpname]

    def do_advertize(self, file_id_cache=None, adname=None, create_files_only=False, reset_unique_id=True):
        """
        Do the advertizing of the requests
        Returns a dictionary of files that still need to be advertised.
          The key is the factory pool, while the element is a list of file names
        Expects that the credentials have already been loaded.
        """
        if file_id_cache is None:
            file_id_cache=CredentialCache()

        unpublished_files={}
        if reset_unique_id:
            self.unique_id=1
        for factory_pool in self.factory_queue.keys():
            self.unique_id+=1 # make sure ads for different factories don't end in the same file
            unpublished_files[factory_pool]=self.do_advertize_one(factory_pool, file_id_cache, adname, create_files_only, False)
        return unpublished_files

    def do_advertize_one(self, factory_pool, file_id_cache=None, adname=None, create_files_only=False, reset_unique_id=True):
            """
            Do the advertizing of requests for one factory
            Returns the list of files that still need to be advertised.
            Expects that the credentials have already been loaded.
            """
            # the different indentation is due to code refactoring
            # this way the diff was minimized
            if not (factory_pool in self.factory_queue.keys()):
                # nothing to be done, prevent failure
                return []

            if file_id_cache is None:
                file_id_cache=CredentialCache()

            if reset_unique_id:
                self.unique_id=1
            if adname is None:
                self.adname = classadSupport.generate_classad_filename(prefix='gfi_ad_gc')
            else:
                self.adname = adname

            # this should be done in parallel, but keep it serial for now
            filename_arr=[]
            if (frontendConfig.advertise_use_multi==True):
                filename_arr.append(self.adname)
            for el in self.factory_queue[factory_pool]:
                params_obj, key_obj = el
                try:
                    filename_arr_el=self.createAdvertizeWorkFile(factory_pool,params_obj,key_obj,file_id_cache=file_id_cache)
                    for f in filename_arr_el:
                        if f not in filename_arr:
                            filename_arr.append(f)
                except NoCredentialException:
                    filename_arr = [] # don't try to advertise
                    logSupport.log.warning("No security credentials match for factory pool %s, not advertising request;"
                                           " if this is not intentional, check for typos frontend's credential "
                                           "trust_domain and type, vs factory's pool trust_domain and auth_method" %
                                           factory_pool)
                except condorExe.ExeError:
                    filename_arr = [] # don't try to advertise
                    logSupport.log.exception("Error creating request files for factory pool %s, unable to advertise: " % factory_pool)
                    logSupport.log.error("Error creating request files for factory pool %s, unable to advertise" % factory_pool)
                
            del self.factory_queue[factory_pool] # clean queue for this factory

            if create_files_only:
                return filename_arr

            # Else, advertize all the files (if multi, should only be one) 
            for filename in filename_arr:
                try:
                    advertizeWorkFromFile(factory_pool, filename, remove_file=True, is_multi=frontendConfig.advertise_use_multi)
                except condorExe.ExeError:
                    logSupport.log.exception("Advertising request failed for factory pool %s: " % factory_pool)

            return [] # No files left to be advertized

    def vm_attribute_from_file(self, filename, prefix):
        """
        Expected syntax: VM_ID=<ami id> or VM_TYPE=<instance type>

        Note: This method does not check if the string that follows VM_ID
              is meaningful AMI or the string that follows VM_TYPE is one
              of AWS instance types.
        """

        values = []
        try:
            vmfile = open(filename, 'r')
            for line in vmfile.readlines():
                sep_idx = line.find('=')
                if (sep_idx > 0):
                    key = (line[:sep_idx]).strip()
                    if (key.upper() == prefix.upper()):
                        value = (line[sep_idx+1:]).strip()
                        if value != '':
                            values.append(value)
        except:
            logSupport.log.exception('Failed to read the file %s' % (filename))
            raise NoCredentialException

        if len(values) > 1:
            logSupport.log.error("Found multiple lines that contain %s in %s" % (prefix, filename))
            raise NoCredentialException
        elif len(values) == 0:
            logSupport.log.error("File %s does not contain %s" % (filename, prefix))
            raise NoCredentialException

        logSupport.log.debug("Found %s = %s from file %s" % (prefix, values[0], filename))
        return values[0]

    def createAdvertizeWorkFile(self, factory_pool, params_obj, key_obj=None, file_id_cache=None): 
        """
        Create the advertize file
        Expects the object variables
          adname, unique_id and x509_proxies_data
        to be set.
        """
        global frontendConfig
        global advertizeGCCounter
        
        descript_obj=self.descript_obj
        
        logSupport.log.debug("In create Advertize work")

        factory_trust,factory_auth=self.factory_constraint[params_obj.request_name]

        total_nr_credentials = len(self.x509_proxies_data)

        cred_filename_arr=[]

        if total_nr_credentials == 0:
            raise NoCredentialException

        # get_credentials will augment the needed credentials with the requests
        # A little weird, but that's how it works right now
        # The credential objects are also persistent, so this will be a subset of self.x509_proxies_data
        credentials_with_requests = descript_obj.x509_proxies_plugin.get_credentials(params_obj=params_obj,credential_type=factory_auth,trust_domain=factory_trust)
        nr_credentials = len(credentials_with_requests)
        if nr_credentials == 0:
            raise NoCredentialException

        if file_id_cache is None:
            # create a local cache, if no global provided
            file_id_cache=CredentialCache()

        for i in range(nr_credentials):
            fd=None
            glidein_monitors_this_cred = {}
            try:
                encrypted_params={} # none by default
                glidein_params_to_encrypt=params_obj.glidein_params_to_encrypt
                if glidein_params_to_encrypt is None:
                    glidein_params_to_encrypt={}
                else:
                    glidein_params_to_encrypt=copy.deepcopy(glidein_params_to_encrypt)
                classad_name="%s@%s"%(params_obj.request_name,descript_obj.my_name)
               
                req_idle=0
                req_max_run=0
                if True: # for historical reasons... to preserve indentation
                    credential_el=credentials_with_requests[i]
                    logSupport.log.debug("Checking Credential file %s ..."%(credential_el.filename))
                    if credential_el.advertize==False:
                        # We already determined it cannot be used
                        #if hasattr(credential_el,'filename'):
                        #    filestr=credential_el.filename
                        #logSupport.log.warning("Credential file %s had some earlier problem in loading so not advertizing, skipping..."%(filestr))
                        continue

                    if (params_obj.request_name in self.factory_constraint):
                        if (credential_el.type!=factory_auth) and (factory_auth!="Any"):
                            logSupport.log.warning("Credential %s does not match auth method %s (for %s), skipping..."%(credential_el.type,factory_auth,params_obj.request_name))
                            continue
                        if (credential_el.trust_domain!=factory_trust) and (factory_trust!="Any"):
                            logSupport.log.warning("Credential %s does not match %s (for %s) domain, skipping..."%(credential_el.trust_domain,factory_trust,params_obj.request_name))
                            continue
                    # Convert the sec class to a string so the Factory can interpret the value correctly
                    glidein_params_to_encrypt['SecurityClass']=str(credential_el.security_class)
                    classad_name=credential_el.file_id(credential_el.filename,ignoredn=True)+"_"+classad_name
                    if "username_password"in credential_el.type:
                        glidein_params_to_encrypt['Username']=file_id_cache.file_id(credential_el, credential_el.filename)
                        glidein_params_to_encrypt['Password']=file_id_cache.file_id(credential_el, credential_el.key_fname)
                    if "grid_proxy" in credential_el.type:
                        glidein_params_to_encrypt['SubmitProxy']=file_id_cache.file_id(credential_el, credential_el.filename)
                    if "cert_pair" in credential_el.type:
                        glidein_params_to_encrypt['PublicCert']=file_id_cache.file_id(credential_el, credential_el.filename)
                        glidein_params_to_encrypt['PrivateCert']=file_id_cache.file_id(credential_el, credential_el.key_fname)
                    if "key_pair" in credential_el.type:
                        glidein_params_to_encrypt['PublicKey']=file_id_cache.file_id(credential_el, credential_el.filename)
                        glidein_params_to_encrypt['PrivateKey']=file_id_cache.file_id(credential_el, credential_el.key_fname)
                    if credential_el.pilot_fname:
                        glidein_params_to_encrypt['GlideinProxy']=file_id_cache.file_id(credential_el, credential_el.pilot_fname)
                    

                    if "vm_id" in credential_el.type:
                        if credential_el.vm_id_fname:
                            glidein_params_to_encrypt['VMId']=self.vm_attribute_from_file( credential_el.vm_id_fname, 'VM_ID' )
                        else:
                            glidein_params_to_encrypt['VMId']=str(credential_el.vm_id)

                    if "vm_type" in credential_el.type:
                        if credential_el.vm_type_fname:
                            glidein_params_to_encrypt['VMType']=self.vm_attribute_from_file( credential_el.vm_type_fname, 'VM_TYPE' )
                        else:
                            glidein_params_to_encrypt['VMType']=str(credential_el.vm_type)

                        
                    (req_idle,req_max_run)=credential_el.get_usage_details()
                    logSupport.log.debug("Advertizing credential %s with (%d idle, %d max run) for request %s"%(credential_el.filename, req_idle, req_max_run, params_obj.request_name))
                
                    glidein_monitors_this_cred = params_obj.glidein_monitors_per_cred.get(credential_el.getId(), {})

                if (frontendConfig.advertise_use_multi==True):
                    fname=self.adname
                    cred_filename_arr.append(fname)
                else:
                    fname=self.adname+"_"+str(self.unique_id)
                    self.unique_id=self.unique_id+1
                    cred_filename_arr.append(fname)
                logSupport.log.debug("Writing %s"%fname)
                fd = file(fname, "a")
            
                fd.write('MyType = "%s"\n'%frontendConfig.client_id)
                fd.write('GlideinMyType = "%s"\n'%frontendConfig.client_id)
                fd.write('GlideinWMSVersion = "%s"\n'%frontendConfig.glideinwms_version)
                fd.write('Name = "%s"\n'%classad_name)
                fd.write(string.join(descript_obj.get_id_attrs(),'\n')+"\n")
                fd.write('ReqName = "%s"\n'%params_obj.request_name)
                fd.write('ReqGlidein = "%s"\n'%params_obj.glidein_name)

                fd.write(string.join(descript_obj.get_web_attrs(),'\n')+"\n")

                if params_obj.security_name is not None:
                    glidein_params_to_encrypt['SecurityName']=params_obj.security_name
                                  
                if key_obj is not None:
                    fd.write(string.join(key_obj.get_key_attrs(),'\n')+"\n")
                    for attr in glidein_params_to_encrypt.keys():
                        encrypted_params[attr]=key_obj.encrypt_hex(glidein_params_to_encrypt[attr])
                    

                fd.write('ReqIdleGlideins = %i\n'%req_idle)
                fd.write('ReqMaxGlideins = %i\n'%req_max_run)
                fd.write('ReqRemoveExcess = "%s"\n'%params_obj.remove_excess_str)
                fd.write('WebMonitoringURL = "%s"\n'%descript_obj.monitoring_web_url)
                         
                # write out both the params 
                for (prefix, data) in ((frontendConfig.glidein_param_prefix, params_obj.glidein_params),
                                       (frontendConfig.encrypted_param_prefix, encrypted_params)):
                    for attr in data.keys():
                        writeTypedClassadAttrToFile(fd,
                                                    '%s%s' % (prefix, attr),
                                                    data[attr])

                for attr_name in params_obj.glidein_monitors:
                    prefix = frontendConfig.glidein_monitor_prefix
                    #attr_value = params_obj.glidein_monitors[attr_name] 
                    if (attr_name == 'RunningHere') and glidein_monitors_this_cred:
                        # This double check is for backward compatibility
                        attr_value = glidein_monitors_this_cred.get(
                                         'GlideinsRunning', 0)
                    elif (attr_name == 'Running') and glidein_monitors_this_cred:
                        # This double check is for backward compatibility
                        attr_value = glidein_monitors_this_cred.get(
                                         'ScaledRunning', 0)
                    else:
                        attr_value = glidein_monitors_this_cred.get(
                                         attr_name,
                                         params_obj.glidein_monitors[attr_name])
                    writeTypedClassadAttrToFile(fd,
                                                '%s%s' % (prefix, attr_name),
                                                attr_value)
                    

                # Update Sequence number information
                if advertizeGCCounter.has_key(classad_name):
                    advertizeGCCounter[classad_name] += 1
                else:
                    advertizeGCCounter[classad_name] = 0
                fd.write('UpdateSequenceNumber = %s\n' % advertizeGCCounter[classad_name])
                            
                # add a final empty line... useful when appending
                fd.write('\n')
                fd.close()
            except:
                logSupport.log.exception("Exception writing advertisement file: ")
                # remove file in case of problems
                if (fd is not None):
                    fd.close()
                    os.remove(fname)
                raise
        return cred_filename_arr



def writeTypedClassadAttrToFile(fd, attr_name, attr_value):
    """
    Given the FD, type check the value and write the info the classad file
    """
    if type(attr_value) == type(1):
        # don't quote ints
        fd.write('%s = %s\n' % (attr_name, attr_value))
    else:
        escaped_value = string.replace(string.replace(str(attr_value), '"', '\\"'), '\n', '\\n')
        fd.write('%s = "%s"\n' % (attr_name, escaped_value))


# Remove ClassAd from Collector
def deadvertizeAllWork(factory_pool, my_name, ha_mode='master'):
    """
    Removes all work requests for the client in the factory.
    """
    global frontendConfig

    tmpnam = classadSupport.generate_classad_filename(prefix='gfi_de_gc')
    fd = file(tmpnam, "w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n' % frontendConfig.client_id)
            fd.write('Requirements = (ClientName == "%s") && (GlideinMyType == "%s") && (FrontendHAMode == "%s")\n' % (my_name, frontendConfig.client_id, ha_mode))
        finally:
            fd.close()

        exe_condor_advertise(tmpnam, "INVALIDATE_MASTER_ADS", factory_pool)
    finally:
        os.remove(tmpnam)

def deadvertizeAllGlobals(factory_pool, my_name, ha_mode='master'):
    """
    Removes all globals classads for the client in the factory.
    """
    global frontendConfig

    tmpnam = classadSupport.generate_classad_filename(prefix='gfi_de_gcg')
    fd = file(tmpnam, "w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n' % frontendConfig.client_global)
            fd.write('Requirements = (ClientName == "%s") && (GlideinMyType == "%s") && (FrontendHAMode == "%s")\n' % (my_name, frontendConfig.client_global, ha_mode))
        finally:
            fd.close()

        exe_condor_advertise(tmpnam, "INVALIDATE_MASTER_ADS", factory_pool)
    finally:
        os.remove(tmpnam)

###############################################################################
# Code to advertise glideresource classads to the User Pool
###############################################################################

class ResourceClassad(classadSupport.Classad):
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
        
        classadSupport.Classad.__init__(self, 'glideresource',
                                        'UPDATE_AD_GENERIC',
                                        'INVALIDATE_ADS_GENERIC')
        
        self.adParams['GlideinWMSVersion'] = frontendConfig.glideinwms_version
        self.adParams['GlideFactoryName'] = "%s" % factory_ref
        self.adParams['GlideClientName'] = "%s" % frontend_ref
        self.adParams['Name'] = "%s@%s" % (factory_ref, frontend_ref)
        self.adParams['GLIDEIN_In_Downtime'] = 'False'
        
        if advertizeGRCounter.has_key(self.adParams['Name']):
            advertizeGRCounter[self.adParams['Name']] += 1
        else:       
            advertizeGRCounter[self.adParams['Name']] = 0
        self.adParams['UpdateSequenceNumber'] = advertizeGRCounter[self.adParams['Name']]


    def setFrontendDetails(self, frontend_name, group_name, ha_mode):
        """
        Add the detailed description of the frontend.
        @type frontend_name: string
        @param frontend_name: A representation of the  frontend MatchExpr
        @type group_name: string
        @param group_name: Representation of the job query_expr
        """
        self.adParams['GlideFrontendName'] = "%s" % frontend_name
        self.adParams['GlideGroupName'] = "%s" % group_name
        self.adParams['GlideFrontendHAMode'] = "%s" % ha_mode
        

    def setMatchExprs(self, match_expr, job_query_expr, factory_query_expr, start_expr):
        """
        Sets the matching expressions for the resource classad
        Thus, it would be possible to find out why a job
        is not matching.
        @type match_expr: string
        @param match_expr: A representation of the  frontend MatchExpr
        @type job_query_expr: string
        @param job_query_expr: Representation of the job query_expr
        @type factory_query_expr: string
        @param factory_query_expr: Representation of the factory query_expr
        @type start_expr: string
        @param start_expr: Representation of the match start expr (on the glidein)
        """
        self.adParams['GlideClientMatchingGlideinCondorExpr'] = "%s" % match_expr
        self.adParams['GlideClientConstraintJobCondorExpr'] = "%s" % job_query_expr
        self.adParams['GlideClientMatchingInternalPythonExpr'] = "%s" % factory_query_expr
        self.adParams['GlideClientConstraintFactoryCondorExpr'] = "%s" % start_expr
        

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

        if len(monitorInfo) == 17:
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
            self.adParams['GlideClientMonitorGlideinsFailed'] = monitorInfo[11]
            self.adParams['GlideClientMonitorGlideinsTotalCores'] = monitorInfo[12]
            self.adParams['GlideClientMonitorGlideinsIdleCores'] = monitorInfo[13]
            self.adParams['GlideClientMonitorGlideinsRunningCores'] = monitorInfo[14]
            self.adParams['GlideClientMonitorGlideinsRequestIdle'] = monitorInfo[15]
            self.adParams['GlideClientMonitorGlideinsRequestMaxRun'] = monitorInfo[16]
        else:
            raise RuntimeError, 'Glide client monitoring structure changed. Resource ad may have incorrect GlideClientMonitor values'


    def setEntryInfo(self, info):
        """
        Set the useful entry specific info for the resource in the classad

        @type info: dict 
        @param info: Useful info from the glidefactory classad  
        """
        
        eliminate_attrs = set([
                 'CurrentTime', 'PubKeyValue', 'PubKeyType',
                 'AuthenticatedIdentity', 'GlideinName', 'FactoryName', 
                 'EntryName', 'GlideinWMSVersion', 'PubKeyObj', 
                 'LastHeardFrom', 'PubKeyID', 'SupportedSignTypes',
                 'GLIDEIN_In_Downtime'
                ])
        available_attrs = set(info.keys())
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
        # start with Total or Status or Requested. Append GlideFactoryMonitor
        # to these keys and put them in the classad

        for key in info.keys():
            ad_key = key
            if not key.startswith('TotalClientMonitor'):
                if key.startswith('Total') or key.startswith('Status') or key.startswith('Requested'):
                    ad_key = 'GlideFactoryMonitor' + key
                    self.adParams[ad_key] = info[key]


    def setCurbsAndLimits(self, limits_triggered):
        """
        Set descriptive messages about which limits and curbs
            have been triggered in deciding number of glideins to request
        @type  limits_triggered: dictionary
        @param limits_triggered: limits and curbs that have been triggered
        """
        for k,v in limits_triggered.iteritems():
            if k.startswith('Curb'):
                classadmessage = "GlideResource_Curb_"+k
            else:
                classadmessage = "GlideResource_Limit_"+k
                
            self.adParams[classadmessage] = 'CurbLimit'


class ResourceClassadAdvertiser(classadSupport.ClassadAdvertiser):
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

        classadSupport.ClassadAdvertiser.__init__(self, pool=pool, 
                                                  multi_support=multi_support,
                                                  tcp_support=frontendConfig.advertise_use_tcp)
        
        self.adType = 'glideresource'
        self.adAdvertiseCmd = 'UPDATE_AD_GENERIC'
        self.adInvalidateCmd = 'INVALIDATE_ADS_GENERIC'
        self.advertiseFilePrefix = 'gfi_ar'


class FrontendMonitorClassad(classadSupport.Classad):
    """
    This class describes the resource classad. Frontend advertises the 
    resource classad to the user pool as an UPDATE_AD_GENERIC type classad
    """
    

    def __init__(self, frontend_ref):
        """
        Class Constructor

        @type frontend_ref: string 
        @param type: Name of the resource in the glideclient classad
        """

        global advertizeGFMCounter
        
        classadSupport.Classad.__init__(self, 'glidefrontendmonitor',
                                        'UPDATE_AD_GENERIC',
                                        'INVALIDATE_ADS_GENERIC')
        
        self.adParams['GlideinWMSVersion'] = frontendConfig.glideinwms_version
        self.adParams['Name'] = '%s' % (frontend_ref)
        #self.adParams['GlideFrontend_In_Downtime'] = 'False'
        
        if self.adParams['Name'] in advertizeGFMCounter:
            advertizeGFMCounter[self.adParams['Name']] += 1
        else:       
            advertizeGFMCounter[self.adParams['Name']] = 0
        self.adParams['UpdateSequenceNumber'] = advertizeGFMCounter[self.adParams['Name']]


    def setFrontendDetails(self, frontend_name, groups, ha_mode):
        """
        Add the detailed description of the frontend.
        @type frontend_name: string
        @param frontend_name: A representation of the  frontend MatchExpr
        @type group_name: string
        @param group_name: Representation of the job query_expr
        """
        self.adParams['GlideFrontendName'] = "%s" % frontend_name
        self.adParams['GlideFrontendGroups'] = "%s" % groups
        self.adParams['GlideFrontendHAMode'] = "%s" % ha_mode


    def setIdleJobCount(self, idle_jobs):
        """
        Set the idle jobs info in the classad

        @type idle_jobs: dict 
        @param idle_jobs: Dictionary of idle jobs keyed on idle duration.
                          For example - Total for all idle jobs,
                                        3600 for jobs idle more than 1 Hour
        """

        for key in idle_jobs:
            k = '%s' % key
            self.adParams['GlideFrontend_IdleJobs_%s' % k.title()] = idle_jobs[key]


class FrontendMonitorClassadAdvertiser(classadSupport.ClassadAdvertiser):
    """
    Class to handle the advertisement of frontend monitor classads
    to the user pool
    """


    def __init__(self, pool=None, multi_support=False):
        """
        Constructor

        @type pool: string 
        @param pool: Collector address
        @type multi_support: bool 
        @param multi_support: True if the installation support advertising multiple classads with one condor_advertise command. Defaults to False.
        """

        classadSupport.ClassadAdvertiser.__init__(self, pool=pool, 
                                                  multi_support=multi_support,
                                                  tcp_support=frontendConfig.advertise_use_tcp)
        
        self.adType = 'glidefrontendmonitor'
        self.adAdvertiseCmd = 'UPDATE_AD_GENERIC'
        self.adInvalidateCmd = 'INVALIDATE_ADS_GENERIC'
        self.advertiseFilePrefix = 'gfi_afm'



############################################################
#
# I N T E R N A L - Do not use
#
############################################################

def exe_condor_advertise(fname,command, pool, is_multi=False):
    logSupport.log.debug("CONDOR ADVERTISE %s %s %s %s" % (fname, command,
                                                           pool, is_multi))
    return condorManager.condorAdvertise(fname, command, 
                                         frontendConfig.advertise_use_tcp,
                                         is_multi, pool)

class NoCredentialException(Exception):
    pass
