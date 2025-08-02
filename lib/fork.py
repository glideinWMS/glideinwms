# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements functions and classes to handle forking of processes and the collection of results."""

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


################################################
# Low level fork and collect functions


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
        dict: Dictionary with {'r': fd, 'pid': pid} where fd is the stdout from a pipe.
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
            # Exit, immediately. Don't want any cleanup, since I was created just for performing the work
            os._exit(0)
    else:
        register_sighandler()
        os.close(w)

    return {"r": r, "pid": pid}


def fetch_fork_result(r, pid):
    """Used with fork clients to retrieve results.

    Can raise OSError and FetchError.
    Other errors can come from `os.read` and `pickle.load` (but are caught here):
      - EOFError if the forked process failed and nothing was written to the pipe, if cPickle finds an empty string.
      - IOError failure for I/O-related reason, e.g., "pipe file not found" or "disk full".
      - OSError other system-related error (includes both former OSError and IOError since Py3.4).
      - pickle.UnpicklingError incomplete pickled data.

    Args:
        r (int): Input pipe.
        pid (int): PID of the child.

    Returns:
        object: Unpickled object.

    Raises:
        FetchError: If an `os.read` error was encountered or if the forked process failed.
        OSError: If Bad file descriptor or file already closed or if waitpid syscall returns -1.
        EOFError: If the forked process failed and nothing was written to the pipe, if cPickle finds an empty string.
        IOError: Failure for I/O-related reason, E.g., "pipe file not found" or "disk full".
        OSError: Other system-related error (includes both former OSError and IOError since Py3.4).
        pickle.UnpicklingError: Incomplete pickled data.
    """
    r_in = b""
    out = None
    try:
        s = os.read(r, 1024 * 1024)
        while s != b"":  # "" means EOF
            r_in += s
            s = os.read(r, 1024 * 1024)
        # pickle can fail w/ EOFError if r_in is empty.
        # Any output from pickle is never an empty string, e.g. None is 'N.'
        out = pickle.loads(r_in)
    except (OSError, EOFError, pickle.UnpicklingError) as err:
        etype, evalue, etraceback = sys.exc_info()
        # Adding message in case close/waitpid fail and preempt raise
        logSupport.log.exception(f"Re-raising exception during read: {err}")
        # Removed .with_traceback(etraceback) since already in the chaining
        raise FetchError(
            f"Exception during read probably due to worker failure, original exception and trace {etype}: {evalue}"
        ) from err
    finally:
        os.close(r)
        os.waitpid(pid, 0)
    return out


