# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#  Handle frontend pids

import os

from glideinwms.lib import pidSupport

############################################################


class FrontendPidSupport(pidSupport.PidSupport):
    def __init__(self, startup_dir):
        lock_file = os.path.join(startup_dir, "lock/frontend.lock")
        pidSupport.PidSupport.__init__(self, lock_file)
        self.action_type = None

    def register(self, action_type, pid=None, started_time=None):
        """See parent for full description
        We add action_type here

        Args:
            action_type:
            pid: if None, will default to os.getpid()
            started_time: if None, use time.time()
        """
        self.action_type = action_type
        pidSupport.PidSupport.register(self, pid, started_time)

    ###############################
    # INTERNAL
    # Extend the parent methods
    ###############################
    def format_pid_file_content(self):
        base_cnt = pidSupport.PidSupport.format_pid_file_content(self)
        if self.action_type is None:
            cnt = base_cnt
        else:
            cnt = base_cnt + ("TYPE: %s\n" % self.action_type)
        return cnt

    def reset_to_default(self):
        pidSupport.PidSupport.reset_to_default(self)
        self.action_type = None

    def parse_pid_file_content(self, lines):
        self.action_type = None

        pidSupport.PidSupport.parse_pid_file_content(self, lines)
        # the above will throw in case of error
        if len(lines) >= 3:
            if lines[2].startswith("TYPE: "):
                self.action_type = lines[2][6:].strip()

        return


def get_frontend_pid(startup_dir):
    """Return the Frontend pid. Raise an exception if not running

    Args:
        startup_dir:

    Returns:


    Raises:
        RuntimeError: if the Frontend is not running or is unable to find the pid
    """
    pid_obj = FrontendPidSupport(startup_dir)
    pid_obj.load_registered()
    if not pid_obj.lock_in_place:
        raise RuntimeError("Frontend not running")
    if pid_obj.mypid is None:
        raise RuntimeError("Could not determine the pid")
    return pid_obj.mypid


def get_frontend_action_type(startup_dir):
    """Get the action type (). Raise an exception if not running


    Args:
        startup_dir:

    Returns:

    Raises:
        RuntimeError: if the Frontend is not running
    """
    pid_obj = FrontendPidSupport(startup_dir)
    pid_obj.load_registered()
    if not pid_obj.lock_in_place:
        raise RuntimeError("Frontend not running")
    return pid_obj.action_type


############################################################


class ElementPidSupport(pidSupport.PidWParentSupport):
    def __init__(self, startup_dir, group_name):
        lock_file = os.path.join(startup_dir, f"{startup_dir}/group_{group_name}/lock/frontend.lock")
        pidSupport.PidWParentSupport.__init__(self, lock_file)


def get_element_pid(startup_dir, group_name):
    """Raise an exception if not running

    Args:
        startup_dir:
        group_name:

    Returns:

    Raises:
        RuntimeError: if the Group element process is not running or has no parent
    """
    pid_obj = ElementPidSupport(startup_dir, group_name)
    pid_obj.load_registered()
    if pid_obj.mypid is None:
        raise RuntimeError("Group element not running")
    if pid_obj.parent_pid is None:
        raise RuntimeError("Group element has no parent???")
    return (pid_obj.mypid, pid_obj.parent_pid)
