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

import os
import os.path
import sys
import condorExe
from condorExe import UnconfigError
from condorExe import ExeError
import logSupport

# All the functions below can throw either ExeError or UnconfigError exceptions
def mkdir(base_dir, subdir, target_user):
    """Create subdir within base_dir owned by target_user

    The base_name (and all the parents) must be root owned and being authorized
    in the valid-dirs of /etc/condor/privsep_config

    The target_user must be authorized in the valid-target-uids list of
    /etc/condor/privsep_config

    @type base_dir: string
    @param base_dir: The base directory in which to create the user owned sub-directory
    @type subdir: string
    @param subdir: The user owned sub-directory to be created
    @type target_user: string
    @param target_user: The username of the user that will own the newly created sub-directory
    """
    return exe_privsep("mkdir", "user-uid=%s\nuser-dir=%s/%s" % (target_user, base_dir, subdir))

def rmtree(base_dir, subdir):
    """Remove subdir tree within base_dir

    The base_name (and all the parents) must be root owned and being authorized
    in the valid-dirs of /etc/condor/privsep_config

    Any subdir, owned by any user in the base_dir can be removed

    @type base_dir: string
    @param base_dir: The base directory in which user owned sub-directory exists
    @type subdir: string
    @param subdir: The user owned sub-directory to be removed
    """
    return exe_privsep("rmdir", "user-dir=%s/%s" % (base_dir, subdir))

def chowntree(base_dir, subdir, old_user, new_user):
    """Change owndership of the subdir tree within base_dir from old_user to
    new_user

    The base_name (and all the parents) must be root owned and being authorized
    in the valid-dirs of /etc/condor/privsep_config

    Both old_user and new_user must be authorized in the valid-target-uids list
    of /etc/condor/privsep_config

    @type base_dir: string
    @param base_dir: The base directory in which user owned sub-directory exists
    @type subdir: string
    @param subdir: The user owned sub-directory whose ownership will be changed
    @type old_user: string
    @param old_user: The original user owning the sub-directory
    @type new_user: string
    @param new_user: The new user who will own the sub-directory
    """
    return exe_privsep("chowndir", "user-dir=%s/%s\nchown-source-uid=%s\nuser-uid=%s" % (base_dir, subdir, old_user, new_user))

def execute(target_user, init_dir, exe, args=None, env=None, stdin_fname=None, stdout_fname="-", stderr_fname=None):
    """Execute a command as a target_user

    @type target_user: string
    @param target_user: The user that exe will be run as.  The target_user must
        be authorized in the valid-target-uids list of /etc/condor/privsep_config
    @type init_dir: string
    @param init_dir: The init_dir is the initial working directory
    @type exe: string
    @param exe: The absolute path to the executable.  Note: The exe B{must} be an abspath
    @type args: list
    @param args: The optional args is a list of arguments, args[0] should
        contain the exe name
    @type env: list
    @param env: env is a list of 'key=value' strings
    @type stdin_fname: string
    @param stdin_fname: Defaults to None.  If set can be used to redirect stdin
        to the specified filename
    @type stdout_fname: string
    @param stdout_fname:  Defaults to '-'.  If set can be used to redirect stdin
        to the specified filename.  If stdout_fname == '-' it is just passed through
        (not available for stdin and stderr)
    @type stderr_fname: string
    @param stderr_fname:  Defaults to None.  If set can be used to redirect stderr
        to the specified filename
    """
    other = ""
    if args is not None:
        for arg in args:
            arg = str(arg) #get rid of unicode
            other += "\nexec-arg<%d>\n%s" % (len(arg), arg)

    if env is not None:
        for el in env:
            el = str(el) #get rid of unicode
            other += "\nexec-env<%d>\n%s" % (len(el), el)

    if stdin_fname is not None:
        other += "\nexec-stdin=%s" % stdin_fname

    if stdout_fname is not None:
        if stdout_fname == '-':
            # special case, pass through
            other += "\nexec-keep-open-fd=1:2"
        else:
            other += "\nexec-stdout=%s" % stdout_fname

    if stderr_fname is not None:
        other += "\nexec-stderr=%s" % stderr_fname

    try:
        privsep_env = {
            'user-uid': target_user,
            'exec-init-dir': init_dir,
            'exec-path': exe,
            'HEX': 'DATA_NOT_LOGGED_FOR_SECURITY'
        }
        #logSupport.log.debug('Condor Privilage Separation options: %s' % privsep_env)
    except:
        # logging hasn't been setup yet
        pass

    return exe_privsep("exec", "user-uid=%s\nexec-init-dir=%s\nexec-path=%s%s" % (target_user, init_dir, exe, other))


def condor_execute(target_user, init_dir, condor_exe, args, env=None, stdin_fname=None, stdout_fname="-", stderr_fname=None):
    """Similar to 'execute', but less flexible - only allows condor command line tools
    The condor_exe binary is relative to the condor_bin_path

    @type target_user: string
    @param target_user: The user that exe will be run as.  The target_user must
        be authorized in the valid-target-uids list of /etc/condor/privsep_config
    @type init_dir: string
    @param init_dir: The init_dir is the initial working directory
    @type condor_exe: string
    @param condor_exe: the particular command that is to be run
    @type args: list
    @param args: The optional args is a list of arguments, args[0] should
        contain the exe name
    @type env: list
    @param env: env is a list of 'key=value' strings
    @type stdin_fname: string
    @param stdin_fname: Defaults to None.  If set can be used to redirect stdin
        to the specified filename
    @type stdout_fname: string
    @param stdout_fname:  Defaults to '-'.  If set can be used to redirect stdin
        to the specified filename.  If stdout_fname == '-' it is just passed through
        (not available for stdin and stderr)
    @type stderr_fname: string
    @param stderr_fname:  Defaults to None.  If set can be used to redirect stderr
        to the specified filename

    """
    if condorExe.condor_bin_path is None:
        raise UnconfigError, "condor_bin_path is undefined!"

    condor_exe_path = os.path.join(condorExe.condor_bin_path, condor_exe)

    # Fixed - According to execute's description, the first item in the args list
    # must be the executable.
    if args and not (args[0] == condor_exe_path):
        if args[0] == condor_exe:
            args[0] = condor_exe_path
        else:
            args.insert(0, condor_exe_path)

    return execute(target_user, init_dir, condor_exe_path, args, env,
                   stdin_fname=stdin_fname,
                   stdout_fname=stdout_fname,
                   stderr_fname=stderr_fname)

##################################
#
# INTERNAL
#
##################################

# TODO: PM: Disabling redirecting of error FD. Needs changes to make it work
#           with the subprocess module. 3>&2 should not be passed as command
#           line argument.
def exe_privsep(cmd, options):
    switchboard_stderr = os.dup( sys.stderr.fileno() )
    # we duplicate stderr because condor_root_switchboard closes it automatically.

    try:
        output = condorExe.exe_cmd("../sbin/condor_root_switchboard", "%s 0 %d" % (cmd, switchboard_stderr), options)
    except:
        try:
            exc_info = sys.exc_info()
            os.close(switchboard_stderr)
        except OSError:
            # Ignore if it is already closed, raise original exception
            raise exc_info[0], exc_info[1], exc_info[2]
        raise
    os.close(switchboard_stderr)
    return output
