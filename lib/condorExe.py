# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   This module implements the functions to execute condor commands


import os

from subprocess import CalledProcessError

from . import logSupport, subprocessSupport


class CondorExeError(RuntimeError):
    """Base class for condorExe module errors"""

    def __init__(self, err_str):
        RuntimeError.__init__(self, err_str)


class UnconfigError(CondorExeError):
    def __init__(self, err_str):
        CondorExeError.__init__(self, err_str)


class ExeError(CondorExeError):
    def __init__(self, err_str):
        CondorExeError.__init__(self, err_str)


#
# Configuration
#


def set_path(new_condor_bin_path, new_condor_sbin_path=None):
    """Set path to condor binaries, if needed

    Works changing the global variables condor_bin_path and condor_sbin_path

    Args:
        new_condor_bin_path (str): directory where the HTCondor binaries are located
        new_condor_sbin_path (str): directory where the HTCondor system binaries are located

    """
    global condor_bin_path, condor_sbin_path
    condor_bin_path = new_condor_bin_path
    if new_condor_sbin_path is not None:
        condor_sbin_path = new_condor_sbin_path


def exe_cmd(condor_exe, args, stdin_data=None, env={}):
    """Execute an arbitrary condor command and return its output as a list of lines
    Fails if stderr is not empty

    Args:
        condor_exe (str): condor_exe uses a relative path to $CONDOR_BIN
        args (str): arguments for the command
        stdin_data (str): Data that will be fed to the command via stdin
        env (dict): Environment to be set before execution

    Returns:
        Lines of stdout from the command

    Raises:
        UnconfigError:
        ExeError:
    """
    global condor_bin_path

    if condor_bin_path is None:
        raise UnconfigError("condor_bin_path is undefined!")
    condor_exe_path = os.path.join(condor_bin_path, condor_exe)

    cmd = f"{condor_exe_path} {args}"

    return iexe_cmd(cmd, stdin_data, env)


def exe_cmd_sbin(condor_exe, args, stdin_data=None, env={}):
    global condor_sbin_path

    if condor_sbin_path is None:
        raise UnconfigError("condor_sbin_path is undefined!")
    condor_exe_path = os.path.join(condor_sbin_path, condor_exe)

    cmd = f"{condor_exe_path} {args}"

    return iexe_cmd(cmd, stdin_data, env)


############################################################
#
# P R I V A T E, do not use
#
############################################################
def generate_bash_script(cmd, environment):
    """Print to a string a shell script setting the environment in 'environment' and running 'cmd'
    If 'cmd' last argument is a file it will be printed as well in the string

    Args:
        cmd (str): command string
        environment (dict): environment as a dictionary

    Returns:
        str: multi-line string with environment, command and eventually the input file
    """
    script = ["script to reproduce failure:", "-" * 20 + " begin script " + "-" * 20, "#!/bin/bash"]
    # FROM:migration_3_1, 3 lines
    # script = ['script to reproduce failure:']
    # script.append('-' * 20 + ' begin script ' + '-' * 20)
    # script.append('#!/bin/bash')

    script += [f"{k}={v}" for k, v in environment.items()]
    script.append(cmd)
    script.append("-" * 20 + "  end script  " + "-" * 20)
    cmd_list = cmd.split()
    if len(cmd_list) > 1:
        last_par = cmd_list[-1]
        if last_par and os.path.isfile(last_par):
            script.append("-" * 20 + "  parameter file: %s  " % last_par + "-" * 20)
            try:
                with open(last_par) as f:
                    script += f.read().splitlines()
            except OSError:
                pass
            script.append("-" * 20 + "  end parameter file " + "-" * 20)
    return "\n".join(script)


