#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   Execute a top command on a condor job
#
# Usage:
#  glidein_top.py <cluster>.<process> [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>]

import os.path
import sys

sys.path.append(os.path.join(sys.path[0], "../.."))

from glideinwms.tools.lib import glideinCmd


def argv_top(argv):
    if len(argv) != 0:
        raise RuntimeError("Unexpected parameters starting with %s found!" % argv[0])
    return ["top", "-b", "-n", "1"]


glideinCmd.exe_cmd_simple(argv_top)
