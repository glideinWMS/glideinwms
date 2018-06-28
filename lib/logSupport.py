#
# Project:
#   glideinWMS
#
# File Version:
#
# Description: log support module
#

import codecs
import sys  # for alternate_log
import os
import re
import stat
import time
import logging
from logging.handlers import BaseRotatingHandler

# Compressions depend on the available module
COMPRESSION_SUPPORTED = {}
try:
   import gzip
   COMPRESSION_SUPPORTED['gz'] = gzip
except ImportError:
   pass
try:
   import zipfile
   COMPRESSION_SUPPORTED['zip'] = zipfile
except ImportError:
   pass


log = None # create a place holder for a global logger, individual modules can create their own loggers if necessary
log_dir = None
disable_rotate = False
handlers = []

DEFAULT_FORMATTER = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
DEBUG_FORMATTER = logging.Formatter('[%(asctime)s] %(levelname)s: %(module)s:%(lineno)d: %(message)s')

# Adding in the capability to use the built in Python logging Module
# This will allow us to log anything, anywhere
#
# Note:  We may need to create a custom class later if we need to handle
#        logging with privilege separation

def alternate_log(msg):
    """
    When an exceptions happen within the logging system (e.g. when the disk is full while rotating a 
    log file) an alternate logging is necessary, e.g. writing to stderr
    """
    sys.stderr.write("%s\n" % msg)
    

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
    def __init__(self, filename, maxDays=1, minDays=0, maxMBytes=10, backupCount=5, compression=None):
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

        self.compression = ''
        try:
            if compression.lower() in COMPRESSION_SUPPORTED:
                self.compression = compression.lower()
        except AttributeError:
            pass
        # bz2 compression can be implementes with encoding='bz2-codec' in BaseRotatingHandler
        mode = 'a'
        BaseRotatingHandler.__init__(self, filename, mode, encoding=None)
        self.backupCount = backupCount
        self.maxBytes = maxMBytes * 1024.0 * 1024.0 # Convert the MB to bytes as needed by the base class
        self.min_lifetime = minDays * 24 * 60 * 60 # Convert min days to seconds
        self.interval = maxDays * 24 * 60 * 60 # Convert max days (interval) to seconds

        # We are enforcing a date/time format for rotated log files to include
        # year, month, day, hours, and minutes.  The hours and minutes are to
        # preserve multiple rotations in a single day.
        self.suffix = "%Y-%m-%d_%H-%M"
        self.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}(\.gz|\.zip)?$")

        if os.path.exists(filename):
            begin_interval_time = os.stat(filename)[stat.ST_MTIME]
        else:
            begin_interval_time = int(time.time())
        self.rolloverAt = begin_interval_time + self.interval

    def shouldRollover(self, record, empty_record=False):
        """
        Determine if rollover should occur.

        Basically, we are combining the checks for size and time interval

        @type record: string
        @param record: The message that will be logged.

        @attention: Due to the architecture decision to fork "workers" we run
        into an issue where the child that was forked could cause a log
        rotation.  However the parent will never know and the parent's file
        descriptor will still be pointing at the old log file (now renamed by
        the child).  This will in turn cause the parent to immediately request
        a log rotate, which results in what appears to be truncated logs.  To
        handle this we add a flag to disable log rotation.  By default this is
        set to False, but anywhere we want to fork a child (or in any object
        that will be forked) we set the flag to True.  Then in the parent, we
        initiate a log function that will log and rotate if necessary.
        """
        if disable_rotate: return 0

        do_timed_rollover = 0
        t = int(time.time())
        if t >= self.rolloverAt:
            do_timed_rollover = 1

        do_size_rollover = 0
        if self.maxBytes > 0:                   # are we rolling over?
            if empty_record:
                msg = ""
            else:
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
        self.stream.close()
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
        newRolloverAt = currentTime + self.interval
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval

        self.rolloverAt = newRolloverAt

        # Compress the log file (if requested)
        if self.compression == "zip":
            if os.path.exists(dfn + ".zip"):
                os.remove(dfn + ".zip")
            try:
                f_out = zipfile.ZipFile(dfn + ".zip", "w")
                f_out.write(dfn, os.path.basename(dfn), zipfile.ZIP_DEFLATED)
                f_out.close()
                os.remove(dfn)
            except IOError as e:
                alternate_log("Log file zip compression failed: %s" % e)
        elif self.compression == "gz":
            if os.path.exists(dfn + ".gz"):
                os.remove(dfn + ".gz")
            f_in = open(dfn, "rb")
            try:
                f_out = gzip.open(dfn + ".gz", "wb")
                f_out.writelines(f_in)
                f_out.close()
                f_in.close()
                os.remove(dfn)
            except IOError as e:
                alternate_log("Log file gzip compression failed: %s" % e)

    def _open_new_log(self):
        """
        This function is here to bridge the gap between the old (python 2.4) way
        of opening new log files and the new (python 2.7) way.
        """
        new_stream = None
        try:
            # pylint: disable=E1101
            new_stream = self._open()
            # pylint: enable=E1101
        except:
            if self.encoding:
                new_stream = codecs.open(self.baseFilename, self.mode, self.encoding)
            else:
                new_stream = open(self.baseFilename, self.mode)
        return new_stream

    def check_and_perform_rollover(self):
        if self.shouldRollover(None, empty_record=True):
            self.doRollover()

def roll_all_logs():
    for handler in handlers:
        handler.check_and_perform_rollover()

def add_processlog_handler(logger_name, log_dir, msg_types, extension, maxDays, minDays, maxMBytes, backupCount=5, compression=None):
    """
    Adds a handler to the GlideinLogger logger referenced by logger_name.
    """

    logfile = os.path.expandvars("%s/%s.%s.log" % (log_dir, logger_name, extension.lower()))

    mylog = logging.getLogger(logger_name)
    mylog.setLevel(logging.DEBUG)
    # Jack Lundell
    mylog.addLevelName(11, "PROFILE")

    handler = GlideinHandler(logfile, maxDays, minDays, maxMBytes, backupCount, compression)
    handler.setFormatter(DEFAULT_FORMATTER)
    handler.setLevel(logging.DEBUG)

    has_debug = False
    msg_type_list = []
    for msg_type in msg_types.split(","):
        msg_type = msg_type.upper().strip()
        if msg_type == "INFO":
            msg_type_list.append(logging.INFO)
        if msg_type == "WARN":
            msg_type_list.append(logging.WARN)
            msg_type_list.append(logging.WARNING)
        if msg_type == "ERR":
            msg_type_list.append(logging.ERROR)
            msg_type_list.append(logging.CRITICAL)
        if msg_type == "DEBUG":
            msg_type_list.append(logging.DEBUG)
            has_debug = True
        # Jack Lundell
        if msg_type == "PROFILE":
            msg_type_list.append(11)

    if has_debug:
        handler.setFormatter(DEBUG_FORMATTER)
    else:
        handler.setFormatter(DEFAULT_FORMATTER)

    handler.addFilter(MsgFilter(msg_type_list))

    mylog.addHandler(handler)
    handlers.append(handler)

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
