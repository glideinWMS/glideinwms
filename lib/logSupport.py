#
# Project:
#   glideinWMS
#
# File Version:
#   $Id: logSupport.py,v 1.21.10.2.4.2 2011/04/20 14:30:44 tiradani Exp $
#
# Description: log support module
#
# Author:
#  Igor Sfiligoi (Oct 25th 2006)
#
import os
import os.path
import stat
import sys
import timeConversion
import time
import re
import logging
from logging import config
from logging.handlers import TimedRotatingFileHandler

# this class can be used instead of a file for writing
class DayLogFile:
    def __init__(self,base_fname,extension="log"):
        self.base_fname=base_fname
        self.extension=extension
        return

    def close(self):
        return # nothing to do, just a placeholder

    def write(self,msg):
        now=time.time()
        fname=self.get_fname(now)
        try:
            fd=open(fname,"a")
        except:
            self.write_on_exception("Cannot open %s"%fname,msg)
            raise
        try:
            try:
                fd.write(self.format_msg(now,msg)+"\n")
            except:
                self.write_on_exception("Cannot open %s"%fname,msg)
                raise
        finally:
            fd.close()

        return

    ##########################
    # these can be customized
    ##########################

    def write_on_exception(self,exception_msg,msg):
        print "%s: %s" % (exception_msg,msg)
        return

    def get_fname(self,timestamp):
        return "%s.%s.%s"%(self.base_fname,time.strftime("%Y%m%d",time.localtime(timestamp)),self.extension)

    def format_msg(self,timestamp,msg):
        return "[%s %s] %s"%(self.format_time(timestamp),os.getpid(),msg)

    def format_time(self,timestamp):
        return timeConversion.getISO8601_Local(timestamp)

# this class is used for cleanup
class DirCleanup:
    def __init__(self,
                 dirname,
                 fname_expression, # regular expression, used with re.match
                 maxlife,
                 activity_log,warning_log): # if None, no logging
        self.dirname=dirname
        self.fname_expression=fname_expression
        self.fname_expression_obj=re.compile(fname_expression)
        self.maxlife=maxlife
        self.activity_log=activity_log
        self.warning_log=warning_log
        return

    def cleanup(self):
        count_removes=0

        treshold_time=time.time()-self.maxlife
        files_wstats=self.get_files_wstats()

        for fpath in files_wstats.keys():
            fstat=files_wstats[fpath]

            update_time=fstat[stat.ST_MTIME]
            if update_time<treshold_time:
                try:
                    self.delete_file(fpath)
                    count_removes+=1
                except:
                   if self.warning_log!=None:
                       self.warning_log.write("Could not remove %s"%fpath)

        if count_removes>0:
            if self.activity_log!=None:
                self.activity_log.write("Removed %i files."%count_removes)

        return

    # INTERNAL
    # return a dictionary of fpaths each havinf the os.lstat output
    def get_files_wstats(self):
        out_data={}

        fnames=os.listdir(self.dirname)
        for fname in fnames:
            if self.fname_expression_obj.match(fname)==None:
                continue # ignore files that do not match

            fpath=os.path.join(self.dirname,fname)
            fstat=os.lstat(fpath)
            fmode=fstat[stat.ST_MODE]
            isdir=stat.S_ISDIR(fmode)
            if isdir:
                continue #ignore directories
            out_data[fpath]=fstat

        return out_data

    # this may reimplemented by the children
    def delete_file(self,fpath):
        os.unlink(fpath)

# this class is used for cleanup
class DirCleanupWSpace(DirCleanup):
    def __init__(self,
                 dirname,
                 fname_expression, # regular expression, used with re.match
                 maxlife,          # max lifetime after which it is deleted
                 minlife,maxspace, # max space allowed for the sum of files, unless they are too young
                 activity_log,warning_log): # if None, no logging
        DirCleanup.__init__(self,dirname,fname_expression,maxlife,activity_log,warning_log)
        self.minlife=minlife
        self.maxspace=maxspace
        return

    def cleanup(self):
        count_removes=0
        count_removes_bytes=0L

        min_treshold_time=time.time()-self.minlife
        treshold_time=time.time()-self.maxlife

        files_wstats=self.get_files_wstats()
        fpaths=files_wstats.keys()
        # order based on time (older first)
        fpaths.sort(lambda i,j:cmp(files_wstats[i][stat.ST_MTIME],files_wstats[j][stat.ST_MTIME]))

        # first calc the amount of space currently used
        used_space=0L
        for fpath in fpaths:
            fstat=files_wstats[fpath]
            fsize=fstat[stat.ST_SIZE]
            used_space+=fsize

        for fpath in fpaths:
            fstat=files_wstats[fpath]

            update_time=fstat[stat.ST_MTIME]
            fsize=fstat[stat.ST_SIZE]

            if ((update_time<treshold_time) or
                ((update_time<min_treshold_time) and (used_space>self.maxspace))):
                try:
                    self.delete_file(fpath)
                    count_removes+=1
                    count_removes_bytes+=fsize
                    used_space-=fsize
                except:
                   if self.warning_log!=None:
                       self.warning_log.write("Could not remove %s"%fpath)

        if count_removes>0:
            if self.activity_log!=None:
                self.activity_log.write("Removed %i files for %.2fMB."%(count_removes,count_removes_bytes/(1024.0*1024.0)))
        return

