# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Handle factory pids"""

import os
import os.path

from glideinwms.lib import pidSupport

############################################################


class FactoryPidSupport(pidSupport.PidSupport):
    """Factory PID support class.

    This class is a thin wrapper around pidSupport.PidSupport to support the Factory
    process PID file.
    """

    def __init__(self, startup_dir):
        """Initialize the FactoryPidSupport.

        Args:
            startup_dir (str): The startup directory where the lock directory is located.
        """
        lock_file = os.path.join(startup_dir, "lock/glideinWMS.lock")
        pidSupport.PidSupport.__init__(self, lock_file)


# raise an exception if not running
def get_factory_pid(startup_dir):
    """Retrieve the factory PID.

    Loads the registered PID from the factory's lock file and raises an exception
    if the factory is not running or the PID is not found.

    Args:
        startup_dir (str): The startup directory where the factory's lock file is located.

    Returns:
        int: The PID of the factory process.

    Raises:
        RuntimeError: If the factory is not running or the factory process is not found.
    """
    pid_obj = FactoryPidSupport(startup_dir)
    pid_obj.load_registered()
    if not pid_obj.lock_in_place:
        raise RuntimeError("Factory not running")
    if pid_obj.mypid is None:
        raise RuntimeError("Factory process not found")
    return pid_obj.mypid


############################################################


class EntryPidSupport(pidSupport.PidWParentSupport):
    """Entry PID support class.

    This class is a thin wrapper around pidSupport.PidWParentSupport to support the entry process
    PID file.
    """

    def __init__(self, startup_dir, entry_name):
        """Initialize the EntryPidSupport.

        Args:
            startup_dir (str): The startup directory.
            entry_name (str): The entry name.
        """
        lock_file = os.path.join(startup_dir, f"{startup_dir}/entry_{entry_name}/lock/factory.lock")
        pidSupport.PidWParentSupport.__init__(self, lock_file)


# raise an exception if not running
def get_entry_pid(startup_dir, entry_name):
    """Retrieve the entry PID and its parent PID (the entry group one).

    Loads the registered PID from the entry's lock file and raises an exception
    if the entry is not running, the process is not found, or the parent PID is missing.

    Args:
        startup_dir (str): The startup directory.
        entry_name (str): The entry name.

    Returns:
        tuple: A tuple (entry_pid, parent_pid).

    Raises:
        RuntimeError: If the entry is not running, the entry process is not found, or the parent PID is missing.
    """
    pid_obj = EntryPidSupport(startup_dir, entry_name)
    pid_obj.load_registered()
    if not pid_obj.lock_in_place:
        raise RuntimeError("Entry not running")
    if pid_obj.mypid is None:
        raise RuntimeError("Entry process not found")
    if pid_obj.parent_pid is None:
        raise RuntimeError("Entry has no parent???")
    return (pid_obj.mypid, pid_obj.parent_pid)


############################################################


class EntryGroupPidSupport(pidSupport.PidWParentSupport):
    """Entry Group PID support class.

    This class is a thin wrapper around pidSupport.PidWParentSupport to support the entry group
    PID file.
    """

    def __init__(self, startup_dir, group_name):
        """Initialize the EntryGroupPidSupport.

        Args:
            startup_dir (str): The startup directory.
            group_name (str): The entry group name.
        """
        lock_file = os.path.join(startup_dir, f"{startup_dir}/lock/{group_name}.lock")
        pidSupport.PidWParentSupport.__init__(self, lock_file)


# raise an exception if not running
def get_entrygroup_pid(startup_dir, group_name):
    """Retrieve the entry group PID and its parent PID (the Factory one).

    Loads the registered PID from the entry group's lock file and raises an exception
    if the entry group is not running, the process is not found, or the parent PID is missing.

    Args:
        startup_dir (str): The startup directory.
        group_name (str): The entry group name.

    Returns:
        tuple: A tuple (entry_group_pid, parent_pid).

    Raises:
        RuntimeError: If the entry group is not running, the entry group process is not found, or the parent PID is missing.
    """
    pid_obj = EntryGroupPidSupport(startup_dir, group_name)
    pid_obj.load_registered()
    if not pid_obj.lock_in_place:
        raise RuntimeError("Entry Group %s not running" % group_name)
    if pid_obj.mypid is None:
        raise RuntimeError("Entry Group %s process not found" % group_name)
    if pid_obj.parent_pid is None:
        raise RuntimeError("Entry Group %s has no parent" % group_name)
