#
# Description:
#  Helper module for all glideinWMS pseudo-interactive commands
#
# Author:
#   Igor Sfiligoi (May 2008)
#

import sys,string,os,stat
import glideinMonitor


# Try to execute the pesudo interactive command
# based on the passed arguments
#
# argv_func is a callback that transforms the unrecognized arguments
# into a list of arguments to pass to the command line after it has
# moved into the monitored job dir
#
def exe_cmd(argv_func):
    try:
        args=glideinMonitor.parseArgs(sys.argv[1:])
        glideinMonitor.monitor(args['jid'],args['schedd_name'],args['pool_name'],
                               args['timeout'],
                               createCmdMonitorFile,argv_func(args['argv']))
    except RuntimeError,e:
        print e
        sys.exit(1)

# Try to execute the pesudo interactive command
# based on the passed arguments
#
# argv_func is a callback that transforms the unrecognized arguments
# into a list of arguments to pass to the command line
#
def exe_cmd_simple(argv_func):
    try:
        args=glideinMonitor.parseArgs(sys.argv[1:])
        glideinMonitor.monitor(args['jid'],args['schedd_name'],args['pool_name'],
                               args['timeout'],
                               createCmdMonitorFileSimple,argv_func(args['argv']))
    except RuntimeError,e:
        print e
        sys.exit(1)

# Try to execute the pesudo interactive command
# based on the passed arguments
#
# argv_func is a callback that creates the monitoring script
# arguments are (file_name,out_relname,argv,condor_status)
# where argv is the list of unrecognized arguments
#
def exe_script(argv_func):
    try:
        args=glideinMonitor.parseArgs(sys.argv[1:])
        glideinMonitor.monitor(args['jid'],args['schedd_name'],args['pool_name'],
                               args['timeout'],
                               argv_func,args['argv'])
    except RuntimeError,e:
        print e
        sys.exit(1)

######################################
# INTERNAL - Do not use directly
######################################

# create a file usable by a callback function for glideinMonitor.monitor
def createCmdMonitorFileScript(monitor_file_name,monitor_control_relname,
                               script_list):
    # create the command file
    fd=open(monitor_file_name,"w")
    try:
        fd.write("#!/bin/sh\n")
        fd.write("glidein_cmd_startdir=$PWD\n")
        for script_line in script_list:
            fd.write("%s\n"%script_line)
        fd.write('echo Done > "$glidein_cmd_startdir/%s"\n'%monitor_control_relname)
    finally:
        fd.close()

    os.chmod(monitor_file_name,stat.S_IRWXU)

# convert a list into a command line string
def argv2cmd(argv):
    # escape the spaces
    # everything else should be passed to the cmsdline as it is
    eargv=[]
    for arg in argv:
        eargv.append(string.replace(arg,' ','\ '))
    return string.join(eargv)

# callback function for glideinMonitor.monitor
# changes to the work dir and executes the command
def createCmdMonitorFile(monitor_file_name,monitor_control_relname,
                         argv,condor_status):
    script_lines=[]
    script_lines.append("outdir=`ls -lt .. | tail -1 | awk '{print $9}'`")
    # execute command in work dir
    script_lines.append("(cd ../$outdir; if [ $? -eq 0 ]; then %s; else echo Internal error; fi)"%argv2cmd(argv))
    return createCmdMonitorFileScript(monitor_file_name,monitor_control_relname,script_list)

# callback function for glideinMonitor.monitor
# executes the command
def createCmdMonitorFileSimple(monitor_file_name,monitor_control_relname,
                         argv,condor_status):
    script_lines=[]
    script_lines.append(argv2cmd(argv))
    return createCmdMonitorFileScript(monitor_file_name,monitor_control_relname,script_list)


