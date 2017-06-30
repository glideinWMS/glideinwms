import os
import subprocess
import shlex

# Exception classes used by this module.
class CalledProcessError(Exception):
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
        return "Command '%s' returned non-zero exit status %s: %s" % (self.cmd, self.returncode, self.output)


def iexe_cmd(cmd, useShell=False, stdin_data=None, child_env=None):
    """
    Fork a process and execute cmd - rewritten to use select to avoid filling
    up stderr and stdout queues.

    The useShell value of True should be used sparingly.  It allows for
    executing commands that need access to shell features such as pipes,
    filename wildcards.  Refer to the python manual for more information on
    this.  When used, the 'cmd' string is not tokenized.

    One possible improvment would be to add a function to accept
    an array instead of a command string.

    @type cmd: string
    @param cmd: Sting containing the entire command including all arguments
    @type stdin_data: string
    @param stdin_data: Data that will be fed to the command via stdin
    @type env: dict
    @param env: Environment to be set before execution
    """
    stdoutdata = stderrdata = ""
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
          command_list = ['%s' % cmd,]
        else:
          command_list = shlex.split(cmd.encode('utf8'))
        # launch process - Converted to using the subprocess module
        process = subprocess.Popen(command_list, shell=useShell,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   env=child_env)

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
        raise RuntimeError, err_str % (cmd, stdoutdata, stderrdata, e)
    if exitStatus:
        raise CalledProcessError(exitStatus, cmd, output="".join(stderrdata))
    return stdoutdata

def call(*popenargs, **kwargs):
    """Run command with arguments.  Wait for command to complete, then
    return the returncode attribute.

    The arguments are the same as for the Popen constructor.  Example:

    retcode = call(["ls", "-l"])
    """
    return subprocess.Popen(*popenargs, **kwargs).wait()


def check_call(*popenargs, **kwargs):
    """Run command with arguments.  Wait for command to complete.  If
    the exit code was zero then return, otherwise raise
    CalledProcessError.  The CalledProcessError object will have the
    return code in the returncode attribute.

    The arguments are the same as for the Popen constructor.  Example:

    check_call(["ls", "-l"])
    """
    retcode = call(*popenargs, **kwargs)
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise CalledProcessError(retcode, cmd)
    return 0


def check_output(*popenargs, **kwargs):
    """Run command with arguments and return its output as a byte string.

    If the exit code was non-zero it raises a CalledProcessError.  The
    CalledProcessError object will have the return code in the returncode
    attribute and output in the output attribute.

    The arguments are the same as for the Popen constructor.  Example:

    >>> check_output(["ls", "-l", "/dev/null"])
    'crw-rw-rw- 1 root root 1, 3 Oct 18  2007 /dev/null\n'

    The stdout argument is not allowed as it is used internally.
    To capture standard error in the result, use stderr=STDOUT.

    >>> check_output(["/bin/sh", "-c",
    ...               "ls -l non_existent_file ; exit 0"],
    ...              stderr=STDOUT)
    'ls: non_existent_file: No such file or directory\n'
    """
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, _ = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise CalledProcessError(retcode, cmd, output=output)
    return output
