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
            'sbin/condor_procd', 'sbin/gcb_broker_query',
            'sbin/condor_fetchlog', 'sbin/condor_advertise'
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

        # for RPM installations, add libexec/condor as libexec into the
        # tarball instead
        condor_bins_map = {}
        condor_opt_libexecs_rpm = []

        for libexec in condor_opt_libexecs:
            libexec_rpm = libexec.replace('libexec', 'libexec/condor')
            condor_opt_libexecs_rpm.append(libexec_rpm)
            condor_bins_map[libexec_rpm] = libexec

        condor_opt_libexecs += condor_opt_libexecs_rpm

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
            tf.add(os.path.join(condor_base_dir,f), condor_bins_map.get(f, f))
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
                 entry_name, gridtype, gatekeeper, rsl, auth_method, web_base,
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
        elif gridtype == 'condor':
            # Condor-C is the same as normal grid with a few additions
            # so we first do the normal population
            self.populate_standard_grid(rsl, auth_method, gridtype)
            # next we add the Condor-C additions
            self.populate_condorc_grid()
        else:
            self.populate_standard_grid(rsl, auth_method, gridtype)

        self.populate_glidein_classad(proxy_url)

        # Notification and Owner are the same no matter what grid type
        self.add("Notification", "Never")
        self.add("+Owner", "undefined")

        # The logging of the jobs will be the same across grid types
        self.add("Log", "%s/user_$ENV(GLIDEIN_USER)/glidein_%s/entry_%s/condor_activity_$ENV(GLIDEIN_LOGNR)_$ENV(GLIDEIN_CLIENT).log" % (client_log_base_dir, glidein_name, entry_name))
        self.add("Output", "%s/user_$ENV(GLIDEIN_USER)/glidein_%s/entry_%s/job.$(Cluster).$(Process).out" % (client_log_base_dir, glidein_name, entry_name))
        self.add("Error", "%s/user_$ENV(GLIDEIN_USER)/glidein_%s/entry_%s/job.$(Cluster).$(Process).err" % (client_log_base_dir, glidein_name, entry_name))

        self.jobs_in_cluster = "$ENV(GLIDEIN_COUNT)"


    def populate_standard_grid(self, rsl, auth_method, gridtype):
        if gridtype == 'gt2' or gridtype =='gt5':
            if "project_id" in auth_method or ((rsl is not None) and rsl !=""):
                self.add("globus_rsl", "$ENV(GLIDEIN_RSL)")
        elif gridtype == 'cream' and ((rsl is not None) and rsl !=""):
            self.add("cream_attributes", "$ENV(GLIDEIN_RSL)")
        elif gridtype == 'nordugrid' and rsl:
            self.add("nordugrid_rsl", "$ENV(GLIDEIN_RSL)")
        else:
            pass
            # do we want to raise an error here?  we do in v2+

        # Force the copy to spool to prevent caching at the CE side
        self.add("copy_to_spool", "True")

        self.add("Arguments", "$ENV(GLIDEIN_ARGUMENTS)")

        self.add("Transfer_Executable", "True")
        self.add("transfer_Input_files", "")
        self.add("transfer_Output_files", "")
        self.add("WhenToTransferOutput ", "ON_EXIT")

        self.add("stream_output", "False")
        self.add("stream_error ", "False")

    def populate_condorc_grid(self):
        self.add('+TransferOutput', '""')
        self.add('x509userproxy', '$ENV(X509_USER_PROXY)')

    def populate_ec2_grid(self):
        self.add("ec2_ami_id", "$ENV(AMI_ID)")
        self.add("ec2_instance_type", "$ENV(INSTANCE_TYPE)")
        self.add("ec2_access_key_id", "$ENV(ACCESS_KEY_FILE)")
        self.add("ec2_secret_access_key", "$ENV(SECRET_KEY_FILE)")
        self.add("ec2_keypair_file", "$ENV(CREDENTIAL_DIR)/ssh_key_pair.$(Cluster).$(Process).pem")
        # We do not add the entire argument list to the userdata directly since we want to be able
        # to change the argument list without having to modify every piece of code under the sun
        # this way only the submit_glideins function has to change (and of course glidein_startup.sh)
        self.add("ec2_user_data", "$ENV(USER_DATA)#### -cluster $(Cluster) -subcluster $(Process)####")
        self.add("ec2_user_data_file", "$ENV(GLIDEIN_PROXY_FNAME)")

    def populate_glidein_classad(self, proxy_url):
        # add in the classad attributes for the WMS collector
        self.add('+GlideinFactory', '"$ENV(FACTORY_NAME)"')
        self.add('+GlideinName', '"$ENV(GLIDEIN_NAME)"')
        self.add('+GlideinEntryName', '"$ENV(GLIDEIN_ENTRY_NAME)"')
        self.add('+GlideinClient', '"$ENV(GLIDEIN_CLIENT)"')
        self.add('+GlideinFrontendName', '"$ENV(GLIDEIN_FRONTEND_NAME)"')
        self.add('+GlideinCredentialIdentifier','"$ENV(GLIDEIN_CREDENTIAL_ID)"')
        self.add('+GlideinSecurityClass', '"$ENV(GLIDEIN_SEC_CLASS)"')
        self.add('+GlideinWebBase', '"$ENV(WEB_URL)"')
        self.add('+GlideinLogNr', '"$ENV(GLIDEIN_LOGNR)"')
        self.add('+GlideinWorkDir', '"$ENV(GLIDEIN_STARTUP_DIR)"')
        self.add('+GlideinSlotsLayout', '"$ENV(GLIDEIN_SLOTS_LAYOUT)"')
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
def create_initd_startup(startup_fname, factory_dir, glideinWMS_dir, cfg_name, is_rpm=''):
    """
    Creates the factory startup script from the template.
    """
    template = get_template("factory_initd_startup_template", glideinWMS_dir)
    fd = open(startup_fname,"w")
    try:
        template = template % {"factory_dir": factory_dir, 
                               "glideinWMS_dir": glideinWMS_dir, 
                               "default_cfg_fpath": cfg_name,
                               "this_is_rpm_install": is_rpm}
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
    os.chmod(os.path.join(work_dir, filename), 0555)

def get_template(template_name, glideinWMS_dir):
    template_fd = open("%s/creation/templates/%s" % (glideinWMS_dir, template_name), "r")
    template_str = template_fd.read()
    template_fd.close()

    return template_str

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

