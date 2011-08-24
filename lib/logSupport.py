#
# Project:
#   glideinWMS
#
# File Version:
#
# Description: log support module
#
# Author:
#  Igor Sfiligoi (Oct 25th 2006)
#
import os
import sys
import timeConversion
import time
import logging
from logging.handlers import TimedRotatingFileHandler

log = None # create a place holder for a global logger, individual modules can create their own loggers if necessary
log_dir = None
debug_on = True

# this class can be used instead of a file for writing
class DayLogFile:
    def __init__(self, base_fname, extension="log"):
        self.base_fname = base_fname
        self.extension = extension
        return

    def close(self):
        return # nothing to do, just a placeholder

    def write(self, msg):
        now = time.time()
        fname = self.get_fname(now)
        try:
            fd = open(fname, "a")
        except:
            self.write_on_exception("Cannot open %s" % fname, msg)
            raise
        try:
            try:
                fd.write(self.format_msg(now, msg) + "\n")
            except:
                self.write_on_exception("Cannot open %s" % fname, msg)
                raise
        finally:
            fd.close()

        return

    ##########################
    # these can be customized
    ##########################

    def write_on_exception(self, exception_msg, msg):
        print "%s: %s" % (exception_msg, msg)
        return

    def get_fname(self, timestamp):
        return "%s.%s.%s" % (self.base_fname, time.strftime("%Y%m%d", time.localtime(timestamp)), self.extension)

    def format_msg(self, timestamp, msg):
        return "[%s %s] %s" % (self.format_time(timestamp), os.getpid(), msg)

    def format_time(self, timestamp):
        return timeConversion.getISO8601_Local(timestamp)

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
        when = 'D'
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


def add_glideinlog_handler(logger_name, log_dir, maxDays, maxBytes):
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

    mylog = logging.getLogger(logger_name)
    mylog.setLevel(logging.DEBUG)

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
    handler.addFilter(InfoFilter())
    mylog.addHandler(handler)

    # DEBUG Logger
    if debug_on:
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s:::%(module)s::%(lineno)d: %(message)s ')
        logfile = os.path.expandvars("%s/%s.debug.log" % (log_dir, logger_name))
        handler = GlideinHandler(logfile, maxDays, maxBytes, backupCount=5)
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        mylog.addHandler(handler)
    
class InfoFilter(logging.Filter):
    """
    Filter used in handling records for the info logs.
    """
    def filter(self, rec):
        return rec.levelno == logging.INFO or rec.levelno == logging.WARNING or rec.levelno == logging.WARN
    
