#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Functions needed to create files used by the VO Frontend
#
# Author: Igor Sfiligoi
#

import os,os.path
import stat
import string
import re
import traceback
import tarfile
import cStringIO
#import cvWConsts
from glideinwms.lib import condorExe
from glideinwms.lib import condorSecurity

#########################################
# Create init.d compatible startup file
def create_initd_startup(startup_fname,frontend_dir,glideinWMS_dir, cfg_name):
    fd=open(startup_fname,"w")
    try:
        fd.write("#!/bin/bash\n")
        fd.write("# condor   This is the glideinWMS frontend startup script\n")
        fd.write("# chkconfig: 35 90 30\n")
        fd.write("# description: Starts and stops a glideinWMS frontend\n\n")
        
        fd.write("# Emulate function library.\n")
        fd.write("success() {\n")
        fd.write(' echo -en "\\033[60G[\033[32mOK\033[0m]"\n')
        fd.write(" return 0\n}\n\n")

        fd.write("failure() {\n")
        fd.write(' echo -en "\\033[60G[\033[31mFAILED\033[0m]"\n')
        fd.write(" return 1\n}\n\n")
        
        fd.write("frontend_dir='%s'\n"%frontend_dir)
        fd.write("glideinWMS_dir='%s'\n"%glideinWMS_dir)
        fd.write("default_cfg_fpath='%s'\n"%cfg_name)
        fd.write("\n")
        
        fd.write("frontend_name=`awk '/^FrontendName /{print $2}' $frontend_dir/frontend.descript`\n")
        fd.write('id_str="$frontend_name"\n')
        fd.write("\n")
        
        fd.write("start() {\n")
        fd.write('        echo -n "Starting glideinWMS frontend $id_str: "\n')
        fd.write('        nice -2 "$glideinWMS_dir/frontend/glideinFrontend.py" "$frontend_dir" 2>/dev/null 1>&2 </dev/null &\n')
        fd.write('        sleep 5\n')
        fd.write('        "$glideinWMS_dir/frontend/checkFrontend.py" "$frontend_dir"  2>/dev/null 1>&2 </dev/null && success || failure\n')
        fd.write("        RETVAL=$?\n")
        fd.write("        echo\n")
        fd.write("}\n\n")
        
        fd.write("stop() {\n")
        fd.write('        echo -n "Shutting down glideinWMS frontend $id_str: "\n')
        fd.write('        "$glideinWMS_dir/frontend/stopFrontend.py" "$frontend_dir" 2>/dev/null 1>&2 </dev/null && success || failure\n')
        fd.write("        RETVAL=$?\n")
        fd.write("        echo\n")
        fd.write("}\n\n")
        
        fd.write("restart() {\n")
        fd.write("        stop\n")
        fd.write("        if [ $RETVAL -ne 0 ]; then\n")
        fd.write("          exit $RETVAL\n")
        fd.write("        fi\n")
        fd.write("        start\n")
        fd.write("}\n\n")

        fd.write("reconfig() {\n")
        fd.write('        if [ -f "$2" ]; then\n')
        fd.write("           has_arg=1\n")
        fd.write('           echo "Using frontend config file arg: $2"\n')
        fd.write("           cfg_loc=$2\n")
        fd.write("        else\n")
        fd.write("           has_arg=0\n")
        fd.write('           echo "Using default frontend config file: $default_cfg_fpath"\n')
        fd.write("           cfg_loc=$default_cfg_fpath\n")
        fd.write("        fi\n")
        fd.write('        shift\n')
        fd.write('        update_def_cfg="no"\n')
        fd.write('        writeback="yes"\n')
        fd.write('        fix_rrd=""\n')
        fd.write('        \n')
        fd.write('        for var in "$@"\n')
        fd.write('           do\n')
        fd.write('           case "$var" in\n')
        fd.write('           yes | no) writeback="$var"\n')
        fd.write('           ;;\n')
        fd.write('           update_default_cfg) update_def_cfg="yes"\n')
        fd.write('           ;;\n')
        fd.write('              "-fix_rrd") fix_rrd="-fix_rrd"\n')
        fd.write('                 ;;\n')
        fd.write('           *) if [ "$cfg_loc" != "$var" ]; then\n')
        fd.write('              echo "Unknown argument passed: $var"\n')
        fd.write('              echo $"Usage: frontend_startup {reconfig xml <update_default_cfg> <writeback yes|no>}"\n')
        fd.write('              exit 1\n')
        fd.write('              fi\n')
        fd.write('           ;;\n')
        fd.write('           esac\n')
        fd.write('        done\n')
        fd.write('        if [ -n "$GLIDEIN_WRITEBACK" ]; then\n')
        fd.write('           writeback="$GLIDEIN_WRITEBACK"\n')
        fd.write('        fi\n')
        fd.write('        "$glideinWMS_dir/frontend/checkFrontend.py" "$frontend_dir" >/dev/null 2>&1 </dev/null\n')
        fd.write("        notrun=$?\n")
        fd.write("        if [ $notrun -eq 0 ]; then\n")
        fd.write("          stop\n")
        fd.write("          if [ $RETVAL -ne 0 ]; then\n")
        fd.write("            exit $RETVAL\n")
        fd.write("          fi\n")
        fd.write("        fi\n")
        fd.write('        "$glideinWMS_dir/creation/reconfig_frontend" -force_name "$frontend_name" -writeback "$writeback" -update_scripts "no" -xml "$cfg_loc" -update_def_cfg "$update_def_cfg" $fix_rrd\n')
        fd.write('      RETVAL=$?\n')
        fd.write("        reconfig_failed=$?\n")
        fd.write('        echo -n "Reconfiguring the frontend"\n')
        fd.write("        test $reconfig_failed -eq 0 && success || failure\n")
        fd.write("        echo\n")
        fd.write("        if [ $notrun -eq 0 ]; then\n")
        fd.write("          start\n")
        fd.write("        fi\n")
        fd.write("}\n\n")
        
        fd.write("upgrade() {\n")
        fd.write('        if [ -f "$1" ]; then\n')
        fd.write("           has_arg=1\n")
        fd.write('           echo "Using frontend config file arg: $1"\n')
        fd.write("           cfg_loc=$1\n")
        fd.write("        else\n")
        fd.write("           has_arg=0\n")
        fd.write('           echo "Using default frontend config file: $default_cfg_fpath"\n')
        fd.write("           cfg_loc=$default_cfg_fpath\n")
        fd.write("        fi\n")
        fd.write('        "$glideinWMS_dir/frontend/checkFrontend.py" "$frontend_dir" >/dev/null 2>&1 </dev/null\n')
        fd.write("        notrun=$?\n")
        fd.write("        if [ $notrun -eq 0 ]; then\n")
        fd.write("          stop\n")
        fd.write("          if [ $RETVAL -ne 0 ]; then\n")
        fd.write("            exit $RETVAL\n")
        fd.write("          fi\n")
        fd.write("        fi\n")
        fd.write('        "$glideinWMS_dir/creation/reconfig_frontend" -force_name "$frontend_name" -writeback "yes" -update_scripts "yes" -xml "$cfg_loc"\n')
        fd.write("        reconfig_failed=$?\n")
        fd.write('        echo -n "Reconfiguring the frontend"\n')
        fd.write("        test $reconfig_failed -eq 0 && success || failure\n")
        fd.write('          RETVAL=$?\n')
        fd.write("        echo\n")
        fd.write("        if [ $notrun -eq 0 ]; then\n")
        fd.write("          start\n")
        fd.write("        fi\n")
        fd.write("}\n\n")

        fd.write('downtime() {\n')
        fd.write('       if [ -z "$2" ]; then\n')
        fd.write('           echo $"Usage: frontend_startup $1 \'frontend\'|\'entries\'|entry_name [delay]"\n')
        fd.write('           exit 1\n')
        fd.write('       fi\n\n')
        fd.write('	 if [ "$1" == "down" ]; then\n')
        fd.write('	   echo -n "Setting downtime for"\n')
        fd.write('	 elif [ "$1" == "up" ]; then\n')
        fd.write('	   echo -n "Removing downtime for"\n')
        fd.write('	 else\n')
        fd.write('	   echo -n "Infosys-based downtime management for"\n')
        fd.write('	 fi\n\n')
        fd.write('	 if [ "$2" == "frontend" ]; then\n')
        fd.write('	   echo -n " frontend:"\n')
        fd.write('       else\n')
        fd.write('	   echo -n " entry $2:"\n')
        fd.write('	 fi\n\n')
        fd.write('	 "$glideinWMS_dir/frontend/manageFrontendDowntimes.py" "$frontend_dir" $2 $1 $3 2>/dev/null 1>&2 </dev/null && success || failure\n')
        fd.write('	 RETVAL=$?\n')
        fd.write('	 echo\n')
        fd.write('}\n\n')
        
        fd.write("case $1 in\n")
        fd.write("        start)\n")
        fd.write("                start\n")
        fd.write("        ;;\n")
        fd.write("        stop)\n")
        fd.write("                stop\n")
        fd.write("        ;;\n")
        fd.write("        restart)\n")
        fd.write("                restart\n")
        fd.write("        ;;\n")
        fd.write("        status)\n")
        fd.write('               "$glideinWMS_dir/frontend/checkFrontend.py" "$frontend_dir"\n')
        fd.write('	         RETVAL=$?\n')
        fd.write("        ;;\n")
        #fd.write("        info)\n")
        #fd.write("               shift\n")
        #fd.write('               "$glideinWMS_dir/creation/info_frontend" $@ "$frontend_dir/%s"\n'%cvWConsts.XML_CONFIG_FILE)
        #fd.write('	         RETVAL=$?\n')
        #fd.write("        ;;\n")
        fd.write("        reconfig)\n")
        fd.write('                reconfig "$@"\n')
        fd.write("        ;;\n")
        fd.write("        upgrade)\n")
        fd.write("                upgrade $2\n")
        fd.write("        ;;\n")
        #fd.write("	  down)\n")
        #fd.write("		  downtime down $2 $3\n")
        #fd.write("	  ;;\n")
        #fd.write("	  up)\n")
        #fd.write("		  downtime up $2 $3\n")
        #fd.write("	  ;;\n")
        #fd.write("	  statusdown)\n")
        #fd.write('            if [ -z "$2" ]; then\n')
        #fd.write('              echo $"Usage: frontend_startup $1 \'frontend\'|\'entries\'|entry_name [delay]"\n')
        #fd.write('              exit 1\n')
        #fd.write('            fi\n')
        #fd.write('            "$glideinWMS_dir/frontend/manageFrontendDowntimes.py" "$frontend_dir" $2 check $3\n')
        #fd.write('            RETVAL=$?\n')
        #fd.write("	  ;;\n")
        fd.write("        *)\n")
        #fd.write('        echo $"Usage: frontend_startup {start|stop|restart|status|info|reconfig|down|up|statusdown}"\n')
        fd.write('        echo $"Usage: frontend_startup {start|stop|restart|status|reconfig|upgrade}"\n')
        fd.write("        exit 1\n")
        fd.write("esac\n\n")

        fd.write("exit $RETVAL\n")
    finally:
        fd.close()
        
    os.chmod(startup_fname,
             stat.S_IRWXU|stat.S_IROTH|stat.S_IRGRP|stat.S_IXOTH|stat.S_IXGRP)

    return

