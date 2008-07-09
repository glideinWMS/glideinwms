####################################
#
# Functions needed to create files
# used by the glidein entry points
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
import cgWConsts
import cgWDictFile

##############################
# Create condor tarball and store it into a StringIO
def create_condor_tar_fd(condor_base_dir):
    try:
        condor_bins=['sbin/condor_master','sbin/condor_startd','sbin/condor_starter']

        # check that dir and files exist
        if not os.path.isdir(condor_base_dir):
            raise RuntimeError, "%s is not a directory"%condor_base_dir
        for f in condor_bins:
            if not os.path.isfile(os.path.join(condor_base_dir,f)):
                raise RuntimeError, "Cannot find %s"%os.path.join(condor_base_dir,f)

        # check if optional binaries exist, if they do, include
        for f in ['sbin/condor_procd','libexec/glexec_starter_setup.sh','libexec/condor_glexec_wrapper']:
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
                 work_dir):
        entry_submit_dir=cgWConsts.get_entry_submit_dir("",entry_name)
        
        self.add("Universe","grid")
        self.add("Grid_Resource","%s %s"%(gridtype,gatekeeper))
        if rsl!=None:
            self.add("globus_rsl",rsl)
        self.add("Executable",exe_fname)

        self.add("Arguments","-fail") # just a placeholder for now
        self.add('+GlideinFactory','"%s"'%factory_name)
        self.add('+GlideinName','"%s"'%glidein_name)
        self.add('+GlideinEntryName','"%s"'%entry_name)
        self.add('+GlideinClient','"$ENV(GLIDEIN_CLIENT)"')
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
        self.add("Log","%s/log/condor_activity_$ENV(GLIDEIN_LOGNR)_$ENV(GLIDEIN_CLIENT).log"%entry_submit_dir)
        self.add("Output","%s/log/job.$(Cluster).$(Process).out"%entry_submit_dir)
        self.add("Error","%s/log/job.$(Cluster).$(Process).err"%entry_submit_dir)
        self.add("stream_output","False")
        self.add("stream_error ","False")
        self.jobs_in_cluster="$ENV(GLIDEIN_COUNT)"

    def finalize(self,
                 sign,entry_sign,
                 descript,entry_descript):
        arg_str="-v $ENV(GLIDEIN_VERBOSITY) -cluster $(Cluster) -name %s -entry %s -subcluster $(Process) -schedd $ENV(GLIDEIN_SCHEDD)  -factory %s "%(self['+GlideinName'][1:-1],self['+GlideinEntryName'][1:-1],self['+GlideinFactory'][1:-1])
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
def create_initd_startup(startup_fname,factory_dir,glideinWMS_dir):
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
        fd.write("\n")
        
        fd.write("factory_name=`awk '/^FactoryName /{print $2}' $factory_dir/glidein.descript`\n")
        fd.write("glidein_name=`awk '/^GlideinName /{print $2}' $factory_dir/glidein.descript`\n")
        fd.write('id_str="$glidein_name@$factory_name"\n')
        fd.write("\n")
        
        fd.write("start() {\n")
        fd.write('        echo -n "Starting glideinWMS factory $id_str: "\n')
        fd.write('        "$glideinWMS_dir/factory/glideFactory.py" "$factory_dir" 2>/dev/null 1>&2 </dev/null &\n')
        fd.write('        sleep 1\n')
        fd.write('        "$glideinWMS_dir/factory/checkFactory.py" "$factory_dir"  2>/dev/null 1>&2 </dev/null && success || failure\n')
        fd.write("        RETVAL=$?\n")
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
        fd.write("        start\n")
        fd.write("}\n\n")

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
        fd.write('               "$glideinWMS_dir/factory/checkFactory.py" "$factory_dir"\n')
        fd.write("        ;;\n")
        fd.write("        *)\n")
        fd.write('        echo $"Usage: factory_startup {start|stop|restart|status}"\n')
        fd.write("        exit 1\n")
        fd.write("esac\n\n")

        fd.write("exit $RETVAL\n")
    finally:
        fd.close()
        
    os.chmod(startup_fname,
             stat.S_IRWXU|stat.S_IROTH|stat.S_IRGRP|stat.S_IXOTH|stat.S_IXGRP)

    return


###########################################################
#
# CVS info
#
# $Id: cgWCreate.py,v 1.26 2008/07/09 18:43:14 sfiligoi Exp $
#
# Log:
#  $Log: cgWCreate.py,v $
#  Revision 1.26  2008/07/09 18:43:14  sfiligoi
#  Fix typo
#
#  Revision 1.24  2008/07/09 18:40:02  sfiligoi
#  Use checkFactory
#
#  Revision 1.22  2008/07/09 16:29:31  sfiligoi
#  Add color to initd_startup
#
#  Revision 1.17  2008/07/08 20:49:07  sfiligoi
#  Add init.d startup file
#
#  Revision 1.16  2008/06/30 18:37:33  sfiligoi
#  Add the missing ondor_glexec_wrapper
#
#  Revision 1.15  2007/12/14 19:57:26  sfiligoi
#  Remove old create_condor_tar
#
#  Revision 1.14  2007/12/13 23:26:20  sfiligoi
#  Get attributes out of stage and only into submit
#
#  Revision 1.13  2007/12/13 22:35:10  sfiligoi
#  Move entry specific arguments into the creation stage
#
#  Revision 1.7  2007/12/13 20:19:45  sfiligoi
#  Move condor jdl into entry subdir, and implement it via a dictionary
#
#  Revision 1.5  2007/12/12 00:35:36  sfiligoi
#  Move creation of glidein and job_descript files from cgWCreate to cgWParamDict
#
#  Revision 1.3  2007/12/11 15:35:35  sfiligoi
#  Make condor in memory
#
#  Revision 1.2  2007/10/18 19:04:06  sfiligoi
#  Remove useless parameter
#
#  Revision 1.1  2007/10/12 20:25:40  sfiligoi
#  Add creation of dynamic files into a different module
#
#
###########################################################
