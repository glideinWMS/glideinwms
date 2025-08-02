# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os
import re
import stat
import time

from . import logSupport
from .pidSupport import register_sighandler, unregister_sighandler


class Cleanup:
    """A class used to manage cleanup tasks for various objects and processes.

    Attributes:
        cleanup_objects (list): A list of cleanup objects to be processed.
        cleanup_pids (list): A list of process IDs for cleanup tasks.
    """

    def __init__(self):
        """Initializes a Cleanup instance with empty lists for cleanup objects and PIDs."""
        self.cleanup_objects = []
        self.cleanup_pids = []

    def add_cleaner(self, cleaner):
        """Adds a cleanup object to the list of objects to be cleaned.

        Args:
            cleaner: An object with a cleanup method.
        """
        self.cleanup_objects.append(cleaner)

    def start_background_cleanup(self):
        """Starts background cleanup processes by forking the current process.

        This method forks the current process into multiple subprocesses to handle
        the cleanup tasks in parallel.
        """
        if self.cleanup_pids:
            logSupport.log.warning("Earlier cleanup PIDs %s still exist; skipping this cycle" % self.cleanup_pids)
        else:
            num_forks = 4  # arbitrary - could be configurable
            cleanup_lists = [self.cleanup_objects[x::num_forks] for x in range(num_forks)]
            for i in range(num_forks):
                unregister_sighandler()
                cl_pid = os.fork()
                if cl_pid != 0:
                    register_sighandler()
                    self.cleanup_pids.append(cl_pid)
                else:
                    for cleaner in cleanup_lists[i]:
                        cleaner.cleanup()
                    os._exit(0)
            logSupport.log.debug("Forked cleanup PIDS %s" % self.cleanup_pids)
            del cleanup_lists

    def wait_for_cleanup(self):
        """Waits for all cleanup subprocesses to finish.

        This method checks the status of the cleanup subprocesses and logs
        when they have finished.
        """
        for pid in self.cleanup_pids:
            try:
                return_pid, _ = os.waitpid(pid, os.WNOHANG)
                if return_pid:
                    logSupport.log.debug("Collected cleanup PID %s" % pid)
                    self.cleanup_pids.remove(pid)
            except OSError as e:
                self.cleanup_pids.remove(pid)
                logSupport.log.warning(f"Received error {e.strerror} while waiting for PID {pid}")

    def cleanup(self):
        """Performs foreground cleanup tasks.

        This method iterates over all registered cleanup objects and calls
        their cleanup methods.
        """
        for cleaner in self.cleanup_objects:
            cleaner.cleanup()


cleaners = Cleanup()


class CredCleanup(Cleanup):
    """A class used to clean up old credential files."""

    def cleanup(self, in_use_proxies):
        """Cleans up credential files that are no longer in use.

        Args:
            in_use_proxies (list): A list of currently in-use proxy files.
        """
        for cleaner in self.cleanup_objects:
            cleaner.cleanup(in_use_proxies)


cred_cleaners = CredCleanup()


class DirCleanup:
    """A class used for cleaning up old files in a directory.

    Attributes:
        dirname (str): The directory to clean.
        fname_expression (str): A regular expression to match file names.
        maxlife (int): The maximum lifetime of files in seconds.
        should_log (bool): Whether to log information messages.
        should_log_warnings (bool): Whether to log warning messages.
    """

    def __init__(
        self,
        dirname,
        fname_expression,  # regular expression, used with re.match
        maxlife,
        should_log=True,
        should_log_warnings=True,
    ):
        """Initializes a DirCleanup instance.

        Args:
            dirname (str): The directory to clean.
            fname_expression (str): A regular expression to match file names.
            maxlife (int): The maximum lifetime of files in seconds.
            should_log (bool, optional): Whether to log information messages. Defaults to True.
            should_log_warnings (bool, optional): Whether to log warning messages. Defaults to True.
        """
        self.dirname = dirname
        self.fname_expression = fname_expression
        self.fname_expression_obj = re.compile(fname_expression)
        self.maxlife = maxlife
        self.should_log = should_log
        self.should_log_warnings = should_log_warnings

    def cleanup(self):
        """Cleans up files in the directory that match the filename expression and are older than maxlife.

        This method removes files that are older than the specified maximum lifetime.
        """
        count_removes = 0

        treshold_time = time.time() - self.maxlife
        files_wstats = self.get_files_wstats()

        for fpath in list(files_wstats.keys()):
            fstat = files_wstats[fpath]

            update_time = fstat[stat.ST_MTIME]
            if update_time < treshold_time:
                try:
                    self.delete_file(fpath)
                    count_removes += 1
                except Exception:
                    if self.should_log_warnings:
                        logSupport.log.warning("Could not remove %s" % fpath)

        if count_removes > 0:
            if self.should_log:
                logSupport.log.info("Removed %i files." % count_removes)

    # INTERNAL
    def get_files_wstats(self):
        """Retrieves a dictionary of file paths and their statistics.

        This method returns a dictionary where the keys are file paths and the
        values are the output of os.lstat for each file.

        Returns:
            dict: A dictionary of file paths and their statistics.
        """
        out_data = {}

        fnames = os.listdir(self.dirname)
        for fname in fnames:
            if self.fname_expression_obj.match(fname) is None:
                continue  # ignore files that do not match

            fpath = os.path.join(self.dirname, fname)
            fstat = os.lstat(fpath)
            fmode = fstat[stat.ST_MODE]
            isdir = stat.S_ISDIR(fmode)
            if isdir:
                continue  # ignore directories
            out_data[fpath] = fstat

        return out_data

    def delete_file(self, fpath):
        """Deletes a file from the filesystem.

        This is likely reimplemented by the children.

        Args:
            fpath (str): The path to the file to be deleted.
        """
        os.unlink(fpath)