def fetch_fork_result_list(pipe_ids):
    """Read the output pipe of the children, used after forking to perform work and after forking to entry.writeStats().

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
            # Collect the results
            out[key] = fetch_fork_result(pipe_ids[key]["r"], pipe_ids[key]["pid"])
        except (KeyError, OSError, FetchError) as err:
            # fetch_fork_result can raise OSError and FetchError
            errmsg = f"Failed to extract info from child '{key}': {err}"
            logSupport.log.warning(errmsg)
            logSupport.log.exception(errmsg)
            # Record failed keys
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
    # Timeout for epoll/poll in milliseconds: -1 is blocking, 0 non blocking, >0 timeout
    # Select timeout (in seconds) = POLL_TIMEOUT/1000.0
    # Waiting at most POLL_TIMEOUT for one event to be triggered.
    # If there are no ready fd by the timeout and empty list is returned (no exception triggered)
    #
    # From the linux kernel (v4.10) and man (http://man7.org/linux/man-pages/man2/select.2.html)
    # these are the 3 sets of poll events that correspond to select read, write, error:
    # define POLLIN_SET (POLLRDNORM | POLLRDBAND | POLLIN | POLLHUP | POLLERR)
    # define POLLOUT_SET (POLLWRBAND | POLLWRNORM | POLLOUT | POLLERR)
    # define POLLEX_SET (POLLPRI)
    # To maintain a similar behavior to check readable fd in select we should check for. Anyway Python documentation
    # lists different events for poll (no POLLRDBAND, ... ), but looking at the library they are there... dir(select),
    # but should not be triggered or different, so the complete enough and safe option seems:
    #  poll_obj.register(read_fd, select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR | select.EPOLLRDBAND | select.EPOLLRDNORM)
    #  poll_obj.register(read_fd, select.POLLIN | select.POLLHUP | select.POLLERR )
    # TODO: this may be revised to use select that seems more performant and able to support >1024: https://aivarsk.github.io/2017/04/06/select/

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
        # epoll tested fastest, and supports > 1024 open fds
        # unfortunately linux only
        # Level Trigger behavior (default)
        poll_obj = select.epoll()
        poll_type = "epoll"
        for read_fd in list(fds_to_entry.keys()):
            try:
                poll_obj.register(
                    read_fd,
                    select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR | select.EPOLLRDBAND | select.EPOLLRDNORM,
                )
            except OSError as err:
                # Epoll (contrary to poll) complains about duplicate registrations:  IOError: [Errno 17] File exists
                # All other errors are re-risen
                if err.errno == errno.EEXIST:
                    logSupport.log.warning(f"Ignoring duplicate fd {read_fd} registration in epoll(): '{err}'")
                else:
                    logSupport.log.warning(f"Unsupported fd {read_fd} registration failure in epoll(): '{err}'")
                    raise
        # File descriptors: [i[0] for i in poll_obj.poll(0) if i[1] & (select.EPOLLIN|select.EPOLLPRI)]
        # Filtering is not needed, done by epoll, both EPOLLIN and EPOLLPRI are OK
        # EPOLLHUP events are registered by default. The consumer will read eventual data and close the fd
        readable_fds = [i[0] for i in poll_obj.poll(POLL_TIMEOUT)]
    except (AttributeError, OSError) as err:
        logSupport.log.warning(f"Failed to load select.epoll(): {err}")
        try:
            # no epoll(), try poll(). Still supports > 1024 fds and
            # tested faster than select() on linux when multiple forks configured
            poll_obj = select.poll()
            poll_type = "poll"
            for read_fd in list(fds_to_entry.keys()):
                poll_obj.register(read_fd, select.POLLIN | select.POLLHUP | select.POLLERR)
            readable_fds = [i[0] for i in poll_obj.poll(POLL_TIMEOUT)]
        except (AttributeError, OSError) as err:
            logSupport.log.warning(f"Failed to load select.poll(): {err}")
            # no epoll() or poll(), use select()
            readable_fds = select.select(list(fds_to_entry.keys()), [], [], POLL_TIMEOUT / 1000.0)[0]
            poll_type = "select"

    count = 0
    # logSupport.log.debug("Data available via %s, fd list: %s" % (poll_type, readable_fds))
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
                    poll_obj.unregister(fd)  # Is this needed? Lots of hoops to jump through here
            except OSError as err:
                if err.errno != 9:
                    # Ignore OSError with errno == 9
                    # python.select < 3.9 treated unregister on  closed pipe as NO_OP
                    # python 3.9 + raises OSError: [Errno 9] Bad file descriptor
                    # we don't care about this for now, continue processing fd's
                    # Some other OSError, log and raise
                    errmsg = f"unregister failed pid='{pid}' fd='{fd}' key='{key}': {err}"
                    logSupport.log.warning(errmsg)
                    logSupport.log.exception(errmsg)
                    raise
            work_info[key] = out
            count += 1
        except (OSError, ValueError, KeyError, FetchError) as err:
            # KeyError: inconsistent dictionary or reverse dictionary
            # IOError: Error in poll_obj.unregister()
            # OSError: [Errno 9] Bad file descriptor - fetch_fork_result with wrong file descriptor
            # FetchError: read error in fetch_fork_result
            errmsg = f"Failed to extract info from child '{key}': {err}"
            logSupport.log.warning(errmsg)
            logSupport.log.exception(errmsg)
            # Record failed keys
            failed.append(key)
            failures += 1

    if failures > 0:
        raise ForkResultError(failures, work_info, failed=failed)

    if time_this:
        logSupport.log.debug(
            "%s: using %s fetched %s of %s in %s seconds"
            % ("fetch_ready_fork_result_list", poll_type, count, len(fds_to_entry), time.time() - t_begin)
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
            # empty the read buffer first
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
        # Needs a separate list to keep the order
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

        # Try to fork all the functions
        for key in self.key_list:
            # Check if we can fork more
            if forks_remaining == 0:
                if log_progress:
                    # Log here, since we will have to wait
                    logSupport.log.info(f"Active forks = {max_forks}, Forks to finish = {functions_remaining}")
            while forks_remaining == 0:
                failed_keys = []
                # Give some time for the processes to finish the work
                # logSupport.log.debug("Reached parallel_workers limit of %s" % parallel_workers)
                time.sleep(sleep_time)

                # Wait and gather results for work done so far before forking more
                try:
                    # logSupport.log.debug("Checking finished workers")
                    post_work_info_subset = fetch_ready_fork_result_list(pipe_ids)
                except ForkResultError as e:
                    # Collect the partial result
                    post_work_info_subset = e.good_results
                    # Expect all errors logged already, just count
                    nr_errors += e.nr_errors
                    functions_remaining -= e.nr_errors
                    failed_keys = e.failed

                post_work_info.update(post_work_info_subset)
                forks_remaining += len(post_work_info_subset)
                functions_remaining -= len(post_work_info_subset)

                for i in list(post_work_info_subset.keys()) + failed_keys:
                    if pipe_ids.get(i):
                        del pipe_ids[i]
                # end for
            # end while

            # Yes, we can fork, do it
            pipe_ids[key] = fork_in_bg(*self.functions_tofork[key])
            forks_remaining -= 1
        # end for

        if log_progress:
            logSupport.log.info(
                f"Active forks = {max_forks - forks_remaining}, Forks to finish = {functions_remaining}"
            )

        # now we just have to wait for all to finish
        while functions_remaining > 0:
            failed_keys = []
            # Give some time for the processes to finish the work
            time.sleep(sleep_time)
            # Wait and gather results for work done so far before forking more
            try:
                # logSupport.log.debug("Checking finished workers")
                post_work_info_subset = fetch_ready_fork_result_list(pipe_ids)
            except ForkResultError as e:
                # Collect the partial result
                post_work_info_subset = e.good_results
                # Expect all errors logged already, just count
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
        # end while

        if nr_errors > 0:
            raise ForkResultError(nr_errors, post_work_info)

        return post_work_info


####################
# Utilities
def print_child_processes(root_pid=str(os.getppid()), this_pid=str(os.getpid())):
    """Print the process tree of the root PID.

    Args:
        root_pid (str, optional): String containing the process ID to use as root of the process tree.
                                  Defaults to the current process.
        this_pid (str, optional): String containing the process ID of the current process (will get a star in the line).
                                  Defaults to the current process.

    Returns:
        list: List of str containing all the lines of the process tree.
    """

    def print_children(id, ps_dict, my_id="", level=0):
        """Auxiliary recursive sub-function to print the children subtree of a given process ID.

        Args:
            id (str): String with process ID root of the tree.
            ps_dict (dict): Dictionary with all processes and their children.
            my_id (str, optional): String with process ID of the print_children caller. Defaults to "".
            level (int, optional): Level of the subtree. Defaults to 0.

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
