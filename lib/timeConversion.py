#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements time2string functions
#
# Author:
#   Igor Sfiligoi (Mar 15th 2007)
#

import time,calendar

def getSeconds(now=None):
    if now is None:
        now=time.time()
    return "%li"%long(now)

def extractSeconds(str):
    return long(str)

def getHuman(now=None):
    if now is None:
        now=time.time()
    return time.strftime("%c",time.localtime(now))

def extractHuman(str):
    return time.mktime(time.strptime(str,"%c"))

def getISO8601_UTC(now=None):
    if now is None:
        now=time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(now))

def extractISO8601_UTC(str):
    return calendar.timegm(time.strptime(str,"%Y-%m-%dT%H:%M:%SZ"))

def getISO8601_Local(now=None):
    if now is None:
        now=time.time()
    tzval=getTZval()
    return time.strftime("%Y-%m-%dT%H:%M:%S",time.localtime(now))+("%+03i:%02i"%((-tzval/3600),(-tzval%3600/60)))

def extractISO8601_Local(str):
    timestr=str[:-6]
    tzstr=str[-6:]
    tzval=(long(tzstr[:3])*60+long(tzstr[4:]))*60
    return calendar.timegm(time.strptime(timestr,"%Y-%m-%dT%H:%M:%S"))-tzval

def getRFC2822_UTC(now=None):
    if now is None:
        now=time.time()
    return time.strftime("%a, %d %b %Y %H:%M:%S +0000",time.gmtime(now))

def extractRFC2822_UTC(str):
    return calendar.timegm(time.strptime(str,"%a, %d %b %Y %H:%M:%S +0000"))

def getRFC2822_Local(now=None):
    if now is None:
        now=time.time()
    tzval=getTZval()
    return time.strftime("%a, %d %b %Y %H:%M:%S ",time.localtime(now))+("%+03i%02i"%((-tzval/3600),(-tzval%3600/60)))

def extractRFC2822_Local(str):
    timestr=str[:-6]
    tzstr=str[-5:]
    tzval=(long(tzstr[:3])*60+long(tzstr[3:]))*60
    return calendar.timegm(time.strptime(timestr,"%a, %d %b %Y %H:%M:%S"))-tzval

#########################
# Internal
#########################

def getTZval():
    if time.daylight:
        return time.altzone
    else:
        return time.timezone


