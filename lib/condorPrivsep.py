#
# Description:
#   This module implements Condor PrivSep-related functions
#
# Author:
#   Igor Sfiligoi (Mar 16th 2010)
#

import condorExe
from condorExe import ExeError,UnconfigError

# All the functions below can throw either
#  ExeError or UnconfigError exceptions

########################################################
#
# Create subdir within base_dir un target_user name
# The base_name (and all the parents) must be root owned
# The target_user must be authorized in the
#   valid-target-uids list of
#   /etc/condor/privsep_config
def mkdir(base_dir,subdir,target_user):
    condorExe.exe_cmd("../sbin/condor_root_switchboard","mkdir 0 1","user-uid=%s\nuser-dir=%s/%s"%(target_user,base_dir,subdir))
    
