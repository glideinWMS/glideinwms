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
import os
import time


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

        # String to prefix for the attributes
        self.glidein_attr_prefix = ""

        # String to prefix for the parameters
        self.glidein_param_prefix = "GlideinParam"

        # String to prefix for the parameters
        self.glidein_count_prefix = "GlideinCount"

        # String to prefix for the requests
        self.client_req_prefix = "Req"

        # log files
        # default is None, any other value must implement the write(str) method
        self.activity_log = None
        self.warning_log = None

    #
    # The following are used by the module
    #

    def logActivity(self,str):
        if self.activity_log!=None:
            try:
                self.activity_log.write(str+"\n")
            except:
                # logging must never throw an exception!
                logWarning("logActivity failed, was logging: %s"+str)

    def logWarning(self,str):
        if self.warining_log!=None:
            try:
                self.warining_log.write(str+"\n")
            except:
                # logging must throw an exception!
                # silently ignore
                pass 


# global configuration of the module
frontendConfig=FrontendConfig()

############################################################
#
# User functions
#
############################################################


def findGlideins(factory_pool=None,
                 additional_constraint=None):
    global frontendConfig
    
    status_constraint='(GlideinMyType=?="%s")'%(frontendConfig.factory_id)
    if additional_constraint!=None:
        status_constraint="%s && (%s)"%(status_constraint,additional_constraint)
    status=condorMonitor.CondorStatus("any",pool_name=factory_pool)
    status.load(status_constraint)

    data=status.fetchStored()

    reserved_names=("MyType","TargetType","GlideinMyType","MyAddress")
    for k in reserved_names:
        if data.has_key(k):
            del data[k]

    out={}

    # copy over requests and parameters
    for k in data.keys():
        kel=data[k].copy()

        el={"params":{}}

        # first remove reserved anmes
        for attr in reserved_names:
            if kel.has_key(attr):
                del kel[attr]

        # then move the parameters
        prefix = frontendConfig.glidein_param_prefix
        plen=len(prefix)
        for attr in kel.keys():
            if attr[:plen]==prefix:
                el["params"][attr[plen:]]=kel[attr]
                del kel[attr]

        # what is left are glidein attributes
        el["attrs"]=kel
        
        out[k]=el

    return out

# glidein_params is a dictionary of values to publish
#  like {"GLIDEIN_Collector":"myname.myplace.us","MinDisk":200000}
def advertizeWork(client_name,request_name,
                  glidein_name,min_nr_glideins,
                  glidein_params={},
                  factory_pool=None):
    global frontendConfig

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_ag_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "%s"\n'%frontendConfig.client_id)
            fd.write('GlideinMyType = "%s"\n'%frontendConfig.client_id)
            fd.write('Name = "%s@%s"\n'%(request_name,client_name))
            fd.write('ClientName = "%s"\n'%client_name)
            fd.write('ReqName = "%s"\n'%request_name)
            fd.write('ReqGlidein = "%s"\n'%glidein_name)
            fd.write('ReqIdleGlideins = %i\n'%min_nr_glideins)

            # write out both the params
            prefix=frontendConfig.glidein_param_prefix
            for attr in glidein_params.keys():
                el=glidein_params[attr]
                if type(el)==type(1):
                    # don't quote ints
                    fd.write('%s%s = %s\n'%(prefix,attr,el))
                else:
                    fd.write('%s%s = "%s"\n'%(prefix,attr,el))
        finally:
            fd.close()

        condorExe.exe_cmd("../sbin/condor_advertise","UPDATE_MASTER_AD %s %s"%(pool2str(factory_pool),tmpnam))
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

