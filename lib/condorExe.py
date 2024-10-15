# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module implements the functions to execute condor commands.
"""

import os

from subprocess import CalledProcessError

from . import logSupport, subprocessSupport


class CondorExeError(RuntimeError):
    """
    Base class for condorExe module errors.
    """

    def __init__(self, err_str):
        """
        Initializes the CondorExeError with an error message.

        Args:
            err_str (str): The error message.
        """
        RuntimeError.__init__(self, err_str)


class UnconfigError(CondorExeError):
    """
    Exception raised when condor is unconfigured.
    """

    def __init__(self, err_str):
        """
        Initializes the UnconfigError with an error message.

        Args:
            err_str (str): The error message.
        """
        CondorExeError.__init__(self, err_str)


class ExeError(CondorExeError):
    """
    Exception raised when there is an error executing a condor command.
    """

    def __init__(self, err_str):
        """
        Initializes the ExeError with an error message.

        Args:
            err_str (str): The error message.
        """
        CondorExeError.__init__(self, err_str)


def set_path(new_condor_bin_path, new_condor_sbin_path=None):
    """
    Set path to condor binaries, if needed.

    Works by changing the global variables condor_bin_path and condor_sbin_path.

    Args:
        new_condor_bin_path (str): Directory where the HTCondor binaries are located.
        new_condor_sbin_path (str, optional): Directory where the HTCondor system binaries are located. Defaults to None.
    """
    global condor_bin_path, condor_sbin_path
    condor_bin_path = new_condor_bin_path
    if new_condor_sbin_path is not None:
        condor_sbin_path = new_condor_sbin_path


def exe_cmd(condor_exe, args, stdin_data=None, env={}):
    """
    Execute an arbitrary condor command and return its output as a list of lines.

    Fails if stderr is not empty.

    Args:
        condor_exe (str): Condor executable, uses a relative path to $CONDOR_BIN.
        args (str): Arguments for the command.
        stdin_data (str, optional): Data that will be fed to the command via stdin. Defaults to None.
        env (dict, optional): Environment to be set before execution. Defaults to {}.

    Returns:
        list: Lines of stdout from the command.

    Raises:
        UnconfigError: If condor_bin_path is undefined.
        ExeError: If there is an error executing the command.
    """
    global condor_bin_path

    if condor_bin_path is None:
        raise UnconfigError("condor_bin_path is undefined!")
    condor_exe_path = os.path.join(condor_bin_path, condor_exe)

    cmd = f"{condor_exe_path} {args}"

    return iexe_cmd(cmd, stdin_data, env)


def exe_cmd_sbin(condor_exe, args, stdin_data=None, env={}):
    """
    Execute an arbitrary condor system command and return its output as a list of lines.

    Fails if stderr is not empty.

    Args:
        condor_exe (str): Condor executable, uses a relative path to $CONDOR_SBIN.
        args (str): Arguments for the command.
        stdin_data (str, optional): Data that will be fed to the command via stdin. Defaults to None.
        env (dict, optional): Environment to be set before execution. Defaults to {}.

    Returns:
        list: Lines of stdout from the command.

    Raises:
        UnconfigError: If condor_sbin_path is undefined.
        ExeError: If there is an error executing the command.
    """
    global condor_sbin_path

    if condor_sbin_path is None:
        raise UnconfigError("condor_sbin_path is undefined!")
    condor_exe_path = os.path.join(condor_sbin_path, condor_exe)

    cmd = f"{condor_exe_path} {args}"

    return iexe_cmd(cmd, stdin_data, env)


def generate_bash_script(cmd, environment):
    """
    Print to a string a shell script setting the environment in 'environment' and running 'cmd'.

    If 'cmd' last argument is a file it will be printed as well in the string.

    Args:
        cmd (str): Command string.
        environment (dict): Environment as a dictionary.

    Returns:
        str: Multi-line string with environment, command, and eventually the input file.
    """
    script = ["script to reproduce failure:", "-" * 20 + " begin script " + "-" * 20, "#!/bin/bash"]
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


def iexe_cmd(cmd, stdin_data=None, child_env=None, log=None):
    """
    Fork a process and execute cmd - rewritten to use select to avoid filling up stderr and stdout queues.

    Args:
        cmd (str): Command string containing the entire command including all arguments.
        stdin_data (str, optional): Data that will be fed to the command via stdin. Defaults to None.
        child_env (dict, optional): Environment to be set before execution. Defaults to None.
        log (optional): Logger instance. Defaults to None.

    Returns:
        list: Lines of stdout from the command.

    Raises:
        ExeError: If there is an error executing the command.
    """
    stdout_data = ""
    if log is None:
        log = logSupport.log
    try:
        # invoking subprocessSupport.iexe_cmd w/ text=True (default), stdin_data and returned output are str
        stdout_data = subprocessSupport.iexe_cmd(cmd, stdin_data=stdin_data, child_env=child_env)
    except CalledProcessError as ex:
        msg = f"Failed condor command '{cmd}'. Exit code: {ex.returncode}. Stdout: {ex.stdout}. Stderr: {ex.stderr}"
        try:
            if log is not None:
                log.error(msg)
                log.debug(generate_bash_script(cmd, os.environ))
        except Exception:
            # log may be missing
            pass
        raise ExeError(msg) from ex
    except Exception as ex:
        msg = f"Unexpected Error running '{cmd}'. Details: {ex}. Stdout: {stdout_data}"
        try:
            if log is not None:
                log.error(msg)
                log.debug(generate_bash_script(cmd, os.environ))
        except Exception:
            # log may be missing
            pass
        raise ExeError(msg) from ex

    return stdout_data.splitlines()


def init1():
    """
    Set condor_bin_path using various methods to locate the HTCondor binaries.
    """
    global condor_bin_path
    # try using condor commands to find it out
    try:
        condor_bin_path = iexe_cmd("condor_config_val BIN")[0].strip()  # remove trailing newline
    except ExeError:
        # try to find the RELEASE_DIR, and append bin
        try:
            release_path = iexe_cmd("condor_config_val RELEASE_DIR")
            condor_bin_path = os.path.join(release_path[0].strip(), "bin")
        except ExeError:
            # try condor_q in the path
            try:
                condorq_bin_path = iexe_cmd("which condor_q")
                condor_bin_path = os.path.dirname(condorq_bin_path[0].strip())
            except ExeError:
                # look for condor_config in /etc
                if "CONDOR_CONFIG" in os.environ:
                    condor_config = os.environ["CONDOR_CONFIG"]
                else:
                    condor_config = "/etc/condor/condor_config"

                try:
                    # BIN = <path>
                    bin_def = iexe_cmd('grep "^ *BIN" %s' % condor_config)
                    condor_bin_path = bin_def[0].strip().split()[2]
                except ExeError:
                    try:
                        # RELEASE_DIR = <path>
                        release_def = iexe_cmd('grep "^ *RELEASE_DIR" %s' % condor_config)
                        condor_bin_path = os.path.join(release_def[0].strip().split()[2], "bin")
                    except ExeError:
                        pass  # don't know what else to try


def init2():
    """
    Set condor_sbin_path using various methods to locate the HTCondor system binaries.
    """
    global condor_sbin_path
    # try using condor commands to find it out
    try:
        condor_sbin_path = iexe_cmd("condor_config_val SBIN")[0].strip()  # remove trailing newline
    except ExeError:
        # try to find the RELEASE_DIR, and append bin
        try:
            release_path = iexe_cmd("condor_config_val RELEASE_DIR")
            condor_sbin_path = os.path.join(release_path[0].strip(), "sbin")
        except ExeError:
            # try condor_q in the path
            try:
                condora_sbin_path = iexe_cmd("which condor_advertise")
                condor_sbin_path = os.path.dirname(condora_sbin_path[0].strip())
            except ExeError:
                # look for condor_config in /etc
                if "CONDOR_CONFIG" in os.environ:
                    condor_config = os.environ["CONDOR_CONFIG"]
                else:
                    condor_config = "/etc/condor/condor_config"

                try:
                    # BIN = <path>
                    bin_def = iexe_cmd('grep "^ *SBIN" %s' % condor_config)
                    condor_sbin_path = bin_def[0].strip().split()[2]
                except ExeError:
                    try:
                        # RELEASE_DIR = <path>
                        release_def = iexe_cmd('grep "^ *RELEASE_DIR" %s' % condor_config)
                        condor_sbin_path = os.path.join(release_def[0].strip().split()[2], "sbin")
                    except ExeError:
                        pass  # don't know what else to try


def init():
    """
    Initialize both condor_bin_path and condor_sbin_path.
    """
    init1()
    init2()


# This way we know that it is undefined
condor_bin_path = None
condor_sbin_path = None

init()
