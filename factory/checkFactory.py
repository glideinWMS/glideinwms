#!/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: checkFactory.py,v 1.4.24.1 2010/08/31 18:49:16 parag Exp $
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
sys.path.append(os.path.join(sys.path[0],"../lib"))
import glideFactoryPidLib

try:
    startup_dir=sys.argv[1]
    factory_pid=glideFactoryPidLib.get_factory_pid(startup_dir)
except:
    print "Not running"
    sys.exit(1)

print "Running"
sys.exit(0)

