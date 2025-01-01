# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements functions and classes to handle forking of processes and the collection of results.
"""

# TODO: This could be rewritten so that the polling lists are registered once and the fd are removed only when
#       not needed anymore (currently there is an external structure and the poll object is a new one each time)

import errno
import os
import pickle
import select
import subprocess
import sys
import time

from . import logSupport
from .pidSupport import register_sighandler, unregister_sighandler


class ForkError(RuntimeError):
    """Base class for this module's errors."""

    def __init__(self, msg):
        RuntimeError.__init__(self, msg)


class FetchError(ForkError):
    pass


class ForkResultError(ForkError):
    """Raised when there are errors in the forked processes.

    Attributes:
        nr_errors (int): Number of errors.
        good_results (dict): Results of successful forks.
        failed (list): List of failed forks.
    """

    def __init__(self, nr_errors, good_results, failed=[]):
        super().__init__(f"Found {nr_errors} errors")
        self.nr_errors = nr_errors
        self.good_results = good_results
        self.failed = failed


def fork_in_bg(function_torun, *args):
    """Forks and calls a function with args.

    This function returns right away, returning the pid and a pipe to the stdout of the function process
    where the output of the function will be pickled.

    Example:
        def add(i, j): return i + j
        d = fork_in_bg(add, i, j)

    Args:
        function_torun (function): Function to call after forking the process.
        *args: Arguments list to pass to the function.

    Returns:
        dict: Dict with {'r': fd, 'pid': pid} where fd is the stdout from a pipe.
    """
    r, w = os.pipe()
    unregister_sighandler()
    pid = os.fork()
    if pid == 0:
        logSupport.disable_rotate = True
        os.close(r)
        try:
            out = function_torun(*args)
            os.write(w, pickle.dumps(out))
        except Exception:
            logSupport.log.warning(f"Forked process '{function_torun}' failed")
            logSupport.log.exception(f"Forked process '{function_torun}' failed")
        finally:
            os.close(w)
            os._exit(0)
    else:
        register_sighandler()
        os.close(w)

    return {"r": r, "pid": pid}


def fetch_fork_result(r, pid):
    """Used with fork clients to retrieve results.

    Args:
        r (int): Input pipe.
        pid (int): PID of the child.

    Returns:
        object: Unpickled object.

    Raises:
        FetchError: If an os.read error was encountered or if the forked process failed.
    """
    rin = b""
    out = None
    try:
        s = os.read(r, 1024 * 1024)
        while s != b"":  # "" means EOF
            rin += s
            s = os.read(r, 1024 * 1024)
        out = pickle.loads(rin)
    except (OSError, EOFError, pickle.UnpicklingError) as err:
        logSupport.log.exception(f"Re-raising exception during read: {err}")
        raise FetchError(
            f"Exception during read probably due to worker failure, original exception and trace: {err}"
        ) from err
    finally:
        os.close(r)
        os.waitpid(pid, 0)
    return out


def fetch_fork_result_list(pipe_ids):
    """Read the output pipe of the children, used after forking to perform work.

    Args:
        pipe_ids (dict): Dictionary of pipe and pid.

    Returns:
        dict: Dictionary of fork results.

    Raises:
        ForkResultError: If there are failures in fetching fork results.
    """
    out = {}
    failures = 0
    failed = []
    for key in pipe_ids:
        try:
            out[key] = fetch_fork_result(pipe_ids[key]["r"], pipe_ids[key]["pid"])
        except (KeyError, OSError, FetchError) as err:
            errmsg = f"Failed to extract info from child '{key}': {err}"
            logSupport.log.warning(errmsg)
            logSupport.log.exception(errmsg)
            failed.append(key)
            failures += 1

    if failures > 0:
        raise ForkResultError(failures, out, failed=failed)

    return out


