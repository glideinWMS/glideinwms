# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements classes and functions to parse the condor log files.

NOTE:
Inactive files are log files that have only completed or removed entries.
Such files will not change in the future.
"""

import mmap
import os
import os.path
import stat
import time

from . import util

# -------------- Single Log classes ------------------------


class cachedLogClass:
    """Abstract base class for most Log Parsers in lib/condorLogParser and factory/glideFactoryLogParser.
    (Virtual, do not use directly)

    The Constructor for inherited classes needs to define logname and cachename
    (possibly by using clInit) as well as the methods loadFromLog, merge, and isActive.

    Attributes:
        logname (str): The name of the log file.
        cachename (str): The name of the cache file.
    """

    def clInit(self, logname, cache_dir, cache_ext):
        """Initializes the log and cache names.

        Args:
            logname (str): The name of the log file.
            cache_dir (str): The directory where the cache is stored.
            cache_ext (str): The extension for the cache file.
        """
        self.logname = logname
        if cache_dir is None:
            self.cachename = logname + cache_ext
        else:
            self.cachename = os.path.join(cache_dir, os.path.basename(logname) + cache_ext)

    def has_changed(self):
        """Compares to cache, and tells if the log file has changed since last cached.

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
        """Loads data from the most recent file. Updates the cache if needed.

        If the file has not changed, use the cache.
        The cache is typically named something like filename.ftstpk and is in a pickle format.
        If file is newer, use the `loadFromLog()` method of the child class to load from the file.
        Then, save the values in the pickle cache.
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

    def loadCache(self):
        """Loads data from the cache file."""
        self.data = loadCache(self.cachename)
        return

    def loadFromLog(self):
        """Loads data from the log file.

        This method should be implemented by subclasses.
        """
        raise RuntimeError("loadFromLog not implemented!")

    ####### PRIVATE ###########
    def saveCache(self):
        """Saves data to the cache file."""
        saveCache(self.cachename, self.data)
        return


class logSummary(cachedLogClass):
    """Keeps track of jobs in various statuses ('Wait', 'Idle', 'Running', 'Held', 'Completed', 'Removed').

    This data is available in self.data dictionary, for example:
    `self.data = {'Idle': ['123.003', '123.004'], 'Running': ['123.001', '123.002']}`
    """

    def __init__(self, logname, cache_dir):
        """Initializes logSummary with log and cache names.

        Args:
            logname (str): The name of the log file.
            cache_dir (str): The directory where the cache is stored.
        """
        self.clInit(logname, cache_dir, ".cstpk")

    def loadFromLog(self):
        """Parses the condor activity log and interprets the HTCondor status codes.

        Stores the result in `self.data`.
        """
        jobs = parseSubmitLogFastRaw(self.logname)
        self.data = listAndInterpretRawStatuses(jobs, listStatuses)
        return

    def isActive(self):
        """Determines if there are any active jobs.

        Returns:
            bool: True if there are active jobs, False otherwise.
        """
        active = False
        for k in list(self.data.keys()):
            if k not in ["Completed", "Removed"]:
                if len(self.data[k]) > 0:
                    active = True  # it is enough that at least one non Completed/Removed job exists
        return active

    def merge(self, other_data):
        """Merges the current log data with another dataset.

        Args:
            other_data (dict): The dataset to merge with.

        Returns:
            dict: The merged data. May modify also `other_data`.
        """
        if other_data is None:
            return self.data
        elif self.data is None:
            return other_data
        else:
            for k in list(self.data.keys()):
                try:
                    other_data[k] += self.data[k]
                except KeyError:  # missing key
                    other_data[k] = self.data[k]
            return other_data

    def diff(self, other_data):
        """Finds differences between the current log dataset and another dataset.

        Used to compare the previous iteration with the current iteration.

        Performs symmetric difference on the two sets and
        creates a dictionary for each job status.

        Args:
            other_data (dict): The dataset to compare with.

        Returns:
            dict: A dictionary with the differences, showing entered and exited jobs.
                `data[status]['Entered'|'Exited']` contains a list of jobs.
        """
        if other_data is None:
            outdata = {}
            if self.data is not None:
                for k in list(self.data.keys()):
                    outdata[k] = {"Exited": [], "Entered": self.data[k]}
            return outdata
        elif self.data is None:
            outdata = {}
            for k in list(other_data.keys()):
                outdata[k] = {"Entered": [], "Exited": other_data[k]}
            return outdata
        else:
            outdata = {}

            keys = {}  # keys will contain the merge of the two lists

            for s in list(self.data.keys()) + list(other_data.keys()):
                keys[s] = None

            for s in list(keys.keys()):
                if s in self.data:
                    sel = self.data[s]
                else:
                    sel = []

                if s in other_data:
                    oel = other_data[s]
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
    """Keeps track of counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
    and a list of completed jobs.

    This data is available in `self.data` dictionary, for example:
    `self.data = {'completed_jobs': ['123.002', '555.001'], 'counts': {'Idle': 1145, 'Completed': 2}}`
    """

    def __init__(self, logname, cache_dir):
        """Initializes logCompleted with log and cache names.

        Args:
            logname (str): The name of the log file.
            cache_dir (str): The directory where the cache is stored.
        """
        self.clInit(logname, cache_dir, ".clspk")

    def loadFromLog(self):
        """Loads information from condor_activity logs, interprets the HTCondor status codes,
        and stores the count per status and list of completed jobs.

        Stores the result in `self.data`.
        """
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
        """Determine if there are any active jobs.

        Returns:
            bool: True if there are active jobs, False otherwise.
        """
        active = False
        counts = self.data["counts"]
        for k in list(counts.keys()):
            if k not in ["Completed", "Removed"]:
                if counts[k] > 0:
                    # Enough that at least one non Completed/Removed job exists
                    active = True
        return active

    def merge(self, other_data):
        """Merges the current log data with another dataset.

        Args:
            other_data (dict): The dataset to merge with.

        Returns:
            dict: The merged data. May modify also `other_data`.
        """
        if other_data is None:
            return self.data
        elif self.data is None:
            return other_data
        else:
            for k in list(self.data["counts"].keys()):
                try:
                    other_data["counts"][k] += self.data["counts"][k]
                except KeyError:  # missing key
                    other_data["counts"][k] = self.data["counts"][k]
            other_data["completed_jobs"] += self.data["completed_jobs"]
            return other_data

    def diff(self, other_data):
        """Finds differences between the current log dataset and another dataset.

        For use in comparing the previous iteration with the current iteration.
        Uses a symmetric difference of sets.

        Args:
            other_data (dict): The dataset to compare with.

        Returns:
            dict: A dictionary with the differences, showing entered and exited jobs.
        """
        if other_data is None:
            if self.data is not None:
                outcj = {"Exited": [], "Entered": self.data["completed_jobs"]}
                outdata = {"counts": self.data["counts"], "completed_jobs": outcj}
            else:
                outdata = {"counts": {}, "completed_jobs": {"Exited": [], "Entered": []}}
            return outdata
        elif self.data is None:
            outcj = {"Entered": [], "Exited": other_data["completed_jobs"]}
            outct = {}
            for s in list(other_data["counts"].keys()):
                outct[s] = -other_data["counts"][s]
            outdata = {"counts": outct, "completed_jobs": outcj}
            return outdata
        else:
            outct = {}
            outcj = {"Entered": [], "Exited": []}
            outdata = {"counts": outct, "completed_jobs": outcj}

            keys = {}  # keys will contain the merge of the two lists
            for s in list(self.data["counts"].keys()) + list(other_data["counts"].keys()):
                keys[s] = None

            for s in list(keys.keys()):
                if s in self.data["counts"]:
                    sct = self.data["counts"][s]
                else:
                    sct = 0

                if s in other_data["counts"]:
                    oct = other_data["counts"][s]
                else:
                    oct = 0

                outct[s] = sct - oct

            sel = self.data["completed_jobs"]
            oel = other_data["completed_jobs"]
            sset = set(sel)
            oset = set(oel)

            outcj["Entered"] = list(sset.difference(oset))
            outcj["Exited"] = list(oset.difference(sset))

            return outdata


class logCounts(cachedLogClass):
    """Keeps track of counts of statuses (Wait, Idle, Running, Held, Completed, Removed).

    This data is available in `self.data` dictionary, for example:
    `self.data = {'Idle': 1145, 'Completed': 2}`
    """

    def __init__(self, logname, cache_dir):
        """Initializes logCounts with log and cache names.

        Args:
            logname (str): The name of the log file.
            cache_dir (str): The directory where the cache is stored.
        """
        self.clInit(logname, cache_dir, ".clcpk")

    def loadFromLog(self):
        """Loads and parses jobs from the log file, then counts, interprets and stores the counts of various job statuses.

        Stores the result in `self.data`.
        """
        jobs = parseSubmitLogFastRaw(self.logname)
        self.data = countAndInterpretRawStatuses(jobs)
        return

    def isActive(self):
        """Determines if there are any active jobs.

        Returns:
            bool: True if there are active jobs, False otherwise.
        """
        active = False
        for k in list(self.data.keys()):
            if k not in ["Completed", "Removed"]:
                if self.data[k] > 0:
                    active = True  # Enough that at least one non Completed/Removed job exists
        return active

    def merge(self, other_data):
        """Merges the current log data with another dataset.

        Args:
            other_data (dict): The dataset to merge with.

        Returns:
            dict: The merged data. May modify also `other_data`.
        """
        if other_data is None:
            return self.data
        elif self.data is None:
            return other_data
        else:
            for k in list(self.data.keys()):
                try:
                    other_data[k] += self.data[k]
                except KeyError:  # missing key
                    other_data[k] = self.data[k]
            return other_data

    def diff(self, other_data):
        """Finds differences between the current log dataset and another dataset.

        Args:
            other_data (dict): The dataset to compare with.

        Returns:
            dict: A dictionary with the differences in counts.
        """
        if other_data is None:
            if self.data is not None:
                return self.data
            else:
                return {}
        elif self.data is None:
            outdata = {}
            for s in list(other_data.keys()):
                outdata[s] = -other_data[s]
            return outdata
        else:
            outdata = {}

            keys = {}  # keys will contain the merge of the two lists
            for s in list(self.data.keys()) + list(other_data.keys()):
                keys[s] = None

            for s in list(keys.keys()):
                if s in self.data:
                    sel = self.data[s]
                else:
                    sel = 0

                if s in other_data:
                    oel = other_data[s]
                else:
                    oel = 0

                outdata[s] = sel - oel

            return outdata


class logSummaryTimings(cachedLogClass):
    """Keeps track of jobs in various statuses (Wait, Idle, Running, Held, Completed, Removed) with timings.

    This data is available in `self.data` dictionary, for example:
    `self.data = {'Idle': ['123.003', '123.004'], 'Running': ['123.001', '123.002']}`
    """

    def __init__(self, logname, cache_dir):
        """Initializes logSummaryTimings with log and cache names.

        Args:
            logname (str): The name of the log file.
            cache_dir (str): The directory where the cache is stored.
        """
        self.clInit(logname, cache_dir, ".ctstpk")

    def loadFromLog(self):
        """Loads and parses jobs from the log file, including timings.

        Stores the result in `self.data`.
        """
        jobs, self.startTime, self.endTime = parseSubmitLogFastRawTimings(self.logname)
        self.data = listAndInterpretRawStatuses(jobs, listStatusesTimings)
        return

    def isActive(self):
        """Determines if there are any active jobs.

        Returns:
            bool: True if there are active jobs, False otherwise.
        """
        active = False
        for k in list(self.data.keys()):
            if k not in ["Completed", "Removed"]:
                if len(self.data[k]) > 0:
                    # Enough that at least one non Completed/Removed job exists
                    active = True
        return active

    def merge(self, other_data):
        """Merges the current log data with another dataset.

        Args:
            other_data (dict): The dataset to merge with. May modify also `other_data`.

        Returns:
            dict: The merged data, including job statuses with timings.
        """
        if other_data is None:
            return self.data
        elif self.data is None:
            return other_data
        else:
            for k in list(self.data.keys()):
                try:
                    other_data[k] += self.data[k]
                except KeyError:  # missing key
                    other_data[k] = self.data[k]
            return other_data

    def diff(self, other_data):
        """Finds differences between the current log dataset and another dataset.

        Args:
            other_data (dict): The dataset to compare with.

        Returns:
            dict: A dictionary with the differences, showing entered and exited jobs and timings.
                `data[status]['Entered'|'Exited']` is a list of jobs.
        """
        if other_data is None:
            outdata = {}
            if self.data is not None:
                for k in list(self.data.keys()):
                    outdata[k] = {"Exited": [], "Entered": self.data[k]}
            return outdata
        elif self.data is None:
            outdata = {}
            for k in list(other_data.keys()):
                outdata[k] = {"Entered": [], "Exited": other_data[k]}
            return outdata
        else:
            outdata = {}

            keys = {}  # keys will contain the merge of the two lists

            for s in list(self.data.keys()) + list(other_data.keys()):
                keys[s] = None

            for s in list(keys.keys()):
                sel = []
                if s in self.data:
                    for sel_e in self.data[s]:
                        sel.append(sel_e[0])

                oel = []
                if s in other_data:
                    for oel_e in other_data[s]:
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
                if s in other_data:
                    for oel_e in other_data[s]:
                        if oel_e[0] in exited_set:
                            exited.append(oel_e)

                outdata_s["Entered"] = entered
                outdata_s["Exited"] = exited
            return outdata


# -------------- Multiple Log classes ------------------------


class cacheDirClass:
    """This is the base class for all the directory log Parser classes.
    It parses some/all log files in a directory.
    It should generally not be called directly. Rather,
    call one of the inherited classes.
    """

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
        """Initializes the cacheDirClass.

        Args:
            logClass: The class used for parsing the logs.
            dirname (str): The directory containing the log files.
            log_prefix (str): The prefix for log files.
            log_suffix (str): The suffix for log files. Defaults to ".log".
            cache_ext (str): The extension for the cache file. Defaults to ".cifpk".
            inactive_files (list): List of inactive files. If None, will be reloaded from cache.
            inactive_timeout (int): Time in seconds before a file can be declared inactive. Defaults to 24 * 3600.
            cache_dir (str): Directory for the cache files. If None, use dirname.
            wrapperClass: The wrapper class, if any.
            username (str): The username, if any.
        """
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
        """Initializes the cache directory.

        Args:
            logClass: The class used for parsing the logs.
            dirname (str): The directory containing the log files.
            log_prefix (str): The prefix for log files.
            log_suffix (str): The suffix for log files. Defaults to ".log".
            cache_ext (str): The extension for the cache file. Defaults to ".cifpk".
            inactive_files (list): List of inactive files. If None, will be reloaded from cache.
            inactive_timeout (int): Time in seconds before a file can be declared inactive. Defaults to 24 * 3600.
            cache_dir (str): Directory for the cache files. If None, use dirname.
            wrapperClass: The wrapper class, if any.
            username (str): The username, if any.
        """
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

    def getFileList(self, active_only):
        """Lists the directory and returns files that match the
        prefix/suffix extensions and are active (modified within
        inactivity_timeout).

        Args:
            active_only (bool): If True, only return active files.

        Returns:
            list: A list of log files.
        """
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
        """Checks all the files in the list to see if any have changed.

        Returns:
            bool: True if any file has changed, False otherwise.
        """
        ch = False
        fnames = self.getFileList(active_only=True)
        for fname in fnames:
            if (self.wrapperClass is not None) and (self.username is not None):
                obj = self.wrapperClass.get_obj(
                    logname=os.path.join(self.dirname, fname), cache_dir=self.cache_dir, username=self.username
                )
            else:
                obj = self.logClass(os.path.join(self.dirname, fname), self.cache_dir)

            ch = ch or obj.has_changed()  # it is enough that one changes
        return ch

    def load(self, active_only=True):
        """For each file in the file list, call the appropriate load()
        function for that file. Merge all the data from all the files
        into temporary array mydata then set it to self.data.
        It will save the list of inactive_files it finds in a cache
        for quick access.

        This function should set `self.data`.

        Args:
            active_only (bool): If True, only load active files.
        """
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
                obj = self.wrapperClass.get_obj(logname=absfname, cache_dir=self.cache_dir, username=self.username)
            else:
                obj = self.logClass(absfname, self.cache_dir)
            obj.load()
            mydata = obj.merge(mydata)
            if ((now - last_mod) > self.inactive_timeout) and (not obj.isActive()):
                new_inactives.append(fname)
        self.data = mydata

        # Try to save inactive files in the cache if one was looking at inactive only
        if active_only and (len(new_inactives) > 0):
            self.inactive_files += new_inactives
            try:
                saveCache(self.inactive_files_cache, self.inactive_files)
            except OSError:
                return  # silently ignore, this was a load in the end

    def diff(self, other_data):
        """Compare self data with other data.

        This is a virtual function that just calls the class
        diff() function.

        Args:
            other_data (dict): The data to compare with.

        Returns:
            dict: The differences between `self.data` and `other_data`.
        """
        if (self.wrapperClass is not None) and (self.username is not None):
            dummyobj = self.wrapperClass.get_obj(os.path.join(self.dirname, "dummy.txt"), self.cache_dir, self.username)
        else:
            dummyobj = self.logClass(os.path.join(self.dirname, "dummy.txt"), self.cache_dir)

        dummyobj.data = self.data  # a little rough but works
        return dummyobj.diff(other_data)


class dirSummary(cacheDirClass):
    """Keeps track of jobs in various statuses (Wait, Idle, Running, Held, Completed, Removed).

    This data is available in `self.data` dictionary, for example:
    `self.data = {'Idle': ['123.003', '123.004'], 'Running': ['123.001', '123.002']}`
    """

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
        """Initializes dirSummary with log and cache parameters.

        Args:
            dirname (str): The directory containing the log files.
            log_prefix (str): The prefix for log files.
            log_suffix (str): The suffix for log files. Defaults to ".log".
            cache_ext (str): The extension for the cache file. Defaults to ".cifpk".
            inactive_files (list): List of inactive files. If None, will be reloaded from cache.
            inactive_timeout (int): Time in seconds before a file can be declared inactive. Defaults to 24 * 3600.
            cache_dir (str): Directory for the cache files. If None, use dirname.
        """
        self.cdInit(logSummary, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir)


class dirCompleted(cacheDirClass):
    """Keeps track of counts of statuses (Wait, Idle, Running, Held, Completed, Removed)
    and a list of completed jobs.

    This data is available in `self.data` dictionary, for example:
    `self.data = {'completed_jobs': ['123.002', '555.001'], 'counts': {'Idle': 1145, 'Completed': 2}}`
    """

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
        """Initializes dirCompleted with log and cache parameters.

        Args:
            dirname (str): The directory containing the log files.
            log_prefix (str): The prefix for log files.
            log_suffix (str): The suffix for log files. Defaults to ".log".
            cache_ext (str): The extension for the cache file. Defaults to ".cifpk".
            inactive_files (list): List of inactive files. If None, will be reloaded from cache.
            inactive_timeout (int): Time in seconds before a file can be declared inactive. Defaults to 24 * 3600.
            cache_dir (str): Directory for the cache files. If None, use dirname.
        """
        self.cdInit(
            logCompleted, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir
        )


class dirCounts(cacheDirClass):
    """Keeps track of counts of statuses (Wait, Idle, Running, Held, Completed, Removed).

    This data is available in `self.data` dictionary, for example:
    `self.data = {'Idle': 1145, 'Completed': 2}`
    """

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
        """Initializes dirCounts with log and cache parameters.

        Args:
            dirname (str): The directory containing the log files.
            log_prefix (str): The prefix for log files.
            log_suffix (str): The suffix for log files. Defaults to ".log".
            cache_ext (str): The extension for the cache file. Defaults to ".cifpk".
            inactive_files (list): List of inactive files. If None, will be reloaded from cache.
            inactive_timeout (int): Time in seconds before a file can be declared inactive. Defaults to 24 * 3600.
            cache_dir (str): Directory for the cache files. If None, use dirname.
        """
        self.cdInit(logCounts, dirname, log_prefix, log_suffix, cache_ext, inactive_files, inactive_timeout, cache_dir)


class dirSummaryTimings(cacheDirClass):
    """Keeps track of jobs in various statuses (Wait, Idle, Running, Held, Completed, Removed) with timings.

    This data is available in `self.data` dictionary, for example:
    ```
    self.data = {'Idle': [('123.003', '09/28 01:38:53', '09/28 01:42:23', '09/28 08:06:33'),
                          ('123.004', '09/28 02:38:53', '09/28 02:42:23', '09/28 09:06:33')],
                 'Running': [('123.001', '09/28 01:32:53', '09/28 01:43:23', '09/28 08:07:33'),
                             ('123.002', '09/28 02:38:53', '09/28 03:42:23', '09/28 06:06:33')]
                 }
    ```
    """

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
        """Initializes dirSummaryTimings with log and cache parameters.

        Args:
            dirname (str): The directory containing the log files.
            log_prefix (str): The prefix for log files.
            log_suffix (str): The suffix for log files. Defaults to ".log".
            cache_ext (str): The extension for the cache file. Defaults to ".cifpk".
            inactive_files (list): List of inactive files. If None, will be reloaded from cache.
            inactive_timeout (int): Time in seconds before a file can be declared inactive. Defaults to 24 * 3600.
            cache_dir (str): Directory for the cache files. If None, use dirname.
        """
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
# 022 - Remote system disconnected
# 023 - Remote system reconnected
# 024 - Remote system cannot reconnect
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
    """Determines the updated job status based on the old and new statuses.

    Args:
        old_status (bytes): The current Globus job status.
        new_status (bytes): The new Globus job status.

    Returns:
        bytes: The updated job status after applying the logic for status correction in transitions.
    """
    # keep the old status unless you really want to change
    status = old_status

    if new_status in (b"019", b"020", b"025", b"026", b"022", b"023", b"010", b"011", b"029", b"030"):
        # these are intermediate states, so just flip a bit
        if new_status in (b"020", b"026", b"022", b"010", b"029"):  # connection lost
            status = bytes([int(old_status[0]) + 1]) + old_status[1:]
        else:
            if bytes([old_status[0]]) != b"0":  # may have already fixed it, out of order
                status = bytes([int(old_status[0]) - 1]) + old_status[1:]
            # else keep the old one
    elif new_status in (b"004", b"007", b"024"):
        # this is an abort... back to idle/wait
        status = b"000"
    elif new_status in (b"003", b"006", b"008", b"028"):
        pass  # do nothing, that was just informational
    else:
        # a significant status found, use it
        status = new_status

    return status


def parseSubmitLogFastRaw(fname):
    """Parses a HTCondor submit log file and extracts job statuses without timing information.

    Additional notes: The line format of the HTCondor submit log file (aka Job Event Log which is a sequence of event records), as of HTCondor 24.12.x, is shown below.
    More information can be found at https://htcondor.readthedocs.io/en/latest/users-manual/managing-a-job.html#in-the-job-event-log-file:
    ```
    jobEventType (ClusterId.ProcessId.NodeNumber) YYYY-MM-DD HH:MM:SS jobEventBriefDescription
            Optional additional info specific to the event under question
    ... (job event separator)
    ```

    Args:
        fname (str): Filename of the log to parse.

    Returns:
        dict: A dictionary representing job status information. The keys denote job IDs and their values indicate the job event type, which is a 3-digit code, for the corresponding jobs.
            For example, {b'1583.004': b'000', b'3616.008': b'009'}
    """
    jobs = {}

    size = os.path.getsize(fname)
    if size == 0:
        # nothing to read, if empty
        return jobs

    with open(fname, "rb") as fd:
        with mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ) as buf:
            idx = 0

            while (idx + 5) < size:  # else we are at the end of the file format
                # Old format:
                # 001 (123.2332.000) MM/DD HH:MM:SS Blablabla
                # ...
                # New format:
                # 001 (123.2332.000) YYYY-MM-DD HH:MM:SS Blablabla
                # ...

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

    return jobs


def parseSubmitLogFastRawTimings(fname):
    """Parses a HTCondor submit log file and extracts job statuses along with timing information.

    This method returns a dictionary consisting of job information such as the last known job status, job start time, job running time, and job end time.
    It also returns the first and last date in the file.

    Additional notes: The line format of the HTCondor submit log file (aka Job Event Log which is a sequence of event records), as of HTCondor 24.12.x, is shown below. More information can be found at https://htcondor.readthedocs.io/en/v10_0/users-manual/managing-a-job.html#in-the-job-event-log-file:
    ```
    jobEventType (ClusterId.ProcessId.NodeNumber) YYYY-MM-DD HH:MM:SS jobEventBriefDescription
            Optional additional info specific to the event under question
    ... (job event separator)
    ```

    NOTE: This method is invoked from `logSummaryTimings.loadFromLog()` and `parseSubmitLogFastTimings()` methods in this module.

    Args:
        fname (str): Filename of the log to parse.

    Returns:
        tuple: A tuple containing:
                - dict: A dictionary of bytestrings representing job information, where keys denote job IDs and values are tuples with job event type, start time, running time (if completed), and end time.
                - str: The timestamp of the first log entry.
                - str: The timestamp of the last log entry.
               For example:
               ```
                ( {b'9568.001': (b'000', b'2026-09-28 01:38:53', b'', b'2026-09-28 01:38:53'), b'9868.003': (b'005', b'2026-09-28 01:48:52', b'2026-09-28 16:11:23', b'2026-09-28 20:31:53')},
                b'2026-09-28 01:38:53', b'2026-09-28 20:31:53' )
               ```
               ```
                ( {b'2357.001': (b'000', b'09/28 01:38:53', b'', b'09/28 01:38:53'), b'9868.003': (b'005', b'09/28 01:48:52', b'09/28 16:11:23', b'09/28 20:31:53')},
                b'09/28 01:38:53', b'09/28 20:31:53' )
               ```
    """
    jobs = {}

    first_time = None
    last_time = None

    size = os.path.getsize(fname)
    if size == 0:
        # nothing to read, if empty
        return jobs, first_time, last_time

    with open(fname, "rb") as fd:
        with mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ) as buf:
            idx = 0

            while (idx + 5) < size:  # else we are at the end of the file
                # Old format:
                # 001 (123.2332.000) MM/DD HH:MM:SS Blablabla
                # ...
                # New format:
                # 001 (123.2332.000) YYYY-MM-DD HH:MM:SS Blablabla
                # ...

                # extract job event type
                # first 3 chars represent 3-digit code for the job event type
                status = buf[idx : idx + 3]
                idx += 5
                # extract job id
                end_idx = buf.find(b")", idx)
                if end_idx != -1:
                    i1 = buf.rfind(b".", idx, end_idx)
                    if i1 < 0:
                        break
                    jobid = buf[idx:i1]
                else:
                    break
                idx = end_idx + 2
                # extract date and time
                i1 = buf.find(b" ", idx)
                if i1 != -1:
                    i2 = buf.find(b" ", i1 + 1)
                    if i2 < 0:
                        break
                    line_time = buf[idx:i2]
                else:
                    break
                idx = i2 + 1

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

    return jobs, first_time, last_time


# def parseSubmitLogFastRawCallback(fname, callback):
#    """Parses a HTCondor submit log file and invokes a callback function for each status change.

