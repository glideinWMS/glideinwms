#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0


"""Print out the StartdLog for a glidein output file.

Usage:
    cat_StartdLog.py [-monitor] <logname>
"""

import os.path
import sys

from glideinwms.factory.tools.lib import gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))

USAGE = "Usage: cat_StartdLog.py [-monitor] <logname>"


def main():
    """Extract and print the StartdLog from a glidein output file.

    If the command-line argument '-monitor' is provided, the log identifier is set to
    "StartdLog.monitor". Otherwise, it is set to "StartdLog". The function then prints
    the corresponding log content to standard output. If an error occurs during log retrieval,
    the usage message is printed to standard error and the program exits with a non-zero status.

    Raises:
        Exception: If an error occurs during log retrieval.
    """
    if sys.argv[1] == "-monitor":
        fname = sys.argv[2]
        condor_log_id = "StartdLog.monitor"
    else:
        fname = sys.argv[1]
        condor_log_id = "StartdLog"

    try:
        print(gWftLogParser.get_CondorLog(fname, condor_log_id))
    except Exception:
        sys.stderr.write("%s\n" % USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
