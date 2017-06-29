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
# Usage: cat_XMLResult.py [-raw] [-forcemulti] logname+
#        If -raw is present, do not wrap multiple XMLs into a ResultSet
#        If -forcemulti is present, make it a ResultSet even if only one file present
#

import os.path
import string
import sys
STARTUP_DIR=sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR,"../../.."))
from glideinwms.factory.tools.lib import gWftLogParser

USAGE="Usage: cat_XMLResult.py -h|[-raw] [-forcemulti] <logname>+"

def main(args):
    raw_out=False
    force_multi=False

    while 1:
        if (len(args)<1):
            sys.stderr.write("Missing logname.\n")
            sys.stderr.write("%s\n"%USAGE)
            sys.exit(1)        

        if (args[0]=="-h"):
            print USAGE
            sys.exit(0)
        elif (args[0]=="-raw"):
            raw_out=True
            args=args[1:]
        elif (args[0]=="-forcemulti"):
            force_multi=True
            args=args[1:]
        else:
            break # looks like I found a log name
    
    if (len(args)==1) and (not force_multi):
        # single file, just pass through
        try:
            fname=args[0]
            out=gWftLogParser.get_XMLResult(fname)
        except OSError as e:
            sys.stderr.write("Error reading file: %s\n"%e)
            sys.exit(1)
        except:
            raise
            sys.stderr.write("%s\n"%USAGE)
            sys.exit(1)

        for l in string.split(out,"\n"):
            if raw_out and (l[:2]=="<?"):
                #skip comments for raw output
                continue
            if l[:15]=="<OSGTestResult ":
                # insert file name
                l=l[:15]+('logname="%s" '%fname)+l[15:]
            print l
    else:
        # multiple files, combine in a set
        xmls=[]
        for i in range(len(args)):
            try:
                fname=args[i]
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
            except OSError as e:
                # just warn
                sys.stderr.write("Error reading file: %s\n"%e)
            except:
                # serious error... die
                raise
            pass
        
        if (len(xmls)==0):
            sys.stderr.write("Could not read a single file!")
            sys.exit(1)
        if not raw_out:
            sys.stdout.write('<?xml version="1.0"?>\n')
            sys.stdout.write("<OSGTestResultSet>\n")
        
        for l in xmls:
            sys.stdout.write(l+"\n")
        
        if not raw_out:
            sys.stdout.write("</OSGTestResultSet>\n")


if __name__ == '__main__':
    main(sys.argv[1:])
 
