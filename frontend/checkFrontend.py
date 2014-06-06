#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Check if a glideinFrontend is running
# 
# Arguments:
#   $1 = work_dir
#   $2 = (optional) run mode (defaults to "run")
#
# Author:
#   Igor Sfiligoi
#

import sys,os.path
sys.path.append(os.path.join(sys.path[0],"../.."))
from glideinwms.frontend import glideinFrontendPidLib

try:
    work_dir=sys.argv[1]
    action_type=glideinFrontendPidLib.get_frontend_action_type(work_dir)
except:
    print "Not running"
    sys.exit(1)

if action_type is None:
    # if not defined, assume it is the standard running type
    action_type = "run"

if len(sys.argv)>=3:
    req_action_type = sys.argv[2]
else:
    req_action_type = "run"


if action_type!=req_action_type:
    print "Not running my type"
    sys.exit(1)

print "Running"
sys.exit(0)
