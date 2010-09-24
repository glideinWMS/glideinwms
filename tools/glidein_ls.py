#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glidein_ls.py,v 1.4.28.2 2010/09/24 15:38:11 parag Exp $
#
# Description:
#   Execute a ls command on a condor job working directory
#
# Usage:
#  glidein_ls.py <cluster>.<process> [<dir>] [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>]
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

glideinCmd.exe_cmd(lambda argv:(['ls']+argv))
