#!/usr/bin/env python

# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glidein_cat.py,v 1.2.12.2 2010/09/24 15:30:37 parag Exp $
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

import glideinCmd

glideinCmd.exe_cmd(lambda argv:(['cat'] + argv))

