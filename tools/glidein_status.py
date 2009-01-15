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

import time
import sys,os.path
sys.path.append(os.path.join(sys.path[0],"../lib"))

import condorMonitor

pool_name=None
constraint=None

format_list=[('Machine','s'),('State','s'),('Activity','s'),
             ('GLIDEIN_Site','s'),
             ('GLIDEIN_Factory','s'),('GLIDEIN_Name','s'),('GLIDEIN_Entry_Name','s'),('EnteredCurrentActivity','i')]
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

keys.sort(machine_cmp)


now=long(time.time())
def fmt_time(t):
    diff=t-now
    diff_secs=diff%60
    diff=diff/60
    diff_mins=diff%60
    diff=diff/60
    diff_hours=diff%24
    diff_days=diff/24
    return "%i+%02i:%02i:%02i"%(diff_days,diff_hours,diff_mins,diff_secs)


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
    if cel['EnteredCurrentActivity']!='???':
        cel['EnteredCurrentActivity']=fmt_time(long(cel['EnteredCurrentActivity']))
    
    print print_mask%(vm_name,cel['GLIDEIN_Site'],"%s@%s"%(cel['GLIDEIN_Name'],cel['GLIDEIN_Factory']),cel['GLIDEIN_Entry_Name'],cel['State'],cel['Activity'],cel['EnteredCurrentActivity'])

print