#    Args:
#        fname (str): Filename of the log to parse.
#        callback (function): Callback function to call for each status change.
#                             It takes three arguments: job status entered (str), time (str), and job ID (str).
#                             E.g: `callback(new_status_str, timestamp_str, job_str)`.
#    """
#    Removed because this method is currently not in use.


def rawJobId2Nr(job_identifier):
    """Convert the HTCondor submit log (aka job event log) representation of job identifier into (ClusterId, ProcessId) format.

    NOTE: This method is externally used in `glideFactoryLogParser.py` and `gWftLogParser.py` modules. Additionally, this method was also used previously in `parseSubmitLogFast()` and `parseSubmitLogFastTimings()` methods in this module.

    Args:
        job_identifier (bytes): Job identifier as a bytes literal in the format 'ClusterId.ProcessId'.

    Returns:
        tuple(int, int): A tuple consisting of two integers: ('ClusterId', 'ProcessId') or (-1, -1) in case of error.
    """
    arr = job_identifier.split(b".")
    try:
        return int(arr[0]), int(arr[1])
    except (IndexError, ValueError):
        return -1, -1  # Invalid


def rawTime2cTime(date_timestamp, year):
    """Convert the date and time representation existing in the HTCondor submit log into ctime, works only for the past year.

    NOTE: This method is used in `rawTime2cTimeLastYear()` method and also in `glideFactoryLogParser.py` module. Additionally, this method was previously used in `diffTimes()` and `diffTimeswWrap()` methods.

    Args:
        date_timestamp (bytes): Time, as a bytes literal, in either of the following two formats: 'MM/DD HH:MM:SS' [old] (OR) YYYY-MM-DD HH:MM:SS [newer]
        year (int): The year.

    Returns:
        int: ctime or -1 in case of error.
    """
    try:
        if date_timestamp[2:3] == b"/":
            # old format of HTCondor job event log
            ctime = time.mktime(
                (
                    year,
                    int(date_timestamp[0:2]),
                    int(date_timestamp[3:5]),
                    int(date_timestamp[6:8]),
                    int(date_timestamp[9:11]),
                    int(date_timestamp[12:14]),
                    0,
                    0,
                    -1,
                )
            )
        else:
            # new format of HTCondor job event log
            # ignoring the year argument that was passed; use from date_timestamp argument itself
            ctime = time.mktime(
                (
                    int(date_timestamp[0:4]),
                    int(date_timestamp[5:7]),
                    int(date_timestamp[8:10]),
                    int(date_timestamp[11:13]),
                    int(date_timestamp[14:16]),
                    int(date_timestamp[17:19]),
                    0,
                    0,
                    -1,
                )
            )
    except (IndexError, ValueError):
        return -1  # Invalid
    return ctime


