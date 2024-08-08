# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements classes and functions to parse the condor log files.

NOTE:
Inactive files are log files that have only completed or removed entries
Such files will not change in the future
"""

import mmap
import os
import os.path
import stat
import time

from . import util

# -------------- Single Log classes ------------------------


class cachedLogClass:


    def clInit(self, logname, cache_dir, cache_ext):
        """Initializes the log and cache file paths.

        Args:
            logname (str): The name of the log file.
            cache_dir (str): The directory where the cache file should be stored.
            cache_ext (str): The extension to be used for the cache file.
        """
        self.logname = logname
        if cache_dir is None:
            self.cachename = logname + cache_ext
        else:
            self.cachename = os.path.join(cache_dir, os.path.basename(logname) + cache_ext)

    def has_changed(self):
        """Checks if the log file has changed since the last cache.

        Returns:
            bool: True if the log file has changed or if there is no cache, False otherwise.
         """
        if os.path.isfile(self.logname):
            fstat = os.lstat(self.logname)
            logtime = fstat[stat.ST_MTIME]
        else:
            return False  # does not exist, so it could not change

        if os.path.isfile(self.cachename):
            fstat = os.lstat(self.cachename)
            cachetime = fstat[stat.ST_MTIME]
        else:
            return True  # no cache, so it has changed for sure

        # both exist -> check if log file is newer
        return logtime > cachetime

    def load(self):
        """Loads data either from the cache or directly from the log.

        If the log has changed, the data is loaded from the log and the cache is updated.
        If the log has not changed, the data is loaded from the cache.
        """
        if not self.has_changed():
            # cache is newer, just load the cache
            return self.loadCache()

        while True:  # could need more than one loop if the log file is changing
            fstat = os.lstat(self.logname)
            start_logtime = fstat[stat.ST_MTIME]
            del fstat

            self.loadFromLog()
            try:
                self.saveCache()
            except OSError:
                return  # silently ignore, this was a load in the end
            # the log may have changed -> check
            fstat = os.lstat(self.logname)
            logtime = fstat[stat.ST_MTIME]
            del fstat
            if logtime <= start_logtime:
                return  # OK, not changed, can exit

        return  # should never reach this point

    def loadCache(self):
        """Loads data from cache file"""
        self.data = loadCache(self.cachename)
        return

    def loadFromLog(self):
        """Loads data from the log file.

        Raises:
            RuntimeError: If the method is not implemented in a subclass.
        """
        raise RuntimeError("loadFromLog not implemented!")

    ####### PRIVATE ###########
    def saveCache(self):
        """Saves the current data to the cache file"""
        saveCache(self.cachename, self.data)
        return


class logSummary(cachedLogClass):


    def __init__(self, logname, cache_dir):
        """Initializes the logSummary class with log and cache paths.

        Args:
            logname (str): The name of the log file.
            cache_dir (str): The directory where the cache file should be stored.
        """
        self.clInit(logname, cache_dir, ".cstpk")

    def loadFromLog(self):
        """Parses the log file and stores the data."""
        jobs = parseSubmitLogFastRaw(self.logname)
        self.data = listAndInterpretRawStatuses(jobs, listStatuses)
        return

    def isActive(self):
        """Determines if there are any active jobs in the log.

        Returns:
            bool: True if there are active jobs, False otherwise.
        """
        active = False
        for k in list(self.data.keys()):
            if k not in ["Completed", "Removed"]:
                if len(self.data[k]) > 0:
                    active = True  # it is enought that at least one non Completed/removed job exist
        return active

    def merge(self, other):
        """Merges the current data with another dataset.

        Args:
            other (dict): The other dataset to merge with.

        Returns:
            dict: The merged dataset.
        """
        if other is None:
            return self.data
        elif self.data is None:
            return other
        else:
            for k in list(self.data.keys()):
                try:
                    other[k] += self.data[k]
                except KeyError:  # missing key
                    other[k] = self.data[k]
            return other

    def diff(self, other):
        """Finds differences between the current dataset and another dataset.

        Args:
            other (dict): The other dataset to compare with.

        Returns:
            dict: A dictionary with 'Entered' and 'Exited' differences.
        """
        if other is None:
            outdata = {}
            if self.data is not None:
                for k in list(self.data.keys()):
                    outdata[k] = {"Exited": [], "Entered": self.data[k]}
            return outdata
        elif self.data is None:
            outdata = {}
            for k in list(other.keys()):
                outdata[k] = {"Entered": [], "Exited": other[k]}
            return outdata
        else:
            outdata = {}

            keys = {}  # keys will contain the merge of the two lists

            for s in list(self.data.keys()) + list(other.keys()):
                keys[s] = None

            for s in list(keys.keys()):
                if s in self.data:
                    sel = self.data[s]
                else:
                    sel = []

                if s in other:
                    oel = other[s]
                else:
                    oel = []

                outdata_s = {"Entered": [], "Exited": []}
                outdata[s] = outdata_s

                sset = set(sel)
                oset = set(oel)

                outdata_s["Entered"] = list(sset.difference(oset))
                outdata_s["Exited"] = list(oset.difference(sset))
            return outdata


class logCompleted(cachedLogClass):


    def __init__(self, logname, cache_dir):
        """Initializes the logCompleted clas with log and cache paths.

        Args:
            logname (str): The name of the log file
            cache_dir (str): The directory where the cache file should be stored
        """
        self.clInit(logname, cache_dir, ".clspk")

    def loadFromLog(self):
        """Parses the log file and stores the count and list of completed jobs."""
        tmpdata = {}
        jobs = parseSubmitLogFastRaw(self.logname)
        status = listAndInterpretRawStatuses(jobs, listStatuses)
        counts = {}
        for s in list(status.keys()):
            counts[s] = len(status[s])
        tmpdata["counts"] = counts
        if "Completed" in status:
            tmpdata["completed_jobs"] = status["Completed"]
        else:
            tmpdata["completed_jobs"] = []
        self.data = tmpdata
        return

    def isActive(self):
        """Determines if there are any active jobs in the log

        Returns:
            bool: True if there are active jobs, False otherwise.
        """
        active = False
        counts = self.data["counts"]
        for k in list(counts.keys()):
            if k not in ["Completed", "Removed"]:
                if counts[k] > 0:
                    # Enough that at least one non Completed/removed job exist
                    active = True
        return active

    def merge(self, other):
        """Merges the current data with another dataset.

        Args:
            other (dict): The other dataset to merge with

        Returns:
            dict: The merged dataset, including job counts and completed job
        """
        if other is None:
            return self.data
        elif self.data is None:
            return other
        else:
            for k in list(self.data["counts"].keys()):
                try:
                    other["counts"][k] += self.data["counts"][k]
                except KeyError:  # missing key
                    other["counts"][k] = self.data["counts"][k]
            other["completed_jobs"] += self.data["completed_jobs"]
            return other

    def diff(self, other):
        """Finds differences between the current dataset and another dataset.

        Args:
            other (dict): The other dataset to compare with.

        Returns:
            dict: A dictionary with the differences in job counts and completed jobs.
        """
        if other is None:
            if self.data is not None:
                outcj = {"Exited": [], "Entered": self.data["completed_jobs"]}
                outdata = {"counts": self.data["counts"], "completed_jobs": outcj}
            else:
                outdata = {"counts": {}, "completed_jobs": {"Exited": [], "Entered": []}}
            return outdata
        elif self.data is None:
            outcj = {"Entered": [], "Exited": other["completed_jobs"]}
            outct = {}
            for s in list(other["counts"].keys()):
                outct[s] = -other["counts"][s]
            outdata = {"counts": outct, "completed_jobs": outcj}
            return outdata
        else:
            outct = {}
            outcj = {"Entered": [], "Exited": []}
            outdata = {"counts": outct, "completed_jobs": outcj}

            keys = {}  # keys will contain the merge of the two lists
            for s in list(self.data["counts"].keys()) + list(other["counts"].keys()):
                keys[s] = None

            for s in list(keys.keys()):
                if s in self.data["counts"]:
                    sct = self.data["counts"][s]
                else:
                    sct = 0

                if s in other["counts"]:
                    oct = other["counts"][s]
                else:
                    oct = 0

                outct[s] = sct - oct

            sel = self.data["completed_jobs"]
            oel = other["completed_jobs"]
            sset = set(sel)
            oset = set(oel)

            outcj["Entered"] = list(sset.difference(oset))
            outcj["Exited"] = list(oset.difference(sset))

            return outdata


class logCounts(cachedLogClass):


    def __init__(self, logname, cache_dir):
        """Initializes the logCounts class with log and cache paths.

        Args:
            logname (str): The name of the log file.
            cache_dir (str): The directory where the cache file should be stored.
        """
        self.clInit(logname, cache_dir, ".clcpk")

    def loadFromLog(self):
        """Parses the log file and stores the counts of various job statuses"""

        jobs = parseSubmitLogFastRaw(self.logname)
        self.data = countAndInterpretRawStatuses(jobs)
        return

    def isActive(self):
        """Determines if there are any active (non-completed) jobs in the log.

        Returns:
            bool: True if there are active jobs, False otherwise.
        """
        active = False
        for k in list(self.data.keys()):
            if k not in ["Completed", "Removed"]:
                if self.data[k] > 0:
                    # Enough that at least one non Completed/removed job exist
                    active = True
        return active

    def merge(self, other):
        """Merges the current data with another dataset.

        Args:
            other (dict): The other dataset to merge with.

        Returns:
            dict: The merged dataset, including job counts.
        """
        if other is None:
            return self.data
        elif self.data is None:
            return other
        else:
            for k in list(self.data.keys()):
                try:
                    other[k] += self.data[k]
                except KeyError:  # missing key
                    other[k] = self.data[k]
            return other

    def diff(self, other):
        """Finds differences between the current dataset and another dataset.

        Args:
            other (dict): The other dataset to compare with.

        Returns:
            dict: A dictionary with the differences in job counts.
        """
        if other is None:
            if self.data is not None:
                return self.data
            else:
                return {}
        elif self.data is None:
            outdata = {}
            for s in list(other.keys()):
                outdata[s] = -other[s]
            return outdata
        else:
            outdata = {}

            keys = {}  # keys will contain the merge of the two lists
            for s in list(self.data.keys()) + list(other.keys()):
                keys[s] = None

            for s in list(keys.keys()):
                if s in self.data:
                    sel = self.data[s]
                else:
                    sel = 0

                if s in other:
                    oel = other[s]
                else:
                    oel = 0

                outdata[s] = sel - oel

            return outdata


class logSummaryTimings(cachedLogClass):


    def __init__(self, logname, cache_dir):
        """Initializes the logSummaryTimings class with log and cache paths.

        Args:
            logname (str): Name of the log file.
            cache_dir (str): Directory where the cache file should be stored.
        """
        self.clInit(logname, cache_dir, ".ctstpk")

    def loadFromLog(self):
        """Parses the log file and stores the job statuses with timings."""
        jobs, self.startTime, self.endTime = parseSubmitLogFastRawTimings(self.logname)
        self.data = listAndInterpretRawStatuses(jobs, listStatusesTimings)
        return

    def isActive(self):
        """Determines if there are any active jobs in the log.

        Returns:
            bool: True if there are active jobs, False otherwise.
        """
        active = False
        for k in list(self.data.keys()):
            if k not in ["Completed", "Removed"]:
                if len(self.data[k]) > 0:
                    # Enough that at least one non Completed/removed job exist
                    active = True
        return active

    def merge(self, other):
        """Merges the current data with another dataset.

        Args:
            other (dict): The other dataset to merge with.

        Returns:
            dict: The merged dataset, including job statuses with timings.
        """
        if other is None:
            return self.data
        elif self.data is None:
            return other
        else:
            for k in list(self.data.keys()):
                try:
                    other[k] += self.data[k]
                except KeyError:  # missing key
                    other[k] = self.data[k]
            return other

    def diff(self, other):
        """Finds differences between the current dataset and another dataset.

        Args:
            other (dict): The other dataset to compare with.

        Returns:
            dict: A dictionary with the differences in job statuses and timings.
        """
        if other is None:
            outdata = {}
            if self.data is not None:
                for k in list(self.data.keys()):
                    outdata[k] = {"Exited": [], "Entered": self.data[k]}
            return outdata
        elif self.data is None:
            outdata = {}
            for k in list(other.keys()):
                outdata[k] = {"Entered": [], "Exited": other[k]}
            return outdata
        else:
            outdata = {}

            keys = {}  # keys will contain the merge of the two lists

            for s in list(self.data.keys()) + list(other.keys()):
                keys[s] = None

            for s in list(keys.keys()):
                sel = []
                if s in self.data:
                    for sel_e in self.data[s]:
                        sel.append(sel_e[0])

                oel = []
                if s in other:
                    for oel_e in other[s]:
                        oel.append(oel_e[0])

                #################
                # Need to finish

                outdata_s = {"Entered": [], "Exited": []}
                outdata[s] = outdata_s

                sset = set(sel)
                oset = set(oel)

                entered_set = sset.difference(oset)
                entered = []
                if s in self.data:
                    for sel_e in self.data[s]:
                        if sel_e[0] in entered_set:
                            entered.append(sel_e)

                exited_set = oset.difference(sset)
                exited = []
                if s in other:
                    for oel_e in other[s]:
                        if oel_e[0] in exited_set:
                            exited.append(oel_e)

                outdata_s["Entered"] = entered
                outdata_s["Exited"] = exited
            return outdata


# -------------- Multiple Log classes ------------------------


class cacheDirClass:

    def __init__(
        self,
        logClass,
        dirname,
        log_prefix,
        log_suffix=".log",
        cache_ext=".cifpk",
        inactive_files=None,
        inactive_timeout=24 * 3600,
        cache_dir=None,
        wrapperClass=None,
        username=None,
    ):
        
        self.cdInit(
            logClass,
            dirname,
            log_prefix,
            log_suffix,
            cache_ext,
            inactive_files,
            inactive_timeout,
            cache_dir,
            wrapperClass=wrapperClass,
            username=username,
        )

    def cdInit(
        self,
        logClass,
        dirname,
        log_prefix,
        log_suffix=".log",
        cache_ext=".cifpk",
        inactive_files=None,
        inactive_timeout=24 * 3600,
        cache_dir=None,
        wrapperClass=None,
        username=None,
    ):
        

        self.wrapperClass = wrapperClass
        self.username = username

        self.logClass = logClass
        self.dirname = dirname
        if cache_dir is None:
            cache_dir = dirname
        self.cache_dir = cache_dir
        self.log_prefix = log_prefix
        self.log_suffix = log_suffix
        self.inactive_timeout = inactive_timeout
        self.inactive_files_cache = os.path.join(cache_dir, log_prefix + log_suffix + cache_ext)
        if inactive_files is None:
            if os.path.isfile(self.inactive_files_cache):
                self.inactive_files = loadCache(self.inactive_files_cache)
            else:
                self.inactive_files = []
        else:
            self.inactive_files = inactive_files
        return

    def getFileList(self, active_only):
        

        prefix_len = len(self.log_prefix)
        suffix_len = len(self.log_suffix)
        files = []
        fnames = os.listdir(self.dirname)
        for fname in fnames:
            if (
                (fname[:prefix_len] == self.log_prefix)
                and (fname[-suffix_len:] == self.log_suffix)
                and ((not active_only) or (fname not in self.inactive_files))
            ):
                files.append(fname)
        return files

    def has_changed(self):

        ch = False
        fnames = self.getFileList(active_only=True)
        for fname in fnames:
            if (self.wrapperClass is not None) and (self.username is not None):
                obj = self.wrapperClass.getObj(
                    logname=os.path.join(self.dirname, fname), cache_dir=self.cache_dir, username=self.username
                )
            else:
                obj = self.logClass(os.path.join(self.dirname, fname), self.cache_dir)

            ch = ch or obj.has_changed()  # it is enough that one changes
        return ch

    def load(self, active_only=True):

        mydata = None
        new_inactives = []

        # get list of log files
        fnames = self.getFileList(active_only)

        now = time.time()
        # load and merge data
        for fname in fnames:
            absfname = os.path.join(self.dirname, fname)
            if os.path.getsize(absfname) < 1:
                continue  # skip empty files
            last_mod = os.path.getmtime(absfname)
            if (self.wrapperClass is not None) and (self.username is not None):
                obj = self.wrapperClass.getObj(logname=absfname, cache_dir=self.cache_dir, username=self.username)
            else:
                obj = self.logClass(absfname, self.cache_dir)
            obj.load()
            mydata = obj.merge(mydata)
            if ((now - last_mod) > self.inactive_timeout) and (not obj.isActive()):
                new_inactives.append(fname)
        self.data = mydata

        # try to save inactive files in the cache
        # if one was looking at inactive only
        if active_only and (len(new_inactives) > 0):
            self.inactive_files += new_inactives
            try:
                saveCache(self.inactive_files_cache, self.inactive_files)
            except OSError:
                return  # silently ignore, this was a load in the end

        return

    def diff(self, other):


        if (self.wrapperClass is not None) and (self.username is not None):
            dummyobj = self.wrapperClass.getObj(os.path.join(self.dirname, "dummy.txt"), self.cache_dir, self.username)
        else:
            dummyobj = self.logClass(os.path.join(self.dirname, "dummy.txt"), self.cache_dir)

        dummyobj.data = self.data  # a little rough but works
        return dummyobj.diff(other)


class dirSummary(cacheDirClass):


    def __init__(
        self,
        dirname,
        log_prefix,
        log_suffix=".log",
        cache_ext=".cifpk",
        inactive_files=None,
        inactive_timeout=24 * 3600,
        cache_dir=None,
    ):
  

        self.cdInit(logSummary, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir)


class dirCompleted(cacheDirClass):
  
    def __init__(
        self,
        dirname,
        log_prefix,
        log_suffix=".log",
        cache_ext=".cifpk",
        inactive_files=None,
        inactive_timeout=24 * 3600,
        cache_dir=None,
    ):
       

        self.cdInit(
            logCompleted, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir
        )


class dirCounts(cacheDirClass):
 

    def __init__(
        self,
        dirname,
        log_prefix,
        log_suffix=".log",
        cache_ext=".cifpk",
        inactive_files=None,
        inactive_timeout=24 * 3600,
        cache_dir=None,
    ):
       
        self.cdInit(logCounts, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir)


class dirSummaryTimings(cacheDirClass):


    def __init__(
        self,
        dirname,
        log_prefix,
        log_suffix=".log",
        cache_ext=".cifpk",
        inactive_files=None,
        inactive_timeout=24 * 3600,
        cache_dir=None,
    ):
      

        self.cdInit(
            logSummaryTimings, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir
        )


##############################################################################
#
# Low level functions
#
##############################################################################

################################
#  Condor log parsing functions
################################

# Status codes
# ------------
# 000 - Job submitted
# 001 - Job executing
# 002 - Error in executable
# 003 - Job was checkpointed
# 004 - Job was evicted
# 005 - Job terminated
# 006 - Image size of job updated
# 007 - Shadow exception
# 008 - <Not used>
# 009 - Job was aborted
# 010 - Job was suspended
# 011 - Job was unsuspended
# 012 - Job was held
# 013 - Job was released
# 014 - Parallel node executed (not used here)
# 015 - Parallel node terminated (not used here)
# 016 - POST script terminated
# 017 - Job submitted to Globus
# 018 - Globus submission failed
# 019 - Globus Resource Back Up
# 020 - Detected Down Globus Resource
# 021 - Remote error
# 022 - Remote system diconnected
# 023 - Remote system reconnected
# 024 - Remote system cannot recconect
# 025 - Grid Resource Back Up
# 026 - Detected Down Grid Resource
# 027 - Job submitted to grid resource
# 028 - Job ad information event triggered
# 029 - The job's remote status is unknown
# 030 - The job's remote status is known again

# Flags in the first char
# 0XX - No Flag
# YXX - Y is number of flags set


def get_new_status(old_status, new_status):
    """Determines the updated status based on the old and new statuses

    Args:
        old_status (str): The current status of the job.
        new_status (str): The new status of the job.

    Returns:
        str: The updated status after applying the logic for status transitions.
    """
    # keep the old status unless you really want to change
    status = old_status

    if new_status in ("019", "020", "025", "026", "022", "023", "010", "011", "029", "030"):
        # these are intermediate states, so just flip a bit
        if new_status in ("020", "026", "022", "010", "029"):  # connection lost
            status = str(int(old_status[0]) + 1) + old_status[1:]
        else:
            if old_status[0] != "0":  # may have already fixed it, out of order
                status = str(int(old_status[0]) - 1) + old_status[1:]
            # else keep the old one
    elif new_status in ("004", "007", "024"):
        # this is an abort... back to idle/wait
        status = "000"
    elif new_status in ("003", "006", "008", "028"):
        pass  # do nothing, that was just informational
    else:
        # a significant status found, use it
        status = new_status

    return status


def parseSubmitLogFastRaw(fname):
    """Parses a log file and extracts job statuses without timing information.

    Args:
        fname (str): The path to the log file to be parsed.

    Returns:
        dict: A dictionary where keys are job IDs and values are their corresponding statuses.
    """
    jobs = {}

    size = os.path.getsize(fname)
    if size == 0:
        # nothing to read, if empty
        return jobs

    with open(fname) as fd:
        buf = mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)

        idx = 0

        while (idx + 5) < size:  # else we are at the end of the file
            # format
            # 023 (123.2332.000) Bla

            # first 3 chars are status
            status = buf[idx : idx + 3]
            idx += 5
            # extract job id
            i1 = buf.find(b")", idx)
            if i1 < 0:
                break
            jobid = buf[idx : i1 - 4]
            idx = i1 + 1

            if jobid in jobs:
                jobs[jobid] = get_new_status(jobs[jobid], status)
            else:
                jobs[jobid] = status

            i1 = buf.find(b"...", idx)
            if i1 < 0:
                break
            idx = i1 + 4  # the 3 dots plus newline

        buf.close()

    return jobs


def parseSubmitLogFastRawTimings(fname):
    """Parses a log file and extracts job statuses along with timing information.

    Args:
        fname (str): The path to the log file to be parsed.

    Returns:
        tuple: A tuple containing:
            - dict: A dictionary where keys are job IDs and values are tuples
            - str: The timestamp of the first log entry.
            - str: The timestamp of the last log entry.
    """
    jobs = {}

    first_time = None
    last_time = None

    size = os.path.getsize(fname)
    if size == 0:
        # nothing to read, if empty
        return jobs, first_time, last_time

    with open(fname) as fd:
        buf = mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)

        idx = 0

        while (idx + 5) < size:  # else we are at the end of the file
            # format
            # 023 (123.2332.000) MM/DD HH:MM:SS

            # first 3 chars are status
            status = buf[idx : idx + 3]
            idx += 5
            # extract job id
            i1 = buf.find(b")", idx)
            if i1 < 0:
                break
            jobid = buf[idx : i1 - 4]
            idx = i1 + 2
            # extract time
            line_time = buf[idx : idx + 14]
            idx += 16

            if first_time is None:
                first_time = line_time
            last_time = line_time

            if jobid in jobs:
                if status == b"001":
                    running_time = line_time
                else:
                    running_time = jobs[jobid][2]
                jobs[jobid] = (
                    get_new_status(jobs[jobid][0], status),
                    jobs[jobid][1],
                    running_time,
                    line_time,
                )  # start time never changes
            else:
                jobs[jobid] = (status, line_time, b"", line_time)

            i1 = buf.find(b"...", idx)
            if i1 < 0:
                break
            idx = i1 + 4  # the 3 dots plus newline

        buf.close()
    return jobs, first_time, last_time


def parseSubmitLogFastRawCallback(fname, callback):
    """Parses a log file and applies a callback function to each status change.

    Args:
        fname (str): The path to the log file to be parsed.
        callback (function): A callback function that takes three arguments: status,
            time, and job ID.
    """

    jobs = {}

    size = os.path.getsize(fname)
    if size == 0:
        # nothing to read, if empty
        return

    with open(fname) as fd:
        buf = mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)

        idx = 0

        while (idx + 5) < size:  # else we are at the end of the file
            # format
            # 023 (123.2332.000) MM/DD HH:MM:SS

            # first 3 chars are status
            status = buf[idx : idx + 3]
            idx += 5
            # extract job id
            i1 = buf.find(b")", idx)
            if i1 < 0:
                break
            jobid = buf[idx : i1 - 4]
            idx = i1 + 2
            # extract time
            line_time = buf[idx : idx + 14]
            idx += 16

            if jobid in jobs:
                old_status = jobs[jobid]
                new_status = get_new_status(old_status, status)
                if new_status != old_status:
                    callback(new_status, line_time, jobid)
                    if new_status in ("005", "009"):
                        del jobs[jobid]  # end of live, don't need it anymore
                    else:
                        jobs[jobid] = new_status
            else:
                jobs[jobid] = status
                callback(status, line_time, jobid)

            i1 = buf.find("...", idx)
            if i1 < 0:
                break
            idx = i1 + 4  # the 3 dots plus newline

        buf.close()
    return


def rawJobId2Nr(str):

    arr = str.split(b".")
    try:
        return (int(arr[0]), int(arr[1]))
    except (IndexError, ValueError):
        return (-1, -1)  # invalid


def rawTime2cTime(instr, year):

    try:
        ctime = time.mktime(
            (year, int(instr[0:2]), int(instr[3:5]), int(instr[6:8]), int(instr[9:11]), int(instr[12:14]), 0, 0, -1)
        )
    except ValueError:
        return -1  # invalid
    return ctime


def rawTime2cTimeLastYear(instr):
    
    now = time.time()
    current_year = time.localtime(now)[0]
    ctime = rawTime2cTime(instr, current_year)
    if ctime <= now:
        return ctime
    else:  # cannot be in the future... it must have been in the past year
        ctime = rawTime2cTime(instr, current_year - 1)
        return ctime


def diffTimes(start_time, end_time, year):

    start_ctime = rawTime2cTime(start_time, year)
    end_ctime = rawTime2cTime(end_time, year)
    if (start_time < 0) or (end_time < 0):
        return -1  # invalid

    return int(end_ctime) - int(start_ctime)


def diffTimeswWrap(start_time, end_time, year, wrap_time):

    if start_time > wrap_time:
        start_year = year
    else:
        start_year = year + 1
    start_ctime = rawTime2cTime(start_time, start_year)

    if end_time > wrap_time:
        end_year = year
    else:
        end_year = year + 1
    end_ctime = rawTime2cTime(end_time, end_year)

    if (start_time < 0) or (end_time < 0):
        return -1  # invalid

    return int(end_ctime) - int(start_ctime)


def interpretStatus(status, default_status="Idle"):

    if status == 5:
        return "Completed"
    elif status == 9:
        return "Removed"
    elif status == 1:
        return "Running"
    elif status == 12:
        return "Held"
    elif status == 0:
        return "Wait"
    elif status == 17:
        return "Idle"
    else:
        return default_status


def countStatuses(jobs):

    counts = {}
    for e in list(jobs.values()):
        try:
            counts[e] += 1
        except KeyError:
            # there are only few possible values, so exceptions is faster
            counts[e] = 1
    return counts


def countAndInterpretRawStatuses(jobs_raw):


    outc = {}
    tmpc = countStatuses(jobs_raw)
    for s in list(tmpc.keys()):
        i_s = interpretStatus(int(s[1:]))  # ignore flags
        try:
            outc[i_s] += tmpc[s]
        except KeyError:
            # there are only few possible values, using exceptions is faster
            outc[i_s] = tmpc[s]
    return outc


def listStatuses(jobs):


    status = {}
    for k, e in list(jobs.items()):
        try:
            status[e].append(k)
        except KeyError:
            # there are only few possible values, using exceptions is faster
            status[e] = [k]
    return status


def listStatusesTimings(jobs):


    status = {}
    for k, e in list(jobs.items()):
        try:
            status[e[0]].append((k,) + e[1:])
        except KeyError:
            # there are only few possible values, using exceptions is faster
            status[e[0]] = [(k,) + e[1:]]
    return status


def listAndInterpretRawStatuses(jobs_raw, invert_function):

    outc = {}
    tmpc = invert_function(jobs_raw)
    for s in list(tmpc.keys()):
        try:
            i_s = interpretStatus(int(s[1:]))  # ignore flags
        except Exception:  # file corrupted, protect
            # print "lairs: Unexpect line: %s"%s
            continue
        try:
            outc[i_s] += tmpc[s]
        except KeyError:
            # there are only few possible values, using exceptions is faster
            outc[i_s] = tmpc[s]
    return outc


def parseSubmitLogFast(fname):


    jobs_raw = parseSubmitLogFastRaw(fname)
    jobs = {}
    for k in list(jobs_raw.keys()):
        jobs[rawJobId2Nr(k)] = int(jobs_raw[k])
    return jobs


def parseSubmitLogFastTimings(fname, year=None):


    jobs_raw, first_time, last_time = parseSubmitLogFastRawTimings(fname)

    if year is None:
        year = time.localtime()[0]

    # it wrapped over, dates really in previous year
    year_wrap = first_time > last_time

    jobs = {}
    if year_wrap:
        year1 = year - 1
        for k in list(jobs_raw.keys()):
            el = jobs_raw[k]
            status = int(el[0])
            diff_time = diffTimeswWrap(el[1], el[3], year1, first_time)
            if status == 5:
                running_time = diffTimeswWrap(el[2], el[3], year1, first_time)
            else:
                running_time = None
            jobs[rawJobId2Nr(k)] = (status, diff_time, running_time)
    else:
        for k in list(jobs_raw.keys()):
            el = jobs_raw[k]
            status = int(el[0])
            diff_time = diffTimes(el[1], el[3], year)
            if status == 5:
                running_time = diffTimes(el[2], el[3], year)
            else:
                running_time = None
            jobs[rawJobId2Nr(k)] = (status, diff_time, running_time)

    return jobs


################################
#  Cache handling functions
################################


def loadCache(fname):

    try:
        data = util.file_pickle_load(fname)
    except Exception as e:
        raise RuntimeError("Could not read %s" % fname) from e
    return data


def saveCache(fname, data):

    util.file_pickle_dump(fname, data)
    return