def fetch_ready_fork_result_list(pipe_ids):
    """Read the output pipe of the children, used after forking. If there is data
    on the pipes to consume, read the data and close the pipe.

    Args:
        pipe_ids (dict): Dictionary of pipe and pid.

    Returns:
        dict: Dictionary of work done.

    Raises:
        ForkResultError: If there are failures in fetching ready fork results.
    """
    POLL_TIMEOUT = 100
    work_info = {}
    failures = 0
    failed = []
    fds_to_entry = {pipe_ids[x]["r"]: x for x in pipe_ids}
    poll_obj = None
    time_this = False
    t_begin = None
    if time_this:
        t_begin = time.time()
    try:
        poll_obj = select.epoll()
        poll_type = "epoll"
        for read_fd in list(fds_to_entry.keys()):
            try:
                poll_obj.register(
                    read_fd,
                    select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR | select.EPOLLRDBAND | select.EPOLLRDNORM,
                )
            except OSError as err:
                if err.errno == errno.EEXIST:
                    logSupport.log.warning(f"Ignoring duplicate fd {read_fd} registration in epoll(): '{err}'")
                else:
                    logSupport.log.warning(f"Unsupported fd {read_fd} registration failure in epoll(): '{err}'")
                    raise
        readable_fds = [i[0] for i in poll_obj.poll(POLL_TIMEOUT)]
    except (AttributeError, OSError) as err:
        logSupport.log.warning(f"Failed to load select.epoll(): {err}")
        try:
            poll_obj = select.poll()
            poll_type = "poll"
            for read_fd in list(fds_to_entry.keys()):
                poll_obj.register(read_fd, select.POLLIN | select.POLLHUP | select.POLLERR)
            readable_fds = [i[0] for i in poll_obj.poll(POLL_TIMEOUT)]
        except (AttributeError, OSError) as err:
            logSupport.log.warning(f"Failed to load select.poll(): {err}")
            readable_fds = select.select(list(fds_to_entry.keys()), [], [], POLL_TIMEOUT / 1000.0)[0]
            poll_type = "select"

    count = 0
    for fd in readable_fds:
        if fd not in fds_to_entry:
            continue
        key = None
        try:
            key = fds_to_entry[fd]
            pid = pipe_ids[key]["pid"]
            out = fetch_fork_result(fd, pid)
            try:
                if poll_obj:
                    poll_obj.unregister(fd)
            except OSError as err:
                if err.errno != 9:
                    errmsg = f"unregister failed pid='{pid}' fd='{fd}' key='{key}': {err}"
                    logSupport.log.warning(errmsg)
                    logSupport.log.exception(errmsg)
                    raise
            work_info[key] = out
            count += 1
        except (OSError, ValueError, KeyError, FetchError) as err:
            errmsg = f"Failed to extract info from child '{key}': {err}"
            logSupport.log.warning(errmsg)
            logSupport.log.exception(errmsg)
            failed.append(key)
            failures += 1

    if failures > 0:
        raise ForkResultError(failures, work_info, failed=failed)

    if time_this:
        logSupport.log.debug(
            f"fetch_ready_fork_result_list: using {poll_type} fetched {count} of {len(fds_to_entry)} in {time.time() - t_begin} seconds"
        )

    return work_info


def wait_for_pids(pid_list):
    """Wait for all pids to finish and discard any stdout or stderr.

    Args:
        pid_list (list): List of pids to wait for.
    """
    for pidel in pid_list:
        pid = pidel["pid"]
        r = pidel["r"]
        try:
            s = os.read(r, 1024)
            while s != b"":  # "" means EOF, pipes are binary
                s = os.read(r, 1024)
        finally:
            os.close(r)
            os.waitpid(pid, 0)


