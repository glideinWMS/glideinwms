#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   Execute an arbitrary command on a condor job working directory
#
# Usage:
#  glidein_interactive.py <cluster>.<process> [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>] command

import os.path
import sys

sys.path.append(os.path.join(sys.path[0], "../.."))

from glideinwms.tools.lib import glideinCmd


def argv_interactive(argv):
    if len(argv) < 1:
        raise RuntimeError("Please specify the command to run")
    return argv


glideinCmd.exe_cmd(argv_interactive)
