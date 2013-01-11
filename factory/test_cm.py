#
# Project:
#   glideinWMS
#
# File Version: 
#

from glideinwms.lib import condorMonitor

condorMonitor.set_path("/home/sfiligoi/condor/dist/bin")
c=condorMonitor.CondorQ(schedd_name="schedd_glideins@cms-xen6.fnal.gov")
c.load()
d=c.fetchStored()

s=condorMonitor.CondorStatus()
s.load("GLIDEIN_CLUSTER=!=Undefined")
e=s.fetchStored()

def group_unclaimed(c_list):
    out={"nr_els":0,"TotalDisk":0,"MyAddress":""}
    for c in c_list:
        out["nr_els"]+=1
        out["TotalDisk"]+=c["TotalDisk"]
        out["MyAddress"]+=c["MyAddress"]
    return out

sg=condorMonitor.Group(s,lambda el:el["GLIDEIN_CLUSTER"],group_unclaimed)
sg.load()
f=sg.fetchStored()
