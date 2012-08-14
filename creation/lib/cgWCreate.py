#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   Functions needed to create files used by the glidein entry points
#
# Author: Igor Sfiligoi
#
####################################

import os
import shutil
import subprocess
import stat
import string
import tarfile
import cStringIO
import cgWDictFile

##############################
# Create condor tarball and store it into a StringIO
def create_condor_tar_fd(condor_base_dir):
    try:
        # List of required files
        condor_bins = [
            'sbin/condor_master', 'sbin/condor_startd', 'sbin/condor_starter'
                      ]

        # List of optional files, included if found in condor distro
        condor_opt_bins = [
            'sbin/condor_procd', 'sbin/gcb_broker_query', 'sbin/condor_fetchlog'
                          ]

        condor_opt_libs = [
            'lib/condor_ssh_to_job_sshd_config_template',
            'lib/CondorJavaInfo.class', 'lib/CondorJavaWrapper.class',
            'lib/scimark2lib.jar',
                          ]
        condor_opt_libexecs = [
                  'libexec/glexec_starter_setup.sh',
                  'libexec/condor_glexec_wrapper',
                  'libexec/condor_glexec_cleanup',
                  'libexec/condor_glexec_job_wrapper',
                  'libexec/condor_glexec_kill',
                  'libexec/condor_glexec_run',
                  'libexec/condor_glexec_update_proxy',
                  'libexec/condor_glexec_setup',
                  'libexec/condor_ssh_to_job_sshd_setup',
                  'libexec/condor_ssh_to_job_shell_setup',
                  'libexec/condor_kflops',
                  'libexec/condor_mips',
                  'libexec/curl_plugin',
                  'libexec/data_plugin',
                              ]
        # check that dir and files exist
        if not os.path.isdir(condor_base_dir):
            raise RuntimeError, "%s is not a directory"%condor_base_dir
        for f in condor_bins:
            if not os.path.isfile(os.path.join(condor_base_dir,f)):
                raise RuntimeError, "Cannot find %s"%os.path.join(condor_base_dir,f)

        # Get the list of dlls required
        dlls = get_condor_dlls(condor_base_dir,
                               condor_opt_bins + condor_opt_libexecs)

        # check if optional files and their libs exist, if they do, include
        for f in (condor_opt_bins+condor_opt_libs+condor_opt_libexecs+dlls):
            if os.path.isfile(os.path.join(condor_base_dir,f)):
                condor_bins.append(f)

        # tar
        fd=cStringIO.StringIO()
        tf=tarfile.open("dummy.tgz",'w:gz',fd)
        for f in condor_bins:
            tf.add(os.path.join(condor_base_dir,f),f)
        tf.close()
        # rewind the file to the beginning
        fd.seek(0)
    except RuntimeError, e:
        raise RuntimeError, "Error creating condor tgz: %s"%e
    return fd


