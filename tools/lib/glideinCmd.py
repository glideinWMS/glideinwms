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
# into a list of arguments to pass to the command line
#
def exe_cmd(argv_func):
    args=glideinMonitor.parseArgs(sys.argv[1:])
    glideinMonitor.monitor(args['jid'],args['schedd_name'],args['pool_name'],
                           args['timeout'],
                           createCmdMonitorFile,argv_func(args['argv']))

######################################
# INTERNAL - Do not use directly
######################################

# callback function for glideinMonitor.monitor
# changes to the work dir and executes the command
def createCmdMonitorFile(monitor_file_name,monitor_control_relname,
                         argv,condor_status):
    fd=open(monitor_file_name,"w")
    try:
        fd.write("#!/bin/sh\n")
        # find out work dir
        fd.write("outdir=`ls -lt .. | tail -1 | awk '{print $9}'`\n")
        # execute command in work dir
        fd.write("(cd ../$outdir; if [ $? -eq 0 ]; then %s; else echo Internal error; fi)\n"%(string.join(argv)))
        fd.write("echo Done > %s\n"%monitor_control_relname)
    finally:
        fd.close()

    os.chmod(monitor_file_name,stat.S_IRWXU)

