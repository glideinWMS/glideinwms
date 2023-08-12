# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description: log support module
#   Uses the Python built-in logging to log anything anywhere
#   and structlog to improve machine parsing

import logging
import os
import re
import stat
import sys  # for alternate_log
import time

from logging.handlers import BaseRotatingHandler

import structlog

from . import util

# Compressions depend on the available module
COMPRESSION_SUPPORTED = {}
try:
    import gzip

    COMPRESSION_SUPPORTED["gz"] = gzip
except ImportError:
    pass
try:
    import zipfile

    COMPRESSION_SUPPORTED["zip"] = zipfile
except ImportError:
    pass


# Create a placeholder for a global logger (logging.Logger),
# individual modules can create their own loggers if necessary
log = None

log_dir = None
disable_rotate = False
handlers = []

DEFAULT_FORMATTER = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
DEBUG_FORMATTER = logging.Formatter("[%(asctime)s] %(levelname)s: %(module)s:%(lineno)d: %(message)s")

# A reminder of the logging levels:
# 0  NOTSET
# 10 DEBUG
# 20 INFO
# 30 WARN WARNING
# 40 ERROR
# 50 FATAL CRITICAL
# A message will be printed if it's level >= max(handler.level, logger.level)


def alternate_log(msg):
    """
    When an exceptions happen within the logging system (e.g. when the disk is full while rotating a
    log file) an alternate logging is necessary, e.g. writing to stderr
    """
    sys.stderr.write("%s\n" % msg)


