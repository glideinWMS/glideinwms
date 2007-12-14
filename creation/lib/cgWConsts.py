####################################
#
# Keep all the constants used to
# create glidein entries in this
# module
#
# Author: Igor Sfiligoi
#
####################################

import time
import string
import os.path


def get_timestr(when=time.time()):
    start_time_tuple=time.localtime(when)
    timestr=(string.printable[start_time_tuple[0]-2000]+ #year, will work until ~2060
             string.printable[start_time_tuple[1]]+      #month
             string.printable[start_time_tuple[2]]+      #day
             string.printable[start_time_tuple[3]]+      #hour
             string.digits[start_time_tuple[4]/10])      #first minute digit 
    return timestr

TIMESTR=get_timestr()

# insert timestr just before the last .
def insert_timestr(str):
    arr=string.split(str,'.')
    arr.insert(-1,TIMESTR)
    return string.join(arr,'.')
    
# these two are in the submit dir, so they can be changed
PARAMS_FILE="params.cfg"
ATTRS_FILE="attributes.cfg"
SUMMARY_SIGNATURE_FILE="signatures.sha1"

# these are in the stage dir, so they need to be renamed if changed
DESCRIPTION_FILE="description.cfg"

CONSTS_FILE_BASE="constants.cfg"

FILE_LISTFILE_BASE="file_list.lst"
SUBSYSTEM_LISTFILE="subsystem_list.lst"
SIGNATURE_FILE="signature.sha1"


CONDOR_FILE="condor_bin.tgz"
CONDOR_DIR="condor"
CONDOR_ATTR="CONDOR_DIR"
VARS_FILE="condor_vars.lst"

CONDOR_STARTUP_FILE="condor_startup.sh"


# these are again in the submit dir
STARTUP_FILE="glidein_startup.sh"
GLIDEIN_FILE="glidein.descript"
JOB_DESCRIPT_FILE="job.descript"
SUBMIT_FILE="job.condor"
SUBMIT_WRAPPER="job_submit.sh"
XML_CONFIG_FILE="glideinWMS.xml"

###################################################
#
# These functions append constant parts to strings
#
###################################################

def get_entry_submit_dir(submit_dir,entry_name):
    entry_submit_dir=os.path.join(submit_dir,"entry_"+entry_name)
    return entry_submit_dir

def get_entry_name_from_entry_submit_dir(entry_submit_dir):
    entry_name_arr=os.path.basename(entry_submit_dir).split('_',1)
    if entry_name_arr[0]!='entry':
        raise ValueError('%s not a entry_submit_dir'%entry_submit_dir)
    return entry_name_arr[1]

def get_entry_stage_dir(stage_dir,entry_name):
    entry_stage_dir=os.path.join(stage_dir,"entry_"+entry_name)
    return entry_stage_dir

def get_entry_name_from_entry_stage_dir(entry_stage_dir):
    entry_name_arr=os.path.basename(entry_stage_dir).split('_',1)
    if entry_name_arr[0]!='entry':
        raise ValueError('%s not a entry_stage_dir'%entry_stage_dir)
    return entry_name_arr[1]

def get_entry_monitor_dir(monitor_dir,entry_name):
    entry_monitor_dir=os.path.join(monitor_dir,"entry_"+entry_name)
    return entry_monitor_dir

def get_entry_name_from_entry_monitor_dir(entry_monitor_dir):
    entry_name_arr=os.path.basename(entry_monitor_dir).split('_',1)
    if entry_name_arr[0]!='entry':
        raise ValueError('%s not a entry_monitor_dir'%entry_monitor_dir)
    return entry_name_arr[1]


###########################################################
#
# CVS info
#
# $Id: cgWConsts.py,v 1.8 2007/12/14 22:28:08 sfiligoi Exp $
#
# Log:
#  $Log: cgWConsts.py,v $
#  Revision 1.8  2007/12/14 22:28:08  sfiligoi
#  Change file_list format and remove script_list (merged into file_list now)
#
#  Revision 1.7  2007/11/28 21:02:30  sfiligoi
#  Add inverse entry functions
#
#  Revision 1.6  2007/11/28 20:51:48  sfiligoi
#  Add get_timestra and get_entry_monitor_dir
#
#  Revision 1.5  2007/11/27 20:29:27  sfiligoi
#  Fix typo
#
#  Revision 1.4  2007/11/27 19:58:51  sfiligoi
#  Move dicts initialization into cgWDictFile and entry subdir definition in cgWConsts
#
#  Revision 1.3  2007/10/12 21:56:24  sfiligoi
#  Add glideinWMS.cfg in the list of constants
#
#  Revision 1.2  2007/10/12 21:02:24  sfiligoi
#  Add missing import
#
#  Revision 1.1  2007/10/12 20:20:26  sfiligoi
#  Put constants into a dedicated module
#
#
###########################################################
