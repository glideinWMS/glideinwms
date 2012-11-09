#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements Condor PrivSep-related functions
#
# Author:
#   Igor Sfiligoi (Mar 16th 2010)
#

import os.path
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
    return exe_privsep("mkdir","user-uid=%s\nuser-dir=%s/%s"%(target_user,base_dir,subdir))
    
########################################################
#
# Remove subdir tree within base_dir
# The base_name (and all the parents) must be root owned
#   and being authorized in the
#   valid-dirs of
#    /etc/condor/privsep_config
# Any subdir, owned by any user in the base_dir can be removed
def rmtree(base_dir,subdir):
    return exe_privsep("rmdir","user-dir=%s/%s"%(base_dir,subdir))
    
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
    return exe_privsep("chowndir","user-dir=%s/%s\nchown-source-uid=%s\nuser-uid=%s"%(base_dir,subdir,old_user,new_user))

########################################################
#
# Execute a command as a target_user
# The target_user must be authorized in the 
#   valid-target-uids list of
#   /etc/condor/privsep_config
# The init_dir is the initial working directory
# The exe must be an abspath
# The optional args is a list of arguments,
#   args[0] should contain the exe name
# The env is a list of 'key=value' strings
# The stdin_fname, stdout_fname, stderr_fname can be used
#   to redirect stdin, stdout and/or stderr to/from files
# If stdout_fname=='-' (the default), it is just passed through (not available for stdin and stderr)
def execute(target_user,init_dir,exe,args=None,env=None,
            stdin_fname=None,stdout_fname="-",stderr_fname=None):
    other=""
    if args is not None:
        for arg in args:
            arg=str(arg) #get rid of unicode
            other+="\nexec-arg<%d>\n%s"%(len(arg),arg)
    if env is not None:
        for el in env:
            el=str(el) #get rid of unicode
            other+="\nexec-env<%d>\n%s"%(len(el),el)
    if stdin_fname is not None:
        other+="\nexec-stdin=%s"%stdin_fname
    if stdout_fname is not None:
        if stdout_fname=='-':
            # special case, pass through
            other+="\nexec-keep-open-fd=1"
        else:
            other+="\nexec-stdout=%s"%stdout_fname
    if stderr_fname is not None:
        other+="\nexec-stderr=%s"%stderr_fname

    return exe_privsep("exec","user-uid=%s\nexec-init-dir=%s\nexec-path=%s%s"%(target_user,init_dir,exe,other))

########################################################
#
# Similar to the above 'execute', but less flexible
# The condor_exe binary is relative to the condor_bin_path
# By default, the stdout will be passed through
#  but stderr can only be redirected to a file (no way to pass it through)
def condor_execute(target_user,init_dir,condor_exe,args,
                   stdin_fname=None,stdout_fname="-",stderr_fname=None):
    if condorExe.condor_bin_path is None:
        raise UnconfigError, "condor_bin_path is undefined!"
    condor_exe_path=os.path.join(condorExe.condor_bin_path,condor_exe)

    return execute(target_user,init_dir,condor_exe_path,args,
                   stdin_fname=stdin_fname,stdout_fname=stdout_fname,stderr_fname=stderr_fname)

##################################
#
# INTERNAL
#
##################################

def exe_privsep(cmd,options):
    return condorExe.exe_cmd("../sbin/condor_root_switchboard","%s 0 2"%cmd,
                             options)
