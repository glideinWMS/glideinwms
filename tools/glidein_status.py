#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Equivalent to condor_status, but with glidein specific info
#
# Usage:
#  glidein_status.py [-help] [-gatekeeper] [-glidecluster] [-withmonitor] [-total] [-site] [-pool name]
#
# Author:
#   Igor Sfiligoi
#

def help():
    print "glidein_status.py [-help] [-gatekeeper] [-glidecluster] [-glexec] [-withmonitor] [-bench] [-total] [-site] [-pool name] [-constraint name]"
    print
    print "Options:"
    print " -gatekeeper   : Print out the glidein gatekeeper"
    print " -glidecluster : Print out the glidein cluster nr"
    print " -glexec       : Print out if glexec is used"
    print " -withmonitor  : Print out the monitoring VMs, too"
    print " -bench        : Print out the benchmarking numbers, too"
    print " -total        : Print out only the totals (skip details)"
    print " -site         : Summarize by site (default by entry name)"
    print " -pool         : Same as -pool in condor_status"
    print " -constraint   : Same as -constraint in condor_status"
    print


import time
import sys,os.path
sys.path.append(os.path.join(sys.path[0],"../.."))

from glideinwms.lib import condorMonitor

pool_name=None
constraint=None

want_gk=False
want_glidecluster=False
want_monitor=False
want_bench=False
want_glexec=False
total_only=False
summarize='entry'

arglen=len(sys.argv)
i=1
while i<arglen:
    arg=sys.argv[i]

    if arg=='-gatekeeper':
        want_gk=True
    elif arg=='-glidecluster':
        want_glidecluster=True
    elif arg=='-glexec':
        want_glexec=True
    elif arg=='-withmonitor':
        want_monitor=True
    elif arg=='-bench':
        want_bench=True
    elif arg=='-total':
        total_only=True
    elif arg=='-site':
        summarize='site'
    elif arg=='-pool':
        i+=1
        pool_name=sys.argv[i]
    elif arg=='-constraint':
        i+=1
        constraint=sys.argv[i]
    else:
        help()
        sys.exit(1)

    i+=1

if not want_monitor:
    if constraint==None:
        constraint='IS_MONITOR_VM =!= TRUE'
    else:
        constraint='(%s) && (IS_MONITOR_VM =!= TRUE)'%constraint

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

if want_glexec:
    format_list.append(('GLEXEC_STARTER','b'))
    format_list.append(('GLEXEC_JOB','b'))
    attrs.append('GLEXEC_STARTER')
    attrs.append('GLEXEC_JOB')

if want_bench:
    format_list.append(('KFlops','i'))
    format_list.append(('Mips','i'))
    attrs.append('KFlops')
    attrs.append('Mips')

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

if want_bench:
    counts_header+=('GFlops','  GIPS')

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
print_mask+=" %-19s %-19s"
if want_glidecluster:
    print_mask+=" %-39s %-14s"
if want_glexec:
    print_mask+=" %-7s"
if want_bench:
    print_mask+=" %-5s %-5s"
print_mask+=" %-9s %-8s %-10s"

header=('Name','Site')
if want_gk:
    header+=('Grid','Gatekeeper')
header+=('Factory','Entry')
if want_glidecluster:
    header+=('GlideSchedd','GlideCluster')
if want_glexec:
    header+=('gLExec',)
if want_bench:
    header+=('MFlop','Mips')
header+=('State','Activity','ActvtyTime')

if not total_only:
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

    if el.has_key('KFlops'):
        gflops=(el['KFlops']*1.e-6)
        mflops_str="%i"%(el['KFlops']/1000)
    else:
        mflops=0.0
        mflops_str="???"
        
    if el.has_key('Mips'):
        gips=el['Mips']*1.e-3
        mips_str=el['Mips']
    else:
        mips=0.0
        mips_str="???"
        
    if summarize=='site':
        sum_str=cel['GLIDEIN_Site']
    else:
        sum_str="%s@%s@%s"%(cel['GLIDEIN_Entry_Name'],cel['GLIDEIN_Name'],cel['GLIDEIN_Factory'])
    if not counts.has_key(sum_str):
        counts[sum_str]={}
        for c in counts_header:
            counts[sum_str][c]=0

    for t in ('Total',sum_str):
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
        if want_bench:
            ct['GFlops']+=gflops
            ct['  GIPS']+=gips


    if not total_only:
        print_arr=(vm_name,cel['GLIDEIN_Site'])
        if want_gk:
            print_arr+=(cel['GLIDEIN_GridType'],cel['GLIDEIN_Gatekeeper'])
        print_arr+=("%s@%s"%(cel['GLIDEIN_Name'],cel['GLIDEIN_Factory']),cel['GLIDEIN_Entry_Name'])
        if want_glidecluster:
            print_arr+=(cel['GLIDEIN_Schedd'],"%i.%i"%(cel['GLIDEIN_ClusterId'],cel['GLIDEIN_ProcId']))
        if want_glexec:
            glexec_str='None'
            if el.has_key('GLEXEC_JOB') and el['GLEXEC_JOB']:
                glexec_str='Job'
            elif el.has_key('GLEXEC_STARTER') and el['GLEXEC_STARTER']:
                glexec_str='Starter'
            print_arr+=(glexec_str,)
        if want_bench:
            print_arr+=(mflops_str,mips_str)
        print_arr+=(state,activity,cel['EnteredCurrentActivity'])

        print print_mask%print_arr

print

count_print_mask="%39s"
for c in counts_header:
    count_print_mask+=" %%%is"%len(c)
print count_print_mask%(('',)+counts_header)

ckeys=counts.keys()

def ltotal_cmp(x,y): # Total last
    # Total always last
    if x=='Total':
       if y=='Total':
           return 0;
       else:
           return 1;
    elif y=='Total':
        return -1

    return cmp(x,y)

def entry_cmp(x,y):
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

if summarize=='site':
    ckeys.sort(ltotal_cmp)
else: # default is entry
    ckeys.sort(entry_cmp)

if len(ckeys)>1:
    print # put a space before the entry names

for t in ckeys:
    if t=='Total':
        print # put an empty line before Total
    count_print_val=[t]
    for c in counts_header:
        count_print_val.append(int(counts[t][c]))
    
    print count_print_mask%tuple(count_print_val)

print

