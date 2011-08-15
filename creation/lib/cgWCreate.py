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

import os, shutil
import stat
import tarfile
import cStringIO
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
        for f in ['sbin/condor_procd','sbin/gcb_broker_query',
                  'libexec/glexec_starter_setup.sh',
                  'libexec/condor_glexec_wrapper',
                  'libexec/condor_glexec_cleanup', 
                  'libexec/condor_glexec_job_wrapper',
                  'libexec/condor_glexec_kill','libexec/condor_glexec_run',
                  'libexec/condor_glexec_update_proxy',
                  'libexec/condor_glexec_setup','sbin/condor_fetchlog',
                  'libexec/condor_ssh_to_job_sshd_setup',
                  'libexec/condor_ssh_to_job_shell_setup',
                  'lib/condor_ssh_to_job_sshd_config_template',
                  'lib/CondorJavaInfo.class','lib/CondorJavaWrapper.class',
                  'lib/scimark2lib.jar','libexec/condor_kflops']:
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
    def populate(self, exe_fname, factory_name, glidein_name,
                 entry_name, gridtype, gatekeeper, rsl, web_base,
                 proxy_url, work_dir, client_log_base_dir):
        """
        Many of these arguments are no longer needed, but keeping here for the moment
        since the code is so obscure that removing anything might have unintended
        consequences

        arguments that *are* needed:
            client_log_base_dir
            glidein_name
            entry_name
            gridtype
            gatekeeper
            exe_fname
            proxy_url
        """

        # Add in some common elements before setting up grid type specific attributes
        self.add("Universe", "grid")
        self.add("Grid_Resource", "%s %s" % (gridtype, gatekeeper))
        self.add("Executable", exe_fname)

        # set up the grid specific attributes
        if gridtype == 'ec2':
            self.populate_ec2_grid()
        else:
            self.populate_standard_grid(rsl)

        self.populate_glidein_classad(proxy_url)

        # Notification and Owner are the same no matter what grid type
        self.add("Notification", "Never")
        self.add("+Owner", "undefined")

        # The logging of the jobs will be the same across grid types
        self.add("Log", "%s/user_$ENV(GLIDEIN_USER)/glidein_%s/entry_%s/condor_activity_$ENV(GLIDEIN_LOGNR)_$ENV(GLIDEIN_CLIENT).log" % (client_log_base_dir, glidein_name, entry_name))
        self.add("Output", "%s/user_$ENV(GLIDEIN_USER)/glidein_%s/entry_%s/job.$(Cluster).$(Process).out" % (client_log_base_dir, glidein_name, entry_name))
        self.add("Error", "%s/user_$ENV(GLIDEIN_USER)/glidein_%s/entry_%s/job.$(Cluster).$(Process).err" % (client_log_base_dir, glidein_name, entry_name))

        self.jobs_in_cluster = "$ENV(GLIDEIN_COUNT)"


    def populate_standard_grid(self, rsl):
        if rsl != None:
            self.add("globus_rsl", "$ENV(GLIDEIN_RSL)")

        # Force the copy to spool to prevent caching at the CE side
        self.add("copy_to_spool", "True")

        self.add("Arguments", "$ENV(GLIDEIN_ARGUMENTS)")

        self.add("Transfer_Executable", "True")
        self.add("transfer_Input_files", "")
        self.add("transfer_Output_files", "")
        self.add("WhenToTransferOutput ", "ON_EXIT")

        self.add("stream_output", "False")
        self.add("stream_error ", "False")

    def populate_ec2_grid(self):
        self.add("ec2_ami_id", "$ENV(AMI_ID)")
        self.add("ec2_instance_type", "$ENV(INSTANCE_TYPE)")
        self.add("ec2_access_key_id", "$ENV(ACCESS_KEY_FILE)")
        self.add("ec2_secret_access_key", "$ENV(SECRET_KEY_FILE)")
        self.add("ec2_keypair_file", "ssh_key_pair.$(Cluster).$(Process).pem")
        # We do not add the entire argument list to the userdata directly since we want to be able
        # to change the argument list without having to modify every piece of code under the sun
        # this way only the submit_glideins function has to change (and of course glidein_startup.sh)
        self.add("ec2_user_data", "$ENV(USER_DATA)#### -cluster $(Cluster) -subcluster $(Process)")

    def populate_condorc_grid(self):
        """ This grid type is coming.  A lot of testing has to be completed first before we implement this. """
        pass

    def populate_glidein_classad(self, proxy_url):
        # add in the classad attributes for the WMS collector
        self.add('+GlideinFactory', '"$ENV(FACTORY_NAME)"')
        self.add('+GlideinName', '"$ENV(GLIDEIN_NAME)"')
        self.add('+GlideinEntryName', '"$ENV(GLIDEIN_ENTRY_NAME)"')
        self.add('+GlideinClient', '"$ENV(GLIDEIN_CLIENT)"')
        self.add('+GlideinSecurityClass', '"$ENV(GLIDEIN_SEC_CLASS)"')
        self.add('+GlideinWebBase', '"$ENV(WEB_URL)"')
        self.add('+GlideinLogNr', '"$ENV(GLIDEIN_LOGNR)"')
        self.add('+GlideinWorkDir', '"$ENV(GLIDEIN_STARTUP_DIR)"')
        if proxy_url:
            self.add('+GlideinProxyURL', '"%s"' % proxy_url)


    def finalize(self, sign, entry_sign, descript, entry_descript):
        """
        Since the arguments will be built by the submit script now, just pass. Keeping the function here
        because the code is so obtuse, if I remove the function, I may create unintended effects.
        """
        pass

#########################################
# Create init.d compatible startup file
def create_initd_startup(startup_fname, factory_dir, glideinWMS_dir):
    """
    Creates the factory startup script from the template.
    """
    template = get_template("factory_initd_startup_template", glideinWMS_dir)
    fd = open(startup_fname,"w")
    try:
        template = template % {"factory_dir": factory_dir, "glideinWMS_dir": glideinWMS_dir}
        fd.write(template)
    finally:
        fd.close()

    os.chmod(startup_fname, stat.S_IRWXU|stat.S_IROTH|stat.S_IRGRP|stat.S_IXOTH|stat.S_IXGRP)

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
    os.chmod(os.path.join(org_dir, filename), 0555)

def get_template(template_name, glideinWMS_dir):
    template_fd = open("%s/creation/templates/%s" % (glideinWMS_dir, template_name), "r")
    template_str = template_fd.read()
    template_fd.close()

    return template_str
