#!/bin/env python
#
# Description:
#   Check if a glideinFrontend is running
# 
# Arguments:
#   $1 = config file
#
# Author:
#   Igor Sfiligoi Jul 17th 2008
#

import sys,os.path
sys.path.append(os.path.join(sys.path[0],"../lib"))
import glideinFrontendPidLib

config_dict={}
try:
    execfile(sys.argv[1],config_dict)
    log_dir=config_dict['log_dir']
    frontend_pid=glideinFrontendPidLib.get_frontend_pid(log_dir)
except:
    print "Not running"
    sys.exit(1)

print "Running"
sys.exit(0)

