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

import time
import calendar

def getSeconds(now=None):
    if now == None:
        now = time.time()
    return "%li" % long(now)

def extractSeconds(sec):
    return long(sec)

def getHuman(now=None):
    if now == None:
        now = time.time()
    return time.strftime("%c", time.localtime(now))

def extractHuman(sec):
    return time.mktime(time.strptime(sec, "%c"))

def getISO8601_UTC(now=None):
    if now == None:
        now = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

def extractISO8601_UTC(sec):
    return calendar.timegm(time.strptime(sec, "%Y-%m-%dT%H:%M:%SZ"))

def getISO8601_Local(now=None):
    if now == None:
        now = time.time()
    tzval = getTZval()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)) + ("%+03i:%02i" % ((-tzval/3600), (-tzval%3600/60)))

def extractISO8601_Local(sec):
    timestr = sec[:-6]
    tzstr = sec[-6:]
    tzval = (long(tzstr[:3]) * 60 + long(tzstr[4:])) * 60
    return calendar.timegm(time.strptime(timestr, "%Y-%m-%dT%H:%M:%S")) - tzval

def getRFC2822_UTC(now=None):
    if now == None:
        now = time.time()
    return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now))

def extractRFC2822_UTC(sec):
    return calendar.timegm(time.strptime(sec, "%a, %d %b %Y %H:%M:%S +0000"))

def getRFC2822_Local(now=None):
    if now == None:
        now = time.time()
    tzval = getTZval()
    return time.strftime("%a, %d %b %Y %H:%M:%S ", time.localtime(now)) + ("%+03i%02i" % ((-tzval/3600), (-tzval%3600/60)))

def extractRFC2822_Local(sec):
    timestr = sec[:-6]
    tzstr = sec[-5:]
    tzval = (long(tzstr[:3]) * 60 + long(tzstr[3:])) * 60
    return calendar.timegm(time.strptime(timestr, "%a, %d %b %Y %H:%M:%S")) - tzval

#########################
# Internal
#########################

def getTZval():
    if time.daylight:
        return time.altzone
    else:
        return time.timezone
