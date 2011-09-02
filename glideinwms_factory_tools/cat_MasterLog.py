#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: cat_MasterLog.py,v 1.3.12.2 2010/09/24 15:30:36 parag Exp $
#
# Description:
#   Print out the MasterLog for a glidein output file
#
# Usage: cat_MasterLog.py logname
#

import sys
import gWftLogParser

USAGE = "Usage: cat_MasterLog.py [-monitor] <logname>"

def main():
    if sys.argv[1] == '-monitor':
        fname = sys.argv[2]
        condor_log_id = "MasterLog.monitor"
    else:
        fname = sys.argv[1]
        condor_log_id = "MasterLog"

    try:
        print gWftLogParser.get_CondorLog(fname, condor_log_id)
    except:
        sys.stderr.write("%s\n" % USAGE)
        sys.exit(1)


if __name__ == '__main__':
    main()

