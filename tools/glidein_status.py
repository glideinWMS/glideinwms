#!/bin/env python
#
# glidein_status.py
#
# Description:
#   Equivalent to condor_status, but with glidein specific info
#
# Usage:
#  glidein_status.py [-help] [-gatekeeper] [-glidecluster] [-withmonitor]
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

want_gk=False
want_glidecluster=False
want_monitor=False

for arg in sys.argv:
    if arg=='-gatekeeper':
        want_gk=True
    elif arg=='-glidecluster':
        want_glidecluster=True
    elif arg=='-withmonitor':
        want_monitor=True
    elif arg in ('-h','-help'):
        print "glidein_status.py [-help] [-gatekeeper] [-glidecluster] [-withmonitor]"
        sys.exit(1)

if not want_monitor:
    constraint='IS_MONITOR_VM =!= TRUE'

format_list=[('Machine','s'),('State','s'),('Activity','s'),
             ('GLIDEIN_Site','s'),
             ('GLIDEIN_Factory','s'),('GLIDEIN_Name','s'),('GLIDEIN_Entry_Name','s'),('EnteredCurrentActivity','i')]
attrs=['State','Activity','GLIDEIN_Site','GLIDEIN_Factory','GLIDEIN_Name','GLIDEIN_Entry_Name','EnteredCurrentActivity']

if want_gk:
    format_list.append(('GLIDEIN_Gatekeeper','s'))
    format_list.append(('GLIDEIN_GridType','s'))
    attrs.append('GLIDEIN_Gatekeeper')
    attrs.append('GLIDEIN_GridType')

if want_glidecluster:
    format_list.append(('GLIDEIN_ClusterId','i'))
    format_list.append(('GLIDEIN_ProcId','i'))
    format_list.append(('GLIDEIN_Schedd','s'))
    attrs.append('GLIDEIN_ClusterId')
    attrs.append('GLIDEIN_ProcId')
    attrs.append('GLIDEIN_Schedd')

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


counts_header=('Total','Owner','Claimed/Busy','Claimed/Retiring','Claimed/Other','Unclaimed','Matched','Other')

now=long(time.time())
def fmt_time(t):
    diff=now-t
    diff_secs=diff%60
    diff=diff/60
    diff_mins=diff%60
    diff=diff/60
    diff_hours=diff%24
    diff_days=diff/24
    return "%i+%02i:%02i:%02i"%(diff_days,diff_hours,diff_mins,diff_secs)


print_mask="%-39s %-9s"
if want_gk:
    print_mask+=" %-5s %-43s"
print_mask+=" %-24s %-14s"
if want_glidecluster:
    print_mask+=" %-39s %-14s"
print_mask+=" %-9s %-8s %-10s"

header=('Name','Site')
if want_gk:
    header+=('Grid','Gatekeeper')
header+=('Factory','Entry')
if want_glidecluster:
    header+=('GlideSchedd','GlideCluster')
header+=('State','Activity','ActvtyTime')

print
print print_mask%header
print

counts={'Total':{}}
for c in counts_header:
    counts['Total'][c]=0

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

    state=cel['State']
    activity=cel['Activity']

    entry_str="%s@%s@%s"%(cel['GLIDEIN_Entry_Name'],cel['GLIDEIN_Name'],cel['GLIDEIN_Factory'])
    if not counts.has_key(entry_str):
        counts[entry_str]={}
        for c in counts_header:
            counts[entry_str][c]=0

    for t in ('Total',entry_str):
        ct=counts[t]
        ct['Total']+=1
        if state in ('Owner','Unclaimed','Matched'):
            ct[state]+=1
        elif state=='Claimed':
            if activity in ('Busy','Retiring'):
                ct['%s/%s'%(state,activity)]+=1
            else:
                ct['Claimed/Other']+=1
        else:
            ct['Other']+=1
    
    print_arr=(vm_name,cel['GLIDEIN_Site'])
    if want_gk:
        print_arr+=(cel['GLIDEIN_GridType'],cel['GLIDEIN_Gatekeeper'])
    print_arr+=("%s@%s"%(cel['GLIDEIN_Name'],cel['GLIDEIN_Factory']),cel['GLIDEIN_Entry_Name'])
    if want_glidecluster:
        print_arr+=(cel['GLIDEIN_Schedd'],"%i.%i"%(cel['GLIDEIN_ClusterId'],cel['GLIDEIN_ProcId']))
    print_arr+=(state,activity,cel['EnteredCurrentActivity'])

    print print_mask%print_arr

print

count_print_mask="%39s"
for c in counts_header:
    count_print_mask+=" %%%is"%len(c)
print count_print_mask%(('',)+counts_header)

ckeys=counts.keys()

def ckeys_sort(x,y):
    # Total always last
    if x=='Total':
       if y=='Total':
           return 0;
       else:
           return 1;
    elif y=='Total':
        return -1

    # split in pieces and sort end to front
    x_arr=x.split('@')
    y_arr=y.split('@')
    for i in (2,1,0):
        res=cmp(x_arr[i],y_arr[i])
        if res!=0:
            return res
    return 0

ckeys.sort(ckeys_sort)

if len(ckeys)>1:
    print # put a space before the entry names

for t in ckeys:
    if t=='Total':
        print # put an empty line before Total
    count_print_val=[t]
    for c in counts_header:
        count_print_val.append(counts[t][c])
    
    print count_print_mask%tuple(count_print_val)

print

