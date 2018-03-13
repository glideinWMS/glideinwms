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
    if now is None:
        now = time.time()
    return "%li" % long(now)


def extractSeconds(time_str):
    return long(time_str)


def getHuman(now=None):
    if now is None:
        now = time.time()
    return time.strftime("%c", time.localtime(now))


def extractHuman(time_str):
    return time.mktime(time.strptime(time_str, "%c"))


def getISO8601_UTC(now=None):
    if now is None:
        now = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))


def extractISO8601_UTC(time_str):
    return calendar.timegm(time.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ"))


def getISO8601_Local(now=None):
    if now is None:
        now = time.time()
    tzval = getTZval(now)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)) + ("%+03i:%02i" % ((-tzval / 3600), (-tzval % 3600 / 60)))


def extractISO8601_Local(time_str):
    timestr = time_str[:-6]
    tzstr = time_str[-6:]
    tzval = (long(tzstr[:3]) * 60 + long(tzstr[4:])) * 60
    return calendar.timegm(time.strptime(timestr, "%Y-%m-%dT%H:%M:%S")) - tzval


def getRFC2822_UTC(now=None):
    if now is None:
        now = time.time()
    return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now))


def extractRFC2822_UTC(time_str):
    return calendar.timegm(time.strptime(time_str, "%a, %d %b %Y %H:%M:%S +0000"))


def getRFC2822_Local(now=None):
    if now is None:
        now = time.time()
    tzval = getTZval(now)
    return time.strftime("%a, %d %b %Y %H:%M:%S ", time.localtime(now)) + ("%+03i%02i" % ((-tzval / 3600), (-tzval % 3600 / 60)))


def extractRFC2822_Local(time_str):
    timestr = time_str[:-6]
    tzstr = time_str[-5:]
    tzval = (long(tzstr[:3]) * 60 + long(tzstr[3:])) * 60
    return calendar.timegm(time.strptime(timestr, "%a, %d %b %Y %H:%M:%S")) - tzval


def get_time_in_format(now=None, time_format=None):
    if now is None:
        now = time.time()
    if time_format is None:
        time_str = getHuman()
    else:
        time_str = time.strftime(time_format, time.localtime(now))
    return time_str


#########################
# Internal
#########################

# time.daylight tells only if the computer support daylight saving time,
# tm_isdst must be checked to see if it is in effect at time t
# Some corner cases (changes in standard) are still uncovered, see https://bugs.python.org/issue1647654
# See also https://bugs.python.org/issue7229 for an improved explanation of the Python manual wording
def getTZval(t):
    if time.localtime(t).tm_isdst and time.daylight:
        return time.altzone
    else:
        return time.timezone
