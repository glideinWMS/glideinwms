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
import cPickle
import os
import time
import select
from pidSupport import register_sighandler, unregister_sighandler, termsignal
import logSupport

class ForkResultError(RuntimeError):
    def __init__(self, nr_errors, good_results, failed=[]):
        RuntimeError.__init__(self, "Found %i errors" % nr_errors)
        self.nr_errors = nr_errors
        self.good_results = good_results
        self.failed = failed

################################################
# Low level fork and collect functions

def fork_in_bg(function, *args):
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
            out = function(*args)
            os.write(w, cPickle.dumps(out))
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

    @type r: pipe
    @param r: Input pipe

    @type pid: int
    @param pid: pid of the child

    @rtype: Object
    @return: Unpickled object
    """

    try:
        rin = ""
        s = os.read(r, 1024*1024)
        while (s != ""): # "" means EOF
            rin += s
            s = os.read(r,1024*1024)
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
        except Exception, e:
            logSupport.log.warning("Failed to extract info from child '%s'" % key)
            logSupport.log.exception("Failed to extract info from child '%s'" % key)
            # Record failed keys
            failed.append(key)
            failures += 1

    if failures>0:
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

    work_info = {}
    failures = 0
    failed = []
    fds_to_entry = dict((pipe_ids[x]['r'], x) for x in pipe_ids)

    readable_fds = select.select(fds_to_entry.keys(), [], [], 0)[0]
    for fd in readable_fds:
        try:
            key = fds_to_entry[fd]
            pid = pipe_ids[key]['pid']
            out = fetch_fork_result(fd, pid)
            work_info[key] = out
        except Exception, e:
            logSupport.log.warning("Failed to extract info from child '%s'" % key)
            logSupport.log.exception("Failed to extract info from child '%s'" % key)
            # Record failed keys
            failed.append(key)
            failures += 1

    if failures>0:
        raise ForkResultError(failures, work_info, failed=failed)

    return work_info

def wait_for_pids(pid_list):
    """
    Wait for all pids to finish.
    Throw away any stdout or err
    """
    for pidel in pid_list:
       pid=pidel['pid']
       r=pidel['r']
       try:
          #empty the read buffer first
          s=os.read(r,1024)
          while (s!=""): # "" means EOF
             s=os.read(r,1024) 
       finally:
          os.close(r)
          os.waitpid(pid,0)
         
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
               raise KeyError("Fork key '%s' already in use"%key)
          self.functions_tofork[key] = ( (function, ) + args)
          self.key_list.append(key)

     def fork_and_wait(self):
          pids=[]
          for key in self.key_list:
               pids.append(fork_in_bg(*self.functions_tofork[key]))
          wait_for_pids(pids)

     def fork_and_collect(self):
          pipe_ids = {}
          for key in self.key_list:
               pipe_ids[key] = fork_in_bg(*self.functions_tofork[key])
          results = fetch_fork_result_list(pipe_ids)
          return results

     def bounded_fork_and_collect(self, max_forks,
                                  log_progress=True, sleep_time=0.01):

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
                       logSupport.log.info("Active forks = %i, Forks to finish = %i"%(max_forks,functions_remaining))
             while (forks_remaining == 0):
                 failed_keys = []
                 # Give some time for the processes to finish the work
                 # logSupport.log.debug("Reached parallel_workers limit of %s" % parallel_workers)
                 time.sleep(sleep_time)

                 # Wait and gather results for work done so far before forking more
                 try:
                     # logSupport.log.debug("Checking finished workers")
                     post_work_info_subset = fetch_ready_fork_result_list(pipe_ids)
                 except ForkResultError, e:
                     # Collect the partial result
                     post_work_info_subset = e.good_results
                     # Expect all errors logged already, just count
                     nr_errors += e.nr_errors
                     functions_remaining -= e.nr_errors
                     failed_keys = e.failed

                     # free up a slot from the crashed child
                     forks_remaining += e.nr_errors

                 post_work_info.update(post_work_info_subset)
                 forks_remaining += len(post_work_info_subset)
                 functions_remaining -= len(post_work_info_subset)

                 for i in (post_work_info_subset.keys() + failed_keys):
                     del pipe_ids[i]
                 #end for
             #end while

             # yes, we can, do it
             pipe_ids[key] = fork_in_bg(*self.functions_tofork[key])
             forks_remaining -= 1
         #end for

         if log_progress:
              logSupport.log.info("Active forks = %i, Forks to finish = %i"%(max_forks-forks_remaining,functions_remaining))
         
         # now we just have to wait for all to finish
         while (functions_remaining>0):
            failed_keys = []
            # Give some time for the processes to finish the work
            time.sleep(sleep_time)

            # Wait and gather results for work done so far before forking more
            try:
                # logSupport.log.debug("Checking finished workers")
                post_work_info_subset = fetch_ready_fork_result_list(pipe_ids)
            except ForkResultError, e:
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
                      logSupport.log.info("Active forks = %i, Forks to finish = %i"%(max_forks-forks_remaining,functions_remaining))
         #end while
          
         if nr_errors>0:
              raise ForkResultError(nr_errors, post_work_info)

         return post_work_info
