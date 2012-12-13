#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Execute a top command on a condor job
#
# Usage:
#  glidein_top.py <cluster>.<process> [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>]
#
# Author:
#   Igor Sfiligoi (May 2007)
#
# License:
#  Fermitools
#

import sys,os.path
sys.path.append(os.path.join(sys.path[0],"../.."))

from glideinwms.tools.lib import glideinCmd

def argv_top(argv):
    if len(argv)!=0:
        raise RuntimeError, "Unexpected parameters starting with %s found!"%argv[0]
    return ['top', '-b', '-n', '1']

glideinCmd.exe_cmd_simple(argv_top)
