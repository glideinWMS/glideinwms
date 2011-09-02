#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: glideFactoryPidLib.py,v 1.10.8.1 2010/09/08 03:22:59 parag Exp $
#
# Description:
#  Handle factory pids
# 
# Author:
#   Igor Sfiligoi
#

import os
import glideinwms_libs.pidSupport

############################################################

class FactoryPidSupport(glideinwms_libs.pidSupport.PidSupport):
    def __init__(self, startup_dir):
        lock_file = os.path.join(startup_dir, "lock/glideinWMS.lock")
        glideinwms_libs.pidSupport.PidSupport.__init__(self, lock_file)

#raise an exception if not running
def get_factory_pid(startup_dir):
    pid_obj = FactoryPidSupport(startup_dir)
    pid_obj.load_registered()
    if pid_obj.mypid == None:
        raise RuntimeError, "Factory not running"
    return pid_obj.mypid

############################################################

class EntryPidSupport(glideinwms_libs.pidSupport.PidWParentSupport):
    def __init__(self, startup_dir, entry_name):
        lock_file = os.path.join(startup_dir, "%s/entry_%s/lock/factory.lock" % (startup_dir, entry_name))
        glideinwms_libs.pidSupport.PidWParentSupport.__init__(self, lock_file)

#raise an exception if not running
def get_entry_pid(startup_dir, entry_name):
    pid_obj = EntryPidSupport(startup_dir, entry_name)
    pid_obj.load_registered()
    if pid_obj.mypid == None:
        raise RuntimeError, "Entry not running"
    if pid_obj.parent_pid == None:
        raise RuntimeError, "Entry has no parent???"
    return (pid_obj.mypid, pid_obj.parent_pid)

