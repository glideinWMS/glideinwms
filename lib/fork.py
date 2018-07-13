from __future__ import absolute_import
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements functions and classes
#   to handle forking of processes
#   and the collection of results
#
# Author:
#   Burt Holzman and Igor Sfiligoi
#
# TODO: This could be rewritten so that the polling lists are registered once and the fd are removed only when
#       not needed anymore (currently there is an extrnal structure and the poll object is a new one each time)
import cPickle
import os
#import sys
import time
import select
import errno
from .pidSupport import register_sighandler, unregister_sighandler, termsignal
from . import logSupport


class ForkResultError(RuntimeError):
    def __init__(self, nr_errors, good_results, failed=[]):
        RuntimeError.__init__(self, "Found %i errors" % nr_errors)
        self.nr_errors = nr_errors
        self.good_results = good_results
        self.failed = failed


################################################
# Low level fork and collect functions

def fork_in_bg(function_torun, *args):
    # fork and call a function with args
    #  return a dict with {'r': fd, 'pid': pid} where fd is the stdout from a pipe.
    #    example:
    #      def add(i, j): return i+j
    #      d = fork_in_bg(add, i, j)

    r, w = os.pipe()
    unregister_sighandler()
    pid = os.fork()
    if pid == 0:
        logSupport.disable_rotate = True
        os.close(r)
        try:
            out = function_torun(*args)
            os.write(w, cPickle.dumps(out))
        except:
            logSupport.log.warning("Forked process '%s' failed" % str(function_torun))
            logSupport.log.exception("Forked process '%s' failed" % str(function_torun))
        finally:
            os.close(w)
            # Exit, immediately. Don't want any cleanup, since I was created
            # just for performing the work
            os._exit(0)
    else:
        register_sighandler()
        os.close(w)

    return {'r': r, 'pid': pid}


###############################
def fetch_fork_result(r, pid):
    """
    Used with fork clients
    Can raise OSError if Bad file descriptor or file already closed

    @type r: pipe
    @param r: Input pipe

    @type pid: int
    @param pid: pid of the child

    @rtype: Object
    @return: Unpickled object
    """

    rin = ""
    try:
        s = os.read(r, 1024*1024)
        while s != "":  # "" means EOF
            rin += s
            s = os.read(r, 1024*1024)
    except IOError as err:
        logSupport.log.debug('exception %s' % err)
        logSupport.log.exception('exception %s' % err)
    finally:
        os.close(r)
        os.waitpid(pid, 0)
    out = cPickle.loads(rin)
    return out


def fetch_fork_result_list(pipe_ids):
    """
    Read the output pipe of the children, used after forking to perform work
    and after forking to entry.writeStats()
 
    @type pipe_ids: dict
    @param pipe_ids: Dictinary of pipe and pid 

    @rtype: dict
    @return: Dictionary of fork_results
    """

    out = {}
    failures = 0
    failed = []
    for key in pipe_ids:
        try:
            # Collect the results
            out[key] = fetch_fork_result(pipe_ids[key]['r'],
                                         pipe_ids[key]['pid'])
        except (IOError, KeyError, OSError) as err:
            errmsg = "Failed to extract info from child '%s' %s" % (str(key), err)
            logSupport.log.warning(errmsg)
            logSupport.log.exception(errmsg)
            # Record failed keys
            failed.append(key)
            failures += 1

    if failures > 0:
        raise ForkResultError(failures, out, failed=failed)

    return out


