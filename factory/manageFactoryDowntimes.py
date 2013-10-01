#!/usr/bin/env python

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#  This program allows to add announced downtimes
#  as well as handle unexpected downtimes
#

import os.path
import os
import time,string
import sys
import re

STARTUP_DIR=sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR,"../../"))

from glideinwms.lib import ldapMonitor
from glideinwms.lib import condorMonitor
from glideinwms.creation.lib import cgWDictFile
from glideinwms.creation.lib import cgWConsts

from glideinwms.factory import glideFactoryConfig
from glideinwms.factory import glideFactoryDowntimeLib

def usage():
    print "Usage:"
    print "  manageFactoryDowntimes.py -dir factory_dir -entry ['all'|'factory'|'entries'|entry_name] -cmd [command] [options]"
    print "where command is one of:"
    print "  add           - Add a scheduled downtime period"
    print "  down          - Put the factory down now(+delay)" 
    print "  up            - Get the factory back up now(+delay)"
    print "  ress          - Set the up/down based on RESS status"
    print "  bdii          - Set the up/down based on bdii status"
    print "  ress+bdii     - Set the up/down based both on RESS and bdii status"
    print "  check         - Report if the factory is in downtime now(+delay)"
    print "  vacuum        - Remove all expired downtime info"
    print "Other options:"
    print "  -start [[[YYYY-]MM-]DD-]HH:MM[:SS] (start time for adding a downtime)"
    print "  -end [[[YYYY-]MM-]DD-]HH:MM[:SS]   (end time for adding a downtime)"
    print "  -delay [HHh][MMm][SS[s]]           (delay a downtime for down, up, and check cmds)"
    print "  -ISinfo 'CEStatus'        (attribute used in ress/bdii for creating downtimes)"
    print "  -security SECURITY_CLASS  (restricts a downtime to users of that security class)"
    print "                            (If not specified, the downtime is for all users.)"
    print "  -frontend SECURITY_NAME   (Limits a downtime to one frontend)"
    print "  -comment \"Comment here\"   (user comment for the downtime. Not used by WMS.)"
    print

# [[[YYYY-]MM-]DD-]HH:MM[:SS]
def strtxt2time(timeStr):
    deftime=time.localtime(time.time())
    year=deftime[0]
    month=deftime[1]
    day=deftime[2]
    seconds=0
    
    darr=timeStr.split('-')
    if len(darr)>1: # we have at least part of the date
        timeStr=darr[-1]
        day=long(darr[-2])
        if len(darr)>2:
            month=long(darr[-3])
            if len(darr)>3:
                year=long(darr[-4])

    tarr=timeStr.split(':')
    hours=long(tarr[0])
    minutes=long(tarr[1])
    if len(tarr)>2:
        seconds=long(tarr[2])
    outtime=time.mktime((year, month, day, hours, minutes, seconds, 0, 0, -1))
    return outtime


# [[[YYYY-]MM-]DD-]HH:MM[:SS]
# or
# unix_time
def str2time(timeStr):
    #if (timeStr is None) or (timeStr=="None") or (timeStr==""):
    #    return time.localtime(time.time())
    if len(timeStr.split(':',1))>1:
        # has a :, so it must be a text representation
        return strtxt2time(timeStr)
    else:
        print timeStr
        # should be a simple number
        return long(timeStr)

# Create an array for each value in the frontend descript file
def get_security_classes(factory_dir):
    sec_array=[];
    frontendDescript=glideFactoryConfig.ConfigFile(factory_dir+"/frontend.descript",lambda s:s)
    for fe in frontendDescript.data.keys():
        for sec_class in frontendDescript.data[fe]['usermap']:
            sec_array.append(sec_class);
    return sec_array;

# Create an array for each frontend in the frontend descript file
def get_frontends(factory_dir):
    frontendDescript=glideFactoryConfig.ConfigFile(factory_dir+"/frontend.descript",lambda s:s)
    return frontendDescript.data.keys();

# Create an array for each entry in the glidein descript file
def get_entries(factory_dir):
    glideinDescript=glideFactoryConfig.GlideinDescript()
    #glideinDescript=glideFactoryConfig.ConfigFile(factory_dir+"/glidein.descript",lambda s:s)
    return string.split(glideinDescript.data['Entries'],',');
#
#
def get_downtime_fd(entry_name,cmdname):
    try:
        # New style has config all in the factory file
        #if entry_name=='factory':
        config=glideFactoryConfig.GlideinDescript()
        #else:
        #    config=glideFactoryConfig.JobDescript(entry_name)
    except IOError:
        raise RuntimeError, "Failed to load config for %s"%entry_name

    fd=glideFactoryDowntimeLib.DowntimeFile(config.data['DowntimesFile'])
    return fd

