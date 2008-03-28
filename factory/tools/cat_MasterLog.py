#!/bin/env python
#
# cat_MasterLog.py
#
# Print out the MasterLog for a glidein output file
#
# Usage: cat_MasterLog.py logname
#

import sys
sys.path.append("lib")
import gWftLogParser

USAGE="Usage: cat_MasterLog.py <logname>"

def main():
    try:
        print gWftLogParser.get_CondorLog(sys.argv[1],"MasterLog")
    except:
        sys.stderr.write("%s\n"%USAGE)
        sys.exit(1)


if __name__ == '__main__':
    main()
 