def rawTime2cTimeLastYear(date_timestamp):
    """Convert the date and time representation existing in the HTCondor submit log into ctime.

    NOTE: This method is used externally in `gWftLogParser.py` module.

    Args:
        date_timestamp (bytes): Time, as a bytes literal, in the format 'MM/DD HH:MM:SS' [old] or 'YYYY-MM-DD HH:MM:SS' [new].

    Returns:
        int: ctime or -1 in case of error.
    """
    now = time.time()
    current_year = time.localtime(now)[0]
    ctime = rawTime2cTime(date_timestamp, current_year)
    if ctime <= now:
        return ctime
    else:  # cannot be in the future... it must have been in the past year
        return rawTime2cTime(date_timestamp, current_year - 1)


# def diffTimes(start_time, end_time, year):
#     """Gets two condor time strings and computes the difference.
#     The start_time must be before the end_time.

#     NOTE: This method was used in `parseSubmitLogFastTimings()` method.

#     Args:
#         start_time (str): Start time in the format 'MM/DD HH:MM:SS'.
#         end_time (str): End time in the format 'MM/DD HH:MM:SS'.
#         year (int): The year.

#     Returns:
#         int: Difference in seconds or -1 in case of error.
#     """
#     Removed because this method is currently not in use.


# def diffTimeswWrap(start_time, end_time, year, wrap_time):
# """Gets two condor time strings and computes the difference with wrapping.
# The start_time must be before the end_time.

