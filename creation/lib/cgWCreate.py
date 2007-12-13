####################################
#
# Functions needed to create files
# used by the glidein entry points
#
# Author: Igor Sfiligoi
#
####################################

import os
import copy
import os.path
import string
import traceback
import tarfile
import cStringIO
import cgWConsts
import cgWDictFile

##############################
# Create condor tarball and
def create_condor_tar(stage_dir,condor_base_dir):
    tgz_name=cgWConsts.CONDOR_FILE
    outtar_name=os.path.join(stage_dir,tgz_name)
    try:
        condor_bins=['sbin/condor_master','sbin/condor_startd','sbin/condor_starter']

        # check that dir and files exist
        if not os.path.isdir(condor_base_dir):
            raise RuntimeError, "%s is not a directory"%condor_base_dir
        for f in condor_bins:
            if not os.path.isfile(os.path.join(condor_base_dir,f)):
                raise RuntimeError, "Cannot find %s"%os.path.join(condor_base_dir,f)

        # check if optional binaries exist, if they do, include
        for f in ['sbin/condor_procd','libexec/glexec_starter_setup.sh']:
            if os.path.isfile(os.path.join(condor_base_dir,f)):
                condor_bins.append(f)
        
        # tar
        tf=tarfile.open(outtar_name,'w:gz')
        for f in condor_bins:
            tf.add(os.path.join(condor_base_dir,f),f)
        tf.close()
    except RuntimeError, e:
        raise RuntimeError, "Error creating condor tgz: %s"%e


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
        for f in ['sbin/condor_procd','libexec/glexec_starter_setup.sh']:
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
                 web_base):
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
        self.add('+GlideinLogNr','"$ENV(GLIDEIN_LOGNR)"')
        
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
        self.add("Arguments",
                 ("-v $ENV(GLIDEIN_VERBOSITY) -cluster $(Cluster) -name %s -entry %s -subcluster $(Process) -schedd $ENV(GLIDEIN_SCHEDD) "%(self['+GlideinName'][1:-1],self['+GlideinEntryName'][1:-1]))+
                 ("-web %s -sign %s -signentry %s -signtype sha1 -factory %s "%(sign,entry_sign,self['+GlideinWebBase'][1:-1],self['+GlideinFactory'][1:-1]))+
                 ("-descript %s -descriptentry %s "%(descript,entry_descript)) +
                 "-param_GLIDEIN_Client $ENV(GLIDEIN_CLIENT) $ENV(GLIDEIN_PARAMS)",
                 allow_overwrite=True)

############################
# Create a test shell script
def create_test_submit(submit_dir):
    filepath=os.path.join(submit_dir,"job_test.sh")
    try:
        fd=open(filepath,"w+")
    except IOError,e:
        raise RuntimeError, "Error creating %s: %s"%(filepath,e)
    try:
        fd.write("#!/bin/bash\n")
        fd.write("export GLIDEIN_CLIENT=test\n")
        fd.write("export GLIDEIN_COUNT=1\n")
        fd.write("export GLIDEIN_VERBOSITY=dbg\n")
        fd.write('export GLIDEIN_PARAMS="-param_GLIDEIN_Collector $HOSTNAME"\n')
        fd.write('export GLIDEIN_LOGNR=`date +%Y%m%d`\n')
        fd.write("export GLIDEIN_ENTRY_NAME=test\n")
        fd.write("export GLIDEIN_GRIDTYPE `grep '^GridType' entry_$GLIDEIN_ENTRY_NAME/%s|awk '{print $2}'`\n"%cgWConsts.JOB_DESCRIPT_FILE)
        fd.write("export GLIDEIN_GATEKEEPER `grep '^Gatekeeper' entry_$GLIDEIN_ENTRY_NAME/%s|awk '{print $2}'`\n"%cgWConsts.JOB_DESCRIPT_FILE)
        fd.write("condor_submit -name `grep '^Schedd' %s|awk '{print $2}'` %s/%s\n"%(cgWConsts.GLIDEIN_FILE,cgWConsts.get_entry_submit_dir("",'${GLIDEIN_ENTRY_NAME}'),cgWConsts.SUBMIT_FILE))
    finally:
        fd.close()
    # Make it executable
    os.chmod(filepath,0755)
    
############################
# Create a submit wrapper 
def create_submit_wrapper(submit_dir):
    filepath=os.path.join(submit_dir,cgWConsts.SUBMIT_WRAPPER)
    try:
        fd=open(filepath,"w+")
    except IOError,e:
        raise RuntimeError, "Error creating %s: %s"%(filepath,e)
    try:
        fd.write("#!/bin/bash\n\n")
        fd.write("if [ $# -lt 8 ]; then\n")
        fd.write(' echo "At least 8 args expected!" 1>&2\n echo "Usage: %s entry_name schedd client count mode gridtype gatekeeper gridopts [params]*"\n 1>&2\n'%cgWConsts.SUBMIT_WRAPPER)
        fd.write(" exit 1\n")
        fd.write("fi\n")
        fd.write('GLIDEIN_ENTRY_NAME="$1"\nshift\n')
        fd.write("export GLIDEIN_SCHEDD=$1\nshift\n")
        fd.write('export GLIDEIN_CLIENT="$1"\nshift\n')
        fd.write("export GLIDEIN_COUNT=$1\nshift\n")
        fd.write("export GLIDEIN_VERBOSITY=$1\nshift\n")
        fd.write("GLIDEIN_GRIDTYPE=$1\nshift\n")
        fd.write('GLIDEIN_GATEKEEPER="$1"\nshift\n')
        fd.write('GLIDEIN_GRIDOPTS="$1"\nshift\n')
        fd.write('GLIDEIN_PARAMS=""\n')
        fd.write('while [ "$1" != "--" ]; do\n GLIDEIN_PARAMS="$GLIDEIN_PARAMS $1"\n shift\ndone\nshift # remove --\n')
        fd.write('while [ $# -ge 2 ]; do\n GLIDEIN_PARAMS="$GLIDEIN_PARAMS -param_$1 $2"\n shift\n shift\ndone\nexport GLIDEIN_PARAMS\n')
        fd.write('export GLIDEIN_LOGNR=`date +%Y%m%d`\n')
        fd.write('condor_submit -append "$GLIDEIN_GRIDOPTS" -name $GLIDEIN_SCHEDD %s/%s\n'%(cgWConsts.get_entry_submit_dir("",'${GLIDEIN_ENTRY_NAME}'),cgWConsts.SUBMIT_FILE))
    finally:
        fd.close()
    # Make it executable
    os.chmod(filepath,0755)

###########################################################
#
# CVS info
#
# $Id: cgWCreate.py,v 1.11 2007/12/13 20:34:53 sfiligoi Exp $
#
# Log:
#  $Log: cgWCreate.py,v $
#  Revision 1.11  2007/12/13 20:34:53  sfiligoi
#  Fix dir
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
