#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Print out the StarterLog for a glidein output file.

 Usage:
    cat_StarterLog.py [-monitor]|[-slot <slotname>] <logname>
"""


import os.path
import sys

from glideinwms.factory.tools.lib import gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))

USAGE = "Usage: cat_StarterLog.py [-monitor]|[-slot <slotname>] <logname>"


def main():
    """Extract and print the StarterLog from a glidein output file.

    This function determines the appropriate Condor log identifier based on the
    command-line arguments. If the first argument is "-monitor", it uses the
    "StartdLog.monitor" identifier; otherwise, it uses "StartdLog". The function
    then prints the content of the corresponding log file to standard output. If
    an error occurs during log retrieval, it prints a usage message to standard
    error and exits with a non-zero status.

    Raises:
        Exception: If an error occurs during log retrieval.
    """
    try:
        if sys.argv[1] == "-monitor":
            fname = sys.argv[2]
            condor_log_id = "((StarterLog.monitor)|(StarterLog.vm1))"
        elif sys.argv[1].startswith("-slot"):
            if len(sys.argv) < 4:
                # Either slotname or log name not provided
                raise Exception("Insufficient arguments")
            else:
                fname = sys.argv[len(sys.argv) - 1]
                slotname = sys.argv[2]
                condor_log_id = "(StarterLog.%s)" % slotname
        else:
            fname = sys.argv[len(sys.argv) - 1]
            condor_log_id = "((StarterLog)|(StarterLog.vm2))"

        matches = gWftLogParser.get_starter_slot_names(fname)
        if len(matches):
            logs = ", ".join(matches)
            print("StarterLogs available for slots: %s" % logs.replace("StarterLog.", ""))
        print(gWftLogParser.get_condor_log(fname, condor_log_id))
    except Exception:
        sys.stderr.write("%s\n" % USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
