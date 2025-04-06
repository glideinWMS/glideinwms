#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Print out the named HTCondor Log for a glidein output file.

Usage:
    cat_named_log.py [-monitor] <HTC_log> <GWMS_logname>
"""

import os.path
import sys

from glideinwms.factory.tools.lib import gWftLogParser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))

USAGE = "Usage: cat_named_log.py [-monitor] <HTC_log> <GWMS_logname>"


def main():
    """Extract and print a named HTCondor log from a glidein output file.

    Depending on whether the '-monitor' flag is provided, the function will
    use different log identifiers. If '-monitor' is provided, the first argument
    after '-monitor' is used as the log name (lname) and the next argument is used
    as the file name (fname), with the log identifier set to "<lname>.monitor". If the
    flag is not provided, the first argument is treated as the log identifier and the
    second as the file name.

    The function prints the extracted log content to standard output. If an error
    occurs (e.g. log extraction fails), the usage message is printed to standard error
    and the program exits with a status code of 1.
    """
    if sys.argv[1] == "-monitor":
        lname = sys.argv[2]
        fname = sys.argv[3]
        # ((name1)|(name2)) allows to check for multiple names
        condor_log_id = f"{lname}.monitor"
    else:
        condor_log_id = sys.argv[1]
        fname = sys.argv[2]

    try:
        print(gWftLogParser.get_CondorLog(fname, condor_log_id))
    except Exception:
        sys.stderr.write("%s\n" % USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
