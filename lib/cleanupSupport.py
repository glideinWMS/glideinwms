import os
import os.path
import stat
import sys
import timeConversion
import time
import re
import logging


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
    # return a dictionary of fpaths each havinf the os.lstat output
    def get_files_wstats(self):
        out_data = {}

        fnames = os.listdir(self.dirname)
        for fname in fnames:
            if self.fname_expression_obj.match(fname) == None:
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
                 maxlife,          # max lifetime after which it is deleted
                 minlife, maxspace, # max space allowed for the sum of files, unless they are too young
                 should_log=True, should_log_warnings=True):
        DirCleanup.__init__(self, dirname, fname_expression, maxlife, should_log, should_log_warnings)
        self.minlife = minlife
        self.maxspace = maxspace

    def cleanup(self):
        count_removes = 0
        count_removes_bytes = 0L

        min_treshold_time = time.time() - self.minlife
        treshold_time = time.time() - self.maxlife

        files_wstats = self.get_files_wstats()
        fpaths = files_wstats.keys()
        # order based on time (older first)
        fpaths.sort(lambda i, j:cmp(files_wstats[i][stat.ST_MTIME], files_wstats[j][stat.ST_MTIME]))

        # first calc the amount of space currently used
        used_space = 0L
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
                    self.delete_file(fpath)
                    count_removes += 1
                    count_removes_bytes += fsize
                    used_space -= fsize
                except:
                   if self.should_log_warnings:
                       logSupport.log.warning("Could not remove %s" % fpath)

        if count_removes > 0:
            if self.should_log:
                logSupport.log.info("Removed %i files for %.2fMB." % (count_removes, count_removes_bytes / (1024.0 * 1024.0)))

class PrivsepDirCleanupWSpace(DirCleanupWSpace):
    def __init__(self,
                 username,         # if None, no privsep
                 dirname,
                 fname_expression, # regular expression, used with re.match
                 maxlife,          # max lifetime after which it is deleted
                 minlife,maxspace, # max space allowed for the sum of files, unless they are too young
                 should_log=True, should_log_warnings=True):
        logSupport.DirCleanupWSpace.__init__(self, dirname, fname_expression,
                                             maxlife, minlife, maxspace,
                                             should_log=True, should_log_warnings=True)
        self.username = username

    def delete_file(self, fpath):
        if (self.username != None) and (self.username != MY_USERNAME):
            # use privsep
            # do not use rmtree as we do not want root privileges
            condorPrivsep.execute(self.username, os.path.dirname(fpath), '/bin/rm', ['rm', fpath], stdout_fname=None)
        else:
            # use the native method, if possible
            os.unlink(fpath)

