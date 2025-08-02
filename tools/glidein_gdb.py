#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   Execute a ls command on a condor job working directory
#
# Usage:
#  glidein_gdb.py <cluster>.<process> <pid> [<command>] [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>]
#
# Supported gdb commands:
#  where (default)

import os.path
import sys

from glideinwms.tools.lib import glideinCmd

sys.path.append(os.path.join(sys.path[0], "../.."))


def argv_gdb(argv):
    if len(argv) == 0:
        raise RuntimeError("Missing PID")
    pid = argv[0]

    # parse args to get the command
    gdb_cmd = "where"
    if len(argv) > 1:
        if argv[1] == "where":
            gdb_cmd = "where"
        else:
            raise RuntimeError("Unexpected command %s found!\nOnly where supported." % argv[1])

    # select the lines
    gdbcommand = "gdb.command"

    script_lines = []
    script_lines.append("cat > %s <<EOF" % gdbcommand)
    script_lines.append("set height 0")
    script_lines.append(gdb_cmd)
    script_lines.append("quit")
    script_lines.append("EOF")
    script_lines.append(f"gdb -command {gdbcommand} /proc/{pid}/exe {pid}")
    script_lines.append("rm -f %s" % gdbcommand)

    return script_lines


glideinCmd.exe_cmd_script(argv_gdb)
