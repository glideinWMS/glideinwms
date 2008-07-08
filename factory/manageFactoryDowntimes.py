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
    print "where *_time is of the format:"
    print "  [[MM-]DD-]HH:MM[:SS]"
    print "and delay is of the format:"
    print "  [HHh][MMm][SS[s]]"
    print

def add(down_fd,argv):
    raise RuntimeError, "add not yet implemented"
    return 0

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
    else:
        usage()
        print "Invalid command %s"%cmd
        return 1
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))

