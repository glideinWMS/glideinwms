#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements methods
#   to handle forking of processes
#   and the collection of results
#
# Author:
#   Burt Holzman and Igor Sfiligoi
#
import cPickle
import os
import signal
from pidSupport import register_sighandler, unregister_sighandler, termsignal
import logSupport

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
        os.close(r)
        try:
            out = function(*args)
            os.write(w, cPickle.dumps(out))
        finally:
            os.close(w)
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
    for key in pipe_ids:
        try:
            # Collect the results
            out[key] = fetch_fork_result(pipe_ids[key]['r'],
                                         pipe_ids[key]['pid'])
        except Exception, e:
            logSupport.log.warning("Failed to extract info from child '%s'" % key)
            logSupport.log.exception("Failed to extract info from child '%s'" % key)
            failures += 1

    if failures>0:
        raise RuntimeError, "Found %i errors" % failures

    return out

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
         
