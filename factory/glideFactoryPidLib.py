# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#  Handle factory pids
#
# Author:
#   Igor Sfiligoi
#

import os
import os.path
import sys

from glideinwms.lib import pidSupport

############################################################


class FactoryPidSupport(pidSupport.PidSupport):
    def __init__(self, startup_dir):
        lock_file = os.path.join(startup_dir, "lock/glideinWMS.lock")
        pidSupport.PidSupport.__init__(self, lock_file)


# raise an exception if not running
def get_factory_pid(startup_dir):
    pid_obj = FactoryPidSupport(startup_dir)
    pid_obj.load_registered()
    if not pid_obj.lock_in_place:
        raise RuntimeError("Factory not running")
    if pid_obj.mypid is None:
        raise RuntimeError("Factory process not found")
    return pid_obj.mypid


############################################################


class EntryPidSupport(pidSupport.PidWParentSupport):
    def __init__(self, startup_dir, entry_name):
        lock_file = os.path.join(startup_dir, f"{startup_dir}/entry_{entry_name}/lock/factory.lock")
        pidSupport.PidWParentSupport.__init__(self, lock_file)


# raise an exception if not running
def get_entry_pid(startup_dir, entry_name):
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
    def __init__(self, startup_dir, group_name):
        lock_file = os.path.join(startup_dir, f"{startup_dir}/lock/{group_name}.lock")
        pidSupport.PidWParentSupport.__init__(self, lock_file)


# raise an exception if not running
def get_entrygroup_pid(startup_dir, group_name):
    pid_obj = EntryGroupPidSupport(startup_dir, group_name)
    pid_obj.load_registered()
    if not pid_obj.lock_in_place:
        raise RuntimeError("Entry Group %s not running" % group_name)
    if pid_obj.mypid is None:
        raise RuntimeError("Entry Group %s process not found" % group_name)
    if pid_obj.parent_pid is None:
        raise RuntimeError("Entry Group %s has no parent" % group_name)