# NOTE: This method was used in `parseSubmitLogFastTimings()` method.

# Args:
#     start_time (str): Start time in the format 'MM/DD HH:MM:SS'.
#     end_time (str): End time in the format 'MM/DD HH:MM:SS'.
#     year (int): The year.
#     wrap_time (str): Wrap time in the format 'MM/DD HH:MM:SS'.

# Returns:
#     int: Difference in seconds or -1 in case of error.
# """
# Removed because this method is currently not in use.


def interpretStatus(status, default_status="Idle"):
    """Transforms an integer HTCondor status to either Wait, Idle, Running, Held, Completed or Removed.

    NOTE: This method is used in `countAndInterpretRawStatuses()` and `listAndInterpretRawStatuses()` methods.

    Args:
        status (int): HTCondor status code.
        default_status (str): Default status to return if status code is unknown. Defaults to "Idle".

    Returns:
        str: Interpreted status.
    """
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
    """Given a dictionary of job statuses (like the one got from `parseSubmitLogFastRaw`), returns a dictionary of status counts.

    NOTE: This method is used in `countAndInterpretRawStatuses()` method.

    Args:
        jobs (dict): Dictionary of job statuses.

    Returns:
        dict: Dictionary of status counts.
              For example, {b'012': 25170, b'009': 418, b'005': 1503}
    """
    counts = {}
    for e in jobs.values():
        try:
            counts[e] += 1
        except KeyError:
            # there are only few possible values, so exceptions is faster
            counts[e] = 1
    return counts


