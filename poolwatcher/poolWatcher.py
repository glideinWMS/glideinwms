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
    gsite=condorMonitor.Group(status,lambda el:el['GLIDEIN_Site'],lambda el:el)
    gsite.load()
    sites=gsite.fetchStored()
    print time.ctime()
    for s in sites.keys():
        print "Site: '%s' VMs: %i"%(s,len(sites[s]))
    time.sleep(30)
