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
import cgWConsts

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


#################################
# Create glidein description file
def create_glidein_descript(submit_dir,
                            factory_name,glidein_name,
                            web_base,
                            entries):
    filepath=os.path.join(submit_dir,cgWConsts.GLIDEIN_FILE)
    try:
        fd=open(filepath,"w+")
    except IOError,e:
        raise RuntimeError, "Error creating %s: %s"%(filepath,e)
    try:
        fd.write("FactoryName   %s\n"%factory_name)
        fd.write("GlideinName   %s\n"%glidein_name)
        fd.write("WebURL        %s\n"%web_base)
        fd.write("Entries       %s\n"%string.join(entries,","))
    finally:
        fd.close()
    
#################################
# Create glidein description file
def create_job_descript(submit_dir,
                        entry_name,
                        gridtype,gatekeeper,rsl,
                        schedd_name,
                        startup_dir,proxy_id):
    filepath=os.path.join(submit_dir,cgWConsts.JOB_DESCRIPT_FILE)
    try:
        fd=open(filepath,"w+")
    except IOError,e:
        raise RuntimeError, "Error creating %s: %s"%(filepath,e)
    try:
        fd.write("EntryName     %s\n"%entry_name)
        fd.write("GridType      %s\n"%gridtype)
        fd.write("Gatekeeper    %s\n"%gatekeeper)
        if rsl!=None:
            fd.write("GlobusRSL     %s\n"%rsl)
        fd.write("Schedd        %s\n"%schedd_name)
        fd.write("StartupDir    %s\n"%startup_dir)
        if proxy_id!=None:
            fd.write("ProxyURL      %s\n"%proxy_id)
    finally:
        fd.close()
    