def countAndInterpretRawStatuses(jobs_raw):
    """Given a dictionary of job statuses (like the one got from `parseSubmitLogFastRaw`), returns a dictionary of interpreted status counts.

    NOTE: This method is used in `logCounts.loadFromLog()` method in this module.

    Args:
        jobs_raw (dict): Dictionary of bytestrings representing job information, where keys denote job IDs and values are job event type, which is a 3-digit event code.

    Returns:
        dict: Dictionary of interpreted status counts.
              For example, {'Held': 30170, 'Removed': 418, 'Completed': 5013}
    """
    outc = {}
    tmpc = countStatuses(jobs_raw)
    for s in tmpc.keys():
        i_s = interpretStatus(int(s[1:]))  # ignore flags
        try:
            outc[i_s] += tmpc[s]
        except KeyError:
            # there are only few possible values, using exceptions is faster
            outc[i_s] = tmpc[s]
    return outc


def listStatuses(jobs):
    """Given a dictionary of job information (like the one got from `parseSubmitLogFastRaw`), returns a dictionary of job IDs keyed by job event type.

    NOTE: This method is used in `logSummary.loadFromLog()` and `logCompleted.loadFromLog()` methods.

    Args:
        jobs (dict): Dictionary of bytestrings representing job information, where keys denote job IDs and values are job event type, which is a 3-digit event code.

    Returns:
        dict: Dictionary of jobs in each status category.
              For example, {b'009': [ b'102.003', b'245.001'], b'012': [ b'418.001'], b'005': [ b'1503.001', b'1555.002']}
    """
    status = {}
    for k, e in jobs.items():
        try:
            status[e].append(k)
        except KeyError:
            # there are only few possible values, using exceptions is faster
            status[e] = [k]
    return status


