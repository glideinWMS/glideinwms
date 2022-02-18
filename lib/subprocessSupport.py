# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os
import shlex
import subprocess

from subprocess import CalledProcessError

# CalledProcessError(self, returncode, cmd, output=None, stderr=None)
# Provides: cmd, returncode, stdout, stderr, output (same as stdout)
# __str__ of this class is not printing the stdout in the error message


# TODO: remove once the import from subprocess is proven to work
#    Helper functions below have been remoced as well since they are the same as in subprocess and seem not used
# Exception classes used by this module.
class CalledProcessError2(Exception):
    """This exception is raised when a process run by check_call() or
    check_output() returns a non-zero exit status.
    The exit status will be stored in the returncode attribute;
    check_output() will also store the output in the output attribute.
    """

    def __init__(self, returncode, cmd, output=None):
        self.returncode = returncode
        self.cmd = cmd
        self.output = output

    def __str__(self):
        return "Command '{}' returned non-zero exit status {}: {}".format(
            self.cmd,
            self.returncode,
            self.output,
        )


def iexe_cmd(cmd, useShell=False, stdin_data=None, child_env=None, text=True):
    """
    Fork a process and execute cmd - rewritten to use select to avoid filling
    up stderr and stdout queues.

    The useShell value of True should be used sparingly.  It allows for
    executing commands that need access to shell features such as pipes,
    filename wildcards.  Refer to the python manual for more information on
    this.  When used, the 'cmd' string is not tokenized.

    One possible improvement would be to add a function to accept
    an array instead of a command string.

    Args:
        cmd (str): String containing the entire command including all arguments
        useShell (bool): if True run the command in a shell (passed to Popen as shell)
        stdin_data (str/bytes): Data that will be fed to the command via stdin. It will be bytes if text is False,
            str otherwise
        child_env (dict): Environment to be set before execution
        text (bool): if False, then stdin_data and the return value are bytes instead of str (default: True)

    Returns:
        str/bytes: output of the command. It will be bytes if text is False,
            str otherwise

    """
    # TODO: use subprocess.run instead of Pipe
    #   could this be replaced directly by subprocess run throughout the program?

    stdoutdata = stderrdata = ""
    if not text:
        stdoutdata = stderrdata = b""
    exitStatus = 0

    try:
        # Add in parent process environment, make sure that env ovrrides parent
        if child_env:
            for k in os.environ:
                if not k in child_env:
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
        process = subprocess.Popen(
            command_list,
            shell=useShell,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=child_env,
            universal_newlines=text,
        )

        # GOTCHAS:
        # 1) stdin should be buffered in memory.
        # 2) Python docs suggest not to use communicate if the data size is
        #    large or unlimited. With large or unlimited stdout and stderr
        #    communicate at best starts trashing. So far testing for 1000000
        #    stdout/stderr lines are ok
        # 3) Do not use communicate when you are dealing with multiple threads
        #    or processes at same time. It will serialize the process voiding
        #    any benefits from multiple processes
        stdoutdata, stderrdata = process.communicate(input=stdin_data)
        exitStatus = process.returncode

    except OSError as e:
        err_str = "Error running '%s'\nStdout:%s\nStderr:%s\nException OSError:%s"
        raise RuntimeError(err_str % (cmd, stdoutdata, stderrdata, e))
    if exitStatus:
        raise CalledProcessError(exitStatus, cmd, output="".join(stderrdata))
    return stdoutdata
