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
import time
import logging
from logging.handlers import TimedRotatingFileHandler

log = None # create a place holder for a global logger, individual modules can create their own loggers if necessary
log_dir = None

KEL_test_log = None

DEFAULT_FORMATTER = logging.Formatter('[%(asctime)s] %(levelname)s:  %(message)s')
DEBUG_FORMATTER = logging.Formatter('[%(asctime)s] %(levelname)s:::%(module)s::%(lineno)d: %(message)s ')

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
    @param maxMBytes: Maximum size of the logfile in MB before file rotation (used with min days)
    @type minDays: int
    @param minDays: Minimum number of days (used with max bytes)
    @type backupCount: int
    @ivar backupCount: How many backups to keep
    """
    
    def __init__(self, filename, interval=1, maxMBytes=10, minDays=0, backupCount=5):
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
        @type maxMBytes: int
        @param maxMBytes: Maximum size of the logfile in MB before file rotation
        @type backupCount: int
        @param backupCount: Number of backups to keep

        """
        when = 'D'
        TimedRotatingFileHandler.__init__(self, filename, when, interval, backupCount, encoding=None)
        
        # Convert the MB to bytes as needed by the base class
        self.maxBytes = maxMBytes * 1024.0 * 1024.0
        
        # Convert min days to seconds
        self.minDays = minDays * 24 * 60 * 60

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, we are combining the checks for size and time interval

        @type record: string
        @param record: The message that will be logged.
        """
        do_timed_rollover = logging.handlers.TimedRotatingFileHandler.shouldRollover(self, record)
        min_day_time = self.rolloverAt - self.interval + int(time.time())
        do_size_rollover = 0
        if self.maxBytes > 0:                   # are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
            if (self.stream.tell() + len(msg) >= self.maxBytes) and (min_day_time > self.minDays):
                do_size_rollover = 1

        return do_timed_rollover or do_size_rollover


def add_glideinlog_handler(logger_name, log_dir, maxDays, minDays, maxMBytes):
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
    @type MinDays: int
    @param MinDays: Min number of days before will be rotated (used with mas bytes)
    @type maxMBytes: int
    @param maxMBytes: Maximum size in bytes of the logfile before it will be rotated (used with min days)

    """

    mylog = logging.getLogger(logger_name)
    mylog.setLevel(logging.DEBUG)

    # Error Logger (warning messages)
    logfile = os.path.expandvars("%s/%s.err.log" % (log_dir, logger_name))
    handler = GlideinHandler(logfile, maxDays, minDays, maxMBytes, backupCount=5)
    handler.setFormatter(DEFAULT_FORMATTER)
    handler.setLevel(logging.DEBUG)
    handler.addFilter(WarningFilter())
    mylog.addHandler(handler)

    # INFO Logger
    logfile = os.path.expandvars("%s/%s.info.log" % (log_dir, logger_name))
    handler = GlideinHandler(logfile, maxDays, minDays, maxMBytes, backupCount=5)
    handler.setFormatter(DEFAULT_FORMATTER)
    handler.setLevel(logging.DEBUG)
    handler.addFilter(InfoFilter())
    mylog.addHandler(handler)

    # DEBUG Logger
    logfile = os.path.expandvars("%s/%s.debug.log" % (log_dir, logger_name))
    handler = GlideinHandler(logfile, maxDays, minDays, maxMBytes, backupCount=5)
    handler.setFormatter(DEBUG_FORMATTER)
    handler.setLevel(logging.DEBUG)
    handler.addFilter(DebugFilter())
    mylog.addHandler(handler)


def add_processlog_handler(logger_name, log_dir, log_type, maxDays, minDays, maxMBytes):
    """
    Adds a handler to the GlideinLogger logger referenced by logger_name.
    """
    logfile = os.path.expandvars("%s/%s.%s.log" % (log_dir, logger_name, log_type.lower()))
     
    mylog = logging.getLogger(logger_name)
    mylog.setLevel(logging.DEBUG)
    
    handler = GlideinHandler(logfile, maxDays, minDays, maxMBytes, backupCount=5)
    handler.setFormatter(DEFAULT_FORMATTER)
    handler.setLevel(logging.DEBUG)
    if log_type.upper() == "ALL":
        # don't add any filters
        pass
    elif log_type.upper() == "INFO":
        handler.addFilter(InfoFilter())
    elif log_type.upper() == "DEBUG":
        handler.addFilter(DebugFilter())
        handler.setFormatter(DEBUG_FORMATTER)
    elif log_type.upper() == "ERR":
        handler.addFilter(WarningFilter())
        
    mylog.addHandler(handler)
    

class InfoFilter(logging.Filter):
    """
    Filter used in handling records for the info logs.
    """
    def filter(self, rec):
        return rec.levelno == logging.INFO 

class WarningFilter(logging.Filter):
    """
    Filter used in handling records for the error logs.
    """
    def filter(self, rec):
        return rec.levelno == logging.WARNING or rec.levelno == logging.WARN 
    
class DebugFilter(logging.Filter):
    """
    Filter used in handling records for the error logs.
    """
    def filter(self, rec):
        return rec.levelno == logging.DEBUG or rec.levelno == logging.ERROR

def format_dict(unformated_dict, log_format="   %-25s : %s\n"):
    """
    Convenience function used to format a dictionary for the logs to make it 
    human readable.
    
    @type unformated_dict: dict
    @param unformated_dict: The dictionary to be formatted for logging
    @type log_format: string
    @param log_format: format string for logging
    """
    formatted_string = ""
    for key in unformated_dict:
        formatted_string += log_format % (key, unformated_dict[key])

    return formatted_string
