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

import os
import stat
import string
import re
from glideinwms.lib import condorExe
from glideinwms.lib import condorSecurity

#########################################
# Create init.d compatible startup file
def create_initd_startup(startup_fname, frontend_dir, glideinWMS_dir, cfg_name, is_rpm=''):
    """
    Creates the frontend startup file and changes the permissions.  Can overwrite an existing file.
    """            
    template = get_template("frontend_initd_startup_template", glideinWMS_dir)
    fd = open(startup_fname,"w")
    try:
        template = template % {"frontend_dir": frontend_dir, 
                               "glideinWMS_dir": glideinWMS_dir, 
                               "default_cfg_fpath": cfg_name,
                               "this_is_rpm_install": is_rpm}
        fd.write(template)
    finally:
        fd.close()

    os.chmod(startup_fname, stat.S_IRWXU|stat.S_IROTH|stat.S_IRGRP|stat.S_IXOTH|stat.S_IXGRP)

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

def get_template(template_name, glideinWMS_dir):
    template_fd = open("%s/creation/templates/%s" % (glideinWMS_dir, template_name), "r")
    template_str = template_fd.read()
    template_fd.close()

    return template_str
