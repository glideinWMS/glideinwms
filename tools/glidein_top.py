#!/bin/env python
#
# glidein_top
#
# Execute a top command in the same glidein as the user job
#
# Usage:
#  glidein_top.py <cluster>.<process> [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>
#

import os
import stat
import sys
sys.path.append("lib")
sys.path.append("../lib")

import glideinMonitor

def createTopMonitorFile(monitor_file_name,monitor_control_relname,
                         argv,condor_status):
    fd=open(monitor_file_name,"w")
    try:
        fd.write("#!/bin/sh\n")
        fd.write("top -b -n 1\n")
        fd.write("echo Done > %s\n"%monitor_control_relname)
    finally:
        fd.close()

    os.chmod(monitor_file_name,stat.S_IRWXU)


args=glideinMonitor.parseArgs(sys.argv[1:])
if len(args['argv'])!=0:
    raise RuntimeError, "Unexpected parameters starting with %s found!"%args['argv'][0]

glideinMonitor.monitor(args['jid'],args['schedd_name'],args['pool_name'],
                       args['timeout'],
                       createTopMonitorFile,args['argv'])
