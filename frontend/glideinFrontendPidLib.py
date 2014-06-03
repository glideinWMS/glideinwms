#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#  Handle frontend pids
# 
# Author:
#   Igor Sfiligoi
#

import os
from glideinwms.lib import pidSupport
from glideinwms.lib import logSupport

############################################################

class FrontendPidSupport(pidSupport.PidSupport):
    def __init__(self, startup_dir):
        lock_file = os.path.join(startup_dir, "lock/frontend.lock")
        pidSupport.PidSupport.__init__(self, lock_file)

    # See parent for full description
    # We add action_type here
    def register(self,
                 action_type,
                 pid = None,            # if none, will default to os.getpid()
                 started_time = None):  # if none, use time.time()
        pidSupport.PidSupport.register(self, pid, started_time)
        self.action_type = action_type

    ###############################
    # INTERNAL
    # Extend the parent methods
    ###############################
    def format_pid_file_content(self):
        base_cnt=pidSupport.PidSupport.format_pid_file_content(self)
        if self.action_type is None:
            cnt=base_cnt
        else:
            cnt=base_cnt+("TYPE: %s\n"%self.action_type)
        return cnt


    def parse_pid_file_content(self, lines):
        pidSupport.PidSupport.parse_pid_file_content(self, lines)
        # the above will throw in case of error
        self.action_type = None
        if len(lines)>=3:
            if lines[2].startswith("TYPE: "):
                action_type=lines[2][6:].strip()

        return

#raise an exception if not running
def get_frontend_pid(startup_dir):
    pid_obj = FrontendPidSupport(startup_dir)
    pid_obj.load_registered()
    if pid_obj.mypid is None:
        raise RuntimeError, "Frontend not running"
    return pid_obj.mypid

#raise an exception if not running
def get_frontend_action_type(startup_dir):
    pid_obj = FrontendPidSupport(startup_dir)
    pid_obj.load_registered()
    if pid_obj.mypid is None:
        raise RuntimeError, "Frontend not running"
    return pid_obj.action_type

############################################################

class ElementPidSupport(pidSupport.PidWParentSupport):
    def __init__(self, startup_dir, group_name):
        lock_file = os.path.join(startup_dir, "%s/group_%s/lock/frontend.lock" % (startup_dir, group_name))
        pidSupport.PidWParentSupport.__init__(self, lock_file)

#raise an exception if not running
def get_element_pid(startup_dir, group_name):
    pid_obj = ElementPidSupport(startup_dir, group_name)
    pid_obj.load_registered()
    if pid_obj.mypid is None:
        raise RuntimeError, "Group element not running"
    if pid_obj.parent_pid is None:
        raise RuntimeError, "Group element has no parent???"
    return (pid_obj.mypid, pid_obj.parent_pid)

