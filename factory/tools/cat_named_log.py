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
#   Print out the named HTCondor Log for a glidein output file
#
# Usage: cat_named_log.py [-monitor] HTC_log GWMS_logname
#

from __future__ import print_function

import os.path
import sys

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))
from glideinwms.factory.tools.lib import gWftLogParser

USAGE = "Usage: cat_named_log.py [-monitor] <HTC_log> <GWMS_logname>"


def main():
    if sys.argv[1] == "-monitor":
        lname = sys.argv[2]
        fname = sys.argv[3]
        # ((name1)|(name2)) allows to check for multiple names
        condor_log_id = "%s.monitor" % (lname,)
    else:
        condor_log_id = sys.argv[1]
        fname = sys.argv[2]

    try:
        print(gWftLogParser.get_CondorLog(fname, condor_log_id))
    except:
        sys.stderr.write("%s\n" % USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
