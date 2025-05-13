#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Stop a running glideinFactory.

This program stops a running glideinFactory by killing its process group.
It expects one argument: the glidein submit directory (i.e. factory dir).
Option "-force" uses a hard kill (SIGKILL) after trying a soft one (SIGTERM).

Usage: stopFactory [-f|-force] submit_dir
"""


import os
import signal
import subprocess
import sys
import time

from glideinwms.factory import glideFactoryPidLib


def all_pids_in_pgid_dead(pgid):
    """Check if all processes in the given process group are dead.

    Args:
        pgid (int): Process group ID.

    Returns:
        int: 1 if no processes in the process group are alive, 0 otherwise.
    """
    # return 1 if there are no pids in the pgid still alive
    # 0 otherwise
    devnull = os.open(os.devnull, os.O_RDWR)
    return subprocess.call(["pgrep", "-g", "%s" % pgid], stdout=devnull, stderr=devnull)


def kill_and_check_pgid(pgid, signr=signal.SIGTERM, retries=100, retry_interval=0.5):
    """Send a signal to the process group and check until all processes are dead.

    This function sends the given signal (default SIGTERM) to all processes in the
    specified process group and then checks repeatedly until no processes remain.
    It retries a specified number of times (default 100) with a specified interval (default 0.5 seconds).

    Args:
        pgid (int): Process group ID.
        signr (int, optional): Signal number to send. Defaults to SIGTERM.
        retries (int, optional): Number of retry attempts. Defaults to 100.
        retry_interval (float, optional): Interval in seconds between retries. Defaults to 0.5.

    Returns:
        int: 0 if all processes in the group are dead within the timeout, 1 otherwise.
    """
    # return 0 if all pids in pgid are dead
    # 50 sec timeout by default
    try:
        os.killpg(pgid, signr)
    except OSError:
        # can check err.errno
        # errno.EPERM if it is not allowed
        # errno.ESRCH if the process does not exist
        pass

    for retries in range(retries):
        if all_pids_in_pgid_dead(pgid) == 1:
            return 0
        else:
            time.sleep(retry_interval)
    return 1


def main(startup_dir, force=True):
    """Stop the glideinFactory process.

    This function retrieves the factory PID from the specified startup directory, verifies that
    the factory is running, and then attempts to kill its process group gracefully. If the graceful
    termination fails and force is True, it escalates to a hard kill.

    Args:
        startup_dir (str): The startup directory (factory directory).
        force (bool, optional): If True, force kill if graceful termination fails. Defaults to True.

    Returns:
        int: Exit code, where 0 indicates success, 1 indicates failure to stop, and 2 indicates that
             the factory was not running.
    """
    # get the pids
    try:
        factory_pid = glideFactoryPidLib.get_factory_pid(startup_dir)
    except RuntimeError as e:
        print(e)
        if str(e) == "Factory not running":
            # Workaround to distinguish when the factory is not running
            # string must be the same as in glideFactoryPidLib
            return 2
        return 1
    # print factory_pid

    factory_pgid = os.getpgid(factory_pid)

    if not glideFactoryPidLib.pidSupport.check_pid(factory_pid):
        # Factory already dead
        return 0

    # kill processes
    # first soft kill the factoryprocess group  (50s timeout)
    if kill_and_check_pgid(factory_pgid) == 0:
        return 0

    if not force:
        print("Factory did not die within the timeout")
        return 1

    # retry soft kill the factory... should exit now (5s timeout)
    if kill_and_check_pgid(factory_pgid, retries=30, signr=signal.SIGTERM) == 0:
        return 0

    print("Factory or children still alive... sending hard kill")

    try:
        os.killpg(factory_pgid, signal.SIGKILL)
    except OSError:
        # in case they died between the last check and now
        pass

    return 0


USAGE_STRING = """Usage: stopFactory [-f|-force] submit_dir
     return values: 0 Factory stopped,
         1 unable to stop Factory or wrong invocation, 2 Factory was not running
"""
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(USAGE_STRING)
        sys.exit(1)

    if len(sys.argv) > 2:
        if sys.argv[1] == "-force" or sys.argv[1] == "-f":
            sys.exit(main(sys.argv[2], True))
        else:
            print(USAGE_STRING)
            sys.exit(1)
    else:
        sys.exit(main(sys.argv[1]))