def listStatusesTimings(jobs):
    """Given a dictionary of job information (like the one got from `parseSubmitLogFastRawTimings`), returns a dictionary of jobs' information keyed by their event type.

    NOTE: This method is used in `logSummaryTimings.loadFromLog()` method.

    Args:
        jobs (dict): A dictionary consisting of job information such as the job status, job start time, job running time (if completed), and job end time.

    Returns:
        dict: Dictionary of jobs and their timing information corresponding to their status.
            For example:
            ```
            {   # old log format
                b'009': [
                    ("1.003", '09/28 01:38:53', '', '09/28 01:38:53'),
                    ("2.001",'09/28 03:38:53', '', '09/28 04:38:53')
                ],
                b'005': [
                    ("1503.001", '09/28 01:48:52', '09/28 16:11:23', '09/28 20:31:53'),
                    ("1555.002", '09/28 02:48:52', '09/28 18:11:23', '09/28 23:31:53')
                ]
            }
            ```
            ```
            {   # new log format
                b'009': [
                    ( b'011.003', b'2026-04-01 01:38:53', b'', b'2026-04-02 01:38:53' ),
                    ( b'221.001', b'2026-04-03 03:38:53', b'', b'2026-04-03 04:38:53' )
                ],
                b'005': [
                    ( b'1503.001', b'2026-04-02 01:48:52', b'2026-04-02 16:11:23', b'2026-04-02 16:11:23' ),
                    ( b'1555.002', b'2026-04-01 02:48:52', b'2026-04-01 18:11:23', b'2026-04-01 18:11:23' )
                ]
            }
            ```
    """
    status = {}
    for k, e in jobs.items():
        try:
            status[e[0]].append((k,) + e[1:])
        except KeyError:
            # there are only few possible values, using exceptions is faster
            status[e[0]] = [(k,) + e[1:]]
    return status


