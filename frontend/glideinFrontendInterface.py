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
import time
import string
import pubCrypto,symCrypto
import glideinFrontendLib

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


        self.condor_reserved_names=("MyType","TargetType","GlideinMyType","MyAddress",'UpdatesHistory','UpdatesTotal','UpdatesLost','UpdatesSequenced','UpdateSequenceNumber','DaemonStartTime')


# global configuration of the module
frontendConfig=FrontendConfig()

############################################################
#
# User functions
#
############################################################


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

    try:
        status.load(status_constraint)
    except condorExe.ExeError, e:
        if factory_pool!=None:
            glideinFrontendLib.log_files.logWarning("Failed to talk to factory_pool %s. See debug log for more details."%factory_pool)
            glideinFrontendLib.log_files.logDebug("Failed to talk to factory_pool %s: %s"%(factory_pool, e))
        else:
            glideinFrontendLib.log_files.logWarning("Failed to talk to factory_pool. See debug log for more details.")
            glideinFrontendLib.log_files.logDebug("Failed to talk to factory_pool: %s"%e)
        return {} # retrun empty set

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

def findGlideinClientMonitoring(factory_pool,client_name,
                                additional_constraint=None):
    global frontendConfig
    
    status_constraint='(GlideinMyType=?="%s")'%frontendConfig.factoryclient_id
    if client_name!=None:
        status_constraint='%s && (ReqClientName=?="%s")'%client_name
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

# glidein_params is a dictionary of values to publish
#  like {"GLIDEIN_Collector":"myname.myplace.us","MinDisk":200000}
# similar for glidein_monitors
def advertizeWork(factory_pool,
                  client_name,frontend_name,group_name,
                  request_name,glidein_name,
                  web_url, main_descript, group_descript,
                  signtype, main_sign, group_sign,
                  min_nr_glideins,max_run_glideins,
                  glidein_params={},glidein_monitors={},
                  classad_identity=None, # needed only if sending over encrypted info
                  factory_pub_key_id=None,factory_pub_key=None, #pub_key needs pub_key_id
                  glidein_symKey=None, # if a symkey is not provided, or is not initialized, generate one
                  glidein_params_to_encrypt=None):  #params_to_encrypt need pub_key
    global frontendConfig

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_aw_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            classad_name="%s@%s"%(request_name,client_name)
            
            fd.write('MyType = "%s"\n'%frontendConfig.client_id)
            fd.write('GlideinMyType = "%s"\n'%frontendConfig.client_id)
            fd.write('Name = "%s"\n'%classad_name)
            fd.write('ClientName = "%s"\n'%client_name)
            fd.write('FrontendName = "%s"\n'%frontend_name)
            fd.write('GroupName = "%s"\n'%group_name)
            fd.write('ReqName = "%s"\n'%request_name)
            fd.write('ReqGlidein = "%s"\n'%glidein_name)

            fd.write('WebURL = "%s"\n'%web_url)
            fd.write('WebGroupURL = "%s"\n'%os.path.join(web_url,"group_%s"%group_name))
            fd.write('WebSignType = "%s"\n'%signtype)
            fd.write('WebDescriptFile = "%s"\n'%main_descript)
            fd.write('WebDescriptSign = "%s"\n'%main_sign)
            fd.write('WebGroupDescriptFile = "%s"\n'%group_descript)
            fd.write('WebGroupDescriptSign = "%s"\n'%group_sign)

            encrypted_params={} # none by default
            if (factory_pub_key_id!=None) and (factory_pub_key!=None):
                if glidein_symKey==None:
                    glidein_symKey=symCrypto.SymAES256Key()
                if not glidein_symKey.is_valid():
                    glidein_symKey.new()
                glidein_symKey_str=glidein_symKey.get_code()
                
                fd.write('ReqPubKeyID = "%s"\n'%factory_pub_key_id)

                fd.write('ReqEncKeyCode = "%s"\n'%factory_pub_key.encrypt_hex(glidein_symKey_str))

                # this attribute will be checked against the AuthenticatedIdentity
                # this will prevent replay attacks, as only who knows the symkey can change this field
                # no other changes needed, as Condor provides integrity of the whole classAd
                fd.write('ReqEncIdentity = "%s"\n'%glidein_symKey.encrypt_hex(classad_identity))
                
                if encrypted_params!=None:
                    for attr in glidein_params_to_encrypt.keys():
                        encrypted_params[attr]=glidein_symKey.encrypt_hex(glidein_params_to_encrypt["%s"%attr])
                        
            fd.write('ReqIdleGlideins = %i\n'%min_nr_glideins)
            fd.write('ReqMaxRunningGlideins = %i\n'%max_run_glideins)

            # write out both the params and monitors
            for (prefix,data) in ((frontendConfig.glidein_param_prefix,glidein_params),
                                  (frontendConfig.glidein_monitor_prefix,glidein_monitors),
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

        condorExe.exe_cmd("../sbin/condor_advertise","UPDATE_MASTER_AD %s %s"%(pool2str(factory_pool),tmpnam))
    finally:
        os.remove(tmpnam)

# Remove ClassAd from Collector
def deadvertizeWork(factory_pool,
                    client_name,request_name):
    global frontendConfig

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_aw_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n'%frontendConfig.client_id)
            fd.write('Requirements = Name == "%s@%s"\n'%(request_name,client_name))
        finally:
            fd.close()

        condorExe.exe_cmd("../sbin/condor_advertise","INVALIDATE_MASTER_ADS %s %s"%(pool2str(factory_pool),tmpnam))
    finally:
        os.remove(tmpnam)

# Remove ClassAd from Collector
def deadvertizeAllWork(factory_pool,
                       client_name):
    global frontendConfig

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_aw_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n'%frontendConfig.client_id)
            fd.write('Requirements = ClientName == "%s"\n'%client_name)
        finally:
            fd.close()

        condorExe.exe_cmd("../sbin/condor_advertise","INVALIDATE_MASTER_ADS %s %s"%(pool2str(factory_pool),tmpnam))
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
        return "-pool %s"%pool_name

