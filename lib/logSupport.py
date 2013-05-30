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


DEFAULT_FORMATTER = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
DEBUG_FORMATTER = logging.Formatter('[%(asctime)s] %(levelname)s: %(module)s:%(lineno)d: %(message)s')

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
        #Make dirs if logging directory does not exist
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

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


def add_processlog_handler(logger_name, log_dir, msg_types, extension, maxDays, minDays, maxMBytes):
    """
    Adds a handler to the GlideinLogger logger referenced by logger_name.
    """
    logfile = os.path.expandvars("%s/%s.%s.log" % (log_dir, logger_name, extension.lower()))
     
    mylog = logging.getLogger(logger_name)
    mylog.setLevel(logging.DEBUG)
    
    handler = GlideinHandler(logfile, maxDays, minDays, maxMBytes, backupCount=5)
    handler.setFormatter(DEFAULT_FORMATTER)
    handler.setLevel(logging.DEBUG)
    
    has_debug = False
    msg_type_list = [] 
    for msg_type in msg_types.split(","):
        msg_type = msg_type.upper().strip()
        if msg_type == "INFO":
            msg_type_list.append(logging.INFO)
        elif msg_type == "WARN":
            msg_type_list.append(logging.WARN)
            msg_type_list.append(logging.WARNING)
        if msg_type == "ERR":
            msg_type_list.append(logging.ERROR)
            msg_type_list.append(logging.CRITICAL)
        if msg_type == "DEBUG":
            msg_type_list.append(logging.DEBUG)
            has_debug = True        
        
    if has_debug:
        handler.setFormatter(DEBUG_FORMATTER)  
    else:
        handler.setFormatter(DEFAULT_FORMATTER)
        
    handler.addFilter(MsgFilter(msg_type_list)) 
        
    mylog.addHandler(handler)
    

class MsgFilter(logging.Filter):
    """
    Filter used in handling records for the info logs.
    """
    msg_type_list = [logging.INFO]
    
    def __init__(self, msg_type_list):
        logging.Filter.__init__(self)
        self.msg_type_list = msg_type_list
            
    def filter(self, rec):
        return rec.levelno in self.msg_type_list 

    
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