###########################
# Create Condor submit file
def create_submit(submit_dir,
                  factory_name,glidein_name,
                  web_base):
    filepath=os.path.join(submit_dir,cgWConsts.SUBMIT_FILE)
    try:
        fd=open(filepath,"w+")
    except IOError,e:
        raise RuntimeError, "Error creating %s: %s"%(filepath,e)
    try:
        fd.write("Universe = grid\n")
        fd.write("Grid_Resource = $ENV(GLIDEIN_GRIDTYPE) $ENV(GLIDEIN_GATEKEEPER)\n")
        fd.write("Executable = %s\n"%cgWConsts.STARTUP_FILE)

        fd.write(("Arguments = -v $ENV(GLIDEIN_VERBOSITY) -cluster $(Cluster) -name %s -entry $ENV(GLIDEIN_ENTRY_NAME) -subcluster $(Process) -schedd $ENV(GLIDEIN_SCHEDD) "%glidein_name)+
                 ("-web %s -sign $ENV(GLIDEIN_SIGN) -signentry $ENV(GLIDEIN_SIGNENTRY) -signtype sha1 -factory %s " % (web_base,factory_name))+
                 "-descript $ENV(GLIDEIN_DESCRIPT) -descriptentry $ENV(GLIDEIN_DESCRIPTENTRY) " +
                 "-param_GLIDEIN_Client $ENV(GLIDEIN_CLIENT) $ENV(GLIDEIN_PARAMS)\n")
        fd.write('+GlideinFactory    = "%s"\n'%factory_name)
        fd.write('+GlideinName       = "%s"\n'%glidein_name)
        fd.write('+GlideinEntryName  = "$ENV(GLIDEIN_ENTRY_NAME)"\n')
        fd.write('+GlideinClient     = "$ENV(GLIDEIN_CLIENT)"\n')

        
        fd.write("\nTransfer_Executable   = True\n")
        fd.write("transfer_Input_files  =\n")
        fd.write("transfer_Output_files =\n")
        fd.write("WhenToTransferOutput  = ON_EXIT\n")
        fd.write("\nNotification = Never\n")
        fd.write("\n+Owner = undefined\n")
        fd.write("\nLog = entry_$ENV(GLIDEIN_ENTRY_NAME)/log/condor_activity_$ENV(GLIDEIN_LOGNR)_$ENV(GLIDEIN_CLIENT).log\n")
        fd.write("Output = entry_$ENV(GLIDEIN_ENTRY_NAME)/log/job.$(Cluster).$(Process).out\n")
        fd.write("Error = entry_$ENV(GLIDEIN_ENTRY_NAME)/log/job.$(Cluster).$(Process).err\n")
        fd.write("stream_output = False\n")
        fd.write("stream_error  = False\n")
        fd.write("\nQueue $ENV(GLIDEIN_COUNT)\n")
    finally:
        fd.close()
    
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
        fd.write("export GLIDEIN_SIGN=`awk '/ main$/{print $1}' %s`\n"%cgWConsts.SUMMARY_SIGNATURE_FILE)
        fd.write("export GLIDEIN_DESCRIPT=`awk '/ main$/{print $2}' %s`\n"%cgWConsts.SUMMARY_SIGNATURE_FILE)
        fd.write('export GLIDEIN_SIGNENTRY=`awk "/ entry_$GLIDEIN_ENTRY_NAME\$"\'/{print $1}\' %s`\n'%cgWConsts.SUMMARY_SIGNATURE_FILE)
        fd.write('export GLIDEIN_DESCRIPTENTRY=`awk "/ entry_$GLIDEIN_ENTRY_NAME\$"\'/{print $2}\' %s`\n'%cgWConsts.SUMMARY_SIGNATURE_FILE)
        fd.write("export GLIDEIN_GRIDTYPE `grep '^GridType' entry_$GLIDEIN_ENTRY_NAME/%s|awk '{print $2}'`\n"%cgWConsts.JOB_DESCRIPT_FILE)
        fd.write("export GLIDEIN_GATEKEEPER `grep '^Gatekeeper' entry_$GLIDEIN_ENTRY_NAME/%s|awk '{print $2}'`\n"%cgWConsts.JOB_DESCRIPT_FILE)
        fd.write("condor_submit -name `grep '^Schedd' %s|awk '{print $2}'` %s\n"%(cgWConsts.GLIDEIN_FILE,cgWConsts.SUBMIT_FILE))
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
        fd.write('export GLIDEIN_ENTRY_NAME="$1"\nshift\n')
        fd.write("export GLIDEIN_SCHEDD=$1\nshift\n")
        fd.write('export GLIDEIN_CLIENT="$1"\nshift\n')
        fd.write("export GLIDEIN_COUNT=$1\nshift\n")
        fd.write("export GLIDEIN_VERBOSITY=$1\nshift\n")
        fd.write("export GLIDEIN_GRIDTYPE=$1\nshift\n")
        fd.write('export GLIDEIN_GATEKEEPER="$1"\nshift\n')
        fd.write('GLIDEIN_GRIDOPTS="$1"\nshift\n')
        fd.write('GLIDEIN_PARAMS=""\n')
        fd.write('while [ "$1" != "--" ]; do\n GLIDEIN_PARAMS="$GLIDEIN_PARAMS $1"\n shift\ndone\nshift # remove --\n')
        fd.write('while [ $# -ge 2 ]; do\n GLIDEIN_PARAMS="$GLIDEIN_PARAMS -param_$1 $2"\n shift\n shift\ndone\nexport GLIDEIN_PARAMS\n')
        fd.write('export GLIDEIN_LOGNR=`date +%Y%m%d`\n')
        fd.write("export GLIDEIN_SIGN=`awk '/ main$/{print $1}' %s`\n"%cgWConsts.SUMMARY_SIGNATURE_FILE)
        fd.write("export GLIDEIN_DESCRIPT=`awk '/ main$/{print $2}' %s`\n"%cgWConsts.SUMMARY_SIGNATURE_FILE)
        fd.write('export GLIDEIN_SIGNENTRY=`awk "/ entry_$GLIDEIN_ENTRY_NAME\$/"\'{print $1}\' %s`\n'%cgWConsts.SUMMARY_SIGNATURE_FILE)
        fd.write('export GLIDEIN_DESCRIPTENTRY=`awk "/ entry_$GLIDEIN_ENTRY_NAME\$"\'/{print $2}\' %s`\n'%cgWConsts.SUMMARY_SIGNATURE_FILE)
        fd.write('condor_submit -append "$GLIDEIN_GRIDOPTS" -name $GLIDEIN_SCHEDD %s\n'%cgWConsts.SUBMIT_FILE)
    finally:
        fd.close()
    # Make it executable
    os.chmod(filepath,0755)

###########################################################
#
# CVS info
#
# $Id: cgWCreate.py,v 1.2 2007/10/18 19:04:06 sfiligoi Exp $
#
# Log:
#  $Log: cgWCreate.py,v $
#  Revision 1.2  2007/10/18 19:04:06  sfiligoi
#  Remove useless parameter
#
#  Revision 1.1  2007/10/12 20:25:40  sfiligoi
#  Add creation of dynamic files into a different module
#
#
###########################################################