class GlideinHandler(BaseRotatingHandler):
    """
    Custom logging handler class for GlideinWMS.  It combines the decision tree
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
        """Initialize the Handler.  We assume the following:

            1. Interval is in days
            2. No special encoding
            3. No delays are set
            4. Timestamps are not in UTC

        Args:
            filename (str|Path): The full path of the log file
            maxDays (int): Max number of days before file rotation
            minDays (int): Minimum number of days before file rotation (used with max bytes)
            maxMBytes (int): Maximum size of the logfile in MB before file rotation (used with min days)
            backupCount (int): Number of backups to keep
            compression (str): Compression to use (gz, zip, depending on available compression modules)
        """
        # Make dirs if logging directory does not exist
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        self.compression = ""
        try:
            if compression.lower() in COMPRESSION_SUPPORTED:
                self.compression = compression.lower()
        except AttributeError:
            pass
        # bz2 compression can be implemented with encoding='bz2-codec' in BaseRotatingHandler
        mode = "a"
        BaseRotatingHandler.__init__(self, filename, mode, encoding=None)
        self.backupCount = backupCount
        self.maxBytes = maxMBytes * 1024.0 * 1024.0  # Convert the MB to bytes as needed by the base class
        self.min_lifetime = minDays * 24 * 60 * 60  # Convert min days to seconds
        self.interval = maxDays * 24 * 60 * 60  # Convert max days (interval) to seconds

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
        """Determine if rollover should occur.

        Basically, we are combining the checks for size and time interval

        Args:
            record (str): The message that will be logged.
            empty_record (bool): If False (default)  count also `record` length to evaluate if a rollover is needed

        Returns:
            bool: True if rollover should be performed, False otherwise

        @attention: Due to the architecture decision to fork "workers" we run
        into an issue where the child that was forked could cause a log
        rotation.  However, the parent will never know and the parent's file
        descriptor will still be pointing at the old log file (now renamed by
        the child).  This will in turn cause the parent to immediately request
        a log rotate, which results in what appears to be truncated logs.  To
        handle this we add a flag to disable log rotation.  By default, this is
        set to False, but anywhere we want to fork a child (or in any object
        that will be forked) we set the flag to True.  Then in the parent, we
        initiate a log function that will log and rotate if necessary.
        """
        if disable_rotate:
            return False

        do_timed_rollover = False
        t = int(time.time())
        if t >= self.rolloverAt:
            do_timed_rollover = True

        do_size_rollover = False
        if self.maxBytes > 0:  # are we rolling over?
            if empty_record:
                msg = ""
            else:
                msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  # due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                do_size_rollover = True

        return do_timed_rollover or do_size_rollover

    def getFilesToDelete(self):
        """Determine the files to delete when rolling over.

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
            result = result[: len(result) - self.backupCount]
        return result

    def doRollover(self):
        """Do a rollover

        In this case, a date/time stamp is appended to the filename
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
        self.mode = "w"
        self.stream = self._open()

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
            except OSError as e:
                alternate_log("Log file zip compression failed: %s" % e)
        elif self.compression == "gz":
            if os.path.exists(dfn + ".gz"):
                os.remove(dfn + ".gz")
            try:
                # TODO #23166: Use context managers[with statement] when python 3
                # once we get rid of SL6 and tarballs
                f_out = gzip.open(dfn + ".gz", "wb")
                with open(dfn, "rb") as f_in:
                    f_out.writelines(f_in)
                f_out.close()
                os.remove(dfn)
            except OSError as e:
                alternate_log("Log file gzip compression failed: %s" % e)

    def check_and_perform_rollover(self):
        if self.shouldRollover(None, empty_record=True):
            self.doRollover()


def roll_all_logs():
    for handler in handlers:
        handler.check_and_perform_rollover()


# TODO: to remove once sure that not needed and all use get_logger_with_handlers
def OLD_add_processlog_handler(
    logger_name, log_dir, msg_types, extension, maxDays, minDays, maxMBytes, backupCount=5, compression=None
):
    """
    Adds a handler to the GlideinLogger logger referenced by logger_name.
    """

    logfile = os.path.expandvars(f"{log_dir}/{logger_name}.{extension.lower()}.log")

    mylog = structlog.getLogger(logger_name)
    mylog.setLevel(logging.DEBUG)

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

    if has_debug:
        handler.setFormatter(DEBUG_FORMATTER)
    else:
        handler.setFormatter(DEFAULT_FORMATTER)

    handler.addFilter(MsgFilter(msg_type_list))

    mylog.addHandler(handler)
    handlers.append(handler)


def get_processlog_handler(
    log_file_name, log_dir, msg_types, extension, maxDays, minDays, maxMBytes, backupCount=5, compression=None
):
    """Return a configured handler for the GlideinLogger logger

    The file name is `"{log_dir}/{log_file_name}.{extension.lower()}.log"` and can include env variables

    Args:
        log_file_name (str): log file name (same as the logger name)
        log_dir (str|Path): log directory
        msg_types (str): log levels to include (comma separated list). Keywords are:
            DEBUG,INFO,WARN,ERR, or ADMIN or ALL (which mean all the previous)
        extension (str): file name extension
        maxDays (int): Max number of days before file rotation
        minDays (int): Minimum number of days before file rotation (used with max bytes)
        maxMBytes (int): Maximum size of the logfile in MB before file rotation (used with min days)
        backupCount (int): Number of backups to keep
        compression (str): Compression to use (gz, zip, depending on available compression modules)

    Returns:
        GlideinHandler: configured handler
    """
    # Parameter adjustments
    msg_types = msg_types.upper()
    if "ADMIN" in msg_types:
        msg_types = "DEBUG,INFO,WARN,ERR"
        if not log_file_name.endswith("admin"):
            log_file_name = log_file_name + "admin"
    if "ALL" in msg_types:
        msg_types = "DEBUG,INFO,WARN,ERR"
    # File name
    logfile = os.path.expandvars(f"{log_dir}/{log_file_name}.{extension.lower()}.log")

    handler = GlideinHandler(logfile, maxDays, minDays, maxMBytes, backupCount, compression)
    handler.setFormatter(DEFAULT_FORMATTER)
    # Setting the handler logging level to DEBUG to control all from the logger level and the
    # filter. This allows to pick any level combination, but may be less performant than a
    # min level selection.
    # Should the handler level be logging.NOTSET (0) ?
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
        elif msg_type == "ERR":
            msg_type_list.append(logging.ERROR)
            msg_type_list.append(logging.CRITICAL)
        elif msg_type == "DEBUG":
            msg_type_list.append(logging.DEBUG)
            has_debug = True

    if has_debug:
        handler.setFormatter(DEBUG_FORMATTER)
    else:
        handler.setFormatter(DEFAULT_FORMATTER)

    handler.addFilter(MsgFilter(msg_type_list))

    handlers.append(handler)
    return handler


class MsgFilter(logging.Filter):
    """Filter used in handling records for the info logs.

    Default to logging.INFO
    """

    msg_type_list = [logging.INFO]

    def __init__(self, msg_type_list):
        logging.Filter.__init__(self)
        self.msg_type_list = msg_type_list

    def filter(self, rec):
        return rec.levelno in self.msg_type_list


def format_dict(unformated_dict, log_format="   %-25s : %s\n"):
    """Convenience function used to format a dictionary for the logs to make it  human-readable.

    Args:
        unformated_dict (dict): The dictionary to be formatted for logging
        log_format (str): format string for logging

    Returns:
        str: Formatted string
    """
    formatted_string = ""
    for key in unformated_dict:
        formatted_string += log_format % (key, unformated_dict[key])

    return formatted_string


# From structlog's suggested configurations - separate rendering, using same output
structlog.configure(
    processors=[
        # If log level is too low, abort pipeline and throw away log entry.
        structlog.stdlib.filter_by_level,
        # Add the name of the logger to event dict.
        structlog.stdlib.add_logger_name,
        # Add log level to event dict.
        structlog.stdlib.add_log_level,
        # Perform %-style formatting.
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Add a timestamp in ISO 8601 format.
        structlog.processors.TimeStamper(fmt="iso"),
        # If the "stack_info" key in the event dict is true, remove it and
        # render the current stack trace in the "stack" key.
        structlog.processors.StackInfoRenderer(),
        # If the "exc_info" key in the event dict is either true or a
        # sys.exc_info() tuple, remove "exc_info" and render the exception
        # with traceback into the "exception" key.
        structlog.processors.format_exc_info,
        # If some value is in bytes, decode it to a unicode str.
        structlog.processors.UnicodeDecoder(),
        # Add callsite parameters.
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        # Render the final event dict as JSON.
        structlog.processors.JSONRenderer(),
    ],
    # `wrapper_class` is the bound logger that you get back from
    # get_logger(). This one imitates the API of `logging.Logger`.
    wrapper_class=structlog.stdlib.BoundLogger,
    # `logger_factory` is used to create wrapped loggers that are used for
    # OUTPUT. This one returns a `logging.Logger`. The final value (a JSON
    # string) from the final processor (`JSONRenderer`) will be passed to
    # the method of the same name as that you've called on the bound logger.
    logger_factory=structlog.stdlib.LoggerFactory(),
    # Effectively freeze configuration after creating the first bound
    # logger.
    cache_logger_on_first_use=True,
)


def get_logging_logger(name):
    return logging.getLogger(name)


def get_structlog_logger(name):
    return structlog.get_logger(name)


def get_logger_with_handlers(name, directory, config_data, level=logging.DEBUG):
    """Create/retrieve a logger, set the handlers, set the starting logging level, and return the logger

    The file name is {name}.{plog["extension"].lower()}.log

    Args:
        name (str): logger name (and file base name)
        directory (str|Path): log directory
        config_data (dict): logging configuration
          (the "ProcessLogs" value evaluates to list of dictionary with process_logs section values)
        level: logger's logging level (default: logging.DEBUG)

    Returns:
        logging.Logger: configured logger
    """
    # Contains a dictionary in a string
    process_logs = eval(config_data["ProcessLogs"])
    is_structured = False
    handlers_list = []
    for plog in process_logs:
        # If at least one handler is structured, it will use structured logging
        # All handlers should be consistent and use the same
        is_structured = is_structured or util.is_true(plog["structured"])
        handler = get_processlog_handler(
            name,
            directory,
            plog["msg_types"],
            plog["extension"],
            int(float(plog["max_days"])),
            int(float(plog["min_days"])),
            int(float(plog["max_mbytes"])),
            int(float(plog["backup_count"])),
            plog["compression"],
        )
        handlers_list.append(handler)
    if is_structured:
        mylog = structlog.get_logger(name)
    else:
        mylog = logging.getLogger(name)
    for handler in handlers_list:
        mylog.addHandler(handler)
    mylog.setLevel(level)
    return mylog