#########################################
# Create frontend-specific mapfile
def create_client_mapfile(mapfile_fname,my_DN,factory_DNs,schedd_DNs,collector_DNs):
    fd=open(mapfile_fname,"w")
    try:
        fd.write('GSI "^%s$" %s\n'%(re.escape(my_DN),'me'))
        for (uid,dns) in (('factory',factory_DNs),
                          ('schedd',schedd_DNs),
                          ('collector',collector_DNs)):
            for i in range(len(dns)):
                fd.write('GSI "^%s$" %s%i\n'%(re.escape(dns[i]),uid,i))
        fd.write("GSI (.*) anonymous\n")
        # Add FS and other mappings just for completeness
        # Should never get here
        for t in ('FS','SSL','KERBEROS','PASSWORD','FS_REMOTE','NTSSPI','CLAIMTOBE','ANONYMOUS'):
            fd.write("%s (.*) anonymous\n"%t)
    finally:
        fd.close()
        
    return

#########################################
# Create frontend-specific condor_config
def create_client_condor_config(config_fname, mapfile_fname, collector_nodes, classad_proxy):
    attrs = condorExe.exe_cmd('condor_config_val','-dump')
    def_attrs = filter_unwanted_config_attrs(attrs)

    fd=open(config_fname,"w")
    try:
        fd.write("############################################\n")
        fd.write("#\n")
        fd.write("# Condor config file used by the VO Frontend\n")
        fd.write("#\n")
        fd.write("# This file is generated at each reconfig\n")
        fd.write("# Do not change by hand!\n")
        fd.write("#\n")
        fd.write("############################################\n\n")

        fd.write("###########################\n")
        fd.write("# Base config values\n")
        fd.write("# obtained from\n")
        fd.write("#  condor_config_val -dump\n")
        fd.write("# at config time.\n")
        fd.write("###########################\n\n")

        for attr in def_attrs:
            fd.writelines("%s\n" % attr)

        fd.write("\n##################################\n")
        fd.write("# Add Frontend specific attributes\n")
        fd.write("##################################\n")

        fd.write("\n###########################\n")
        fd.write("# Pool collector(s)\n")
        fd.write("###########################\n")
        fd.write("COLLECTOR_HOST = %s\n"%string.join(collector_nodes,","))

        fd.write("\n###########################\n")
        fd.write("# Authentication settings\n")
        fd.write("############################\n")

        fd.write("\n# Force GSI authentication\n")
        fd.write("SEC_DEFAULT_AUTHENTICATION_METHODS = GSI\n")
        fd.write("SEC_DEFAULT_AUTHENTICATION = REQUIRED\n")

        fd.write("\n#################################\n")
        fd.write("# Where to find ID->uid mappings\n")
        fd.write("# (also disable any GRIDMAP)\n")
        fd.write("#################################\n")
        fd.write("# This is a fake file, redefine at runtime\n")
        fd.write("CERTIFICATE_MAPFILE=%s\n"%mapfile_fname)

        fd.write("\n# Specify that we trust anyone but not anonymous\n")
        fd.write("# I.e. we only talk to servers that have \n")
        fd.write("#  a DN mapped in our mapfile\n")
        for context in condorSecurity.CONDOR_CONTEXT_LIST:
            fd.write("DENY_%s = anonymous@*\n"%context)
        fd.write("\n")
        for context in condorSecurity.CONDOR_CONTEXT_LIST:
            fd.write("ALLOW_%s = *@*\n"%context)
        fd.write("\n")
        fd.write("\n# Unset all the tool specifics\n")

        fd.write("\n# Force integrity\n")
        fd.write("SEC_DEFAULT_INTEGRITY = REQUIRED\n")

        fd.write("\n######################################################\n")
        fd.write("## If someone tried to use this config to start a master\n")
        fd.write("## make sure it is not used to run any daemons\n")
        fd.write("######################################################\n")
        fd.write("DAEMON_LIST=MASTER\n")
        fd.write("DAEMON_SHUTDOWN=True\n")


        fd.write("\n######################################################\n")
        fd.write("## If condor is allowed to use VOMS attributes, it will\n")
        fd.write("## map COLLECTOR DN to anonymous. Just disable it.\n")
        fd.write("######################################################\n")
        fd.write("USE_VOMS_ATTRIBUTES = False\n")
        
        fd.write("\n######################################################\n")
        fd.write("## Add GSI DAEMON PROXY based on the frontend config and \n")
        fd.write("## not what is in the condor configs from install \n")
        fd.write("########################################################\n")
        fd.write("GSI_DAEMON_PROXY = %s\n" % classad_proxy)

    finally:
        fd.close()
        
    return

