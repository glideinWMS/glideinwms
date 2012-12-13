#!/usr/bin/env python
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
STARTUP_DIR=sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR,"../../.."))
from glideinwms.factory.tools.lib import gWftLogParser

USAGE="Usage: cat_StarterLog.py [-monitor] <logname>"

def main():
    if sys.argv[1]=='-monitor':
        fname=sys.argv[2]
        condor_log_id="((StarterLog.monitor)|(StarterLog.vm1))"
    else:
        fname=sys.argv[1]
        condor_log_id="((StarterLog)|(StarterLog.vm2))"
        
    try:
        print gWftLogParser.get_CondorLog(fname,condor_log_id)
    except:
        sys.stderr.write("%s\n"%USAGE)
        sys.exit(1)


if __name__ == '__main__':
    main()
 