class ForkManager:
    """Manages the forking of processes and the collection of results."""

    def __init__(self):
        self.functions_tofork = {}
        self.key_list = []

    def __len__(self):
        return len(self.functions_tofork)

    def add_fork(self, key, function, *args):
        """Adds a function to be forked.

        Args:
            key (str): Unique key for the fork.
            function (function): Function to be forked.
            *args: Arguments to be passed to the function.

        Raises:
            KeyError: If the key is already in use.
        """
        if key in self.functions_tofork:
            raise KeyError(f"Fork key '{key}' already in use")
        self.functions_tofork[key] = (function,) + args
        self.key_list.append(key)

    def fork_and_wait(self):
        """Forks and waits for all functions to complete."""
        pids = []
        for key in self.key_list:
            pids.append(fork_in_bg(*self.functions_tofork[key]))
        wait_for_pids(pids)

    def fork_and_collect(self):
        """Forks and collects the results of all functions.

        Returns:
            dict: Dictionary of results.
        """
        pipe_ids = {}
        for key in self.key_list:
            pipe_ids[key] = fork_in_bg(*self.functions_tofork[key])
        results = fetch_fork_result_list(pipe_ids)
        return results

    def bounded_fork_and_collect(self, max_forks, log_progress=True, sleep_time=0.01):
        """Forks and collects results with a limit on the number of concurrent forks.

        Args:
            max_forks (int): Maximum number of concurrent forks.
            log_progress (bool): Whether to log progress.
            sleep_time (float): Time to sleep between checks.

        Returns:
            dict: Dictionary of results.

        Raises:
            ForkResultError: If there are errors in the forked processes.
        """
        post_work_info = {}
        nr_errors = 0
        pipe_ids = {}
        forks_remaining = max_forks
        functions_remaining = len(self.functions_tofork)

        for key in self.key_list:
            if forks_remaining == 0:
                if log_progress:
                    logSupport.log.info(f"Active forks = {max_forks}, Forks to finish = {functions_remaining}")
            while forks_remaining == 0:
                failed_keys = []
                time.sleep(sleep_time)
                try:
                    post_work_info_subset = fetch_ready_fork_result_list(pipe_ids)
                except ForkResultError as e:
                    post_work_info_subset = e.good_results
                    nr_errors += e.nr_errors
                    functions_remaining -= e.nr_errors
                    failed_keys = e.failed

                post_work_info.update(post_work_info_subset)
                forks_remaining += len(post_work_info_subset)
                functions_remaining -= len(post_work_info_subset)

                for i in list(post_work_info_subset.keys()) + failed_keys:
                    if pipe_ids.get(i):
                        del pipe_ids[i]
            pipe_ids[key] = fork_in_bg(*self.functions_tofork[key])
            forks_remaining -= 1

        if log_progress:
            logSupport.log.info(
                f"Active forks = {max_forks - forks_remaining}, Forks to finish = {functions_remaining}"
            )

        while functions_remaining > 0:
            failed_keys = []
            time.sleep(sleep_time)
            try:
                post_work_info_subset = fetch_ready_fork_result_list(pipe_ids)
            except ForkResultError as e:
                post_work_info_subset = e.good_results
                nr_errors += e.nr_errors
                functions_remaining -= e.nr_errors
                failed_keys = e.failed

            post_work_info.update(post_work_info_subset)
            forks_remaining += len(post_work_info_subset)
            functions_remaining -= len(post_work_info_subset)

            for i in list(post_work_info_subset.keys()) + failed_keys:
                del pipe_ids[i]

            if len(post_work_info_subset) > 0 and log_progress:
                logSupport.log.info(
                    f"Active forks = {max_forks - forks_remaining}, Forks to finish = {functions_remaining}"
                )

        if nr_errors > 0:
            raise ForkResultError(nr_errors, post_work_info)

        return post_work_info


def print_child_processes(root_pid=str(os.getppid()), this_pid=str(os.getpid())):
    """Print the process tree of the root PID.

    Args:
        root_pid (str): String containing the process ID to use as root of the process tree.
        this_pid (str, optional): String containing the process ID of the current process (will get a star in the line).

    Returns:
        list: List of str containing all the lines of the process tree.
    """

    def print_children(id, ps_dict, my_id="", level=0):
        """Auxiliary recursive function to print the children subtree of a given process ID.

        Args:
            id (str): String with process ID root of the tree.
            ps_dict (dict): Dictionary with all processes and their children.
            my_id (str, optional): String with process ID of the print_children caller.
            level (int, optional): Level of the subtree.

        Returns:
            list: List of str containing all the lines of the process subtree.
        """
        if my_id and my_id == id:
            out = ["+" * level + id + " *"]
        else:
            out = ["+" * level + id]
        if id in ps_dict:
            for i in ps_dict[id]:
                if i != id:
                    out += print_children(i, ps_dict, my_id, level + 1)
        return out

    output = subprocess.check_output(["ps", "-o", "pid,ppid", "-ax"])
    ps_cache = {}
    out_tree = []
    for line in output.decode().splitlines():
        pid, ppid = line.split()
        if ppid not in ps_cache:
            ps_cache[ppid] = [pid]
        else:
            ps_cache[ppid].append(pid)
    if root_pid not in ps_cache:
        return out_tree
    out_tree = print_children(root_pid, ps_cache, this_pid)
    return out_tree
