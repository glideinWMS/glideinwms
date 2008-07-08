#!/bin/env python

#
# Description:
#  This program allows to add announced downtimes
#  as well as handle unexpected downtimes
#

import os.path
import time
import sys
import glideFactoryConfig
import glideFactoryDowntimeLib

def usage():
    print "Usage:"
    print "  manageFactoryDowntimes.py factory_dir ['factory'|entry_name] [command]"
    print "where command is one of:"
    print "  add start_time end_time - Add a scheduled downtime period"
    print "  down [delay]            - Put the factory down now(+delay)" 
    print "  up [delay]              - Get the factory back up now(+delay)"
    print "  check [delay]           - Report if the factory is in downtime now(+delay)"
    print "where *_time is in one of the two formats:"
    print "  [[[YYYY-]MM-]DD-]HH:MM[:SS]"
    print "  unix_time"
    print "and delay is of the format:"
    print "  [HHh][MMm][SS[s]]"
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
        len(darr)>2:
            month=long(darr[-3])
            len(darr)>3:
                month=long(darr[-4])

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
    if len(timeStr.split(':',1))>1:
        # has a :, so it must be a text representation
        return strtxt2time(timeStr)
    else:
        # should be a simple number
        return long(timeStr)

def add(down_fd,argv):
    start_time=str2time(argv[1])
    end_time=str2time(argv[2])
    down_fd.addPeriod(start_time,end_time)
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

def down(down_fd,argv):
    when=0
    if len(argv)>1:
        when=delay2time(argv[1])

    when+=long(time.time())

    if not down_fd.checkDowntime(when): #only add a new line if not in downtimeat that time
        down_fd.startDowntime(when)
    return 0

def up(down_fd,argv):
    when=0
    if len(argv)>1:
        when=delay2time(argv[1])

    when+=long(time.time())

    if down_fd.checkDowntime(when): #only terminate downtime if there was an open period
        down_fd.endDowntime(when)
    return 0

def check(down_fd,argv):
    when=0
    if len(argv)>1:
        when=delay2time(argv[1])

    when+=long(time.time())

    in_downtime=down_fd.checkDowntime(when)
    if in_downtime:
        print "Down"
    else:
        print "Up"
    return 0

def main(argv):
    if len(argv)<4:
        usage()
        return 1

    # get the downtime file from config
    factory_dir=argv[1]
    try:
        os.chdir(factory_dir)
    except OSError, e:
        usage()
        print "Failed to locate factory %s"%factory_dir
        print "%s"%e
        return 1

    entry_name=argv[2]
    try:
        if entry_name=='factory':
            config=glideFactoryConfig.GlideinDescript()
        else:
            config=glideFactoryConfig.JobDescript(entry_name)
    except IOError, e:
        usage()
        print "Failed to load config for %s %s"%(factory_dir,entry_name)
        print "%s"%e
        return 1

    #if not os.path.isfile(descr_file):
    #    print "Cound not find config file %s"%descr_file
    #    return 1

    
    fd=glideFactoryDowntimeLib.DowntimeFile(config.data['DowntimesFile'])

    cmd=argv[3]

    if cmd=='add':
        return add(fd,argv[3:])
    elif cmd=='down':
        return down(fd,argv[3:])
    elif cmd=='up':
        return up(fd,argv[3:])
    elif cmd=='check':
        return check(fd,argv[3:])
    else:
        usage()
        print "Invalid command %s"%cmd
        return 1
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))

