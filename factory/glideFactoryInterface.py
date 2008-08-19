#
# Description:
#   This module implements the functions needed to advertize
#   and get commands from the Collector
#
# Author:
#   Igor Sfiligoi (Sept 7th 2006)
#

import condorExe
import condorMonitor
import os
import time
import string


############################################################
#
# Configuration
#
############################################################

class FactoryConfig:
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

        # String to prefix for the monitoring
        self.glidein_monitor_prefix = "GlideinMonitor"

        # String to prefix for the requests
        self.client_req_prefix = "Req"



# global configuration of the module
factoryConfig=FactoryConfig()

############################################################
#
# User functions
#
############################################################


def findWork(factory_name,glidein_name,entry_name):
    """
    Look for requests.
    Look for classAds that have my (factory, glidein name, entry name).

    Return:
      Dictionary, each key is the name of a frontend.
      Each value has a 'requests' and a 'params' key.
        Both refer to classAd dictionaries.
    """

    global factoryConfig
    
    status_constraint='(GlideinMyType=?="%s") && (ReqGlidein=?="%s@%s@%s")'%(factoryConfig.client_id,entry_name,glidein_name,factory_name)
    status=condorMonitor.CondorStatus("any")
    status.glidein_name=glidein_name
    status.entry_name=entry_name
    status.load(status_constraint)

    data=status.fetchStored()

    reserved_names=("ReqName","ReqGlidein","ClientName")

    out={}

    # copy over requests and parameters
    for k in data.keys():
        kel=data[k]
        el={"requests":{},"params":{},"monitor":{},"internals":{}}
        for (key,prefix) in (("requests",factoryConfig.client_req_prefix),
                             ("params",factoryConfig.glidein_param_prefix),
                             ("monitor",factoryConfig.glidein_monitor_prefix)):
            plen=len(prefix)
            for attr in kel.keys():
                if attr in reserved_names:
                    continue # skip reserved names
                if attr[:plen]==prefix:
                    el[key][attr[plen:]]=kel[attr]
        for attr in kel.keys():
            if attr in ("ClientName","ReqName","LastHeardFrom"):
                el["internals"][attr]=kel[attr]
        
        out[k]=el

    return out

start_time=time.time()
advertizeGlideinCounter=0
# glidein_attrs is a dictionary of values to publish
#  like {"Arch":"INTEL","MinDisk":200000}
# similar for glidein_params and glidein_monitor_monitors
def advertizeGlidein(factory_name,glidein_name,entry_name,
                     pub_key_id,pub_key_type,pub_key_value,
                     glidein_attrs={},glidein_params={},glidein_monitors={}):
    global factoryConfig,advertizeGlideinCounter

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_ag_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "%s"\n'%factoryConfig.factory_id)
            fd.write('GlideinMyType = "%s"\n'%factoryConfig.factory_id)
            fd.write('Name = "%s@%s@%s"\n'%(entry_name,glidein_name,factory_name))
            fd.write('FactoryName = "%s"\n'%factory_name)
            fd.write('GlideinName = "%s"\n'%glidein_name)
            fd.write('EntryName = "%s"\n'%entry_name)
            fd.write('PubKeyID = "%s"\n'%pub_key_id)
            fd.write('PubKeyType = "%s"\n'%pub_key_type)
            fd.write('PubKeyValue = "%s"\n'%string.replace(pub_key_value,'\n','\\n'))
            fd.write('DaemonStartTime = %li\n'%start_time)
            fd.write('UpdateSequenceNumber = %i\n'%advertizeGlideinCounter)
            advertizeGlideinCounter+=1

            # write out both the attributes, params and monitors
            for (prefix,data) in ((factoryConfig.glidein_attr_prefix,glidein_attrs),
                                  (factoryConfig.glidein_param_prefix,glidein_params),
                                  (factoryConfig.glidein_monitor_prefix,glidein_monitors)):
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

        condorExe.exe_cmd("../sbin/condor_advertise","UPDATE_MASTER_AD %s"%tmpnam)
    finally:
        os.remove(tmpnam)

