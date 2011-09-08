#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glideinFrontendPidLib.py,v 1.2.8.1 2010/09/08 03:12:32 parag Exp $
#
# Description:
#  Handle frontend pids
# 
# Author:
#   Igor Sfiligoi
#

import os

import glideinwms_libs.pidSupport

############################################################

class FrontendPidSupport(glideinwms_libs.pidSupport.PidSupport):
    def __init__(self, startup_dir):
        lock_file = os.path.join(startup_dir, "lock/frontend.lock")
        glideinwms_libs.pidSupport.PidSupport.__init__(self, lock_file)

#raise an exception if not running
def get_frontend_pid(startup_dir):
    pid_obj = FrontendPidSupport(startup_dir)
    pid_obj.load_registered()
    if pid_obj.mypid == None:
        raise RuntimeError, "Frontend not running"
    return pid_obj.mypid

############################################################

class ElementPidSupport(glideinwms_libs.pidSupport.PidWParentSupport):
    def __init__(self, startup_dir, group_name):
        lock_file = os.path.join(startup_dir, "%s/group_%s/lock/frontend.lock" % (startup_dir, group_name))
        glideinwms_libs.pidSupport.PidWParentSupport.__init__(self, lock_file)

#raise an exception if not running
def get_element_pid(startup_dir, group_name):
    pid_obj = ElementPidSupport(startup_dir, group_name)
    pid_obj.load_registered()
    if pid_obj.mypid == None:
        raise RuntimeError, "Group element not running"
    if pid_obj.parent_pid == None:
        raise RuntimeError, "Group element has no parent???"
    return (pid_obj.mypid, pid_obj.parent_pid)

