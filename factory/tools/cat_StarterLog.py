#!/bin/env python
#
# cat_StarterLog.py
#
# Print out the StarterLog for a glidein output file
#
# Usage: cat_StarterLog.py logname
#

import sys
sys.path.append("lib")
import gWftLogParser

USAGE="Usage: cat_StarterLog.py <logname>"

def main():
    try:
        print gWftLogParser.get_CondorLog(sys.argv[1],"StarterLog.vm2")
    except:
        sys.stderr.write("%s\n"%USAGE)
        sys.exit(1)


if __name__ == '__main__':
    main()
 
