#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glidein_interactive.py,v 1.1.28.2 2010/09/24 15:38:11 parag Exp $
#
# Description:
#   Execute an arbitrary command on a condor job working directory
#
# Usage:
#  glidein_interactive.py <cluster>.<process> [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>] command
#
# Author:
#   Igor Sfiligoi (May 2008)
#
# License:
#  Fermitools
#

import sys,os.path
sys.path.append(os.path.join(sys.path[0],"lib"))
sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideinCmd

def argv_interactive(argv):
    if len(argv)<1:
        raise RuntimeError, "Please specify the command to run"
    return argv

glideinCmd.exe_cmd(argv_interactive)
