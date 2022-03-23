# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

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
import re
import stat
import string

from glideinwms.lib import condorExe, condorSecurity
from glideinwms.lib.util import chmod


#########################################
# Create init.d compatible startup file
def create_initd_startup(startup_fname, frontend_dir, glideinWMS_dir, cfg_name, rpm_install=""):
    """
    Creates the frontend startup file and changes the permissions.  Can overwrite an existing file.
    """
    template = get_template("frontend_initd_startup_template", glideinWMS_dir)
    template = template % {
        "frontend_dir": frontend_dir,
        "glideinWMS_dir": glideinWMS_dir,
        "default_cfg_fpath": cfg_name,
        "rpm_install": rpm_install,
    }
    with open(startup_fname, "w") as fd:
        fd.write(template)

    chmod(startup_fname, stat.S_IRWXU | stat.S_IROTH | stat.S_IRGRP | stat.S_IXOTH | stat.S_IXGRP)

    return


#########################################
# Create frontend-specific mapfile
def create_client_mapfile(mapfile_fname, my_DN, factory_DNs, schedd_DNs, collector_DNs, pilot_DNs=[]):
    """Write a HTCondor map file and add all the provided DNs and map them to the corresponding condor user

    Used to create a frontend-specific mapfile used by the tools

    Args:
        mapfile_fname (str): path to the map file
        my_DN (list): list of DNs corresponding to the Frontend (mapped to me)
        factory_DNs (list): list of DNs corresponding to the Factory (mapped to factory)
        schedd_DNs (list): list of DNs corresponding to the User schedds (mapped to schedd)
        collector_DNs (list): list of DNs corresponding to the User collector/s (mapped to collector)
        pilot_DNs (list): list of DNs corresponding to the pilots (mapped to pilot)

    """
    with open(mapfile_fname, "w") as fd:
        fd.write('GSI "^{}$" {}\n'.format(re.escape(my_DN), "me"))
        for (uid, dns) in (
            ("factory", factory_DNs),
            ("schedd", schedd_DNs),
            ("collector", collector_DNs),
            ("pilot", pilot_DNs),
        ):
            for i in range(len(dns)):
                fd.write('GSI "^%s$" %s%i\n' % (re.escape(dns[i]), uid, i))
        fd.write("GSI (.*) anonymous\n")
        # Add FS and other mappings just for completeness
        # Condor should never get here because these mappings are not accepted
        for t in ("FS", "SSL", "KERBEROS", "PASSWORD", "FS_REMOTE", "NTSSPI", "CLAIMTOBE", "ANONYMOUS"):
            fd.write("%s (.*) anonymous\n" % t)

    return


def find_multilines(config_text):
    """
    Parses condor config file looking for multiline entries
    Args:
        config_text: string, contents of a condor configuration file
    Returns:
        multi: dictionary. keys are first line of multi line config
                         values are the rest of the multi line config
                         keeping original formatting
    """
    multi = {}
    tag = None
    dict_key = None
    for line in config_text:
        parts = line.split()
        if not tag:
            for idx in range(len(parts)):
                if parts[idx].startswith("@="):
                    tag = parts[idx].replace("=", "").strip()
                    dict_key = parts[idx - 1].strip()
                    multi[dict_key] = "".join(parts[idx:]) + "\n"
        else:
            val = multi[dict_key]
            val += line
            multi[dict_key] = val
            for idx in range(len(parts)):
                if tag in parts[idx]:
                    tag = False
    return multi


def parse_configs_for_multis(conf_list):
    """
    processes list of condor config files searching for multi line configurations
    Args:
       conf_list: string, output of condor_config_val -config
    Returns:
        multi: dictionary. keys are first line of multi line config
                         values are the rest of the multi line config
                         keeping original formatting
    """
    multi = {}
    for conf in conf_list:
        conf = conf.strip()
        if os.path.exists(conf):
            with open(conf) as fd:
                text = fd.readlines()
                pdict = find_multilines(text)
            multi.update(pdict)
    return multi


