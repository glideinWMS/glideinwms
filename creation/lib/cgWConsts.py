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

start_time_tuple=time.localtime()
TIMESTR=(string.printable[start_time_tuple[0]-2000]+ #year, will work until ~2060
         string.printable[start_time_tuple[1]]+      #month
         string.printable[start_time_tuple[2]]+      #day
         string.printable[start_time_tuple[3]]+      #hour
         string.digits[start_time_tuple[4]/10])      #first minute digit 
del start_time_tuple

# these two are in the submit dir, so they can be changed
PARAMS_FILE="params.cfg"
SUMMARY_SIGNATURE_FILE="signatures.sha1"

# these are in the stage dir, so they need to be renamed if changed
DESCRIPTION_FILE="description.%s.cfg"%TIMESTR

ATTRS_FILE="attributes.cfg"
CONSTS_FILE="constants.%s.cfg"%TIMESTR

FILE_LISTFILE="file_list.%s.lst"%TIMESTR
SCRIPT_LISTFILE="script_list.%s.lst"%TIMESTR
SUBSYSTEM_LISTFILE="subsystem_list.%s.lst"%TIMESTR
SIGNATURE_FILE="signature.%s.sha1"%TIMESTR


CONDOR_FILE="condor_bin.%s.tgz"%TIMESTR
CONDOR_DIR="condor"
CONDOR_ATTR="CONDOR_DIR"
VARS_FILE="condor_vars.%s.lst"%TIMESTR

CONDOR_STARTUP_FILE="condor_startup.sh"


# these are again in the submit dir
STARTUP_FILE="glidein_startup.sh"
GLIDEIN_FILE="glidein.descript"
JOB_DESCRIPT_FILE="job.descript"
SUBMIT_FILE="job.condor"
SUBMIT_WRAPPER="job_submit.sh"


###########################################################
#
# CVS info
#
# $Id: cgWConsts.py,v 1.1 2007/10/12 20:20:26 sfiligoi Exp $
#
# Log:
#  $Log: cgWConsts.py,v $
#  Revision 1.1  2007/10/12 20:20:26  sfiligoi
#  Put constants into a dedicated module
#
#
###########################################################
