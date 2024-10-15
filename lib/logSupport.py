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

from . import util

USE_STRUCTLOG = True
try:
    import structlog
except ImportError:
    USE_STRUCTLOG = False


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
    """Logs a message to stderr as an alternative logging method.

    This function is used when exceptions occur within the logging system,
    such as when the disk is full during log file rotation.

    Args:
        msg (str): The message to be logged.
    """
    sys.stderr.write("%s\n" % msg)


class GlideinHandler(BaseRotatingHandler):
    """Custom logging handler class for GlideinWMS.

    Combines log rotation based on both time and file size, allowing
    the specification of a lifetime and file size to determine when to rotate the log file.

    Attributes:
        compression (str): Compression format (gz, zip) used for log files.
        backupCount (int): Number of backup files to keep.
        maxBytes (int): Maximum file size in bytes before rotation.
        min_lifetime (int): Minimum lifetime in seconds before rotation.
        interval (int): Time interval in seconds before rotation.
        suffix (str): Suffix format for the rotated files.
        extMatch (re.Pattern): Regex pattern to match the suffix of the rotated files.
        rolloverAt (int): Time when the next rollover should happen.
        rollover_not_before (int): Earliest time when rollover can happen.
    """

    def __init__(self, filename, maxDays=1.0, minDays=0.0, maxMBytes=10.0, backupCount=5, compression=None):
        """Initializes the GlideinHandler.

        Args:
            filename (str|Path): The full path of the log file.
            maxDays (float): Maximum number of days before file rotation.
            minDays (float): Minimum number of days before file rotation.
            maxMBytes (float): Maximum file size in megabytes before rotation.
            backupCount (int): Number of backup files to keep.
            compression (str): Compression format (gz, zip) to use for log files.
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
        mode = "a"
        BaseRotatingHandler.__init__(self, filename, mode, encoding=None)
        self.backupCount = backupCount
        self.maxBytes = int(maxMBytes * 1024.0 * 1024.0)  # Convert the MB to bytes as needed by the base class
        self.min_lifetime = int(minDays * 24 * 60 * 60)  # Convert min days to seconds
        self.interval = int(maxDays * 24 * 60 * 60)  # Convert max days (interval) to seconds

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
        self.rollover_not_before = 0
        if self.min_lifetime > 0:
            self.rollover_not_before = begin_interval_time + self.min_lifetime

    def shouldRollover(self, record, empty_record=False):
        """Determines if a rollover should occur based on time or file size.

        Args:
            record (str): The message that will be logged.
            empty_record (bool): If False, counts `record` length to evaluate if a rollover is needed.

        Returns:
            bool: True if rollover should be performed, False otherwise.
        """
        if disable_rotate:
            return False

        do_timed_rollover = False
        t = int(time.time())
        if t >= self.rolloverAt:
            do_timed_rollover = True

        do_size_rollover = False
        if self.maxBytes > 0 and t >= self.rollover_not_before:  # are we rolling over?
            if empty_record:
                msg = ""
            else:
                msg = f"{self.format(record)}\n"
            self.stream.seek(0, 2)  # due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                do_size_rollover = True

        return do_timed_rollover or do_size_rollover

    def getFilesToDelete(self):
        """Gets the list of files that should be deleted during rollover.

        Returns:
            list: A list of file paths that should be deleted.
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
        """Performs the rollover process for the log file.

        This includes renaming the log file, compressing it if necessary,
        and removing old log files based on the backup count.
        """
        # Close the soon to be rotated log file
        self.stream.close()
        # get the time that this sequence started at and make it a TimeTuple
        timeTuple = time.localtime(time.time())
        dfn = self.baseFilename + "." + time.strftime(self.suffix, timeTuple)

        if os.path.exists(dfn):
            os.remove(dfn)

        # rename the closed log file to the new rotated file name
        os.rename(self.baseFilename, dfn)

        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)

        self.mode = "w"
        self.stream = self._open()

        currentTime = int(time.time())
        if self.min_lifetime > 0:
            self.rollover_not_before = currentTime + self.min_lifetime
        newRolloverAt = currentTime + self.interval
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval
        self.rolloverAt = newRolloverAt

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
                f_out = gzip.open(dfn + ".gz", "wb")
                with open(dfn, "rb") as f_in:
                    f_out.writelines(f_in)
                f_out.close()
                os.remove(dfn)
            except OSError as e:
                alternate_log("Log file gzip compression failed: %s" % e)

    def check_and_perform_rollover(self):
        """Checks if rollover conditions are met and performs the rollover if necessary."""
        if self.shouldRollover(None, empty_record=True):
            self.doRollover()


