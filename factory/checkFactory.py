#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Check if a glideinFactory is running
# 
# Arguments:
#   $1 = glidein submit_dir (i.e. factory dir)
#
# Author:
#   Igor Sfiligoi Jul 9th 2008
#

import sys,os.path
sys.path.append(os.path.join(sys.path[0],"../.."))
from glideinwms.factory import glideFactoryPidLib

try:
    startup_dir=sys.argv[1]
    factory_pid=glideFactoryPidLib.get_factory_pid(startup_dir)
except:
    print "Not running"
    sys.exit(1)

print "Running"
sys.exit(0)

