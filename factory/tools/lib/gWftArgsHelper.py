#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Argument parser helper
#

def str2int_range(str, min, max):
    try:
        val=int(str)
    except ValueError as e:
        raise ValueError, "Must be a number."
    if (val<min) or (val>max):
        raise ValueError, "Must be in the range %i-%i."%(min, max)
    return val
    

def parse_date(str):
    arr=str.split('/')
    if len(arr)!=3:
        raise ValueError, "Invalid date '%s'. Expected YY/MM/DD."%str
    try:
        year=int(arr[0])
    except ValueError as e:
        raise ValueError, "Invalid year '%s'. Must be a number."%arr[0]
    if year<100:
        year=year+2000

    try:
        mon=str2int_range(arr[1], 1, 12)
    except ValueError as e:
        raise ValueError, "Invalid month '%s'. %s"%(arr[1], e)

    try:
        day=str2int_range(arr[2], 1, 31)
    except ValueError as e:
        raise ValueError, "Invalid day '%s'. %s"%(arr[2], e)

    return (year, mon, day)

def parse_time(str):
    arr=str.split(':')
    if len(arr)!=3:
        raise ValueError, "Invalid time '%s'. Expected hh:mm:ss."%str
    try:
        hour=str2int_range(arr[0], 0, 23)
    except ValueError as e:
        raise ValueError, "Invalid hour '%s'. %s"%(arr[0], e)

    try:
        min=str2int_range(arr[1], 0, 59)
    except ValueError as e:
        raise ValueError, "Invalid minute '%s'. %s"%(arr[1], e)

    try:
        sec=str2int_range(arr[2], 0, 59)
    except ValueError as e:
        raise ValueError, "Invalid second '%s'. %s"%(arr[2], e)

    return (hour, min, sec)

