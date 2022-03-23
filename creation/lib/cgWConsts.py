# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Keep all the constants used to create glidein entries in this module
#
# Author: Igor Sfiligoi
#

import os.path

from . import cWConsts

# these are in the stage dir, so they need to be renamed if changed
AFTER_FILE_LISTFILE = "after_%s" % cWConsts.FILE_LISTFILE
AT_FILE_LISTFILE = "at_%s" % cWConsts.FILE_LISTFILE

CONDOR_FILE = "condor_bin_%s.tgz"
CONDOR_DIR = "condor"
CONDOR_ATTR = "CONDOR_DIR"

CONDOR_STARTUP_FILE = "condor_startup.sh"

# constants for cvmfsexec
CVMFSEXEC_DISTRO_FILE = "cvmfsexec_dist_%s.tgz"
CVMFSEXEC_DIR = "cvmfsexec"
CVMFSEXEC_ATTR = "CVMFSEXEC_DIR"


# these are in the submit dir, so they can be changed
PARAMS_FILE = "params.cfg"
ATTRS_FILE = "attributes.cfg"

STARTUP_FILE = "glidein_startup.sh"
GLIDEIN_FILE = "glidein.descript"
JOB_DESCRIPT_FILE = "job.descript"
SUBMIT_FILE = "job.condor"
SUBMIT_FILE_ENTRYSET = "job.%s.condor"
LOCAL_START_WRAPPER = "local_start.sh"
XML_CONFIG_FILE = "glideinWMS.xml"
INFOSYS_FILE = "infosys.descript"
RSA_KEY = "rsa.key"
MONITOR_CONFIG_FILE = "monitor.xml"

UPDATE_PROXY_FILE = "update_proxy.py"

FRONTEND_DESCRIPT_FILE = "frontend.descript"

INITD_STARTUP_FILE = "factory_startup"

WEB_BASE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "web_base")

STARTUP_FILE_PAYLOAD = (
    "add_config_line.source",
    "get_id_selectors.source",
    "logging_utils.source",
    "b64uuencode.source",
    "glidein_paths.source",
)


###################################################
#
# These functions append constant parts to strings
#
###################################################


def get_entry_submit_dir(submit_dir, entry_name):
    entry_submit_dir = os.path.join(submit_dir, "entry_" + entry_name)
    return entry_submit_dir


def get_entry_name_from_entry_submit_dir(entry_submit_dir):
    entry_name_arr = os.path.basename(entry_submit_dir).split("_", 1)
    if entry_name_arr[0] != "entry":
        raise ValueError("%s not a entry_submit_dir" % entry_submit_dir)
    return entry_name_arr[1]


def get_entry_log_dir(log_dir, entry_name):
    entry_log_dir = os.path.join(log_dir, "entry_" + entry_name)
    return entry_log_dir


def get_entry_userlog_dir(log_dir, entry_name):
    entry_log_dir = os.path.join(log_dir, "entry_" + entry_name)
    return entry_log_dir


def get_entry_userproxies_dir(proxies_dir, entry_name):
    proxies_log_dir = os.path.join(proxies_dir, "entry_" + entry_name)
    return proxies_log_dir


def get_entry_stage_dir(stage_dir, entry_name):
    entry_stage_dir = os.path.join(stage_dir, "entry_" + entry_name)
    return entry_stage_dir


def get_entry_name_from_entry_stage_dir(entry_stage_dir):
    entry_name_arr = os.path.basename(entry_stage_dir).split("_", 1)
    if entry_name_arr[0] != "entry":
        raise ValueError("%s not a entry_stage_dir" % entry_stage_dir)
    return entry_name_arr[1]


def get_entry_monitor_dir(monitor_dir, entry_name):
    entry_monitor_dir = os.path.join(monitor_dir, "entry_" + entry_name)
    return entry_monitor_dir


def get_entry_name_from_entry_monitor_dir(entry_monitor_dir):
    entry_name_arr = os.path.basename(entry_monitor_dir).split("_", 1)
    if entry_name_arr[0] != "entry":
        raise ValueError("%s not a entry_monitor_dir" % entry_monitor_dir)
    return entry_name_arr[1]
