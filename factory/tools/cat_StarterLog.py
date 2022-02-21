#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Print out the StarterLog for a glidein output file
#
# Usage: cat_StarterLog.py logname
#


import os.path
import sys

from glideinwms.factory.tools.lib import gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))

USAGE = "Usage: cat_StarterLog.py [-monitor]|[-slot <slotname>] <logname>"


def main():
    try:
        if sys.argv[1] == "-monitor":
            fname = sys.argv[2]
            condor_log_id = "((StarterLog.monitor)|(StarterLog.vm1))"
        elif sys.argv[1].startswith("-slot"):
            if len(sys.argv) < 4:
                # Either slotname or log name not provided
                raise Exception("Insufficent arguments")
            else:
                fname = sys.argv[len(sys.argv) - 1]
                slotname = sys.argv[2]
                condor_log_id = "(StarterLog.%s)" % slotname
        else:
            fname = sys.argv[len(sys.argv) - 1]
            condor_log_id = "((StarterLog)|(StarterLog.vm2))"

        matches = gWftLogParser.get_StarterSlotNames(fname)
        if len(matches):
            logs = ", ".join(matches)
            print("StarterLogs available for slots: %s" % logs.replace("StarterLog.", ""))
        print(gWftLogParser.get_CondorLog(fname, condor_log_id))
    except:
        sys.stderr.write("%s\n" % USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
