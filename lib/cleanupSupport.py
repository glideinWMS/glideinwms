from __future__ import absolute_import
import os
import stat
import time
import re
import pwd
from . import logSupport
from .pidSupport import register_sighandler, unregister_sighandler

MY_USERNAME = pwd.getpwuid(os.getuid())[0]

class Cleanup:
    def __init__(self):
        self.cleanup_objects = []
        self.cleanup_pids = []

    def add_cleaner(self, cleaner):
        self.cleanup_objects.append(cleaner)

    def start_background_cleanup(self):
        if self.cleanup_pids:
            logSupport.log.warning("Earlier cleanup PIDs %s still exist; skipping this cycle" %
                                   self.cleanup_pids)
        else:
            num_forks = 4 # arbitrary - could be configurable
            cleanup_lists = [self.cleanup_objects[x::num_forks] for x in xrange(num_forks)]
            for i in xrange(num_forks):
                unregister_sighandler()
                cl_pid = os.fork()
                if cl_pid != 0:
                    register_sighandler()
                    self.cleanup_pids.append(cl_pid)
                else:
                    for cleaner in cleanup_lists[i]:
                        cleaner.cleanup()
                    os._exit(0)
            logSupport.log.debug("Forked cleanup PIDS %s" % self.cleanup_pids)
            del cleanup_lists

    def wait_for_cleanup(self):
        for pid in self.cleanup_pids:
            try:
                return_pid, _ = os.waitpid(pid, os.WNOHANG)
                if return_pid:
                    logSupport.log.debug("Collected cleanup PID %s" % pid)
                    self.cleanup_pids.remove(pid)
            except OSError as e:
                self.cleanup_pids.remove(pid)
                logSupport.log.warning("Received error %s while waiting for PID %s" %
                                       (e.strerror, pid))

    def cleanup(self):
        # foreground cleanup
        for cleaner in self.cleanup_objects:
            cleaner.cleanup()

cleaners = Cleanup()

class CredCleanup(Cleanup):
    """
    Cleans up old credential files.
    """
            
    def cleanup(self, in_use_proxies):
        for cleaner in self.cleanup_objects:
            cleaner.cleanup(in_use_proxies)
            
cred_cleaners = CredCleanup()

# this class is used for cleanup
class DirCleanup:
    def __init__(self, dirname, fname_expression, # regular expression, used with re.match
                 maxlife, should_log=True, should_log_warnings=True):
        self.dirname = dirname
        self.fname_expression = fname_expression
        self.fname_expression_obj = re.compile(fname_expression)
        self.maxlife = maxlife
        self.should_log = should_log
        self.should_log_warnings = should_log_warnings

    def cleanup(self):
        count_removes = 0

        treshold_time = time.time() - self.maxlife
        files_wstats = self.get_files_wstats()

        for fpath in files_wstats.keys():
            fstat = files_wstats[fpath]

            update_time = fstat[stat.ST_MTIME]
            if update_time < treshold_time:
                try:
                    self.delete_file(fpath)
                    count_removes += 1
                except:
                    if self.should_log_warnings:
                        logSupport.log.warning("Could not remove %s" % fpath)

        if count_removes > 0:
            if self.should_log:
                logSupport.log.info("Removed %i files." % count_removes)

    # INTERNAL
    # return a dictionary of fpaths each having the os.lstat output
    def get_files_wstats(self):
        out_data = {}

        fnames = os.listdir(self.dirname)
        for fname in fnames:
            if self.fname_expression_obj.match(fname) is None:
                continue # ignore files that do not match

            fpath = os.path.join(self.dirname, fname)
            fstat = os.lstat(fpath)
            fmode = fstat[stat.ST_MODE]
            isdir = stat.S_ISDIR(fmode)
            if isdir:
                continue #ignore directories
            out_data[fpath] = fstat

        return out_data

    # this may reimplemented by the children
    def delete_file(self, fpath):
        os.unlink(fpath)

# this class is used for cleanup
class DirCleanupWSpace(DirCleanup):
    def __init__(self, dirname, fname_expression, # regular expression, used with re.match
                 maxlife, # max lifetime after which it is deleted
                 minlife, maxspace, # max space allowed for the sum of files, unless they are too young
                 should_log=True, should_log_warnings=True):
        DirCleanup.__init__(self, dirname, fname_expression, maxlife, should_log, should_log_warnings)
        self.minlife = minlife
        self.maxspace = maxspace

    def cleanup(self):
        count_removes = 0
        count_removes_bytes = 0

        min_treshold_time = time.time() - self.minlife
        treshold_time = time.time() - self.maxlife

        files_wstats = self.get_files_wstats()
        fpaths = files_wstats.keys()
        # order based on time (older first)
        fpaths.sort(lambda i, j:cmp(files_wstats[i][stat.ST_MTIME], files_wstats[j][stat.ST_MTIME]))

        # first calc the amount of space currently used
        used_space = 0
        for fpath in fpaths:
            fstat = files_wstats[fpath]
            fsize = fstat[stat.ST_SIZE]
            used_space += fsize

        for fpath in fpaths:
            fstat = files_wstats[fpath]

            update_time = fstat[stat.ST_MTIME]
            fsize = fstat[stat.ST_SIZE]

            if ((update_time < treshold_time) or
                ((update_time < min_treshold_time) and (used_space > self.maxspace))):
                try:
                    os.unlink(fpath)
                    count_removes += 1
                    count_removes_bytes += fsize
                    used_space -= fsize
                except:
                    if self.should_log_warnings:
                        logSupport.log.warning("Could not remove %s" % fpath)

        if count_removes > 0:
            if self.should_log:
                logSupport.log.info("Removed %i files for %.2fMB." % (count_removes, count_removes_bytes / (1024.0 * 1024.0)))



class DirCleanupCredentials(DirCleanup):
    """
    Used to cleanup old credential files saved to disk by the factory for glidein submission (based on ctime).
    """
    def __init__(self,
                 dirname,
                 fname_expression, # regular expression, used with re.match
                 maxlife): # max lifetime after which it is deleted
        DirCleanup.__init__(self, dirname, fname_expression, maxlife, should_log=True, should_log_warnings=True)
        
    def cleanup(self, in_use_creds):
        count_removes = 0
        curr_time = time.time()

        threshold_time = curr_time - self.maxlife

        files_wstats = self.get_files_wstats()
        fpaths = files_wstats.keys()

        for fpath in fpaths:            
            fstat = files_wstats[fpath]
            last_access_time = fstat[stat.ST_MTIME]

            if last_access_time < threshold_time and fpath not in in_use_creds:
                try:
                    os.unlink(fpath)
                    count_removes += 1
                except:
                    logSupport.log.warning("Could not remove credential %s" % fpath)

        if count_removes > 0:
            logSupport.log.info("Removed %i credential files." % count_removes)
        else:            
            logSupport.log.info("No old credential files were removed.")
