#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Keep all the constants used in the glideinWMS
#
# Author: Igor Sfiligoi
#

import time
import string


def get_timestr(when=time.time()):
    """Get a 6 char alphanumeric string based on the timestamp.

    The string increases monotonically for each 62 years period starting from 2000.
    A later time corresponds to a bigger string in lexicographic order (within the period).

    Args:
        when (float): time to convert in string (seconds from epoch, only the integer part is used)

    Returns:
        str: 6 chars string depending on the time
    """
    start_time_tuple = time.localtime(when)
    timestr = (string.printable[(start_time_tuple[0]-2000) % 62] +  # year, looping to keep alphanumeric, will repeat after 2062
               string.printable[start_time_tuple[1]] +      # month
               string.printable[start_time_tuple[2]] +      # day
               string.printable[start_time_tuple[3]] +      # hours
               string.printable[start_time_tuple[4]] +      # minutes
               string.printable[start_time_tuple[5]])       # seconds
    return timestr


TIMESTR = get_timestr()

def insert_timestr(instr):
    """insert timestr just before the last '.' (dot)

    Args:
        instr (str): dot separated string, e.g. file name

    Returns:
        str: input string with TIMESTR, dot separated, before the last dot
    """
    arr = instr.split('.')
    if len(arr) == 1:
        arr.append(TIMESTR)
    else:
        arr.insert(-1, TIMESTR)
    return '.'.join(arr)

# these two are in the work dir, so they can be changed
SUMMARY_SIGNATURE_FILE="signatures.sha1"

# these are in the stage dir, so they need to be renamed if changed
DESCRIPTION_FILE="description.cfg"

VARS_FILE="condor_vars.lst"
CONSTS_FILE="constants.cfg"
UNTAR_CFG_FILE="untar.cfg"

FILE_LISTFILE="file_list.lst"
SIGNATURE_FILE="signature.sha1"

BLACKLIST_FILE="nodes.blacklist"

GRIDMAP_FILE='grid-mapfile'