##########################################
# Condor submit file dictionary
class GlideinSubmitDictFile(cgWDictFile.CondorJDLDictFile):
    def populate(self,
                 exe_fname,
                 factory_name,glidein_name,entry_name,
                 gridtype,gatekeeper,rsl,
                 web_base,proxy_url,
                 work_dir,client_log_base_dir):
        self.add("Universe","grid")
        self.add("Grid_Resource","%s %s"%(gridtype,gatekeeper))
        if rsl!=None:
            rsl = '$ENV(GLIDEIN_RSL)'
            if gridtype=='gt2' or gridtype=='gt5':
                #rsl+='$ENV(GLIDEIN_ADDITIONAL_RSL)'
                self.add("globus_rsl",rsl)
            elif gridtype=='gt4':
                self.add("globus_xml",rsl)
            elif gridtype=='nordugrid':
                self.add("nordugrid_rsl",rsl)
            elif gridtype=='cream':
                self.add("cream_attributes",rsl)
            else:
                raise RuntimeError, "Rsl not supported for gridtype %s"%gridtype
        """
        if rsl!=None:
            if gridtype=='gt2':
               self.add("globus_rsl",rsl)
            elif gridtype=='gt4':
               self.add("globus_xml",rsl)
            elif gridtype=='nordugrid':
               self.add("nordugrid_rsl",rsl)
            else:
               raise RuntimeError, 'Rsl not supported for gridtype %s'%gridtype
        """
        self.add("Executable",exe_fname)
        # Force the copy to spool to prevent caching at the CE side
        self.add("copy_to_spool","True")
        
        self.add("Arguments","-fail") # just a placeholder for now
        self.add('+GlideinFactory','"%s"'%factory_name)
        self.add('+GlideinName','"%s"'%glidein_name)
        self.add('+GlideinEntryName','"%s"'%entry_name)
        self.add('+GlideinClient','"$ENV(GLIDEIN_CLIENT)"')
        self.add('+GlideinFrontendName', '"$ENV(GLIDEIN_FRONTEND_NAME)"')
        self.add('+GlideinX509Identifier','"$ENV(GLIDEIN_X509_ID)"')
        self.add('+GlideinX509SecurityClass','"$ENV(GLIDEIN_X509_SEC_CLASS)"')
        self.add('+GlideinWebBase','"%s"'%web_base)
        if proxy_url!=None:
            self.add('+GlideinProxyURL','"%s"'%proxy_url)
        self.add('+GlideinLogNr','"$ENV(GLIDEIN_LOGNR)"')
        self.add('+GlideinWorkDir','"%s"'%work_dir)
        
        self.add("Transfer_Executable","True")
        self.add("transfer_Input_files","")
        self.add("transfer_Output_files","")
        self.add("WhenToTransferOutput ","ON_EXIT")
        self.add("Notification","Never")
        self.add("+Owner","undefined")
        self.add("Log","%s/user_$ENV(GLIDEIN_USER)/glidein_%s/entry_%s/condor_activity_$ENV(GLIDEIN_LOGNR)_$ENV(GLIDEIN_CLIENT).log"%(client_log_base_dir,glidein_name,entry_name))
        self.add("Output","%s/user_$ENV(GLIDEIN_USER)/glidein_%s/entry_%s/job.$(Cluster).$(Process).out"%(client_log_base_dir,glidein_name,entry_name))
        self.add("Error","%s/user_$ENV(GLIDEIN_USER)/glidein_%s/entry_%s/job.$(Cluster).$(Process).err"%(client_log_base_dir,glidein_name,entry_name))
        self.add("stream_output","False")
        self.add("stream_error ","False")
        self.jobs_in_cluster="$ENV(GLIDEIN_COUNT)"

    def finalize(self,
                 sign,entry_sign,
                 descript,entry_descript):
        arg_str="-v $ENV(GLIDEIN_VERBOSITY) -cluster $(Cluster) -name %s -entry %s -clientname $ENV(GLIDEIN_CLIENT) -subcluster $(Process) -schedd $ENV(GLIDEIN_SCHEDD)  -factory %s "%(self['+GlideinName'][1:-1],self['+GlideinEntryName'][1:-1],self['+GlideinFactory'][1:-1])
        arg_str+="-web %s "%self['+GlideinWebBase'][1:-1]
        if self.has_key('+GlideinProxyURL'):
            arg_str+="-proxy %s "%self['+GlideinProxyURL'][1:-1]
        arg_str+="-sign %s -signentry %s -signtype sha1 "%(sign,entry_sign)
        arg_str+="-descript %s -descriptentry %s "%(descript,entry_descript) 
        arg_str+="-dir %s "%self['+GlideinWorkDir'][1:-1]
        arg_str+="-param_GLIDEIN_Client $ENV(GLIDEIN_CLIENT) $ENV(GLIDEIN_PARAMS)"
        self.add("Arguments",arg_str,allow_overwrite=True)

