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
import string
import sys
STARTUP_DIR=sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR,"lib"))
import gWftLogParser

USAGE="Usage: cat_XMLResult.py -h|<logname>+"

def main():
    if (len(sys.argv)<2):
        sys.stderr.write("Missing logname.\n")
        sys.stderr.write("%s\n"%USAGE)
        sys.exit(1)        
    if (sys.argv[1]=="-h"):
        print USAGE
        sys.exit(0)

    if (len(sys.argv)==2):
        # single file, just pass through
        try:
            fname=sys.argv[1]
            print gWftLogParser.get_XMLResult(fname)
        except OSError,e:
            sys.stderr.write("Error reading file: %s\n"%e)
            sys.exit(1)
        except:
            raise
            sys.stderr.write("%s\n"%USAGE)
            sys.exit(1)
    else:
        # multiple files, combine in a set
        xmls=[]
        for i in range(1,len(sys.argv)):
            try:
                fname=sys.argv[i]
                rawx=gWftLogParser.get_XMLResult(fname)
                if (rawx==""):
                    # nothing found, warn
                    sys.stderr.write("No XML in file %s\n"%fname)
                    continue

                x=[]
                for l in string.split(rawx,"\n"):
                    if l[:2]=="<?":
                        #skip comments
                        continue
                    if l[:15]=="<OSGTestResult ":
                        # insert file name
                        l=l[:15]+('logname="%s" '%fname)+l[15:]
                    x.append("  "+l);
                if x[-1]=="  ":
                    x=x[:-1]
                xmls.append(string.join(x,"\n"))
            except OSError,e:
                # just warn
                sys.stderr.write("Error reading file: %s\n"%e)
            except:
                # serious error... die
                raise
            pass
        
        if (len(xmls)==0):
            sys.stderr.write("Could not read a single file!")
            sys.exit(1)
        sys.stdout.write('<?xml version="1.0"?>\n')
        sys.stdout.write("<OSGTestResultSet>\n")
        for l in xmls:
            sys.stdout.write(l+"\n")
        sys.stdout.write("</OSGTestResultSet>\n")


if __name__ == '__main__':
    main()
 
