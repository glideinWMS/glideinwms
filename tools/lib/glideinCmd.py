#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#  Helper module for all glideinWMS pseudo-interactive commands
#
# Author:
#   Igor Sfiligoi (May 2008)
#

import sys,string,os,stat
import glideinMonitor


# Try to execute the pseudo interactive command
# based on the passed arguments
#
# argv_func is a callback that transforms the unrecognized arguments
# into a list of arguments to pass to the command line after it has
# moved into the monitored job dir
#
def exe_cmd(argv_func,argv=sys.argv):
    try:
        args=glideinMonitor.parseArgs(argv[1:])
        glideinMonitor.monitor(args['jid'],args['schedd_name'],args['pool_name'],
                               args['timeout'],
                               createCmdMonitorFile,argv_func(args['argv']))
    except RuntimeError as e:
        print e
        sys.exit(1)

# Try to execute the pseudo interactive command
# based on the passed arguments
#
# argv_func is a callback that transforms the unrecognized arguments
# into a list of arguments to pass to the command line
#
def exe_cmd_simple(argv_func,argv=sys.argv):
    try:
        args=glideinMonitor.parseArgs(argv[1:])
        glideinMonitor.monitor(args['jid'],args['schedd_name'],args['pool_name'],
                               args['timeout'],
                               createCmdMonitorFileSimple,argv_func(args['argv']))
    except RuntimeError as e:
        print e
        sys.exit(1)

# Try to execute the pseudo interactive command
# based on the passed arguments
#
# argv_func is a callback that transforms the unrecognized arguments
# into a list of lines to populate a sh script
#
def exe_cmd_script(argv_func,argv=sys.argv):
    try:
        args=glideinMonitor.parseArgs(argv[1:])
        glideinMonitor.monitor(args['jid'],args['schedd_name'],args['pool_name'],
                               args['timeout'],
                               createCmdMonitorFileScript,argv_func(args['argv']))
    except RuntimeError as e:
        print e
        sys.exit(1)

######################################
# INTERNAL - Do not use directly
######################################

# create a file usable by a callback function for glideinMonitor.monitor
def monitorScriptFromList(monitor_file_name,monitor_control_relname,
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
                         argv,condor_status,monitorVM):
    if condor_status.has_key('GLEXEC_STARTER'):
        glexec_starter=condor_status['GLEXEC_STARTER']
    else:
        glexec_starter=False #if not defined, assume no gLExec

    script_lines=[]
    # find work dir and execute command there
    if glexec_starter:
        # job running in another branch of glexec invocation
        script_lines.append("outdir=`ls -dlt ../../../starter* | tail -1 | awk '{print $9}'`")
        script_lines.append("(cd $outdir/execute/dir*; if [ $? -eq 0 ]; then %s; else echo Internal error; fi)"%argv2cmd(argv))
    else:
        if condor_status.has_key('USES_MONITOR_STARTD'):
            monitor_startd=condor_status['USES_MONITOR_STARTD']
        else:
            monitor_startd=False #if not defined, assume the old operation mode (no monitor startd)

        if monitor_startd:
            # job running in a different execute dir
            script_lines.append("outdir=`ls -dlt ../../../execute* | tail -1 | awk '{print $9}'`")
            script_lines.append("(cd $outdir/dir*; if [ $? -eq 0 ]; then %s; else echo Internal error; fi)"%argv2cmd(argv))
        else:
            # job running in a different subdir of the execute dir
            script_lines.append("outdir=`ls -lt .. | tail -1 | awk '{print $9}'`")
            script_lines.append("(cd ../$outdir; if [ $? -eq 0 ]; then %s; else echo Internal error; fi)"%argv2cmd(argv))

    return monitorScriptFromList(monitor_file_name,monitor_control_relname,script_lines)

# callback function for glideinMonitor.monitor
# executes the command
def createCmdMonitorFileSimple(monitor_file_name,monitor_control_relname,
                               argv,condor_status,monitorVM):
    script_lines=[]
    script_lines.append(argv2cmd(argv))
    return monitorScriptFromList(monitor_file_name,monitor_control_relname,script_lines)

# callback function for glideinMonitor.monitor
# executes the script_list lines
def createCmdMonitorFileScript(monitor_file_name,monitor_control_relname,
                               script_list,condor_status,monitorVM):
    return monitorScriptFromList(monitor_file_name,monitor_control_relname,script_list)


