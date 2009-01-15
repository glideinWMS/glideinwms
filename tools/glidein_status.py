#!/bin/env python
#
# glidein_status.py
#
# Description:
#   Equivalent to condor_status, but with glidein specific info
#
# Usage:
#  glidein_status.py 
#
# Author:
#   Igor Sfiligoi
#

import sys,os.path
#sys.path.append(os.path.join(sys.path[0],"lib"))
sys.path.append(os.path.join(sys.path[0],"../lib"))

import condorMonitor

pool_name=None
constraint=None

format_list=[('Machine','s'),('State','s'),('Activity','s'),
             ('GLIDEIN_Site','s'),
             ('GLIDEIN_Factory','s'),('GLIDEIN_Name','s'),('GLIDEIN_Entry_Name','s')]
attrs=['State','Activity','GLIDEIN_Site','GLIDEIN_Factory','GLIDEIN_Name','GLIDEIN_Entry_Name']

cs=condorMonitor.CondorStatus(pool_name=pool_name)
cs.load(constraint=constraint,format_list=format_list)

data=cs.stored_data
keys=data.keys()

# sort on the Machine attribute
def machine_cmp(x,y):
    res=cmp(data[x]['Machine'],data[y]['Machine'])
    if res==0:
        res=cmp(x,y)
    return res

keys.sort()

print_mask="%-39s %-9s %-24s %-14s %-9s %-8s %-10s"

print
print print_mask%('Name','Site','Factory','Entry','State','Activity','ActvtyTime')
print

for vm_name in keys:
    el=data[vm_name]

    cel={} # this will have all the needed attributes (??? if nothing else)
    for a in attrs:        
        if el.has_key(a):
            cel[a]=el[a]
        else:
            cel[a]='???'
    
    print print_mask%(vm_name,cel['GLIDEIN_Site'],"%s@%s"%(cel['GLIDEIN_Name'],cel['GLIDEIN_Factory']),cel['GLIDEIN_Entry_Name'],cel['State'],cel['Activity'],'TBD')

print
