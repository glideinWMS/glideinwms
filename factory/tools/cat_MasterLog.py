#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Print out the MasterLog for a glidein output file
#
# Usage: cat_MasterLog.py logname
#

from __future__ import print_function
import os.path
import sys
STARTUP_DIR=sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))
from glideinwms.factory.tools.lib import gWftLogParser

USAGE="Usage: cat_MasterLog.py [-monitor] <logname>"

def main():
    if sys.argv[1]=='-monitor':
        fname=sys.argv[2]
        condor_log_id="MasterLog.monitor"
    else:
        fname=sys.argv[1]
        condor_log_id="MasterLog"
        
    try:
        print(gWftLogParser.get_CondorLog(fname, condor_log_id))
    except:
        sys.stderr.write("%s\n"%USAGE)
        sys.exit(1)


if __name__ == '__main__':
    main()
 
