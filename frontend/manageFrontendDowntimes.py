#!/usr/bin/env python

from __future__ import print_function
import os.path
import os
import time, string
import sys
import re

STARTUP_DIR=sys.path[0]
sys.path.append(   os.path.join(STARTUP_DIR, "../../")   )

from glideinwms.frontend import glideinFrontendDowntimeLib
from glideinwms.frontend import glideinFrontendConfig

def usage():
    print("Usage:")
    print("  manageFrontendDowntimes.py -dir frontend_dir -cmd [command] [options]")
    print("where command is one of:")
    print("  add           - Add a scheduled downtime period")
    print("  down          - Put the factory down now(+delay)")
    print("  up            - Get the factory back up now(+delay)")
    print("  check         - Report if the factory is in downtime now(+delay)")
    print("Other options:")
    print("  -start [[[YYYY-]MM-]DD-]HH:MM[:SS] (start time for adding a downtime)")
    print("  -end [[[YYYY-]MM-]DD-]HH:MM[:SS]   (end time for adding a downtime)")
    print("  -delay [HHh][MMm][SS[s]]           (delay a downtime for down, up, and check cmds)")


# [[[YYYY-]MM-]DD-]HH:MM[:SS]
def strtxt2time( timeStr ):
    deftime = time.localtime( time.time() )
    year  = deftime[0]
    month = deftime[1]
    day   = deftime[2]
    seconds=0
    
    darr = timeStr.split('-') # [[[YYYY-]MM-]DD-]HH:MM[:SS]
    if len(darr)>1: # we have at least part of the date
        timeStr=darr[-1]
        day=long(darr[-2])
        if len(darr)>2:
            month=long(darr[-3])
            if len(darr)>3:
                year=long(darr[-4])

    tarr = timeStr.split(':')
    hours  =long(tarr[0])
    minutes=long(tarr[1])
    if len(tarr)>2:
        seconds=long(tarr[2])

    outtime = time.mktime(  (year, month, day, hours, minutes, seconds, 0, 0, -1)  )
    return outtime # this is epoch format


# [[[YYYY-]MM-]DD-]HH:MM[:SS]
# or
# unix_time
def str2time(timeStr):
    if len( timeStr.split(':', 1) )  >  1:
        return strtxt2time(timeStr) # has a :, so it must be a text representation
    else:
        print(timeStr)
        return long(timeStr) # should be a simple number


# [HHh][MMm][SS[s]]
def delay2time( delayStr ):
    hours=0
    minutes=0
    seconds=0

# getting hours
    harr=delayStr.split('h', 1)
    if len(harr)==2:
        hours=long(harr[0])
        delayStr=harr[1]

# getting minutes
    marr=delayStr.split('m', 1)
    if len(marr)==2:
        minutes=long(marr[0])
        delayStr=marr[1]

# getting seconds
    if delayStr[-1:]=='s':
        delayStr=delayStr[:-1] # remove final s if present
    if len(delayStr)>0:
        seconds=long(delayStr)
    
    return seconds+60*(minutes+60*hours)


def get_downtime_fd( work_dir ):
    frontendDescript    = glideinFrontendConfig.FrontendDescript( work_dir )
    fd = glideinFrontendDowntimeLib.DowntimeFile( os.path.join( work_dir, frontendDescript.data['DowntimesFile']  ) )
    return fd


# major commands
def add( opt_dict ):
    # glideinFrontendDowntimeLib.DowntimeFile(  self.elementDescript.frontend_data['DowntimesFile']  )
    down_fd = get_downtime_fd( opt_dict["dir"] ) 

    start_time = str2time( opt_dict["start"] )
    end_time   = str2time( opt_dict["end"]   )
    down_fd.addPeriod( start_time=start_time, end_time=end_time )
    return 0


# this calls checkDowntime(with delayed_start_time ) first and then startDowntime(with delayed_start_time and end_time)
def down( opt_dict ): 
    down_fd = get_downtime_fd(opt_dict["dir"])

    when = delay2time( opt_dict["delay"] )

    if (opt_dict["start"] == "None"):
        when += long(time.time())
    else:
        # delay applies only to the start time
        when += str2time(opt_dict["start"])

    if (opt_dict["end"] == "None"):
        end_time=None
    else:
        end_time = str2time(opt_dict["end"])

    if not down_fd.checkDowntime( check_time=when ):
        # only add a new line if not in downtime at that time
        return down_fd.startDowntime( start_time=when, end_time=end_time) 
    else:
        print("Frontend is already down. ")

    return 0


# calls endDowntime( with end_time only )
def up( opt_dict ): 
    down_fd = get_downtime_fd(opt_dict["dir"])

    when = delay2time( opt_dict["delay"] )

    if (opt_dict["end"]=="None"):
        when += long(time.time())
    else:
        # delay applies only to the end time
        when += str2time(opt_dict["end"])

    rtn = down_fd.endDowntime(  end_time=when )
    if (rtn>0):
        return 0
    else:
        print("Frontend is not in downtime.")
        return 1


def printtimes( opt_dict ):
    down_fd = get_downtime_fd( opt_dict["dir"] )
    when=delay2time( opt_dict["delay"]) + long(time.time())
    down_fd.printDowntime( check_time=when )


def get_args(argv):
    opt_dict = {"comment":"",
                "sec":"All",
                "delay":"0",
                "end":"None",
                "start":"None",
                "frontend":"All"}
    index=0

    for arg in argv:
        if (len(argv)<=index+1):
            continue

        if (arg == "-cmd"):            
            opt_dict["cmd"] = argv[index+1]
        if (arg == "-dir"):            
            opt_dict["dir"] = argv[index+1]
        if (arg == "-start"):          
            opt_dict["start"] = argv[index+1]
        if (arg == "-end"):            
            opt_dict["end"] = argv[index+1]
        if (arg == "-delay"):          
            opt_dict["delay"] = argv[index+1]

        index=index+1
    return opt_dict


def main(argv):
    if len(argv)<3:
        usage()
        return 1

    # Get the command line arguments
    opt_dict = get_args(argv)

    try:
        frontend_dir = opt_dict["dir"]
        cmd = opt_dict["cmd"]
    except KeyError as e:
        usage()
        print("-cmd -dir argument is required.")
        return 1

    try:
        os.chdir(frontend_dir)
    except OSError as e:
        usage()
        print("Failed to locate factory %s" % frontend_dir)
        print("%s"%e)
        return 1

    if   cmd=='add':
        return add( opt_dict )
    elif cmd=='down':
        return down( opt_dict )
    elif cmd=='up':
        return up( opt_dict )
    elif cmd=='check':
        return printtimes( opt_dict )
    else:
        usage()
        print("Invalid command %s" % cmd)
        return 1
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))