def listAndInterpretRawStatuses(jobs_raw, invert_function):
    """Given a dictionary of job information (whatever the `invert_function` recognises), returns a dictionary of jobs in each status according to the provided invert function (syntax depends on the `invert_function`).

    NOTE: This method is used in `logSummary.loadFromLog()`, `logCompleted.loadFromLog()`, `logSummaryTimings.loadFromLog()` methods.

    Args:
        jobs_raw (dict): Dictionary of job information.
        invert_function (function): Function that determines whether the returned job information should only include job IDs or also include the timing information about the corresponding jobs, in conjunction with the job IDs.

    Returns:
        dict: Dictionary of jobs in each category.
              Example : when `invert_function` is `listStatuses`
              ```
              {b'009': [ b'122.003', b'554.001'], b'012': [ b'241.001'], b'005': [ b'408.003']}
              ```
              Example 2: when `invert_function` is `listStatusesTimings`
              ```
              {
                b'012': [
                    ( b'011.003', b'2026-04-01 01:38:53', b'', b'2026-04-02 01:38:53' ),
                    ( b'221.001', b'2026-04-03 03:38:53', b'', b'2026-04-03 04:38:53' )
                ],
                b'005': [
                    ( b'241.001', b'2026-04-02 01:48:52', b'2026-04-02 16:11:23', b'2026-04-02 16:11:23' )
                ],
                b'009': [
                    ( b'408.003', b'2026-04-01 01:38:53', b'', b'2026-04-02 01:38:53')
                ]
              }
              ```
    """
    outc = {}
    tmpc = invert_function(jobs_raw)
    for s in tmpc.keys():
        try:
            i_s = interpretStatus(int(s[1:]))  # ignore flags
        except Exception:  # file corrupted, protect
            # print("lairs: Unexpected line: %s"%s)
            continue
        try:
            outc[i_s] += tmpc[s]
        except KeyError:
            # there are only few possible values, using exceptions is faster
            outc[i_s] = tmpc[s]
    return outc