class DirCleanupWSpace(DirCleanup):
    """A class used for cleaning up files in a directory based on both age and total space used.

    Attributes:
        dirname (str): The directory to clean.
        fname_expression (str): A regular expression to match file names.
        maxlife (int): The maximum lifetime of files in seconds.
        minlife (int): The minimum lifetime of files in seconds.
        maxspace (int): The maximum allowed space for the files in bytes.
        should_log (bool): Whether to log information messages.
        should_log_warnings (bool): Whether to log warning messages.
    """

    def __init__(
        self,
        dirname,
        fname_expression,  # regular expression, used with re.match
        maxlife,  # max lifetime after which it is deleted
        minlife,
        maxspace,  # max space allowed for the sum of files, unless they are too young
        should_log=True,
        should_log_warnings=True,
    ):
        """Initializes a DirCleanupWSpace instance.

        Args:
            dirname (str): The directory to clean.
            fname_expression (str): A regular expression to match file names.
            maxlife (int): The maximum lifetime of files in seconds.
            minlife (int): The minimum lifetime of files in seconds.
            maxspace (int): The maximum allowed space for the files in bytes.
            should_log (bool, optional): Whether to log information messages. Defaults to True.
            should_log_warnings (bool, optional): Whether to log warning messages. Defaults to True.
        """
        DirCleanup.__init__(self, dirname, fname_expression, maxlife, should_log, should_log_warnings)
        self.minlife = minlife
        self.maxspace = maxspace

    def cleanup(self):
        """Cleans up files in the directory based on age and total space used.

        This method removes files that are older than the specified maximum lifetime or if
        the total space used by the files exceeds the specified maximum space.
        """
        count_removes = 0
        count_removes_bytes = 0

        min_treshold_time = time.time() - self.minlife
        treshold_time = time.time() - self.maxlife

        files_wstats = self.get_files_wstats()
        fpaths = list(files_wstats.keys())
        # Order based on time (older first)
        fpaths.sort(key=lambda x: files_wstats[x][stat.ST_MTIME])

        # First calculate the amount of space currently used
        used_space = 0
        for fpath in fpaths:
            fstat = files_wstats[fpath]
            fsize = fstat[stat.ST_SIZE]
            used_space += fsize

        for fpath in fpaths:
            fstat = files_wstats[fpath]

            update_time = fstat[stat.ST_MTIME]
            fsize = fstat[stat.ST_SIZE]

            if (update_time < treshold_time) or ((update_time < min_treshold_time) and (used_space > self.maxspace)):
                try:
                    os.unlink(fpath)
                    count_removes += 1
                    count_removes_bytes += fsize
                    used_space -= fsize
                except Exception:
                    if self.should_log_warnings:
                        logSupport.log.warning("Could not remove %s" % fpath)

        if count_removes > 0:
            if self.should_log:
                logSupport.log.info(
                    "Removed %i files for %.2fMB." % (count_removes, count_removes_bytes / (1024.0 * 1024.0))
                )


class DirCleanupCredentials(DirCleanup):
    """A class used to clean up old credential files saved to disk by the factory for glidein submission.

    Attributes:
        dirname (str): The directory to clean.
        fname_expression (str): A regular expression to match file names.
        maxlife (int): The maximum lifetime of files in seconds.
    """

    def __init__(
        self, dirname, fname_expression, maxlife  # regular expression, used with re.match
    ):  # max lifetime after which it is deleted
        """Initializes a DirCleanupCredentials instance.

        Args:
            dirname (str): The directory to clean.
            fname_expression (str): A regular expression to match file names.
            maxlife (int): The maximum lifetime of files in seconds.
        """
        DirCleanup.__init__(self, dirname, fname_expression, maxlife, should_log=True, should_log_warnings=True)

    def cleanup(self, in_use_creds):
        """Cleans up credential files that are no longer in use.

        Args:
            in_use_creds (list): A list of currently in-use credential files.
        """
        count_removes = 0
        curr_time = time.time()

        threshold_time = curr_time - self.maxlife

        files_wstats = self.get_files_wstats()
        fpaths = list(files_wstats.keys())

        for fpath in fpaths:
            fstat = files_wstats[fpath]
            last_access_time = fstat[stat.ST_MTIME]

            if last_access_time < threshold_time and fpath not in in_use_creds:
                try:
                    os.unlink(fpath)
                    count_removes += 1
                except Exception:
                    logSupport.log.warning("Could not remove credential %s" % fpath)

        if count_removes > 0:
            logSupport.log.info("Removed %i credential files." % count_removes)
        else:
            logSupport.log.info("No old credential files were removed.")
