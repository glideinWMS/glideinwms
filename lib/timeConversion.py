# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements functions for converting between different time formats
and string representations of time.

Functions:
    getSeconds: Returns the current time in seconds since the epoch.
    extractSeconds: Extracts seconds from a string representation.
    getHuman: Returns the current time in human-readable format.
    extractHuman: Extracts a human-readable time string into seconds since the epoch.
    getISO8601_UTC: Returns the current time in ISO 8601 UTC format.
    extractISO8601_UTC: Extracts ISO 8601 UTC time string into seconds since the epoch.
    getISO8601_Local: Returns the current time in ISO 8601 local time format.
    extractISO8601_Local: Extracts ISO 8601 local time string into seconds since the epoch.
    getRFC2822_UTC: Returns the current time in RFC 2822 UTC format.
    extractRFC2822_UTC: Extracts RFC 2822 UTC time string into seconds since the epoch.
    getRFC2822_Local: Returns the current time in RFC 2822 local time format.
    extractRFC2822_Local: Extracts RFC 2822 local time string into seconds since the epoch.
    get_time_in_format: Returns the current time formatted according to the specified format.
    getTZval: Internal function that returns the timezone offset in seconds.
"""

import calendar
import time


def getSeconds(now=None):
    """Returns the current time in seconds since the epoch.

    Args:
        now (float, optional): The time to convert, as a float representing seconds since the epoch.
            If None, the current time will be used. Defaults to None.

    Returns:
        str: The time in seconds as a string.
    """
    if now is None:
        now = time.time()
    return "%li" % int(now)


def extractSeconds(time_str):
    """Extracts seconds from a string representation.

    Args:
        time_str (str): The string representation of time in seconds.

    Returns:
        int: The extracted time as seconds since the epoch.
    """
    return int(time_str)


def getHuman(now=None):
    """Returns the current time in human-readable format.

    Args:
        now (float, optional): The time to format. If None, the current time will be used. Defaults to None.

    Returns:
        str: The time in human-readable format.
    """
    if now is None:
        now = time.time()
    return time.strftime("%c", time.localtime(now))


def extractHuman(time_str):
    """Extracts a human-readable time string into seconds since the epoch.

    Args:
        time_str (str): The human-readable time string.

    Returns:
        float: The time in seconds since the epoch.
    """
    return time.mktime(time.strptime(time_str, "%c"))


def getISO8601_UTC(now=None):
    """Returns the current time in ISO 8601 UTC format.

    Args:
        now (float, optional): The time to format. If None, the current time will be used. Defaults to None.

    Returns:
        str: The time in ISO 8601 UTC format.
    """
    if now is None:
        now = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))


def extractISO8601_UTC(time_str):
    """Extracts ISO 8601 UTC time string into seconds since the epoch.

    Args:
        time_str (str): The ISO 8601 UTC time string.

    Returns:
        int: The time in seconds since the epoch.
    """
    return calendar.timegm(time.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ"))


def getISO8601_Local(now=None):
    """Returns the current time in ISO 8601 local time format.

    Args:
        now (float, optional): The time to format. If None, the current time will be used. Defaults to None.

    Returns:
        str: The time in ISO 8601 local time format.
    """
    if now is None:
        now = time.time()
    tzval = getTZval(now)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)) + (
        "%+03i:%02i" % ((-tzval // 3600), (-tzval % 3600 // 60))
    )


def extractISO8601_Local(time_str):
    """Extracts ISO 8601 local time string into seconds since the epoch.

    Args:
        time_str (str): The ISO 8601 local time string.

    Returns:
        int: The time in seconds since the epoch.
    """
    timestr = time_str[:-6]
    tzstr = time_str[-6:]
    tzval = (int(tzstr[:3]) * 60 + int(tzstr[4:])) * 60
    return calendar.timegm(time.strptime(timestr, "%Y-%m-%dT%H:%M:%S")) - tzval


def getRFC2822_UTC(now=None):
    """Returns the current time in RFC 2822 UTC format.

    Args:
        now (float, optional): The time to format. If None, the current time will be used. Defaults to None.

    Returns:
        str: The time in RFC 2822 UTC format.
    """
    if now is None:
        now = time.time()
    return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now))


def extractRFC2822_UTC(time_str):
    """Extracts RFC 2822 UTC time string into seconds since the epoch.

    Args:
        time_str (str): The RFC 2822 UTC time string.

    Returns:
        int: The time in seconds since the epoch.
    """
    return calendar.timegm(time.strptime(time_str, "%a, %d %b %Y %H:%M:%S +0000"))


def getRFC2822_Local(now=None):
    """Returns the current time in RFC 2822 local time format.

    Args:
        now (float, optional): The time to format. If None, the current time will be used. Defaults to None.

    Returns:
        str: The time in RFC 2822 local time format.
    """
    if now is None:
        now = time.time()
    tzval = getTZval(now)
    return time.strftime("%a, %d %b %Y %H:%M:%S ", time.localtime(now)) + (
        "%+03i%02i" % ((-tzval // 3600), (-tzval % 3600 // 60))
    )


def extractRFC2822_Local(time_str):
    """Extracts RFC 2822 local time string into seconds since the epoch.

    Args:
        time_str (str): The RFC 2822 local time string.

    Returns:
        int: The time in seconds since the epoch.
    """
    timestr = time_str[:-6]
    tzstr = time_str[-5:]
    tzval = (int(tzstr[:3]) * 60 + int(tzstr[3:])) * 60
    return calendar.timegm(time.strptime(timestr, "%a, %d %b %Y %H:%M:%S")) - tzval


def get_time_in_format(now=None, time_format=None):
    """Returns the current time formatted according to the specified format.

    Args:
        now (float, optional): The time to format. If None, the current time will be used. Defaults to None.
        time_format (str, optional): The format string to use. If None, human-readable format is used. Defaults to None.

    Returns:
        str: The formatted time string.
    """
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
    """Returns the timezone offset in seconds for the given time.

    Args:
        t (float): The time in seconds since the epoch.

    Returns:
        int: The timezone offset in seconds.
    """
    if time.localtime(t).tm_isdst and time.daylight:
        return time.altzone
    else:
        return time.timezone
