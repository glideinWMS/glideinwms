#!/bin/env python
#
# Description:
#   This tool displays the status of the glideinWMS pool
#   in a text format
#
# Arguments:
#   [-pool collector_node] Entries|Sites|Gatekeepers
#
# Author:
#   Igor Sfiligoi (May 9th 2007)
#

import string
import sys
sys.path.append("../factory")
sys.path.append("../frontend")
sys.path.append("../lib")

import glideFactoryInterface
import glideinFrontendInterface

pool_name=None
remove_condor_stats=True
remove_internals=True
txt_type=None

# parse arguments
alen=len(sys.argv)
i=1
while (i<alen):
    ael=sys.argv[i]
    if ael=='-pool':
        i=i+1
        pool_name=sys.argv[i]
    elif ael in ('Entries','Sites','Gatekeepers'):
        txt_type=ael
    else:
        raise RuntimeError,"Unknown option '%s'"%ael
    i=i+1

# get data
glideins_obj=glideinFrontendInterface.findGlideins(pool_name)

# Get a dictionary of
#  RequestedIdle
#  Idle
#  Running
txt_data={}

# extract data
glideins=glideins_obj.keys()
for glidein in glideins:
    glidein_el=glideins_obj[glidein]

    key=glidein
    if txt_data.has_key(key):
        key_el=txt_data[key]
    else:
        key_el={'RequestedIdle':0,'Idle':0,'Running':0}
        txt_data[key]=key_el

    if glidein_el.has_key('monitor'):
        key_el['RequestedIdle']+=glidein_el['monitor']['TotalRequestedIdle']
        key_el['Idle']+=glidein_el['monitor']['TotalStatusIdle']
        key_el['Running']+=glidein_el['monitor']['TotalStatusRunning']

#print data
txt_keys=txt_data.keys()
txt_keys.sort()

print '%s  ReqIdle   Idle    Running'%string.ljust('Entry',50)
print '========================================-========-========-========'
for key in txt_keys:
    key_el=txt_data[key]
    print "%s %8i %8i %8i"%(string.ljust(key,50),key_el['RequestedIdle'],key_el['Idle'],key_el['Running'])


