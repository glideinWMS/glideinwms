#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: cat_StartdLog.py,v 1.7.28.2 2010/09/24 15:38:10 parag Exp $
#
# Description:
#   Print out the StartdLog for a glidein output file
#
# Usage: cat_StartdLog.py logname
#

import os.path
import sys
STARTUP_DIR=sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR,"lib"))
import gWftLogParser

USAGE="Usage: cat_StartdLog.py [-monitor] <logname>"

def main():
    if sys.argv[1]=='-monitor':
        fname=sys.argv[2]
        condor_log_id="StartdLog.monitor"
    else:
        fname=sys.argv[1]
        condor_log_id="StartdLog"
        
    try:
        print gWftLogParser.get_CondorLog(fname,condor_log_id)
    except:
        sys.stderr.write("%s\n"%USAGE)
        sys.exit(1)


if __name__ == '__main__':
    main()
 
