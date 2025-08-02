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


def check_pid(pid):
    """Check if a process with the given PID exists.

    Args:
        pid (int): The process ID to check.

    Returns:
        bool: True if the process exists, False otherwise.
    """
    return os.path.isfile(f"/proc/{pid}/cmdline")


############################################################


class AlreadyRunning(RuntimeError):
    """Exception raised during PID registration when a process is already running and owns the PID file."""

    pass


class PidSupport:
    """Class to manage PID files with locking mechanisms.

    This class handles the registration and management of PID files,
    ensuring that only one process can own a PID file at a time.

    Attributes:
        pid_fname (str): The filename of the PID file.
        fd (file object): The file descriptor for the PID file.
        mypid (int): The PID of the current process.
        lock_in_place (bool): Indicates if the lock is in place.
        started_time (float): The time when the process started.

    Notes:
        `self.mypid` is valid only if `self.fd` is valid or after a load
    """

    def __init__(self, pid_fname):
        """Initialize the PidSupport class.

        Args:
            pid_fname (str): The filename of the PID file.
        """
        self.pid_fname = pid_fname
        self.fd = None
        self.mypid = None
        self.lock_in_place = False

    def register(self, pid=None, started_time=None):
        """Register the current process by writing its PID to the PID file.

        This method also gains an exclusive lock on the PID file.

        Args:
            pid (int, optional): The PID to register. Defaults to the current process PID.
            started_time (float, optional): The time when the process started. Defaults to the current time.

        Raises:
            RuntimeError: If a PID is already registered in the same object.
            AlreadyRunning: If another process is already running and owns the PID file.
        """
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

    def relinquish(self):
        """Release the lock on the PID file and remove the PID information."""
        self.fd.seek(0)
        self.fd.truncate()
        self.fd.flush()
        self.fd.close()
        self.fd = None
        self.mypid = None
        self.lock_in_place = False

    def load_registered(self):
        """Load the registered PID from the PID file.

        Updates the instance's PID and lock status based on the contents of the PID file.
        """
        if self.fd is not None:
            return  # we own it, so nothing to do

        # make sure it is initialized (to not registered)
        self.reset_to_default()

        self.lock_in_place = False
        # Else I don't own it
        if not os.path.isfile(self.pid_fname):
            return

        with open(self.pid_fname) as fd:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # If I can get a lock, it means that there is no process
                return
            except OSError:
                # There is a process
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
            # Found not running
            self.mypid = None
        return

    ###############################
    # INTERNAL
    # Can be redefined by children
    ###############################

    def format_pid_file_content(self):
        """Format the content to be written to the PID file.

        Returns:
            str: Formatted string containing the PID and start time.
        """
        return f"PID: {self.mypid}\nStarted: {time.ctime(self.started_time)}\n"

    def reset_to_default(self):
        """Reset the instance attributes to their default values."""
        self.mypid = None

    def parse_pid_file_content(self, lines):
        """Parse the content of the PID file and update the instance attributes.

        Args:
            lines (list): Lines read from the PID file.

        Raises:
            RuntimeError: If the PID file is corrupted or invalid.
        """
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


class PidWParentSupport(PidSupport):
    """Extended PidSupport class that includes parent PID information.

    This class manages PID files while also recording the parent PID.

    Attributes:
        parent_pid (int): The parent process PID.

    Notes:
        `self.mypid` and `self.parent_pid` are valid only if `self.fd` is valid or after a load
    """

    def __init__(self, pid_fname):
        """Initialize the PidWParentSupport class.

        Args:
            pid_fname (str): The filename of the PID file.
        """
        PidSupport.__init__(self, pid_fname)
        self.parent_pid = None

    def register(self, parent_pid, pid=None, started_time=None):
        """Register the current process and its parent by writing PIDs to the PID file.

        Args:
            parent_pid (int): The parent process PID.
            pid (int, optional): The PID to register. Defaults to the current process PID.
            started_time (float, optional): The time when the process started. Defaults to the current time.

        Raises:
            RuntimeError: If a PID is already registered in the same object.
        """
        if self.fd is not None:
            raise RuntimeError("Cannot register two pids in the same object!")

        self.parent_pid = parent_pid
        PidSupport.register(self, pid, started_time)

    ###############################
    # INTERNAL
    # Can be redefined by children
    ###############################

    def format_pid_file_content(self):
        """Format the content to be written to the PID file.

        Returns:
            str: Formatted string containing the PID, parent PID, and start time.
        """
        return f"PID: {self.mypid}\nParent PID:{self.parent_pid}\nStarted: {time.ctime(self.started_time)}\n"

    def reset_to_default(self):
        """Reset the instance attributes to their default values, including parent PID."""
        PidSupport.reset_to_default(self)
        self.parent_pid = None

    def parse_pid_file_content(self, lines):
        """Parse the content of the PID file and update the instance attributes.

        Args:
            lines (list): Lines read from the PID file.

        Raises:
            RuntimeError: If the PID file is corrupted or invalid.
        """
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
    """Handle termination signals by raising a KeyboardInterrupt.

    Args:
        signr (int): Signal number.
        frame (FrameType): Current stack frame.

    Raises:
        KeyboardInterrupt: Always raised with the signal number.
    """
    raise KeyboardInterrupt("Received signal %s" % signr)


def register_sighandler():
    """Register signal handlers for SIGTERM and SIGQUIT."""
    signal.signal(signal.SIGTERM, termsignal)
    signal.signal(signal.SIGQUIT, termsignal)


def unregister_sighandler():
    """Unregister the custom signal handlers, resetting them to the default."""
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGQUIT, signal.SIG_DFL)