def get_downtime_fd_dict(entry_or_id,cmdname,opt_dict):
    out_fds={}
    if entry_or_id in ('entries','All'):
        glideinDescript=glideFactoryConfig.GlideinDescript()
        entries=string.split(glideinDescript.data['Entries'],',')
        for entry in entries:
            out_fds[entry]=get_downtime_fd(entry,cmdname)
        if (entry_or_id=='All') and (not opt_dict.has_key("entries")):
            out_fds['factory']=get_downtime_fd('factory',cmdname)
    else:
        out_fds[entry_or_id]=get_downtime_fd(entry_or_id,cmdname)

    return out_fds

def add(entry_name,opt_dict):
    down_fd=get_downtime_fd(entry_name,opt_dict["dir"])
    start_time=str2time(opt_dict["start"])
    end_time=str2time(opt_dict["end"])
    sec_name=opt_dict["sec"]
    frontend=opt_dict["frontend"]
    down_fd.addPeriod(start_time=start_time,end_time=end_time,entry=entry_name,frontend=frontend,security_class=sec_name,comment=opt_dict["comment"])
    return 0

# [HHh][MMm][SS[s]]
def delay2time(delayStr):
    hours=0
    minutes=0
    seconds=0
    harr=delayStr.split('h',1)
    if len(harr)==2:
        hours=long(harr[0])
        delayStr=harr[1]
    marr=delayStr.split('m',1)
    if len(marr)==2:
        minutes=long(marr[0])
        delayStr=marr[1]
    if delayStr[-1:]=='s':
        delayStr=delayStr[:-1] # remove final s if present
    if len(delayStr)>0:
        seconds=long(delayStr)
    
    return seconds+60*(minutes+60*hours)


def down(entry_name,opt_dict):
    down_fd=get_downtime_fd(entry_name,opt_dict["dir"])
    when=delay2time(opt_dict["delay"])
    if (opt_dict["start"]=="None"):
        when+=long(time.time())
    else:
        when+=str2time(opt_dict["start"]);
    if (opt_dict["end"]=="None"):
        end_time=None
    else:
        end_time=str2time(opt_dict["end"])
    frontend=opt_dict["frontend"]
    sec_name=opt_dict["sec"]
    if not down_fd.checkDowntime(entry=entry_name, frontend=frontend, security_class=sec_name, check_time=when): 
        #only add a new line if not in downtime at that time
        return down_fd.startDowntime(start_time=when,end_time=end_time,frontend=frontend,security_class=sec_name,entry=entry_name,comment=opt_dict["comment"])
    else:
        print "Entry is already down. (%s)" % down_fd.downtime_comment
    return 0

def up(entry_name,opt_dict):
    down_fd=get_downtime_fd(entry_name,opt_dict["dir"])
    when=delay2time(opt_dict["delay"])
    sec_name=opt_dict["sec"]
    frontend=opt_dict["frontend"]
    comment=opt_dict["comment"]
    if (opt_dict["end"]=="None"):
        when+=long(time.time())
    else:
        when+=str2time(opt_dict["end"]);
    # commenting this check out since we could be in a downtime
    # for certain security_classes/frontend, but if we specify
    # -cmd up and -security All, etc, it should clear out all downtimes
    #if (down_fd.checkDowntime(entry=entry_name, frontend=frontend, security_class=sec_name, check_time=when)or (sec_name=="All")): 

    rtn=down_fd.endDowntime(end_time=when,entry=entry_name,frontend=frontend,security_class=sec_name,comment=comment)
    if (rtn>0):
        return 0
    else:
        print "Entry is not in downtime."
        return 1

# This function replaces "check", which does not take into account
# security classes.  This function will read the downtimes file
# and parse it to determine whether the downtime is relevant to the 
# security class
def printtimes(entry_or_id,opt_dict):
    config_els=get_downtime_fd_dict(entry_or_id,opt_dict["dir"],opt_dict)
    when=delay2time(opt_dict["delay"])+long(time.time())
    entry_keys=config_els.keys()
    entry_keys.sort()
    for entry in entry_keys:
        down_fd=config_els[entry]
        down_fd.printDowntime(entry=entry, check_time=when)

