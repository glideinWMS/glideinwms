# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Fork a process and run a command
"""

import os
import shlex
import subprocess

from subprocess import CalledProcessError

from . import defaults

# CalledProcessError(self, returncode, cmd, output=None, stderr=None)
# Provides: cmd, returncode, stdout, stderr, output (same as stdout)
# __str__ of this class is not printing the stdout in the error message


def iexe_cmd(cmd, useShell=False, stdin_data=None, child_env=None, text=True, encoding=None, timeout=None, log=None):
    """Fork a process and execute cmd

    Using `process.communicate()` automatically handling buffers to avoid deadlocks.
    Before it had been rewritten to use select to avoid filling up stderr and stdout queues.

    The useShell value of True should be used sparingly.  It allows for
    executing commands that need access to shell features such as pipes,
    filename wildcards.  Refer to the python manual for more information on
    this.  When used, the 'cmd' string is not tokenized.

    One possible improvement would be to add a function to accept
    an array instead of a command string.

    Args:
        cmd (str): String containing the entire command including all arguments
        useShell (bool): if True run the command in a shell (passed to Popen as shell)
        stdin_data (str/bytes): Data that will be fed to the command via stdin. It should be bytes if text is False
            and encoding is None, str otherwise
        child_env (dict): Environment to be set before execution
        text (bool): if False, then stdin_data and the return value are bytes instead of str (default: True)
        encoding (str|None): encoding to use for the streams. If None (default) and text is True, then the
            defaults.BINARY_ENCODING_DEFAULT (utf-8) encoding is used
        timeout (None|int): timeout in seconds. No timeout by default
        log (logger): optional logger for debug and error messages

    Returns:
        str/bytes: output of the command. It will be bytes if text is False,
            str otherwise

    Raises:
        subprocess.CalledProcessError: if the subprocess fails (exit status not 0)
        RuntimeError: if it fails to invoke the subprocess or the subprocess times out
    """
    # TODO: use subprocess.run instead of Pipe
    #   could this be replaced directly by subprocess run throughout the program?

    stdoutdata = stderrdata = ""
    if not text:
        stdoutdata = stderrdata = b""
    else:
        if encoding is None:
            encoding = defaults.BINARY_ENCODING_DEFAULT
    exit_status = 0

    try:
        # Add in parent process environment, make sure that env overrides parent
        if child_env:
            for k in os.environ:
                if k not in child_env:
                    child_env[k] = os.environ[k]
        # otherwise just use the parent environment
        else:
            child_env = os.environ

        # Tokenize the commandline that should be executed.
        if useShell:
            command_list = [
                "%s" % cmd,
            ]
        else:
            command_list = shlex.split(cmd)
        # launch process - Converted to using the subprocess module
        # when specifying an encoding the streams are text, bytes if encoding is None
        process = subprocess.Popen(
            command_list,
            shell=useShell,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=child_env,
            encoding=encoding,
        )
        if log is not None:
            if encoding is None:
                encoding = "bytes"
            log.debug(f"Spawned subprocess {process.pid} ({encoding}, {timeout}) for {command_list}")

        # GOTCHAS:
        # 1) stdin should be buffered in memory.
        # 2) Python docs suggest not to use communicate if the data size is
        #    large or unlimited. With large or unlimited stdout and stderr
        #    communicate at best starts trashing. So far testing for 1000000
        #    stdout/stderr lines are ok
        # 3) Do not use communicate when you are dealing with multiple threads
        #    or processes at same time. It will serialize the process voiding
        #    any benefits from multiple processes
        try:
            stdoutdata, stderrdata = process.communicate(input=stdin_data, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            process.kill()
            stdoutdata, stderrdata = process.communicate()
            err_str = "Timeout running '{}'\nStdout:{}\nStderr:{}\nException subprocess.TimeoutExpired:{}".format(
                cmd,
                stdoutdata,
                stderrdata,
                e,
            )
            if log is not None:
                log.error(err_str)
            raise RuntimeError(err_str)

        exit_status = process.returncode

    except OSError as e:
        err_str = f"Error running '{cmd}'\nStdout:{stdoutdata}\nStderr:{stderrdata}\nException OSError:{e}"
        if log is not None:
            log.error(err_str)
        raise RuntimeError(err_str) from e

    if exit_status:  # True if exit_status<>0
        if log is not None:
            log.warning(
                f"Command '{cmd}' failed with exit code: {exit_status}\nStdout:{stdoutdata}\nStderr:{stderrdata}"
            )
        raise CalledProcessError(exit_status, cmd, output="".join(stdoutdata), stderr="".join(stderrdata))

    return stdoutdata