def fetch_ready_fork_result_list(pipe_ids):
    """
    Read the output pipe of the children, used after forking. If there is data
    on the pipes to consume, read the data and close the pipe.
    and after forking to entry.writeStats()

    @type pipe_ids: dict
    @param pipe_ids: Dictinary of pipe and pid

    @rtype: dict
    @return: Dictionary of work_done
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
    fds_to_entry = dict((pipe_ids[x]['r'], x) for x in pipe_ids)
    poll_obj = None
    time_this = False
    if time_this:
        t_begin = time.time()
    try:
        # epoll tested fastest, and supports > 1024 open fds
        # unfortunately linux only
        # Level Trigger behavior (default)
        poll_obj = select.epoll()
        poll_type = "epoll"
        for read_fd in fds_to_entry.keys():
            try:
                poll_obj.register(read_fd, select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR | select.EPOLLRDBAND | select.EPOLLRDNORM)
            except IOError as err:
                # Epoll (contrary to poll) complains about duplicate registrations:  IOError: [Errno 17] File exists
                # All other errors are re-risen
                if err.errno == errno.EEXIST:
                    logSupport.log.warning("Ignoring duplicate fd %s registration in epoll(): '%s'" %
                                           (read_fd, str(err)))
                else:
                    logSupport.log.warning("Unsupported fd %s registration failure in epoll(): '%s'" %
                                           (read_fd, str(err)))
                    raise
        # File descriptors: [i[0] for i in poll_obj.poll(0) if i[1] & (select.EPOLLIN|select.EPOLLPRI)]
        # Filtering is not needed, done by epoll, both EPOLLIN and EPOLLPRI are OK
        # EPOLLHUP events are registered by default. The consumer will read eventual data and close the fd
        readable_fds = [i[0] for i in poll_obj.poll(POLL_TIMEOUT)]
    except (AttributeError, IOError) as err:
        logSupport.log.warning("Failed to load select.epoll() '%s'" % str(err))
        try:
            # no epoll(), try poll(). Still supports > 1024 fds and
            # tested faster than select() on linux when multiple forks configured
            poll_obj = select.poll()
            poll_type = "poll"
            for read_fd in fds_to_entry.keys():
                poll_obj.register(read_fd, select.POLLIN | select.POLLHUP | select.POLLERR)
            readable_fds = [i[0] for i in poll_obj.poll(POLL_TIMEOUT)]
        except (AttributeError, IOError) as err:
            logSupport.log.warning("Failed to load select.poll() '%s'" % str(err))
            # no epoll() or poll(), use select()
            readable_fds = select.select(fds_to_entry.keys(), [], [], POLL_TIMEOUT/1000.0)[0]
            poll_type = "select"

    count = 0
    # logSupport.log.debug("Data available via %s, fd list: %s" % (poll_type, readable_fds))
    for fd in readable_fds:
        if fd not in fds_to_entry:
            continue
        try:
            key = fds_to_entry[fd]
            pid = pipe_ids[key]['pid']
            out = fetch_fork_result(fd, pid)
            if poll_obj:
                poll_obj.unregister(fd)  # Is this needed? the poll object is no more used, next time will be a new one
            work_info[key] = out
            count += 1
        except (IOError, ValueError, KeyError, OSError) as err:
            # KeyError: inconsistent dictionary or reverse dictionary
            # IOError: Error in poll_obj.unregister()
            # OSError: [Errno 9] Bad file descriptor - fetch_fork_result with wrong file descriptor
            errmsg = ("Failed to extract info from child '%s': %s" % (str(key), err))
            logSupport.log.warning(errmsg)
            logSupport.log.exception(errmsg)
            # Record failed keys
            failed.append(key)
            failures += 1

    if failures > 0:
        raise ForkResultError(failures, work_info, failed=failed)
    
    if time_this:
        logSupport.log.debug("%s: using %s fetched %s of %s in %s seconds" %
            ('fetch_ready_fork_result_list', poll_type, count, len(fds_to_entry.keys()), time.time()-t_begin))

    return work_info


def wait_for_pids(pid_list):
    """
    Wait for all pids to finish.
    Throw away any stdout or err
    """
    for pidel in pid_list:
        pid = pidel['pid']
        r = pidel['r']
        try:
            # empty the read buffer first
            s = os.read(r, 1024)
            while s != "":  # "" means EOF
                s = os.read(r, 1024)
        finally:
            os.close(r)
            os.waitpid(pid, 0)


################################################
# Fork Class

class ForkManager:
    def __init__(self):
        self.functions_tofork = {}
        # I need a separate list to keep the order
        self.key_list = []
        return

    def __len__(self):
        return len(self.functions_tofork)

    def add_fork(self, key, function, *args):
        if key in self.functions_tofork:
            raise KeyError("Fork key '%s' already in use" % key)
        self.functions_tofork[key] = ((function, ) + args)
        self.key_list.append(key)

    def fork_and_wait(self):
        pids = []
        for key in self.key_list:
            pids.append(fork_in_bg(*self.functions_tofork[key]))
        wait_for_pids(pids)

    def fork_and_collect(self):
        pipe_ids = {}
        for key in self.key_list:
            logSupport.profiler("FORK Key = %s" % (key))
            pipe_ids[key] = fork_in_bg(*self.functions_tofork[key])
        results = fetch_fork_result_list(pipe_ids)
        logSupport.profielr("FORK PIP_IDS = %s" % (pipe_ids))
        return results

    def bounded_fork_and_collect(self, max_forks, log_progress=True, sleep_time=0.01):

        post_work_info = {}
        nr_errors = 0

        pipe_ids = {}
        forks_remaining = max_forks
        functions_remaining = len(self.functions_tofork)

        # try to fork all the functions
        for key in self.key_list:
            # Check if we can fork more
            if (forks_remaining == 0):
                if log_progress:
                    # log here, since we will have to wait
                    logSupport.log.info("Active forks = %i, Forks to finish = %i"%(max_forks, functions_remaining))
            while (forks_remaining == 0):
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

                for i in (post_work_info_subset.keys() + failed_keys):
                    if pipe_ids.get(i):
                        del pipe_ids[i]
                # end for
            # end while

            # yes, we can, do it
            pipe_ids[key] = fork_in_bg(*self.functions_tofork[key])
            forks_remaining -= 1
        # end for

        if log_progress:
            logSupport.log.info("Active forks = %i, Forks to finish = %i" % (max_forks-forks_remaining, functions_remaining))

        # now we just have to wait for all to finish
        while (functions_remaining>0):
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

            for i in (post_work_info_subset.keys() + failed_keys):
                del pipe_ids[i]

            if len(post_work_info_subset)>0:
                if log_progress:
                    logSupport.log.info("Active forks = %i, Forks to finish = %i" % (max_forks-forks_remaining, functions_remaining))
        # end while

        if nr_errors>0:
            raise ForkResultError(nr_errors, post_work_info)

        return post_work_info
