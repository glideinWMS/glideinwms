#!/bin/env python
#
# condor_ls
#
# Description:
#   Execute a ls command on a condor job working directory
#
# Usage:
#  glidein_ls.py <cluster>.<process> [<dir>] [-name <schedd_name>] [-pool <pool_name> ] [-timeout <nr secs>]
#
# Author:
#   Igor Sfiligoi (May 2007)
#
# License:
#  Fermitools
#

import os,os.path
import string
import stat
import sys
sys.path.append(os.path.join(os.path[0],"lib"))
sys.path.append(os.path.join(os.path[0],"../lib"))

import glideinMonitor

def createDirMonitorFile(monitor_file_name,monitor_control_relname,
                         argv,condor_status):
    fd=open(monitor_file_name,"w")
    try:
        fd.write("#!/bin/sh\n")
        fd.write("outdir=`ls -lt .. | tail -1 | awk '{print $9}'`\n")
        fd.write("(cd ../$outdir; if [ $? -eq 0 ]; then ls %s; else echo Internal error; fi)\n"%(string.join(argv)))
        fd.write("echo Done > %s\n"%monitor_control_relname)
    finally:
        fd.close()

    os.chmod(monitor_file_name,stat.S_IRWXU)


args=glideinMonitor.parseArgs(sys.argv[1:])

glideinMonitor.monitor(args['jid'],args['schedd_name'],args['pool_name'],
                       args['timeout'],
                       createDirMonitorFile,args['argv'])
