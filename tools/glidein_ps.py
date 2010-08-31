#!/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glidein_ps.py,v 1.2.28.1 2010/08/31 18:49:17 parag Exp $
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
sys.path.append(os.path.join(sys.path[0],"lib"))
sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideinCmd

glideinCmd.exe_cmd_simple(lambda argv:(['ps', '-u', '`id', '-n', '-u`']+argv))