# def parseSubmitLogFast(fname):
# """Reads a HTCondor submit log and returns a dictionary of job IDs
# each having the last status.

# Args:
#     fname (str): Filename to parse.

# Returns:
#     dict: Dictionary of job IDs and last status.
#           For example, {(1583,4): 0, (3616,8): 9}
# """
# Removed because this method is currently not in use.


# def parseSubmitLogFastTimings(fname, year=None):
# """Reads a HTCondor submit log and returns a dictionary of job IDs each having:
# the last status, seconds in queue, and, if status == 5, seconds running otherwise `None`.

# Args:
#     fname (str): Filename to parse.
#     year (int): The year. If None, use the current year.

# Returns:
#     dict: Dictionary of job IDs with timings.
#           For example, {(1583,4): (0,345,None), (3616,8): (5,7777,4532)}
# """
# Removed because this method is currently not in use


################################
#  Cache handling functions
################################


def loadCache(fname):
    """Loads a pickle file from a file name and returns the resulting data.

    Args:
        fname (str): Name of the file to load.

    Returns:
        Any: Data retrieved from file.

    Raises:
        RuntimeError: If the file could not be read.
    """
    try:
        data = util.file_pickle_load(fname)
    except Exception as e:
        raise RuntimeError(f"Could not read {fname}") from e
    return data


def saveCache(fname, data):
    """Creates a temporary file to store data in, then moves the file into the correct place.
    Uses pickle to store data.

    Args:
        fname (str): Name of the file to write to.
        data (Any): Data to store in pickle format.
    """
    util.file_pickle_dump(fname, data)
    return