#########################################
# Create frontend-specific condor_config
def create_client_condor_config(config_fname, mapfile_fname, collector_nodes, classad_proxy):
    config_files = condorExe.exe_cmd("condor_config_val", "-config")
    multi_line_conf_dict = parse_configs_for_multis(config_files)
    attrs = condorExe.exe_cmd("condor_config_val", "-dump")
    def_attrs = filter_unwanted_config_attrs(attrs, multi_line_conf_dict)
    for tag in multi_line_conf_dict:
        line = f"{tag}  {multi_line_conf_dict[tag]}"
        def_attrs.append(line)

    with open(config_fname, "w") as fd:
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
        fd.write("COLLECTOR_HOST = %s\n" % ",".join(collector_nodes))

        fd.write("\n###########################\n")
        fd.write("# Authentication settings\n")
        fd.write("############################\n")

        fd.write("\n# Force GSI authentication\n")
        fd.write("SEC_DEFAULT_AUTHENTICATION_METHODS = IDTOKENS, GSI\n")
        fd.write("SEC_DEFAULT_AUTHENTICATION = REQUIRED\n")

        fd.write("\n#################################\n")
        fd.write("# Where to find ID->uid mappings\n")
        fd.write("# (also disable any GRIDMAP)\n")
        fd.write("#################################\n")
        fd.write("# This is a fake file, redefine at runtime\n")
        fd.write("CERTIFICATE_MAPFILE=%s\n" % mapfile_fname)

        fd.write("\n# Specify that we trust anyone but not anonymous\n")
        fd.write("# I.e. we only talk to servers that have \n")
        fd.write("#  a DN mapped in our mapfile\n")
        for context in condorSecurity.CONDOR_CONTEXT_LIST:
            fd.write("DENY_%s = anonymous@*\n" % context)
        fd.write("\n")
        for context in condorSecurity.CONDOR_CONTEXT_LIST:
            fd.write("ALLOW_%s = *@*\n" % context)
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
        fd.write("## Newer versions of Condor will try to enforce hostname\n")
        fd.write("## mapping in the server DN. This does not work for\n")
        fd.write("## pilot DNs. We can safely disable this check since\n")
        fd.write("## we explicitly whitelist all DNs.\n")
        fd.write("######################################################\n")
        fd.write("GSI_SKIP_HOST_CHECK = True\n")

        fd.write("\n######################################################\n")
        fd.write("## Add GSI DAEMON PROXY based on the frontend config and \n")
        fd.write("## not what is in the condor configs from install \n")
        fd.write("########################################################\n")
        fd.write("GSI_DAEMON_PROXY = %s\n" % classad_proxy)

    return


def filter_unwanted_config_attrs(attrs, mlcd):
    """
    Filters out unwanted condor configuration settings
    Args:
        attrs: list of strings, output from condor_config_val -dump
        mlcd: multi line config dict
             given multi line input in a condor config file like so:
             CONDOR_SETTING_1  @=xx
                 REQUIREMENTS regexp("^docker://[^/]+$", SingularityImage)
                 COPY SingularityImage orig_SingularityImage
                 EVALSET SingularityImage replace("^docker://(.+)", SingularityImage, "docker://docker.io/library/\\1")
             @xx
             an mlcd entry will be
             mlcd['CONDOR_SETTING_1'] = "@=xx\n   REQUIREMENTS regexp("^docker://[^/]+$", SingularityImage)......."
             the (incorrect) settings from above going through condor_config_val -dump will be filtered out of
             attrs, and replaced with correct formatting from contents of mlcd
     Returns:
        attrs: list of strings reformatted as valid condor config for frontend

    """
    unwanted_attrs = []
    for key in mlcd:
        unwanted_attrs.append(key)

    # Make sure there are no tool specific and other unwanted settings
    # Generate the list of unwanted settings to filter out
    unwanted_attrs.append("TOOL.LOCAL_CONFIG_FILE")
    unwanted_attrs.append("TOOL.CONDOR_HOST")
    unwanted_attrs.append("TOOL.GRIDMAP")
    unwanted_attrs.append("TOOL.CERTIFICATE_MAPFILE")
    unwanted_attrs.append("TOOL.GSI_DAEMON_NAME")
    unwanted_attrs.append("TOOL.GSI_SKIP_HOST_CHECK")

    unwanted_attrs.append("LOCAL_CONFIG_FILE")
    unwanted_attrs.append("LOCAL_CONFIG_DIR")

    unwanted_attrs.append("GRIDMAP")
    unwanted_attrs.append("GSI_DAEMON_NAME")
    unwanted_attrs.append("GSI_DAEMON_PROXY")

    for context in condorSecurity.CONDOR_CONTEXT_LIST:
        unwanted_attrs.append("TOOL.DENY_%s" % context)
        unwanted_attrs.append("TOOL.ALLOW_%s" % context)
        unwanted_attrs.append("TOOL.SEC_%s_AUTHENTICATION" % context)
        unwanted_attrs.append("TOOL.SEC_%s_AUTHENTICATION_METHODS" % context)
        unwanted_attrs.append("TOOL.SEC_%s_INTEGRITY" % context)

        # Keep default setting for following
        if context != "DEFAULT":
            unwanted_attrs.append("SEC_%s_AUTHENTICATION" % context)
            unwanted_attrs.append("SEC_%s_AUTHENTICATION_METHODS" % context)
            unwanted_attrs.append("SEC_%s_INTEGRITY" % context)

    for uattr in unwanted_attrs:
        for i in range(0, len(attrs)):
            attr = ""
            if len(attrs[i].split("=")) > 0:
                attr = ((attrs[i].split("="))[0]).strip()
            if attr == uattr:
                if attr in mlcd:
                    attrs[i] = "#mlcd  %s" % attrs[i]
                    suspects = mlcd[attr].split("\n")
                    for ctr in range(len(suspects)):
                        for ctr2 in range(len(suspects)):
                            if attrs[i + ctr + 1].strip() == suspects[ctr2].strip():
                                attrs[i + ctr + 1] = "#mlcd  %s" % attrs[i + ctr + 1]
                                break
                else:
                    attrs[i] = "#  %s" % attrs[i]
    for attr in reversed(attrs):
        if "#mlcd" in attr:
            attrs.remove(attr)

    return attrs


def get_template(template_name, glideinWMS_dir):
    with open(f"{glideinWMS_dir}/creation/templates/{template_name}") as template_fd:
        template_str = template_fd.read()

    return template_str
