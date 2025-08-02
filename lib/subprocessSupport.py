# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Fork a process and run a command."""

import os
import shlex
import subprocess

from subprocess import CalledProcessError

from . import defaults

# CalledProcessError(self, returncode, cmd, output=None, stderr=None)
# Provides: cmd, returncode, stdout, stderr, output (same as stdout)
# __str__ of this class is not printing the stdout in the error message


def iexe_cmd(cmd, useShell=False, stdin_data=None, child_env=None, text=True, encoding=None, timeout=None, log=None):
    """Fork a process and execute a command.

    This function forks a process to execute the given command using `subprocess.Popen`. It handles
    the command's standard input, output, and error streams, and returns the output of the command.
    If the command fails (i.e., returns a non-zero exit code), a `CalledProcessError` is raised.

    Using `process.communicate()` automatically handling buffers to avoid deadlocks.
    Before it had been rewritten to use select to avoid filling up stderr and stdout queues.

    The useShell value of True should be used sparingly.  It allows for executing commands
    that need access to shell features such as pipes, filename wildcards.  Refer to the
    Python manual for more information on this.  When used, the `cmd` string is not tokenized.

    One possible improvement would be to add a function to accept an array instead of a command string.

    Args:
        cmd (str): The command to execute, including all arguments.
        useShell (bool): Whether to execute the command in a shell. If True, the command is not tokenized. Defaults to False.
        stdin_data (str or bytes, optional): Data to be passed to the command's standard input. Should be bytes if `text` is False and `encoding` is None, str otherwise. Defaults to None.
        child_env (dict, optional): Environment variables to be set before execution. If None, the current environment is used. Defaults to None.
        text (bool): Whether to treat stdin, stdout, and stderr as text (str) or not (bytes). Defaults to True.
        encoding (str, optional): Encoding to use for the streams if `text` is True. Defaults to None, which uses `defaults.BINARY_ENCODING_DEFAULT` (utf-8).
        timeout (int, optional): Timeout in seconds for the command's execution. Defaults to None.
        log (logger, optional): Logger for debug and error messages. Defaults to None.

    Returns:
        str or bytes: The output of the command. The type depends on the value of `text`.

    Raises:
        subprocess.CalledProcessError: If the command returns a non-zero exit code.
        RuntimeError: If the command execution fails or times out.
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
        if child_env:
            # Add in parent process environment, make sure that env overrides parent
            for k in os.environ:
                if k not in child_env:
                    child_env[k] = os.environ[k]
        else:
            # otherwise just use the parent environment
            child_env = os.environ

        # Tokenize the commandline that should be executed.
        if useShell:
            command_list = [f"{cmd}"]
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
            err_str = (
                f"Timeout running '{cmd}'\n"
                f"Stdout:{stdoutdata}\nStderr:{stderrdata}\n"
                f"Exception subprocess.TimeoutExpired:{e}"
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

    if exit_status:  # True if the subprocess exit status<>0 (error)
        if log is not None:
            log.warning(
                f"Command '{cmd}' failed with exit code: {exit_status}\nStdout:{stdoutdata}\nStderr:{stderrdata}"
            )
        raise CalledProcessError(exit_status, cmd, output="".join(stdoutdata), stderr="".join(stderrdata))

    return stdoutdata
