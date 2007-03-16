#
# Description:
#   This module implements time2string functions
#
# Author:
#   Igor Sfiligoi (Mar 15th 2007)
#

import time

def getSeconds(now=None):
    if now==None:
        now=time.time()
    return "%li"%long(now)

def getHuman(now=None):
    if now==None:
        now=time.time()
    return time.strftime("%c",time.localtime(now))

def getISO8601_UTC(now=None):
    if now==None:
        now=time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(now))

def getISO8601_Local(now=None):
    if now==None:
        now=time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S",time.localtime(now))+("%+03i:%02i"%((-time.altzone/3600),(-time.altzone%3600/60)))

def getRFC2822_UTC(now=None):
    if now==None:
        now=time.time()
    return time.strftime("%a, %d %b %Y %H:%M:%S +0000",time.gmtime(now))

def getRFC2822_Local(now=None):
    if now==None:
        now=time.time()
    return time.strftime("%a, %d %b %Y %H:%M:%S",time.localtime(now))+("%+03i%02i"%((-time.altzone/3600),(-time.altzone%3600/60)))