# This function is now deprecated, replaced by printtimes
# as it does not take into account that an entry can be down for
# only some security classes.
def check(entry_or_id,opt_dict):
    config_els=get_downtime_fd_dict(entry_or_id,opt_dict["dir"],opt_dict)
    when=delay2time(opt_dict["delay"])
    sec_name=opt_dict["sec"]
    when+=long(time.time())

    entry_keys=config_els.keys()
    entry_keys.sort()
    for entry in entry_keys:
        down_fd=config_els[entry]
        in_downtime=down_fd.checkDowntime(entry=entry, security_class=sec_name, check_time=when)
        if in_downtime:
            print "%s\tDown"%entry
        else:
            print "%s\tUp"%entry

    return 0

def vacuum(entry_or_id,opt_dict):
    config_els=get_downtime_fd_dict(entry_or_id,opt_dict["dir"],opt_dict)

    entry_keys=config_els.keys()
    entry_keys.sort()
    for entry in entry_keys:
        down_fd=config_els[entry]
        down_fd.purgeOldPeriods()

    return 0

def get_production_ress_entries(server,ref_dict_list):

    production_entries=[]

    condor_obj=condorMonitor.CondorStatus(pool_name=server)
    condor_obj.load(constraint='(GlueCEInfoContactString=!=UNDEFINED)&&(GlueCEStateStatus=?="Production")',format_list=[])
    condor_refs=condor_obj.fetchStored().keys()
    #del condor_obj

    for el in ref_dict_list:
        ref=el['ref']
        if ref in condor_refs:
            production_entries.append(el['entry_name'])    
    
    return production_entries

def get_production_bdii_entries(server,ref_dict_list):

    production_entries=[]

    bdii_obj=ldapMonitor.BDIICEQuery(server)
    bdii_obj.load()
    bdii_obj.filterStatus(usable=True)
    bdii_refs=bdii_obj.fetchStored().keys()
    #del bdii_obj

    for el in ref_dict_list:
        ref=el['ref']
        if ref in bdii_refs:
            production_entries.append(el['entry_name'])    
    
    return production_entries

def infosys_based(entry_name,opt_dict,infosys_types):
    # find out which entries I need to look at
    # gather downtime fds for them
    config_els={}
    if entry_name=='factory':
        return 0 # nothing to do... the whole factory cannot be controlled by infosys
    elif entry_name in ('entries','all'):
        # all==entries in this case, since there is nothing to do for the factory
        glideinDescript=glideFactoryConfig.GlideinDescript()
        entries=string.split(glideinDescript.data['Entries'],',')
        for entry in entries:
            config_els[entry]={}
    else:
        config_els[entry_name]={}

    # load the infosys info

    for entry in config_els.keys():
        infosys_fd=cgWDictFile.InfoSysDictFile(cgWConsts.get_entry_submit_dir('.',entry),cgWConsts.INFOSYS_FILE)
        infosys_fd.load()

        if len(infosys_fd.keys)==0:
            # entry not associated with any infosys, cannot be managed, ignore
            del config_els[entry]
            continue

        compatible_infosys=False
        for k in infosys_fd.keys:
            infosys_type=infosys_fd[k][0]
            if infosys_type in infosys_types:
                compatible_infosys=True
                break
        if not compatible_infosys:
            # entry not associated with a compatible infosys, cannot be managed, ignore
            del config_els[entry]
            continue
            
        config_els[entry]['infosys_fd']=infosys_fd

    if len(config_els.keys())==0:
        return 0 # nothing to do
    # all the remaining entries are handled by one of the supported infosys

    # summarize
    infosys_data={}
    for entry in config_els.keys():
        infosys_fd=config_els[entry]['infosys_fd']
        for k in infosys_fd.keys:
            infosys_type=infosys_fd[k][0]
            server=infosys_fd[k][1]
            ref=infosys_fd[k][2]
            if not infosys_data.has_key(infosys_type):
                infosys_data[infosys_type]={}
            infosys_data_type=infosys_data[infosys_type]
            if not infosys_data_type.has_key(server):
                infosys_data_type[server]=[]
            infosys_data_type[server].append({'ref':ref,'entry_name':entry})

    # get production entries
    production_entries=[]
    for infosys_type in infosys_data.keys():
        if infosys_type in infosys_types:
            infosys_data_type=infosys_data[infosys_type]
            for server in infosys_data_type.keys():
                infosys_data_server=infosys_data_type[server]
                if infosys_type=="RESS":
                    production_entries+=get_production_ress_entries(server,infosys_data_server)
                elif infosys_type=="BDII":
                    production_entries+=get_production_bdii_entries(server,infosys_data_server)
                else:
                    raise RuntimeError, "Unknown infosys type '%s'"%infosys_type # should never get here

    # Use the info to put the 
    entry_keys=config_els.keys()
    entry_keys.sort()
    for entry in entry_keys:
        if entry in production_entries:
            print "%s up"%entry
            up(entry,['up'])
        else:
            print "%s down"%entry
            down(entry,['down']) 
    
    return 0

