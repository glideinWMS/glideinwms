####################################
#
# Functions needed to create files
# used by the VO Frontend entry points
#
# Author: Igor Sfiligoi
#
####################################

import os,os.path
import stat
import string
import traceback
import tarfile
import cStringIO
import cvWConsts

#########################################
# Create init.d compatible startup file
def create_initd_startup(startup_fname,frontend_dir,glideinWMS_dir):
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
        fd.write("\n")
        
        fd.write("frontend_name=`awk '/^FrontendName /{print $2}' $frontend_dir/frontend.descript`\n")
        fd.write('id_str="$frontend_name"\n')
        fd.write("\n")
        
        fd.write("start() {\n")
        fd.write('        echo -n "Starting glideinWMS frontend $id_str: "\n')
        fd.write('        nice -2  "$glideinWMS_dir/frontend/glideinFrontend.py" "$frontend_dir" 2>/dev/null 1>&2 </dev/null &\n')
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
        fd.write("        start\n")
        fd.write("}\n\n")

        fd.write("reconfig() {\n")
        fd.write('        if [ -f "$1" ]; then\n')
        fd.write("           has_arg=1\n")
        fd.write("        else\n")
        fd.write("           has_arg=0\n")
        fd.write('           echo $"Usage: frontend_startup reconfig <fname>"\n')
        fd.write("           exit 1\n")
        fd.write("        fi\n")
        fd.write('        "$glideinWMS_dir/frontend/checkFrontend.py" "$frontend_dir" >/dev/null 2>&1 </dev/null\n')
        fd.write("        notrun=$?\n")
        fd.write("        if [ $notrun -eq 0 ]; then\n")
        fd.write("          stop\n")
        fd.write("        fi\n")
        fd.write('        "$glideinWMS_dir/creation/reconfig_frontend" -force_name "$frontend_name" $1\n')
        fd.write('	  RETVAL=$?\n')
        fd.write("        reconfig_failed=$?\n")
        fd.write('        echo -n "Reconfiguring the frontend"\n')
        fd.write("        test $reconfig_failed -eq 0 && success || failure\n")
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
        #fd.write('               "$glideinWMS_dir/creation/info_glidein" $@ "$frontend_dir/glideinWMS.xml"\n')
        #fd.write('	         RETVAL=$?\n')
        #fd.write("        ;;\n")
        fd.write("        reconfig)\n")
        fd.write("                reconfig $2\n")
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
        fd.write('        echo $"Usage: frontend_startup {start|stop|restart|status|reconfig}"\n')
        fd.write("        exit 1\n")
        fd.write("esac\n\n")

        fd.write("exit $RETVAL\n")
    finally:
        fd.close()
        
    os.chmod(startup_fname,
             stat.S_IRWXU|stat.S_IROTH|stat.S_IRGRP|stat.S_IXOTH|stat.S_IXGRP)

    return