#########################################
# Create init.d compatible startup file
def create_initd_startup(startup_fname, factory_dir, glideinWMS_dir, cfg_name):
    """
    Creates the factory startup file and changes the permissions.  Can overwrite an existing file.
    """    
    
    fd=open(startup_fname,"w")
    try:
        fd.write("#!/bin/bash\n")
        fd.write("# condor   This is the glideinWMS factory startup script\n")
        fd.write("# chkconfig: 35 90 30\n")
        fd.write("# description: Starts and stops a glideinWMS factory\n\n")
        
        fd.write("# Emulate function library.\n")
        fd.write("success() {\n")
        fd.write(' echo -en "\\033[60G[\033[32mOK\033[0m]"\n')
        fd.write(" return 0\n}\n\n")

        fd.write("failure() {\n")
        fd.write(' echo -en "\\033[60G[\033[31mFAILED\033[0m]"\n')
        fd.write(" return 1\n}\n\n")
        
        fd.write("factory_dir='%s'\n"%factory_dir)
        fd.write("glideinWMS_dir='%s'\n"%glideinWMS_dir)
        fd.write("default_cfg_fpath='%s'\n"%cfg_name)
        fd.write("\n")
        
        fd.write("factory_name=`awk '/^FactoryName /{print $2}' $factory_dir/glidein.descript`\n")
        fd.write("glidein_name=`awk '/^GlideinName /{print $2}' $factory_dir/glidein.descript`\n")
        fd.write('id_str="$glidein_name@$factory_name"\n')
        fd.write("\n")
        
        fd.write("start() {\n")
        fd.write("        cwd=`pwd`\n")
        fd.write("        cd $factory_dir\n")
        fd.write('        echo -n "Starting glideinWMS factory $id_str: "\n')
        fd.write('        nice -2 "$glideinWMS_dir/factory/glideFactory.py" "$factory_dir" 2>/dev/null 1>&2 </dev/null &\n')
        fd.write('        sleep 5\n')
        fd.write('        "$glideinWMS_dir/factory/checkFactory.py" "$factory_dir"  2>/dev/null 1>&2 </dev/null && success || failure\n')
        fd.write("        RETVAL=$?\n")
        fd.write('        if [ -n "$cwd" ]; then\n')
        fd.write("           cd $cwd\n")
        fd.write('        fi\n')
        fd.write("        echo\n")
        fd.write("}\n\n")
        
        fd.write("stop() {\n")
        fd.write('        echo -n "Shutting down glideinWMS factory $id_str: "\n')
        fd.write('        "$glideinWMS_dir/factory/stopFactory.py" "$factory_dir" 2>/dev/null 1>&2 </dev/null && success || failure\n')
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
        fd.write('           echo "Using factory config file arg: $2"\n')
        fd.write("           cfg_loc=$2\n")
        fd.write("        else\n")
        fd.write("           has_arg=0\n")
        fd.write('           echo "Using default factory config file: $default_cfg_fpath"\n')
        fd.write("           cfg_loc=$default_cfg_fpath\n")
        fd.write("        fi\n")
        fd.write("        shift\n")
        fd.write('        update_def_cfg="no"\n')
        fd.write('        writeback="yes"\n')
        fd.write('        force_delete=""\n')
        fd.write('        fix_rrd=""\n')
        fd.write('        for var in "$@"\n')
        fd.write("        do\n")
        fd.write('           case "$var" in\n')
        fd.write('              yes | no) writeback="$var"\n')
        fd.write('                 ;;\n')
        fd.write('              update_default_cfg) update_def_cfg="yes"\n')
        fd.write('                 ;;\n')
        fd.write('              "-force_delete") force_delete="-force_delete"\n')
        fd.write('                 ;;\n')
        fd.write('              "-fix_rrd") fix_rrd="-fix_rrd"\n')
        fd.write('                 ;;\n')
        fd.write('              *) if [ "$cfg_loc" != "$var" ]; then\n')
        fd.write('                 echo "Unknown argument passed: $var"\n')
        fd.write('                 echo $"Usage: factory_startup {reconfig xml <update_default_cfg> <writeback yes|no>}"\n')
        fd.write('                 exit 1\n')
        fd.write('                 fi\n')
        fd.write('                 ;;\n')
        fd.write('           esac\n')
        fd.write("        done\n")
        fd.write('        if [ -n "$GLIDEIN_WRITEBACK" ]; then\n')
        fd.write('           writeback="$GLIDEIN_WRITEBACK"\n')
        fd.write("        fi\n")   
        fd.write('        "$glideinWMS_dir/factory/checkFactory.py" "$factory_dir" >/dev/null 2>&1 </dev/null\n')
        fd.write("        notrun=$?\n")
        fd.write("        if [ $notrun -eq 0 ]; then\n")
        fd.write("          stop\n")
        fd.write("          if [ $RETVAL -ne 0 ]; then\n")
        fd.write("            exit $RETVAL\n")
        fd.write("          fi\n")
        fd.write("        fi\n")
        fd.write('        "$glideinWMS_dir/creation/reconfig_glidein" -force_name "$glidein_name" -writeback "$writeback" -update_scripts "no" -xml "$cfg_loc" update_def_cfg "$update_def_cfg" $force_delete $fix_rrd\n')
        fd.write("        reconfig_failed=$?\n")
        fd.write('        echo -n "Reconfiguring the factory"\n')
        fd.write("        test $reconfig_failed -eq 0 && success || failure\n")
        fd.write('        RETVAL=$?\n')
        fd.write("        echo\n")
        fd.write("        if [ $notrun -eq 0 ]; then\n")
        fd.write('          if [ $reconfig_failed -ne 0 ];then\n')
        fd.write('            echo ".. starting factory with old configuration file"\n')
        fd.write('          fi\n')
        fd.write("          start\n")
        fd.write('          if [ $RETVAL -eq 0 ] && [ $reconfig_failed -eq 0 ]; then\n')
        fd.write('            RETVAL=0\n')
        fd.write('          else\n')
        fd.write('            RETVAL=1\n')
        fd.write('          fi\n')
        fd.write("        fi\n")
        fd.write("}\n\n")

        fd.write("upgrade() {\n")
        fd.write('        if [ -f "$1" ]; then\n')
        fd.write("           has_arg=1\n")
        fd.write('           echo "Using factory config file arg: $1"\n')
        fd.write("           cfg_loc=$1\n")
        fd.write("        else\n")
        fd.write("           has_arg=0\n")
        fd.write('           echo "Using default factory config file: $default_cfg_fpath"\n')
        fd.write("           cfg_loc=$default_cfg_fpath\n")
        fd.write("        fi\n")
        fd.write('        "$glideinWMS_dir/factory/checkFactory.py" "$factory_dir" >/dev/null 2>&1 </dev/null\n')
        fd.write("        notrun=$?\n")
        fd.write("        if [ $notrun -eq 0 ]; then\n")
        fd.write("          stop\n")
        fd.write("          if [ $RETVAL -ne 0 ]; then\n")
        fd.write("            exit $RETVAL\n")
        fd.write("          fi\n")
        fd.write("        fi\n")
        fd.write('        "$glideinWMS_dir/creation/reconfig_glidein" -force_name "$glidein_name" -writeback "yes" -update_scripts "yes" -xml "$cfg_loc"\n')
        fd.write("        reconfig_failed=$?\n")
        fd.write('        echo -n "Upgrading the factory"\n')
        fd.write("        test $reconfig_failed -eq 0 && success || failure\n")
        fd.write('        RETVAL=$?\n')
        fd.write("        echo\n")
        fd.write("        if [ $notrun -eq 0 ]; then\n")
        fd.write('          if [ $reconfig_failed -ne 0 ];then\n')
        fd.write('            echo ".. starting factory with old configuration file"\n')
        fd.write('          fi\n')
        fd.write("          start\n")
        fd.write('          if [ $RETVAL -eq 0 ] && [ $reconfig_failed -eq 0 ]; then\n')
        fd.write('            RETVAL=0\n')
        fd.write('          else\n')
        fd.write('            RETVAL=1\n')
        fd.write('          fi\n')
        fd.write("        fi\n")
        fd.write("}\n\n")

        fd.write('downtime() {\n')
        fd.write('       if [ -z "$3" ]; then\n')
        fd.write('           echo $"Usage: factory_startup $1 -entry \'factory\'|\'entries\'|entry_name [-delay delay] [-frontend sec_name|\'All\'] [-security sec_class|\'All\'] [-comment comment]"\n')
        fd.write('           exit 1\n')
        fd.write('       fi\n\n')
        fd.write('	 if [ "$1" == "down" ]; then\n')
        fd.write('	   echo -n "Setting downtime..."\n')
        fd.write('	 elif [ "$1" == "up" ]; then\n')
        fd.write('	   echo -n "Removing downtime..."\n')
        fd.write('	 else\n')
        fd.write('	   echo -n "Infosys-based downtime management."\n')
        fd.write('	 fi\n\n')
        fd.write('	 "$glideinWMS_dir/factory/manageFactoryDowntimes.py" -cmd $1 -dir "$factory_dir" "$@" 2>/dev/null 1>&2 </dev/null && success || failure\n')
        fd.write('	 RETVAL=$?\n')
        fd.write('	 echo\n')
        fd.write('}\n\n')
        
        fd.write("case $1 in\n")
        fd.write("        start)\n")
        fd.write("            start\n")
        fd.write("        ;;\n")
        fd.write("        stop)\n")
        fd.write("            stop\n")
        fd.write("        ;;\n")
        fd.write("        restart)\n")
        fd.write("            restart\n")
        fd.write("        ;;\n")
        fd.write("        status)\n")
        fd.write('            "$glideinWMS_dir/factory/checkFactory.py" "$factory_dir"\n')
        fd.write('            RETVAL=$?\n')
        fd.write("        ;;\n")
        fd.write("        info)\n")
        fd.write("            shift\n")
        fd.write('            "$glideinWMS_dir/creation/info_glidein" $@ "$factory_dir/glideinWMS.xml"\n')
        fd.write('            RETVAL=$?\n')
        fd.write("        ;;\n")
        fd.write("        reconfig)\n")
        fd.write('            reconfig "$@"\n')
        fd.write("        ;;\n")
        fd.write("        upgrade)\n")
        fd.write("            upgrade $2\n")
        fd.write("        ;;\n")
        fd.write("        down)\n")
        fd.write("            downtime down \"$@\"\n")
        fd.write("        ;;\n")
        fd.write("        up)\n")
        fd.write("            downtime up \"$@\"\n")
        fd.write("        ;;\n")
        fd.write("        infosysdown)\n")
        fd.write("            downtime ress+bdii entries \"$@\"\n")
        fd.write("        ;;\n")
        fd.write("        statusdown)\n")
        fd.write('            if [ -z "$2" ]; then\n')
        fd.write('                echo $"Usage: factory_startup $1 -entry \'factory\'|\'entries\'|entry_name [-delay delay]"\n')
        fd.write('                exit 1\n')
        fd.write('            fi\n')
        fd.write('            "$glideinWMS_dir/factory/manageFactoryDowntimes.py" -cmd check -dir "$factory_dir" "$@"\n')
        fd.write('            RETVAL=$?\n')
        fd.write("        ;;\n")
        fd.write("        *)\n")
        fd.write('        echo $"Usage: factory_startup {start|stop|restart|status|info|reconfig|upgrade|down|up|infosysdown|statusdown}"\n')
        fd.write("        exit 1\n")
        fd.write("esac\n\n")

        fd.write("exit $RETVAL\n")
    finally:
        fd.close()
        
    os.chmod(startup_fname,
             stat.S_IRWXU|stat.S_IROTH|stat.S_IRGRP|stat.S_IXOTH|stat.S_IXGRP)

    return

