# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Module with factory/tool specific condor logs helper functions.

Contains functions to locate the glidein log files and to extract sections and
embedded log files from them.
"""

import binascii
import gzip
import io
import mmap
import os.path
import re
import time

from glideinwms.factory import glideFactoryLogParser
from glideinwms.lib import condorLogParser
from glideinwms.lib.defaults import BINARY_ENCODING, force_bytes


# get the list of jobs that were active at a certain time
def get_glideins(log_dir_name, date_arr, time_arr):
    """Get the list of glidein job IDs active at a specified time.

    This function loads a log summary of completed glidein jobs from the given directory and filters
    the jobs based on a reference time computed from the provided date and time arrays. It returns a
    list of glidein IDs that were active (i.e. running during the interval defined by the reference time).

    Args:
        log_dir_name (str): The directory containing the log files.
        date_arr (tuple): A tuple representing a date (e.g., (year, month, day)).
        time_arr (tuple): A tuple representing a time (e.g., (hour, minute, second)).

    Returns:
        list: A list of glidein IDs (job IDs) that were active at the specified time.
    """
    glidein_list = []

    cldata = glideFactoryLogParser.dirSummaryTimingsOutFull(log_dir_name, cache_dir=None)
    cldata.load(active_only=False)
    glidein_data = cldata.data["Completed"]  # I am interested only in the completed ones

    ref_ctime = time.mktime(date_arr + time_arr + (0, 0, -1))

    for glidein_el in glidein_data:
        glidein_id, fistTimeStr, runningStartTimeStr, lastTimeStr = glidein_el
        runningStartTime = condorLogParser.rawTime2cTimeLastYear(runningStartTimeStr)
        if runningStartTime > ref_ctime:
            continue  # not one of them, started after
        lastTime = condorLogParser.rawTime2cTimeLastYear(lastTimeStr)
        if lastTime < ref_ctime:
            continue  # not one of them, ended before
        glidein_list.append(glidein_id)

    return glidein_list


# get the list of log files for an entry that were active at a certain time
def get_glidein_logs_entry(factory_dir, entry, date_arr, time_arr, ext="err"):
    """Get the list of glidein log file paths for an entry active at a specified time.

    This function computes the log directory for a given entry within the Factory, retrieves the list of
    glidein job IDs active at the specified time, and constructs the full paths to the corresponding log files
    with the specified extension.

    Args:
        factory_dir (str): The Factory directory.
        entry (str): The entry name.
        date_arr (tuple): A tuple representing a date (e.g., (year, month, day)).
        time_arr (tuple): A tuple representing a time (e.g., (hour, minute, second)).
        ext (str, optional): The file extension for the log files. Defaults to "err".

    Returns:
        list: A list of log file paths corresponding to the active glidein jobs.
    """
    log_list = []

    log_dir_name = os.path.join(factory_dir, "entry_%s/log" % entry)
    glidein_list = get_glideins(log_dir_name, date_arr, time_arr)
    for glidein_id in glidein_list:
        glidein_log_file = "job.%i.%i." % condorLogParser.rawJobId2Nr(glidein_id)
        glidein_log_file += ext
        glidein_log_filepath = os.path.join(log_dir_name, glidein_log_file)
        if os.path.exists(glidein_log_filepath):
            log_list.append(glidein_log_filepath)

    return log_list


# get the list of log files for an entry that were active at a certain time
def get_glidein_logs(factory_dir, entries, date_arr, time_arr, ext="err"):
    """Get the list of glidein log file paths for multiple entries active at a specified time.

    This function iterates over the list of entries and aggregates the log file paths for each entry by calling
    get_glidein_logs_entry. The combined list is returned.

    Args:
        factory_dir (str): The factory directory.
        entries (list): A list of entry names.
        date_arr (tuple): A tuple representing a date (e.g., (year, month, day)).
        time_arr (tuple): A tuple representing a time (e.g., (hour, minute, second)).
        ext (str, optional): The file extension for the log files. Defaults to "err".

    Returns:
        list: A list of log file paths for all specified entries.
    """
    log_list = []
    for entry in entries:
        entry_log_list = get_glidein_logs_entry(factory_dir, entry, date_arr, time_arr, ext)
        log_list += entry_log_list

    return log_list


# extract the blob from a glidein log file starting from position
def get_compressed_raw(log_fname, start_str, start_pos=0):
    """Extract the raw base64-encoded blob from a glidein log file starting from a specific header.

    This function memory maps the log file, searches for a header that matches the start_str (followed by a
    specific marker), and extracts the block of base64 encoded data that follows. It decodes the data using the
    specified binary encoding.

    Args:
        log_fname (str): The path to the log file.
        start_str (str): The starting string that marks the beginning of the compressed blob.
        start_pos (int, optional): The position in the file to start searching. Defaults to 0.

    Returns:
        str: The decoded base64 string from the log file, or an empty string if not found.
    """
    SL_START_RE = re.compile(b"%s\nbegin-base64 644 -\n" % force_bytes(start_str, BINARY_ENCODING), re.M | re.DOTALL)
    size = os.path.getsize(log_fname)
    if size == 0:
        return ""  # mmap would fail... and I know I will not find anything anyhow
    with open(log_fname) as fd:
        buf = mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)
        try:
            # first find the header that delimits the log in the file
            start_re = SL_START_RE.search(buf, 0)
            if start_re is None:
                return ""  # no StartLog section
            log_start_idx = start_re.end()

            # find where it ends
            log_end_idx = buf.find(b"\n====", log_start_idx)
            if log_end_idx < 0:  # up to the end of the file
                return buf[log_start_idx:].decode(BINARY_ENCODING)
            else:
                return buf[log_start_idx:log_end_idx].decode(BINARY_ENCODING)
        finally:
            buf.close()


# extract the blob from a glidein log file
def get_compressed(log_fname, start_str):
    """Extract and decompress a blob from a glidein log file.

    This function extracts a base64-encoded blob from the log file by calling `get_compressed_raw`.
    If data is found, it decodes the base64 string, decompresses it using gzip, and returns the resulting text.

    Args:
        log_fname (str): The path to the log file.
        start_str (str): The starting string to search for in the log file.

    Returns:
        str: The decompressed data from the log file, or an empty string if no data is found.
    """
    raw_data = get_compressed_raw(log_fname, start_str)
    if raw_data != "":
        gzip_data = binascii.a2b_base64(raw_data)
        del raw_data
        data_fd = gzip.GzipFile(fileobj=io.BytesIO(gzip_data))
        data = data_fd.read().decode(BINARY_ENCODING)
    else:
        data = raw_data
    return data


# extract the blob from a glidein log file
def get_simple(log_fname, start_str, end_str):
    """Extract a simple text blob from a glidein log file between specified markers.

    This function uses memory mapping to read the log file, searches for the start marker (start_str) and the end marker
    (end_str), and extracts the text in between.

    Args:
        log_fname (str): The path to the log file.
        start_str (str): The starting marker string.
        end_str (str): The ending marker string.

    Returns:
        str: The text extracted between the markers, or an empty string if the markers are not found.
    """
    SL_START_RE = re.compile(force_bytes(start_str, BINARY_ENCODING) + b"\n", re.M | re.DOTALL)
    SL_END_RE = re.compile(end_str, re.M | re.DOTALL)
    size = os.path.getsize(log_fname)
    if size == 0:
        return ""  # mmap would fail... and I know I will not find anything anyhow
    with open(log_fname) as fd:
        buf = mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)
        try:
            # first find the header that delimits the log in the file
            start_re = SL_START_RE.search(buf, 0)
            if start_re is None:
                return ""  # no StartLog section
            log_start_idx = start_re.end()

            # find where it ends
            log_end_idx = SL_END_RE.search(buf, log_start_idx)
            if log_end_idx is None:  # up to the end of the file
                return buf[log_start_idx:].decode(BINARY_ENCODING)
            else:
                return buf[log_start_idx : log_end_idx.start()].decode(BINARY_ENCODING)
        finally:
            buf.close()


# extract the Condor Log from a glidein log file
# condor_log_id should be something like "StartdLog"
def get_condor_log(log_fname, condor_log_id):
    """Extract the Condor log from a glidein log file.

    Constructs a start string using the provided condor_log_id and calls `get_compressed` to extract and decompress
    the corresponding Condor log section from the file.

    Args:
        log_fname (str): The path to the log file.
        condor_log_id (str): Identifier for the Condor log section (e.g., "StartdLog").

    Returns:
        str: The decompressed Condor log section.
    """
    start_str = "^%s\n======== gzip . uuencode =============" % condor_log_id
    return get_compressed(log_fname, start_str)


# extract the XML Result from a glidein log file
def get_xml_result(log_fname):
    """Extract the XML result from a glidein log file.

    First attempts to extract an encoded XML description of glidein activity from the log file.
    If not found, it falls back to extracting an uncompressed XML section.

    Args:
        log_fname (str): The path to the log file.

    Returns:
        str: The XML result as a string, or an empty string if not found.
    """
    start_str = "^=== Encoded XML description of glidein activity ==="
    s = get_compressed(log_fname, start_str)
    if s != "":
        return s
    # not found, try the uncompressed version
    start_str = "^=== XML description of glidein activity ==="
    end_str = "^=== End XML description of glidein activity ==="
    return get_simple(log_fname, start_str, end_str)


# extract slot names
def get_starter_slot_names(log_fname, condor_log_id="(StarterLog.slot[0-9]*[_]*[0-9]*)"):
    """Extract slot names from a glidein log file.

    Searches for slot names matching the provided condor_log_id pattern in the log file. The slot names are
    extracted from base64-encoded sections and returned as a list of strings.

    Args:
        log_fname (str): The path to the log file.
        condor_log_id (str, optional): Regular expression pattern to match slot names.
            Defaults to "(StarterLog.slot[0-9]*[_]*[0-9]*)".

    Returns:
        list: A list of slot name strings.
    """
    start_str = "^%s\n======== gzip . uuencode =============" % condor_log_id
    SL_START_RE = re.compile(b"%s\nbegin-base64 644 -\n" % force_bytes(start_str, BINARY_ENCODING), re.M | re.DOTALL)
    size = os.path.getsize(log_fname)
    if size == 0:
        return ""  # mmap would fail... and I know I will not find anything anyhow
    with open(log_fname) as fd:
        buf = mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)
        try:
            strings = [s.decode(BINARY_ENCODING) for s in SL_START_RE.findall(buf, 0)]
            return strings
        finally:
            buf.close()
