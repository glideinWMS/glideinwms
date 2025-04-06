#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

""" Print out the MasterLog for a glidein output file

 Usage: cat_MasterLog.py logname
"""


import os.path
import sys

from glideinwms.factory.tools.lib import gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))

USAGE = "Usage: cat_MasterLog.py [-monitor] <logname>"


def main():
    """Main function to extract and print the MasterLog from the specified log file.

    If the first command-line argument is "-monitor", the script will treat the log as a monitor log
    and use the identifier "MasterLog.monitor". Otherwise, it uses "MasterLog". The function attempts
    to print the extracted log to standard output. If an error occurs, it writes the usage message to
    standard error and exits with status code 1.

    Raises:
        Exception: Any exception during log extraction will trigger printing of the usage message
                   and a non-zero exit.
    """
    if sys.argv[1] == "-monitor":
        fname = sys.argv[2]
        condor_log_id = "MasterLog.monitor"
    else:
        fname = sys.argv[1]
        condor_log_id = "MasterLog"

    try:
        print(gWftLogParser.get_CondorLog(fname, condor_log_id))
    except Exception:
        sys.stderr.write("%s\n" % USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
