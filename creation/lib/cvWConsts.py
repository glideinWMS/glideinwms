#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Keep all the constants used to create frontend entries in this module
#
# Author: Igor Sfiligoi
#

import os.path
import cWConsts

AFTERGROUP_FILE_LISTFILE="aftergroup_%s"%cWConsts.FILE_LISTFILE
PREENTRY_FILE_LISTFILE="preentry_%s"%cWConsts.FILE_LISTFILE
AFTERGROUP_PREENTRY_FILE_LISTFILE="aftergroup_%s"%PREENTRY_FILE_LISTFILE

PARAMS_FILE="params.cfg"
ATTRS_FILE="attrs.cfg"

FRONTEND_DESCRIPT_FILE="frontend.descript"
FRONTEND_MAP_FILE="frontend.mapfile"
FRONTEND_CONDOR_CONFIG_FILE="frontend.condor_config"
GROUP_DESCRIPT_FILE="group.descript"
GROUP_MAP_FILE="group.mapfile"
GROUP_WPILOTS_MAP_FILE="group_wpilots.mapfile"
XML_CONFIG_FILE="frontend.xml"

INITD_STARTUP_FILE="frontend_startup"

###################################################
#
# These functions append constant parts to strings
#
###################################################

def get_group_work_dir(work_dir,group_name):
    group_work_dir=os.path.join(work_dir,"group_"+group_name)
    return group_work_dir

def get_group_name_from_group_work_dir(group_work_dir):
    group_name_arr=os.path.basename(group_work_dir).split('_',1)
    if group_name_arr[0]!='group':
        raise ValueError('%s not a group_work_dir'%group_work_dir)
    return group_name_arr[1]

def get_group_log_dir(log_dir,group_name):
    group_log_dir=os.path.join(log_dir,"group_"+group_name)
    return group_log_dir

def get_group_stage_dir(stage_dir,group_name):
    group_stage_dir=os.path.join(stage_dir,"group_"+group_name)
    return group_stage_dir

def get_group_name_from_group_stage_dir(group_stage_dir):
    group_name_arr=os.path.basename(group_stage_dir).split('_',1)
    if group_name_arr[0]!='group':
        raise ValueError('%s not a group_stage_dir'%group_stage_dir)
    return group_name_arr[1]

def get_group_monitor_dir(monitor_dir,group_name):
    group_monitor_dir=os.path.join(monitor_dir,"group_"+group_name)
    return group_monitor_dir

def get_group_name_from_group_monitor_dir(group_monitor_dir):
    group_name_arr=os.path.basename(group_monitor_dir).split('_',1)
    if group_name_arr[0]!='group':
        raise ValueError('%s not a group_monitor_dir'%group_monitor_dir)
    return group_name_arr[1]


