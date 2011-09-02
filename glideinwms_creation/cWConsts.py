#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: cWConsts.py,v 1.4.10.1 2010/09/08 03:29:59 parag Exp $
#
# Description:
#   Keep all the constants used in the glideinWMS
#
# Author: Igor Sfiligoi
#

import time
import string

def get_timestr(when=time.time()):
    start_time_tuple = time.localtime(when)
    timestr = (string.printable[start_time_tuple[0] - 2000] + #year, will work until ~2060
             string.printable[start_time_tuple[1]] + #month
             string.printable[start_time_tuple[2]] + #day
             string.printable[start_time_tuple[3]] + #hour
             string.printable[start_time_tuple[4]] + #minute
             string.printable[start_time_tuple[5]])      #first minute digit 
    return timestr

TIMESTR = get_timestr()

# insert timestr just before the last .
def insert_timestr(time_str):
    arr = string.split(time_str, '.')
    if len(arr) == 1:
        arr.append(TIMESTR)
    else:
        arr.insert(-1, TIMESTR)
    return '.'.join(arr)

# these two are in the work dir, so they can be changed
SUMMARY_SIGNATURE_FILE = "signatures.sha1"

# these are in the stage dir, so they need to be renamed if changed
DESCRIPTION_FILE = "description.cfg"

VARS_FILE = "condor_vars.lst"
CONSTS_FILE = "constants.cfg"
UNTAR_CFG_FILE = "untar.cfg"

FILE_LISTFILE = "file_list.lst"
SIGNATURE_FILE = "signature.sha1"

BLACKLIST_FILE = "nodes.blacklist"

GRIDMAP_FILE = 'grid-mapfile'



