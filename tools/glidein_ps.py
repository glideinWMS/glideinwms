#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Execute a ps command on a condor job
#
# Usage:
#  glidein_ps.py <cluster>.<process> [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>]  [<options>]
#
# Author:
#   Igor Sfiligoi (May 2008)
#
# License:
#  Fermitools
#

import sys,os.path
sys.path.append(os.path.join(sys.path[0],"../.."))

from glideinwms.tools.lib import glideinCmd

glideinCmd.exe_cmd_simple(lambda argv:(['ps', '-u', '`id', '-n', '-u`']+argv))