# remove add from Collector
def deadvertizeGlidein(factory_name,glidein_name,entry_name):
    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_ag_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n'%factoryConfig.factory_id)
            fd.write('Requirements = Name == "%s@%s@%s"\n'%(entry_name,glidein_name,factory_name))
        finally:
            fd.close()

        condorExe.exe_cmd("../sbin/condor_advertise","INVALIDATE_MASTER_ADS %s"%tmpnam)
    finally:
        os.remove(tmpnam)
    

# glidein_attrs is a dictionary of values to publish
#  like {"Arch":"INTEL","MinDisk":200000}
# similar for glidein_params and glidein_monitor_monitors
def advertizeGlideinClientMonitoring(factory_name,glidein_name,entry_name,
                                     client_name,client_int_name,client_int_req,
                                     glidein_attrs={},client_params={},client_monitors={}):
    #global factoryConfig,advertizeGlideinCounter

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_ag_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "%s"\n'%factoryConfig.factoryclient_id)
            fd.write('GlideinMyType = "%s"\n'%factoryConfig.factoryclient_id)
            fd.write('Name = "%s"\n'%client_name)
            fd.write('ReqGlidein = "%s@%s@%s"\n'%(entry_name,glidein_name,factory_name))
            fd.write('ReqFactoryName = "%s"\n'%factory_name)
            fd.write('ReqGlideinName = "%s"\n'%glidein_name)
            fd.write('ReqEntryName = "%s"\n'%entry_name)
            fd.write('ReqClientName = "%s"\n'%client_int_name)
            fd.write('ReqClientReqName = "%s"\n'%client_int_req)
            #fd.write('DaemonStartTime = %li\n'%start_time)
            #fd.write('UpdateSequenceNumber = %i\n'%advertizeGlideinCounter)
            #advertizeGlideinCounter+=1

            # write out both the attributes, params and monitors
            for (prefix,data) in ((factoryConfig.glidein_attr_prefix,glidein_attrs),
                                  (factoryConfig.glidein_param_prefix,client_params),
                                  (factoryConfig.glidein_monitor_prefix,client_monitors)):
                for attr in data.keys():
                    el=data[attr]
                    if type(el)==type(1):
                        # don't quote ints
                        fd.write('%s%s = %s\n'%(prefix,attr,el))
                    else:
                        escaped_el=string.replace(str(el),'"','\\"')
                        fd.write('%s%s = "%s"\n'%(prefix,attr,escaped_el))
        finally:
            fd.close()

        condorExe.exe_cmd("../sbin/condor_advertise","UPDATE_LICENSE_AD %s"%tmpnam) # must use a different AD that the frontend
    finally:
        os.remove(tmpnam)

# remove add from Collector
def deadvertizeGlideinClientMonitoring(factory_name,glidein_name,entry_name,client_name):
    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_ag_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n'%factoryConfig.factoryclient_id)
            fd.write('Requirements = Name == "%s"\n'%client_name)
        finally:
            fd.close()

        condorExe.exe_cmd("../sbin/condor_advertise","INVALIDATE_LICENSE_ADS %s"%tmpnam)
    finally:
        os.remove(tmpnam)

# remove adds from Collector
def deadvertizeAllGlideinClientMonitoring(factory_name,glidein_name,entry_name):
    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_ag_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n'%factoryConfig.factoryclient_id)
            fd.write('Requirements = ReqGlidein == "%s@%s@%s"\n'%(entry_name,glidein_name,factory_name))
        finally:
            fd.close()

        condorExe.exe_cmd("../sbin/condor_advertise","INVALIDATE_LICENSE_ADS %s"%tmpnam)
    finally:
        os.remove(tmpnam)


###########################################################
#
# CVS info
#
# $Id: glideFactoryInterface.py,v 1.22 2008/08/19 21:53:02 sfiligoi Exp $
#
# Log:
#  $Log: glideFactoryInterface.py,v $
#  Revision 1.22  2008/08/19 21:53:02  sfiligoi
#  Add PubKeyID
#
#  Revision 1.21  2008/08/19 18:01:20  sfiligoi
#  Add protection for newlines
#
#  Revision 1.20  2008/08/19 15:10:56  sfiligoi
#  Use PubKey
#
#  Revision 1.19  2007/05/18 19:10:57  sfiligoi
#  Add CVS tags
#
#
###########################################################
