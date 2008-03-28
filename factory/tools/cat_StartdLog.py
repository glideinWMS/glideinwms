#!/bin/env python
#
# cat_StartdLog.py
#
# Print out the StartdLog for a glidein output file
#
# Usage: cat_StartdLog.py logname
#

import sys,os,os.path,time
sys.path.append("lib")
import gWftArgsHelper,gWftLogParser

USAGE="Usage: cat_StartdLog.py <logname>"

def main():
    try:
        print gWftLogParser.get_StartdLog(sys.argv[1])
    except ValueError, e:
        sys.stderr.write("%s\n\n%s\n"%(e,USAGE))
        sys.exit(1)


if __name__ == '__main__':
    main()
 
