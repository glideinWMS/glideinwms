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
import codecs
import os
import stat
import time
import logging
from logging.handlers import BaseRotatingHandler

log = None # create a place holder for a global logger, individual modules can create their own loggers if necessary
log_dir = None


DEFAULT_FORMATTER = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
DEBUG_FORMATTER = logging.Formatter('[%(asctime)s] %(levelname)s: %(module)s:%(lineno)d: %(message)s')

# Adding in the capability to use the built in Python logging Module
# This will allow us to log anything, anywhere
#
# Note:  We may need to create a custom class later if we need to handle
#        logging with privilege separation

class GlideinHandler(BaseRotatingHandler):
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
        # Make dirs if logging directory does not exist
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        mode = 'a'
        BaseRotatingHandler.__init__(self, filename, mode, encoding=None)
        self.backupCount = backupCount
        self.maxBytes = maxMBytes * 1024.0 * 1024.0 # Convert the MB to bytes as needed by the base class
        self.min_lifetime = minDays * 24 * 60 * 60 # Convert min days to seconds

        # We are enforcing a date/time format for rotated log files to include
        # year, month, day, hours, and minutes.  The hours and minutes are to 
        # preserve multiple rotations in a single day.
        self.suffix = "%Y-%m-%d-%H-%M"
        self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$"

        if os.path.exists(filename):
            begin_interval_time = os.stat(filename)[stat.ST_CTIME]
        else:
            begin_interval_time = int(time.time())
        self.rolloverAt = begin_interval_time + self.interval

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, we are combining the checks for size and time interval

        @type record: string
        @param record: The message that will be logged.
        """
        do_timed_rollover = 0
        t = int(time.time())
        if t >= self.rolloverAt:
            do_timed_rollover = 1

        do_size_rollover = 0
        log_file_ctime = os.stat(self.baseFilename)[stat.ST_CTIME]
        log_file_age = int(time.time()) - log_file_ctime
        # We want to keep the logs around for the minimum number of days no 
        # matter what the size of the log is.
        if log_file_age > self.min_lifetime:
            # the log file is old enough, now lets check the size
            if self.maxBytes > 0:                   # are we rolling over?
                msg = "%s\n" % self.format(record)
                self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
                if (self.stream.tell() + len(msg) >= self.maxBytes):
                    do_size_rollover = 1

        return do_timed_rollover or do_size_rollover

    def getFilesToDelete(self):
        """
        Determine the files to delete when rolling over.

        More specific than the earlier method, which just used glob.glob().
        """
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        result = []
        prefix = baseName + "."
        plen = len(prefix)
        for fileName in fileNames:
            if fileName[:plen] == prefix:
                suffix = fileName[plen:]
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dirName, fileName))
        result.sort()
        if len(result) < self.backupCount:
            result = []
        else:
            result = result[:len(result) - self.backupCount]
        return result

    def doRollover(self):
        """
        do a rollover; in this case, a date/time stamp is appended to the filename
        when the rollover happens.  If there is a backup count, then we have to get
        a list of matching filenames, sort them and remove the one with the oldest 
        suffix.
        """
        # Close the soon to be rotated log file
        self.close()
        # get the time that this sequence started at and make it a TimeTuple
        timeTuple = time.localtime(time.time())
        dfn = self.baseFilename + "." + time.strftime(self.suffix, timeTuple)

        # If you are rotating log files in less than a minute, you either have
        # set your sizes way too low, or you have serious problems.  We are 
        # going to protect against that scenario by removing any files that 
        # whose name collides with the new rotated file name.
        if os.path.exists(dfn):
            os.remove(dfn)

        # rename the closed log file to the new rotated file name
        os.rename(self.baseFilename, dfn)

        # if there is a backup count specified, keep only the specified number of
        # rotated logs, delete the rest
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)

        # Open a new log file
        self.mode = 'w'
        self.stream = self._open_new_log()

        # determine the next rollover time for the timed rollover check
        currentTime = int(time.time())
        newRolloverAt = self.computeRollover(currentTime)
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval

        self.rolloverAt = newRolloverAt

    def _open_new_log(self):
        """
        This function is here to bridge the gap between the old (python 2.4) way
        of opening new log files and the new (python 2.7) way.
        """
        try:
            self._open()
        except:
            if self.encoding:
                self.stream = codecs.open(self.baseFilename, self.mode, self.encoding)
            else:
                self.stream = open(self.baseFilename, self.mode)


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