def roll_all_logs():
    """Triggers log rotation for all registered handlers."""
    for handler in handlers:
        handler.check_and_perform_rollover()


def get_processlog_handler(
    log_file_name, log_dir, msg_types, extension, maxDays, minDays, maxMBytes, backupCount=5, compression=None
):
    """Returns a configured handler for the GlideinLogger logger.

    Args:
        log_file_name (str): Log file name (same as the logger name).
        log_dir (str|Path): Log directory.
        msg_types (str): Log levels to include (comma-separated list).
        extension (str): File name extension.
        maxDays (float): Maximum number of days before file rotation.
        minDays (float): Minimum number of days before file rotation.
        maxMBytes (float): Maximum size of the logfile in MB before file rotation.
        backupCount (int): Number of backups to keep.
        compression (str): Compression to use (gz, zip, depending on available modules).

    Returns:
        GlideinHandler: Configured logging handler.
    """
    # Parameter adjustments
    msg_types = msg_types.upper()
    if "ADMIN" in msg_types:
        msg_types = "DEBUG,INFO,WARN,ERR"
        if not log_file_name.endswith("admin"):
            log_file_name = log_file_name + "admin"
    if "ALL" in msg_types:
        msg_types = "DEBUG,INFO,WARN,ERR"
    logfile = os.path.expandvars(f"{log_dir}/{log_file_name}.{extension.lower()}.log")

    handler = GlideinHandler(logfile, maxDays, minDays, maxMBytes, backupCount, compression)
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
    """Filter class for handling log messages based on log level.

    Args:
        msg_type_list (list): List of log levels to filter.

    Returns:
        bool: True if the log level matches one in the list, False otherwise.
    """

    def __init__(self, msg_type_list):
        """Initializes the MsgFilter.

        Args:
            msg_type_list (list): List of log levels to filter.
        """
        logging.Filter.__init__(self)
        self.msg_type_list = msg_type_list

    def filter(self, rec):
        """Filters log records based on log level.

        Args:
            rec (logging.LogRecord): The log record to be filtered.

        Returns:
            bool: True if the log level is in msg_type_list, False otherwise.
        """
        return rec.levelno in self.msg_type_list


def format_dict(unformated_dict, log_format="   %-25s : %s\n"):
    """Formats a dictionary for human-readable logging.

    Args:
        unformated_dict (dict): The dictionary to be formatted for logging.
        log_format (str): Format string for logging.

    Returns:
        str: Formatted string.
    """
    formatted_string = ""
    for key in unformated_dict:
        formatted_string += log_format % (key, unformated_dict[key])

    return formatted_string


if USE_STRUCTLOG:
    try:
        # From structlog 23.1.0 suggested configurations - separate rendering, using same output
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.CallsiteParameterAdder(
                    {
                        structlog.processors.CallsiteParameter.FILENAME,
                        structlog.processors.CallsiteParameter.FUNC_NAME,
                        structlog.processors.CallsiteParameter.LINENO,
                    }
                ),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    except AttributeError:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


def get_logging_logger(name):
    """Retrieves a standard Python logging logger.

    Args:
        name (str): Name of the logger.

    Returns:
        logging.Logger: Configured logger.
    """
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    return log


def get_structlog_logger(name):
    """Retrieves a structured logger using structlog if available.

    Args:
        name (str): Name of the logger.

    Returns:
        structlog.BoundLogger: Configured structured logger.
    """
    if USE_STRUCTLOG:
        log = structlog.get_logger(name)
        log.setLevel(logging.DEBUG)
        return log
    return get_logging_logger(name)


def get_logger_with_handlers(name, directory, config_data, level=logging.DEBUG):
    """Creates and configures a logger with handlers.

    Args:
        name (str): Logger name.
        directory (str|Path): Directory for the log files.
        config_data (dict): Logging configuration data.
        level (int): Logging level.

    Returns:
        logging.Logger: Configured logger.
    """
    process_logs = eval(config_data["ProcessLogs"])
    is_structured = False
    handlers_list = []
    for plog in process_logs:
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
    if is_structured and USE_STRUCTLOG:
        mylog = structlog.get_logger(name)
    else:
        if is_structured:
            alternate_log("Requesting structured log files but structlog is not available")
        mylog = logging.getLogger(name)
    for handler in handlers_list:
        mylog.addHandler(handler)
    mylog.setLevel(level)
    return mylog
