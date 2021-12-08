#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   Execute a ps command on a condor job
#
# Usage:
#  glidein_ps.py <cluster>.<process> [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>]  [<options>]

import sys, os.path
sys.path.append(os.path.join(sys.path[0], "../.."))

from glideinwms.tools.lib import glideinCmd

glideinCmd.exe_cmd_simple(lambda argv:(['ps', '-u', '`id', '-n', '-u`']+argv))
