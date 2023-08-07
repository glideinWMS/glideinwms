# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#  Handle pid lock files

import fcntl
import os
import os.path
import signal
import time

############################################################

#
# Verify if the system knows about a pid
#
def check_pid(pid):
    return os.path.isfile(f"/proc/{pid}/cmdline")


############################################################

# this exception is raised when trying to register a pid
# but another process is already owning the PID file
class AlreadyRunning(RuntimeError):
    pass


#######################################################
#
# self.mypid is valid only if self.fd is valid
# or after a load
class PidSupport:
    def __init__(self, pid_fname):
        self.pid_fname = pid_fname
        self.fd = None
        self.mypid = None
        self.lock_in_place = False

    # open the pid_file and gain the exclusive lock
    # also write in the PID information
    def register(self, pid=None, started_time=None):  # if none, will default to os.getpid()  # if none, use time.time()
        if self.fd is not None:
            raise RuntimeError("Cannot register two pids in the same object!")

        if pid is None:
            pid = os.getpid()
        if started_time is None:
            started_time = time.time()

        self.mypid = pid
        self.started_time = started_time

        # check lock file
        if not os.path.exists(self.pid_fname):
            # create a lock file if needed
            fd = open(self.pid_fname, "w")
            fd.close()

        # Do not use 'with' or close the file. Will be closed when lock is released
        fd = open(self.pid_fname, "r+")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_in_place = True
        except OSError as e:
            fd.close()
            raise AlreadyRunning(f"Another process already running. Unable to acquire lock {self.pid_fname}") from e
        fd.seek(0)
        fd.truncate()
        fd.write(self.format_pid_file_content())
        fd.flush()

        self.fd = fd
        return

    # release the lock on the PID file
    # also purge the info from the file
    def relinquish(self):
        self.fd.seek(0)
        self.fd.truncate()
        self.fd.flush()
        self.fd.close()
        self.fd = None
        self.mypid = None
        self.lock_in_place = False

    # Will update self.mypid and self.lock_in_place
    def load_registered(self):
        if self.fd is not None:
            return  # we own it, so nothing to do

        # make sure it is initialized (to not registered)
        self.reset_to_default()

        self.lock_in_place = False
        # else I don't own it
        if not os.path.isfile(self.pid_fname):
            return

        with open(self.pid_fname) as fd:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # if I can get a lock, it means that there is no process
                return
            except OSError:
                # there is a process
                # I will read it even if locked, so that I can report what the PID is
                # if the data is corrupted, I will deal with it later
                lines = fd.readlines()
                self.lock_in_place = True

        try:
            self.parse_pid_file_content(lines)
        except Exception:
            # Data is corrupted, cannot get the PID, masking exceptions
            return

        if not check_pid(self.mypid):
            # found not running
            self.mypid = None
        return

    ###############################
    # INTERNAL
    # Can be redefined by children
    ###############################

    def format_pid_file_content(self):
        return f"PID: {self.mypid}\nStarted: {time.ctime(self.started_time)}\n"

    def reset_to_default(self):
        self.mypid = None

    def parse_pid_file_content(self, lines):
        self.mypid = None
        if len(lines) < 2:
            raise RuntimeError("Corrupted lock file: too short")

        pidarr = lines[0].split()
        if (len(pidarr) != 2) or (pidarr[0] != "PID:"):
            raise RuntimeError("Corrupted lock file: no PID")

        try:
            pid = int(pidarr[1])
        except Exception:
            raise RuntimeError("Corrupted lock file: invalid PID") from None

        self.mypid = pid
        return


#######################################################
#
# self.mypid and self.parent_pid are valid only
# if self.fd is valid or after a load
class PidWParentSupport(PidSupport):
    def __init__(self, pid_fname):
        PidSupport.__init__(self, pid_fname)
        self.parent_pid = None

    # open the pid_file and gain the exclusive lock
    # also write in the PID information
    def register(
        self, parent_pid, pid=None, started_time=None  # if none, will default to os.getpid()
    ):  # if none, use time.time()
        if self.fd is not None:
            raise RuntimeError("Cannot register two pids in the same object!")

        self.parent_pid = parent_pid
        PidSupport.register(self, pid, started_time)

    ###############################
    # INTERNAL
    # Can be redefined by children
    ###############################

    def format_pid_file_content(self):
        return f"PID: {self.mypid}\nParent PID:{self.parent_pid}\nStarted: {time.ctime(self.started_time)}\n"

    def reset_to_default(self):
        PidSupport.reset_to_default(self)
        self.parent_pid = None

    def parse_pid_file_content(self, lines):
        self.mypid = None
        self.parent_pid = None

        if len(lines) < 3:
            raise RuntimeError("Corrupted lock file: too short")

        pidarr = lines[0].split()
        if (len(pidarr) != 2) or (pidarr[0] != "PID:"):
            raise RuntimeError("Corrupted lock file: no PID")

        try:
            pid = int(pidarr[1])
        except Exception:
            raise RuntimeError("Corrupted lock file: invalid PID") from None

        pidarr = lines[1].split(":")
        if (len(pidarr) != 2) or (pidarr[0] != "Parent PID"):
            raise RuntimeError("Corrupted lock file: no Parent PID")

        try:
            parent_pid = int(pidarr[1])
        except Exception:
            raise RuntimeError("Corrupted lock file: invalid Parent PID") from None

        self.mypid = pid
        self.parent_pid = parent_pid
        return


def termsignal(signr, frame):
    raise KeyboardInterrupt("Received signal %s" % signr)


def register_sighandler():
    signal.signal(signal.SIGTERM, termsignal)
    signal.signal(signal.SIGQUIT, termsignal)


def unregister_sighandler():
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGQUIT, signal.SIG_DFL)