def iexe_cmd(cmd, stdin_data=None, child_env=None):
    """Fork a process and execute cmd - rewritten to use select to avoid filling
    up stderr and stdout queues.

    Args:
        cmd (str): Sting containing the entire command including all arguments
        stdin_data (str): Data that will be fed to the command via stdin
        child_env (dict): Environment to be set before execution

    Returns:
        list of str: Lines of stdout from the command

    Raises:
        ExeError

    """
    stdout_data = ""
    try:
        # invoking subprocessSupport.iexe_cmd w/ text=True (default), stdin_data and returned output are str
        stdout_data = subprocessSupport.iexe_cmd(cmd, stdin_data=stdin_data, child_env=child_env)
    except CalledProcessError as ex:
        msg = f"Failed condor command '{cmd}'. Exit code: {ex.returncode}. Stdout: {ex.stdout}. Stderr: {ex.stderr}"
        try:
            logSupport.log.error(msg)
            logSupport.log.debug(generate_bash_script(cmd, os.environ))
        except Exception:
            # log may be missing
            pass
        raise ExeError(msg) from ex
    except Exception as ex:
        msg = f"Unexpected Error running '{cmd}'. Details: {ex}. Stdout: {stdout_data}"
        try:
            logSupport.log.error(msg)
            logSupport.log.debug(generate_bash_script(cmd, os.environ))
        except Exception:
            # log may be missing
            pass
        raise ExeError(msg) from ex

    return stdout_data.splitlines()


#########################
# Module initialization
#


def init1():
    """Set condor_bin_path"""
    global condor_bin_path
    # try using condor commands to find it out
    try:
        condor_bin_path = iexe_cmd("condor_config_val BIN")[0].strip()  # remove trailing newline
    except ExeError as e:
        # try to find the RELEASE_DIR, and append bin
        try:
            release_path = iexe_cmd("condor_config_val RELEASE_DIR")
            condor_bin_path = os.path.join(release_path[0].strip(), "bin")
        except ExeError as e:
            # try condor_q in the path
            try:
                condorq_bin_path = iexe_cmd("which condor_q")
                condor_bin_path = os.path.dirname(condorq_bin_path[0].strip())
            except ExeError as e:
                # look for condor_config in /etc
                if "CONDOR_CONFIG" in os.environ:
                    condor_config = os.environ["CONDOR_CONFIG"]
                else:
                    condor_config = "/etc/condor/condor_config"

                try:
                    # BIN = <path>
                    bin_def = iexe_cmd('grep "^ *BIN" %s' % condor_config)
                    condor_bin_path = bin_def[0].strip().split()[2]
                except ExeError as e:
                    try:
                        # RELEASE_DIR = <path>
                        release_def = iexe_cmd('grep "^ *RELEASE_DIR" %s' % condor_config)
                        condor_bin_path = os.path.join(release_def[0].strip().split()[2], "bin")
                    except ExeError as e:
                        pass  # don't know what else to try


def init2():
    """Set condor_sbin_path"""
    global condor_sbin_path
    # try using condor commands to find it out
    try:
        condor_sbin_path = iexe_cmd("condor_config_val SBIN")[0].strip()  # remove trailing newline
    except ExeError as e:
        # try to find the RELEASE_DIR, and append bin
        try:
            release_path = iexe_cmd("condor_config_val RELEASE_DIR")
            condor_sbin_path = os.path.join(release_path[0].strip(), "sbin")
        except ExeError as e:
            # try condor_q in the path
            try:
                condora_sbin_path = iexe_cmd("which condor_advertise")
                condor_sbin_path = os.path.dirname(condora_sbin_path[0].strip())
            except ExeError as e:
                # look for condor_config in /etc
                if "CONDOR_CONFIG" in os.environ:
                    condor_config = os.environ["CONDOR_CONFIG"]
                else:
                    condor_config = "/etc/condor/condor_config"

                try:
                    # BIN = <path>
                    bin_def = iexe_cmd('grep "^ *SBIN" %s' % condor_config)
                    condor_sbin_path = bin_def[0].strip().split()[2]
                except ExeError as e:
                    try:
                        # RELEASE_DIR = <path>
                        release_def = iexe_cmd('grep "^ *RELEASE_DIR" %s' % condor_config)
                        condor_sbin_path = os.path.join(release_def[0].strip().split()[2], "sbin")
                    except ExeError as e:
                        pass  # don't know what else to try


def init():
    """Set both Set condor_bin_path and condor_sbin_path"""
    init1()
    init2()


# This way we know that it is undefined
condor_bin_path = None
condor_sbin_path = None

init()
