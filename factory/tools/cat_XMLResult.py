#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Print out the XML Result for a glidein output file
#
# Usage: cat_XMLResult.py logname
#

import os.path
import sys
STARTUP_DIR=sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR,"lib"))
import gWftLogParser

USAGE="Usage: cat_XMLResult.py <logname>"

def main():
    try:
        fname=sys.argv[1]
        print gWftLogParser.get_XMLResult(fname)
    except:
        raise
        sys.stderr.write("%s\n"%USAGE)
        sys.exit(1)


if __name__ == '__main__':
    main()
 