#####################
# INTERNAL
# Simply copy a file
def copy_file(infile,outfile):
    try:
        shutil.copy2(infile,outfile)
    except IOError, e:
        raise RuntimeError, "Error copying %s in %s: %s"%(infile,outfile,e)
        
#####################################
# Copy an executable between two dirs
def copy_exe(filename, work_dir, org_dir, overwrite=False):
    """
    Copies a file from one dir to another and changes the permissions to 0555.  Can overwrite an existing file.
    """
    if overwrite and os.path.exists(os.path.join(work_dir, filename)):
        # Remove file if already exists
        os.remove(os.path.join(work_dir, filename))
    copy_file(os.path.join(org_dir, filename), work_dir)
    os.chmod(os.path.join(work_dir, filename), 0555)
    

def get_link_chain(link):
    """
    Given a filepath, checks if it is a link and processes all the links until
    the actual file is found

    @type link: string
    @param link: Full path to the file/link

    @return: List containing links in the chain
    @rtype: list
    """

    rlist = set()
    l = link
    while os.path.islink(l):
        if l in rlist:
            # Cycle detected. Break
            break
        rlist.add(l)
        l = os.path.join(os.path.dirname(l), os.readlink(l))
    rlist.add(l)
    return list(rlist)


def ldd(file):
    """
    Given a file return all the libraries referenced by the file

    @type file: string
    @param file: Full path to the file

    @return: List containing linked libraries required by the file
    @rtype: list
    """

    rlist = []
    if os.path.exists(file):
        process = subprocess.Popen(['ldd', file], shell=False,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        for line in process.stdout.readlines():
            tokens = line.split('=>')
            if len(tokens) == 2:
                lib_loc = ((tokens[1].strip()).split(' '))[0].strip()
                if os.path.exists(lib_loc):
                    rlist.append(os.path.abspath(lib_loc))
    return rlist


def get_condor_dlls(condor_dir, files=[], libdirs=['lib', 'lib/condor']):
    """
    Given list of condor files return all the libraries referenced by the files

    @type condor_dir: string
    @param condor_dir: Location containing condor binaries
    @type files: list
    @param files: List of files relative to condor_dir
    @type libdirs: list
    @param libdirs: List of dirs relative to condor_dir that contain libs

    @return: List containing linked libraries required by all the files. 
             Paths a relative to the condor_dir
    @rtype: list
    """

    fileset = set()
    libstodo = set()
    libsdone = set()
    rlist = []

    for file in files:
        libstodo.update(ldd(os.path.join(condor_dir, file)))

    while len(libstodo) > 0:
        lib = libstodo.pop()
        libname = os.path.basename(lib)

        if lib in libsdone:
            # This lib has been processes already
            continue

        if not lib.startswith(condor_dir):
            # Check if the library is provided by condor
            # If so, add the condor provided lib to process
            for libdir in libdirs:
                if os.path.exists(os.path.join(condor_dir, libdir, libname)):
                    new_lib = os.path.join(condor_dir, libdir, libname)
                    if new_lib not in libsdone:
                        libstodo.add(new_lib)
                        libsdone.add(lib)
        else:
            new_libstodo = set(ldd(lib))
            libstodo.update(new_libstodo - libsdone)
            # This could be a link chain
            links = get_link_chain(lib)
            # Consider the system links for further processing
            # Add the links in the condor_dir as processed
            for link in links:
                if link.startswith(condor_dir):
                    fileset.add(link)
                    libsdone.add(link)
                else:
                    libstodo.add(link)

    # Return the list of files relative to condor_dir
    for lib in fileset:
        tokens = lib.split('%s/' % os.path.normpath(condor_dir))
        rlist.append(tokens[1])

    return rlist