def get_args(argv):
    #defaults
    opt_dict={"comment":"","sec":"All","delay":"0",\
            "end":"None","start":"None","frontend":"All"}
    index=0
    for arg in argv:
        if (arg == "-factory"):
            opt_dict["entry"]="factory"
        if (len(argv)<=index+1):
            continue;
        #Change lowercase all to All so checks for "All" work
        if (argv[index+1].lower()=="all"):
            argv[index+1]="All";
        if (arg == "-cmd"):
            opt_dict["cmd"]=argv[index+1]
        if (arg == "-dir"):
            opt_dict["dir"]=argv[index+1]
        if (arg == "-entry"):
            opt_dict["entry"]=argv[index+1]
        if (arg == "-comment"):
            opt_dict["comment"]=argv[index+1]
        if (arg == "-start"):
            opt_dict["start"]=argv[index+1]
        if (arg == "-end"):
            opt_dict["end"]=argv[index+1]
        if (arg == "-delay"):
            opt_dict["delay"]=argv[index+1]
        if (arg == "-ISinfo"):
            opt_dict["ISinfo"]=argv[index+1]
        if (arg == "-security"):
            opt_dict["sec"]=argv[index+1]
        if (arg == "-frontend"):
            opt_dict["frontend"]=argv[index+1]
        index=index+1
    return opt_dict;

def main(argv):
    if len(argv)<3:
        usage()
        return 1

    # Get the command line arguments
    opt_dict=get_args(argv)
    mandatory_comments=False
    if (os.environ.has_key("GLIDEIN_MANDATORY_COMMENTS")):
        if (os.environ["GLIDEIN_MANDATORY_COMMENTS"].lower() in ("on","true","1")):
            mandatory_comments=True
    if (opt_dict["cmd"] in ("check","vacuum")):
        mandatory_comments=False

    try:
        factory_dir=opt_dict["dir"]
        entry_name=opt_dict["entry"]
        cmd=opt_dict["cmd"]
        if (mandatory_comments):
            comments=opt_dict["comment"]
            if (comments == ""):
                raise KeyError
    except KeyError, e:
        usage();
        print "-cmd -dir and -entry arguments are required."
        if (mandatory_comments):
            print "Mandatory comments are enabled.  add -comment."
        return 1;
    if (opt_dict["sec"]!="All"):
        if (not (opt_dict["sec"] in get_security_classes(factory_dir))):
            print "Invalid security class";
            print "Valid security classes are: ";
            for sec_class in get_security_classes(factory_dir):
                print sec_class
            return 1
    if (opt_dict["frontend"]!="All"):
        if (not (opt_dict["frontend"] in get_frontends(factory_dir))):
            print "Invalid frontend identity:";
            print "Valid frontends are: ";
            for fe in get_frontends(factory_dir):
                print fe
            return 1

    try:
        os.chdir(factory_dir)
    except OSError, e:
        usage()
        print "Failed to locate factory %s"%factory_dir
        print "%s"%e
        return 1

    #Verify Entry is an actual entry
    if (opt_dict["entry"].lower()=="entries"):
        opt_dict["entries"]="true";
        opt_dict["entry"]="All";
        entry_name="All";
    if ((opt_dict["entry"]!="All")and(opt_dict["entry"]!="factory")):
        if (not (opt_dict["entry"] in get_entries(factory_dir))):
            print "Invalid entry name";
            print "Valid entries are:";
            for entry in get_entries(factory_dir):
                print entry
            return 1


    if cmd=='add':
        return add(entry_name,opt_dict)
    elif cmd=='down':
        return down(entry_name,opt_dict)
    elif cmd=='up':
        return up(entry_name,opt_dict)
    elif cmd=='check':
        return printtimes(entry_name,opt_dict)
    elif cmd=='ress':
        return infosys_based(entry_name,opt_dict,['RESS'])
    elif cmd=='bdii':
        return infosys_based(entry_name,opt_dict,['BDII'])
    elif cmd=='ress+bdii':
        return infosys_based(entry_name,opt_dict,['RESS','BDII'])
    elif cmd=='vacuum':
        return vacuum(entry_name,opt_dict)
    else:
        usage()
        print "Invalid command %s"%cmd
        return 1
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))

