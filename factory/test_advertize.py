#
# Project:
#   glideinWMS
#
# File Version: 
#

import os,sys,time
from glideinwms.lib import condorExe

client_id="glideclient"

def advertizeWork(client_name,req_name,glidein_name,min_glideins,glidein_params={}):
    # get a 9 digit number that will stay 9 digit for the next 25 years
    short_time = time.time()-1.05e9
    tmpnam="/tmp/aw_%li_%li"%(short_time,os.getpid())
    fd=file(tmpnam,"w")
    try:
        try:
            fd.write('MyType = "%s"\n'%client_id)
            fd.write('GlideMyType = "%s"\n'%client_id)
            fd.write('Name = "%s@%s"\n'%(req_name,client_name))
            fd.write('ClientName = "%s"\n'%client_name)
            fd.write('ReqName = "%s"\n'%req_name)
            fd.write('ReqGlidein = "%s"\n'%glidein_name)
            fd.write('ReqIdleGlideins=%i\n'%min_glideins)

            # write out both the attributes, prefixes and counts
            prefix="GlideinParam"
            data=glidein_params
            for attr in data.keys():
                    el=data[attr]
                    if type(el)==type(1):
                        # don't quote ints
                        fd.write('%s%s = %s\n'%(prefix,attr,el))
                    else:
                        fd.write('%s%s = "%s"\n'%(prefix,attr,el))
        finally:
            fd.close()

        condorExe.exe_cmd("../sbin/condor_advertise","UPDATE_MASTER_AD %s"%tmpnam)
    finally:
        os.remove(tmpnam)

advertizeWork("pcsfiligoi.lnf.infn.it","req1","test9@cms-xen6.fnal.gov",8,{"GLIDEIN_Collector":"cms-xen6.fnal.gov"})
advertizeWork("pcsfiligoi.fnal.gov","req1","test9@cms-xen6.fnal.gov",5,{"GLIDEIN_Collector":"cms-xen6.fnal.gov"})
advertizeWork("pcsfiligoi.lnf.infn.it","req2","test9@cms-xen6.fnal.gov",11,{"GLIDEIN_Collector":"cms-xen6.fnal.gov"})
