#!/usr/bin/env python
 
# Project:
#   glideinWMS
#
# File Version: 
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

import sys
import os.path
sys.path.append(os.path.join(sys.path[0],"../.."))
from glideinwms.tools.lib import glideinCmd

glideinCmd.exe_cmd(lambda argv:(['cat']+argv))