def filter_unwanted_config_attrs(attrs):
    unwanted_attrs = []

    # Make sure there are no tool specific and other unwanted settings
    # Generate the list of unwanted settings to filter out
    unwanted_attrs.append('TOOL.LOCAL_CONFIG_FILE')
    unwanted_attrs.append('TOOL.CONDOR_HOST')
    unwanted_attrs.append('TOOL.GRIDMAP')
    unwanted_attrs.append('TOOL.CERTIFICATE_MAPFILE')
    unwanted_attrs.append('TOOL.GSI_DAEMON_NAME')

    unwanted_attrs.append('LOCAL_CONFIG_FILE')
    unwanted_attrs.append('LOCAL_CONFIG_DIR')

    unwanted_attrs.append('GRIDMAP')
    unwanted_attrs.append('GSI_DAEMON_NAME')
    unwanted_attrs.append('GSI_DAEMON_PROXY')


    for context in condorSecurity.CONDOR_CONTEXT_LIST:
        unwanted_attrs.append('TOOL.DENY_%s' % context)
        unwanted_attrs.append('TOOL.ALLOW_%s' % context)
        unwanted_attrs.append('TOOL.SEC_%s_AUTHENTICATION' % context)
        unwanted_attrs.append('TOOL.SEC_%s_AUTHENTICATION_METHODS' % context)
        unwanted_attrs.append('TOOL.SEC_%s_INTEGRITY' % context)

        # Keep default setting for following
        if context!="DEFAULT":
            unwanted_attrs.append('SEC_%s_AUTHENTICATION' % context)
            unwanted_attrs.append('SEC_%s_AUTHENTICATION_METHODS' % context)
            unwanted_attrs.append('SEC_%s_INTEGRITY' % context)

    for uattr in unwanted_attrs:
        for i in range(0, len(attrs)):
            attr = ''
            if len(attrs[i].split('=')) > 0:
                attr = ((attrs[i].split('='))[0]).strip()
            if attr == uattr:
                attrs[i] = '#%s' % attrs[i]
    return attrs
