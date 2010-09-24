#!/usr/bin/env python

#
# Description:
#  This file is specialized in updating a proxy file
#   in privsep mode
#
# All information is passed via the environment;
#  so it has no arguments
#
# Env variables used:
#  HEXDATA - b2a_hex(proxy_data)
#  FNAME   - file name to update
#
# The python-related environment variables must also
#  be properly set
#  PATH, LD_LIBRARY_PATH, PYTHON_PATH
#
# Author:
#  Igor Sfiligoi (Mar 18th, 2010) @UCSD
#

import os,sys
import binascii

#
# Extract data from environment
# Arguments not used
#

if not os.environ.has_key('HEXDATA'):
   sys.stderr.write('HEXDATA env variable not defined.')
   sys.exit(2)

if not os.environ.has_key('FNAME'):
   sys.stderr.write('FNAME env variable not defined.')
   sys.exit(2)

proxy_data=binascii.a2b_hex(os.environ['HEXDATA'])
fname=os.environ['FNAME']

#
# Update (or create) the file
#

if not os.path.isfile(fname):
   # new file, create
   fd=os.open(fname,os.O_CREAT|os.O_WRONLY,0600)
   try:
      os.write(fd,proxy_data)
   finally:
      os.close(fd)
   sys.exit(0)

# old file exists, check if same content
fl=open(fname,'r')
try:
   old_data=fl.read()
finally:
   fl.close()
if proxy_data==old_data:
   # nothing changed, done
   sys.exit(0)

#
# proxy changed, neeed to update
#

# remove any previous backup file
try:
   os.remove(fname+".old")
except:
   pass # just protect
    
# create new file
fd=os.open(fname+".new",os.O_CREAT|os.O_WRONLY,0600)
try:
   os.write(fd,proxy_data)
finally:
   os.close(fd)

# move the old file to a tmp and the new one into the official name
try:
   os.rename(fname,fname+".old")
except:
   pass # just protect

os.rename(fname+".new",fname)
sys.exit(0)


