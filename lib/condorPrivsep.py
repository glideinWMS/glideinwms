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
# Create subdir within base_dir owned by target_user
# The base_name (and all the parents) must be root owned
#   and being authorized in the
#   valid-dirs of
#    /etc/condor/privsep_config
# The target_user must be authorized in the
#   valid-target-uids list of
#   /etc/condor/privsep_config
def mkdir(base_dir,subdir,target_user):
    exe_privsep("mkdir","user-uid=%s\nuser-dir=%s/%s"%(target_user,base_dir,subdir))
    
########################################################
#
# Remove subdir tree within base_dir
# The base_name (and all the parents) must be root owned
#   and being authorized in the
#   valid-dirs of
#    /etc/condor/privsep_config
# Any subdir, owned by any user in the base_dir can be removed
def rmtree(base_dir,subdir):
    exe_privsep("rmdir","user-dir=%s/%s"%(base_dir,subdir))
    
########################################################
#
# Change owndership of the subdir tree within base_dir
#   from old_user to new_user
# The base_name (and all the parents) must be root owned
#   and being authorized in the
#   valid-dirs of
#    /etc/condor/privsep_config
# Both old_user and new_user must be authorized in the 
#   valid-target-uids list of
#   /etc/condor/privsep_config
def chowntree(base_dir,subdir,old_user,new_user):
    exe_privsep("chowndir","user-dir=%s/%s\nchown-source-uid=%s\nuser-uid=%s"%(base_dir,subdir,old_user,new_user))


##################################
#
# INTERNAL
#
##################################

def exe_privsep(cmd,options):
    condorExe.exe_cmd("../sbin/condor_root_switchboard","%s 0 1"%cmd,
                      options)
