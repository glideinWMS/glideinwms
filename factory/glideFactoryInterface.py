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

        # String to prefix for the attributes
        self.glidein_attr_prefix = ""

        # String to prefix for the parameters
        self.glidein_param_prefix = "GlideinParam"

        # String to prefix for the parameters
        self.glidein_count_prefix = "GlideinCount"

        # String to prefix for the requests
        self.client_req_prefix = "Req"



# global configuration of the module
factoryConfig=FactoryConfig()

############################################################
#
# User functions
#
############################################################


def findWork(factory_name,glidein_name):
    global factoryConfig
    
    status_constraint='(GlideinMyType=?="%s") && (ReqGlidein=?="%s@%s")'%(factoryConfig.client_id,glidein_name,factory_name)
    status=condorMonitor.CondorStatus("any")
    status.glidein_name=glidein_name
    status.load(status_constraint)

    data=status.fetchStored()

    reserved_names=("ReqName","ReqGlidein","ClientName")

    out={}

    # copy over requests and parameters
    for k in data.keys():
        kel=data[k]
        el={"requests":{},"params":{}}
        for (key,prefix) in (("requests",factoryConfig.client_req_prefix),
                             ("params",factoryConfig.glidein_param_prefix)):
            plen=len(prefix)
            for attr in kel.keys():
                if attr in reserved_names:
                    continue # skip reserved names
                if attr[:plen]==prefix:
                    el[key][attr[plen:]]=kel[attr]
        
        out[k]=el

    return out

# glidein_attrs is a dictionary of values to publish
#  like {"Arch":"INTEL","MinDisk":200000}
# similar for glidein_params and glidein_monitor_counts
def advertizeGlidein(factory_name,glidein_name,glidein_attrs={},glidein_params={},glidein_monitor_counts={}):
    global factoryConfig

    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/gfi_ag_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "%s"\n'%factoryConfig.factory_id)
            fd.write('GlideinMyType = "%s"\n'%factoryConfig.factory_id)
            fd.write('Name = "%s@%s"\n'%(glidein_name,factory_name))
            fd.write('FactoryName = "%s"\n'%factory_name)
            fd.write('GlideinName = "%s"\n'%glidein_name)

            # write out both the attributes, params and counts
            for (prefix,data) in ((factoryConfig.glidein_attr_prefix,glidein_attrs),
                                  (factoryConfig.glidein_param_prefix,glidein_params),
                                  (factoryConfig.glidein_count_prefix,glidein_monitor_counts)):
                for attr in data.keys():
                    el=data[attr]
                    if type(el)==type(1):
                        # don't quote ints
                        fd.write('%s%s = %s\n'%(prefix,attr,el))
                    else:
                        escaped_el=string.replace(el,'"','\\"')
                        fd.write('%s%s = "%s"\n'%(prefix,attr,escaped_el))
        finally:
            fd.close()

        condorExe.exe_cmd("../sbin/condor_advertise","UPDATE_MASTER_AD %s"%tmpnam)
    finally:
        os.remove(tmpnam)
