#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: gWftArgsHelper.py,v 1.1.12.1 2010/09/08 03:22:59 parag Exp $
#
# Description:
#   Argument parser helper
#

def str2int_range(input_str, input_min, input_max):
    try:
        val = int(input_str)
    except ValueError:
        raise ValueError, "Must be a number."
    if (val < input_min) or (val > input_max):
        raise ValueError, "Must be in the range %i-%i." % (input_min, input_max)
    return val


def parse_date(input_str):
    arr = input_str.split('/')
    if len(arr) != 3:
        raise ValueError, "Invalid date '%s'. Expected YY/MM/DD." % input_str
    try:
        year = int(arr[0])
    except ValueError, e:
        raise ValueError, "Invalid year '%s'. Must be a number." % arr[0]
    if year < 100:
        year = year + 2000

    try:
        mon = str2int_range(arr[1], 1, 12)
    except ValueError, e:
        raise ValueError, "Invalid month '%s'. %s" % (arr[1], e)

    try:
        day = str2int_range(arr[2], 1, 31)
    except ValueError, e:
        raise ValueError, "Invalid day '%s'. %s" % (arr[2], e)

    return (year, mon, day)

def parse_time(input_str):
    arr = input_str.split(':')
    if len(arr) != 3:
        raise ValueError, "Invalid time '%s'. Expected hh:mm:ss." % input_str
    try:
        hour = str2int_range(arr[0], 0, 23)
    except ValueError, e:
        raise ValueError, "Invalid hour '%s'. %s" % (arr[0], e)

    try:
        minutes = str2int_range(arr[1], 0, 59)
    except ValueError, e:
        raise ValueError, "Invalid minute '%s'. %s" % (arr[1], e)

    try:
        sec = str2int_range(arr[2], 0, 59)
    except ValueError, e:
        raise ValueError, "Invalid second '%s'. %s" % (arr[2], e)

    return (hour, minutes, sec)

