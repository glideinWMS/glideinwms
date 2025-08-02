#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Print out the StartdHistoryLog for a glidein output file.

Usage:
    cat_StartdHistoryLog.py <logname>
"""

import os.path
import sys

from glideinwms.factory.tools.lib import gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))

USAGE = "Usage: cat_StartdHistoryLog.py <logname>"


def main():
    """Extract and print the StartdHistoryLog from a glidein output file.

    This function reads the log file specified as the first command-line
    argument, sets the log identifier to "StartdHistoryLog", and prints out the
    corresponding log content using the gWftLogParser.get_CondorLog function.
    If any exception occurs during log retrieval, it prints the usage message
    to standard error and exits the program with a non-zero status code.
    """
    fname = sys.argv[1]
    condor_log_id = "StartdHistoryLog"

    try:
        print(gWftLogParser.get_condor_log(fname, condor_log_id))
    except Exception:
        sys.stderr.write("%s\n" % USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
