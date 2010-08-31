#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: poolWatcher.py,v 1.3.20.1 2010/08/31 18:49:17 parag Exp $
#
# Description:
#   This is the main of the poolWatcher
#
# Arguments: (eventually)
#   $1 = poll period (in seconds)
#   $2 = advertize rate (every $2 loops)
#   $3 = glidein submit_dir
#
# Author:
#   Igor Sfiligoi (Feb 13th 2007)
#

import os
import os.path
import sys
import traceback
import time
sys.path.append("../lib")

import condorMonitor

while 1:
    status=condorMonitor.CondorStatus()
    status.load()
    ssite=condorMonitor.Summarize(status,lambda el:[el['GLIDEIN_Site'],el['State']])
    sites=ssite.countStored()
    print time.ctime()
    for s in sites.keys():
	states=sites[s]
	if states.has_key('Claimed'):
          claimed=states['Claimed']
        else: 
          claimed=0
        if states.has_key('Unclaimed'):
          unclaimed=states['Unclaimed']
        else:
          unclaimed=0

        print "Site: '%s' Claimed: %i Unclaimed: %i"%(s,claimed,unclaimed)
    time.sleep(30)