# Adding in the capability to use the built in Python logging Module
# This will allow us to log anything, anywhere
#
# Note:  We may need to create a custom class later if we need to handle
#        logging with privilege separation

class GlideinHandler(TimedRotatingFileHandler):
    """
    Custom logging handler class for glideinWMS.  It combines the decision tree
    for log rotation from the TimedRotatingFileHandler with the decision tree
    from the RotatingFileHandler.  This allows us to specify a lifetime AND
    file size to determine when to rotate the file.

    This class assumes that the lifetime specified is in days. (24 hour periods)

    @type filename: string
    @ivar filename: Full path to the log file.  Includes file name.
    @type interval: int
    @ivar interval: Number of days to keep log file before rotating
    @type maxBytes: int
    @ivar maxBytes: Maximum file size before rotating the log file
    @type backupCount: int
    @ivar backupCount: How many backups to keep
    """
    def __init__(self, filename, interval=1, maxBytes=0, backupCount=0):
        """
        Initialize the Handler.  We assume the following:

            1. Interval is in days
            2. No special encoding
            3. No delays are set
            4. Timestamps are not in UTC

        @type filename: string
        @param filename: The full path of the log file
        @type interval: int
        @param interval: Number of days before file rotation
        @type maxBytes: int
        @param maxBytes: Maximum size of the logfile bytes before file rotatation
        @type backupCount: int
        @param backupCount: Number of backups to keep

        """
        when='D'
        TimedRotatingFileHandler.__init__(self, filename, when, interval, backupCount, encoding=None)
        self.maxBytes = maxBytes * 1024.0 * 1024.0

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, we are combining the checks for size and time interval

        @type record: string
        @param record: The message that will be logged.
        """
        do_timed_rollover = logging.handlers.TimedRotatingFileHandler.shouldRollover(self, record)
        do_size_rollover = 0
        if self.maxBytes > 0:                   # are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                do_size_rollover = 1

        return do_timed_rollover or do_size_rollover


def add_glideinlog_handler(logger_name, log_dir, maxDays, maxBytes, debug=False):
    """
    Setup python's built-in logging module.  This is designed to mimic the
    original logging in GlideinWMS, but allow logging in every module.

    In order to use this logging first import the logging module:

        C{import logging}

    Then get the logger by name:

        C{log = logging.getLogger(name)}

    finally:

        C{log.info("message")}

    @type logger_name: string
    @param logger_name: The name of the logger
    @type log_dir: string
    @param log_dir: The directory where the log files will be placed
    @type MaxDays: int
    @param MaxDays: Maximum age of the logfile in days before it will be rotated
    @type maxBytes: int
    @param maxBytes: Maximum size in bytes of the logfile before it will be rotated

    """
    log_conf_file = "%s/logging.conf" % os.path.join(sys.path[0], "../lib")
    config.fileConfig(log_conf_file)

    mylog = logging.getLogger(logger_name)

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s:  %(message)s')

    # Error Logger
    logfile = os.path.expandvars("%s/%s.err.log" % (log_dir, logger_name))
    handler = GlideinHandler(logfile, maxDays, maxBytes, backupCount=5)
    handler.setFormatter(formatter)
    handler.setLevel(logging.ERROR)
    mylog.addHandler(handler)

    # INFO Logger
    logfile = os.path.expandvars("%s/%s.info.log" % (log_dir, logger_name))
    handler = GlideinHandler(logfile, maxDays, maxBytes, backupCount=5)
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    mylog.addHandler(handler)

    # DEBUG Logger
    if debug:
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s:::%(module)s::%(lineno)d: %(message)s ')
        logfile = os.path.expandvars("%s/%s.debug.log" % (log_dir, logger_name))
        handler = GlideinHandler(logfile, maxDays, maxBytes, backupCount=5)
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        mylog.addHandler(handler)
