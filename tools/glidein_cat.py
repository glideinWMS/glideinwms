#!/bin/env python
 
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glidein_cat.py,v 1.2.28.1 2010/08/31 18:08:04 parag Exp $
#
# Description:
#   Execute a cat command on a condor job working directory
#
# Usage:
#  glidein_cat.py <cluster>.<process> [<file>] [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>]
#
# Author:
#   Igor Sfiligoi (May 2007)
#
# License:
#  Fermitools
#

import sys,os.path
sys.path.append(os.path.join(sys.path[0],"lib"))
sys.path.append(os.path.join(sys.path[0],"../lib"))

import glideinCmd

glideinCmd.exe_cmd(lambda argv:(['cat']+argv))
