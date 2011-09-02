#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: timeConversion.py,v 1.6.12.1 2010/09/08 03:10:47 parag Exp $
#
# Description:
#   This module implements time2string functions
#
# Author:
#   Igor Sfiligoi (Mar 15th 2007)
#

import time, calendar

def getSeconds(now=None):
    if now == None:
        now = time.time()
    return "%li" % long(now)

def extractSeconds(sec_str):
    return long(sec_str)

def getHuman(now=None):
    if now == None:
        now = time.time()
    return time.strftime("%c", time.localtime(now))

def extractHuman(human_str):
    return time.mktime(time.strptime(human_str, "%c"))

def getISO8601_UTC(now=None):
    if now == None:
        now = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

def extractISO8601_UTC(utc_str):
    return calendar.timegm(time.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ"))

def getISO8601_Local(now=None):
    if now == None:
        now = time.time()
    tzval = getTZval()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)) + ("%+03i:%02i" % ((-tzval / 3600), (-tzval % 3600 / 60)))

def extractISO8601_Local(local_str):
    timestr = local_str[:-6]
    tzstr = local_str[-6:]
    tzval = (long(tzstr[:3]) * 60 + long(tzstr[4:])) * 60
    return calendar.timegm(time.strptime(timestr, "%Y-%m-%dT%H:%M:%S")) - tzval

def getRFC2822_UTC(now=None):
    if now == None:
        now = time.time()
    return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now))

def extractRFC2822_UTC(utc_str):
    return calendar.timegm(time.strptime(utc_str, "%a, %d %b %Y %H:%M:%S +0000"))

def getRFC2822_Local(now=None):
    if now == None:
        now = time.time()
    tzval = getTZval()
    return time.strftime("%a, %d %b %Y %H:%M:%S ", time.localtime(now)) + ("%+03i%02i" % ((-tzval / 3600), (-tzval % 3600 / 60)))

def extractRFC2822_Local(local_str):
    timestr = local_str[:-6]
    tzstr = local_str[-5:]
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


