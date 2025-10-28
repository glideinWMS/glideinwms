#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Allows to retrieve information from the OSG collector and generate the factory XML file."""


import argparse
import copy
import logging
import math
import os
import sys

import htcondor

from glideinwms.lib.config_util import (
    BEST_FIT_TAG,
    ENTRY_STUB,
    get_attr_str,
    get_limits_str,
    get_submission_speed,
    get_submit_attr_str,
    get_yaml_file_info,
    GLIDEIN_SUPPORTED_VO_MAP,
    GLIDEIN_SUPPORTED_VO_MAP_GPU,
    ProgramError,
    update,
    write_to_xml_file,
    write_to_yaml_file,
)
from glideinwms.lib.util import is_true


def parse_opts():
    """Load a few parameters from the configuration file.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(prog="OSG_autoconf")

    parser.add_argument("config", nargs=1, help="The configuration file")

    parser.add_argument(
        "--cache-fallback",
        action="store_true",
        help="Apply changes in the whitelist yaml files even if the collector is not responding. Uses the OSG_YAML cached data",
    )

    parser.add_argument(
        "--skip-broken",
        action="store_true",
        help="Do not exit with an error when a site in the whitelist is not found in the OSG_YAML or the MISSING_YAML files",
    )

    args = parser.parse_args()

    return args


def get_vos(allowed_vos, GPU_entry=False):
    """Convert the list of VOs from the collector to the Frontend ones.

    Args:
        allowed_vos (list): The list of VOs as returned by the OSG collector.
        GPU_entry (bool, optional): Flag to use GPU VO map. Defaults to False.

    Returns:
        set: A set of Frontend VOs to add to the configuration GLIDEIN_SupportedVOs.
    """
    vos = set()
    for vorg in allowed_vos:
        # Fixup vo found in the collector since there is no consistency with case and presence of quotes
        fix_vorg = vorg.replace('"', "").lower()
        vomap = GLIDEIN_SUPPORTED_VO_MAP_GPU if GPU_entry else GLIDEIN_SUPPORTED_VO_MAP
        if fix_vorg in vomap:
            vos.add(vomap[fix_vorg])

    return vos


def get_bestfit_pilot(celem, resource, site, batchsystem):
    """Find the best-fitting pilot parameters from the resource catalog sections.

    Site admins did not specify a pilot section. This function goes through the resource catalog
    sections and finds the pilot parameters that best fit the CE.

    Args:
        celem (list): List of resource catalog dictionaries as returned by the OSG collector.
        resource (str): The resource name.
        site (str): The site name.

    Returns:
        dict: A dictionary to be used to generate the XML for this CE.
    """
    vos = set()
    memory = None
    walltime = None
    cpus = None
    for osg_catalog in celem["OSG_ResourceCatalog"]:
        if "IsPilotEntry" in osg_catalog:
            continue
        if "AllowedVOs" in osg_catalog:
            if len(vos) == 0:
                vos = get_vos(osg_catalog["AllowedVOs"])
            else:
                vos = vos.intersection(get_vos(osg_catalog["AllowedVOs"]))
        if "Memory" in osg_catalog:
            if memory is None:
                memory = osg_catalog["Memory"]
            else:
                memory = min(memory, osg_catalog["Memory"])
        if "MaxWallTime" in osg_catalog:
            if walltime is None:
                walltime = osg_catalog["MaxWallTime"]
            else:
                walltime = min(walltime, osg_catalog["MaxWallTime"])
        if "CPUs" in osg_catalog:
            if cpus is None:
                cpus = osg_catalog["CPUs"]
            else:
                cpus = math.gcd(cpus, osg_catalog["CPUs"])

    return get_entry_dictionary(resource, site, vos, cpus, walltime, memory, batchsystem)


def get_pilot(resource, site, batchsystem, pilot_entry):
    """Prepare the XML pilot dictionary based on OSG collector information.

    Site admins specified a pilot entry section in the OSG configuration file. This function
    prepares the XML pilot dictionary using that information.

    Args:
        resource (str): The resource name.
        site (str): The site name.
        pilot_entry (dict): Pilot entry information from the OSG configuration file.

    Returns:
        dict: A dictionary to be used to generate the XML for this pilot entry.
    """
    vos = get_vos(pilot_entry.get("AllowedVOs", set()), "GPUs" in pilot_entry)
    cpus = pilot_entry.get("CPUs", None)
    est_cpus = pilot_entry.get("EstimatedCPUs", None)
    walltime = pilot_entry.get("MaxWallTime", None)
    memory = pilot_entry.get("Memory", None)

    res = get_entry_dictionary(resource, site, vos, cpus, walltime, memory, batchsystem)

    if "MaxPilots" in pilot_entry:
        res["limits"] = {"entry": {"glideins": pilot_entry["MaxPilots"]}}
    if "GPUs" in pilot_entry:
        res["submit_attrs"]["Request_GPUs"] = pilot_entry["GPUs"]
    if "Queue" in pilot_entry:
        res["submit_attrs"]["batch_queue"] = pilot_entry["Queue"]
    if pilot_entry.get("RequireSingularity") is False and "OS" in pilot_entry:
        res["attrs"]["GLIDEIN_REQUIRED_OS"] = {"value": pilot_entry["OS"]}
    if "WholeNode" in pilot_entry and pilot_entry["WholeNode"]:
        res["submit_attrs"]["+WantWholeNode"] = pilot_entry["WholeNode"]
        if est_cpus:
            res["attrs"]["GLIDEIN_ESTIMATED_CPUS"] = {"value": est_cpus}
        if "GLIDEIN_CPUS" in res["attrs"]:
            del res["attrs"]["GLIDEIN_CPUS"]
        if "GLIDEIN_MaxMemMBs" in res["attrs"]:
            del res["attrs"]["GLIDEIN_MaxMemMBs"]
        if "+maxMemory" in res["submit_attrs"]:
            del res["submit_attrs"]["+maxMemory"]
        if "+xcount" in res["submit_attrs"]:
            del res["submit_attrs"]["+xcount"]

    return res


def get_entry_dictionary(resource, site, vos, cpus, walltime, memory, batchsystem):
    """Convert parameters into an XML pilot dictionary.

    Args:
        resource (str): The resource name.
        site (str): The site name.
        vos (set): Set of supported VOs.
        cpus (int or None): Number of CPUs.
        walltime (int or None): Maximum wall time (in minutes).
        memory (int or None): Memory in MB.

    Returns:
        dict: An XML pilot dictionary with attributes and submit attributes.
    """
    # Assigning this to an entry dict variable to shorten the line
    edict = {}  # Entry dict
    edict["gridtype"] = "condor"
    edict["attrs"] = {}
    edict["attrs"]["GLIDEIN_Site"] = {"value": resource}
    if str(batchsystem).lower() == "condor":
        edict["work_dir"] = "Condor"
    if resource:
        edict["attrs"]["GLIDEIN_ResourceName"] = {"value": site}
    if len(vos) > 0:
        edict["attrs"]["GLIDEIN_Supported_VOs"] = {"value": ",".join(sorted(vos))}
    edict["submit_attrs"] = {}
    if cpus is not None:
        edict["attrs"]["GLIDEIN_CPUS"] = {"value": cpus}
        edict["submit_attrs"]["+xcount"] = cpus
    if walltime is not None:
        glide_walltime = walltime * 60 - 1800
        edict["attrs"]["GLIDEIN_Max_Walltime"] = {"value": glide_walltime}
        edict["submit_attrs"]["+maxWallTime"] = walltime
    if memory is not None:
        edict["attrs"]["GLIDEIN_MaxMemMBs"] = {"value": memory}
        edict["submit_attrs"]["+maxMemory"] = memory
    return edict


def get_information(host):
    """Query the OSG collector for information on known HTCondor-CEs.

    The OSG collector is queried with the -sched option to obtain information about all HTCondor-CEs.
    Relevant resource information is organized into a dictionary.

    Args:
        host (str): The hostname of the OSG collector.

    Returns:
        dict: A resource dictionary with keys as resource names (e.g., 'cedar', 'UCHICAGO', 'NMSU')
              and values containing the necessary information to create the entry.
              For example:
        ```
            {'hosted-ce32.grid.uchicago.edu':
                     {'DEFAULT_ENTRY': {'attrs': {'GLIDEIN_CPUS': {'value': 16L},
                                                  'GLIDEIN_MaxMemMBs': {'value': 163840L},
                                                  'GLIDEIN_Max_Walltime': {'value': 171000L},
                                                  'GLIDEIN_ResourceName': {'value': 'NEMO'},
                                                  'GLIDEIN_Site': {'value': 'OSG_US_UWM_NEMO'},
                                                  'GLIDEIN_Supported_VOs': {'value': 'OSGVO'}},
                                        'gridtype': 'condor',
                                        'submit_attrs': {'+maxMemory': 163840L,
                                                         '+maxWallTime': 2880L,
                                                         '+xcount': 16L}}}}
        ```
    """
    collector = htcondor.Collector(host)
    ces = collector.query(
        htcondor.AdTypes.Schedd,
        projection=["Name", "OSG_ResourceGroup", "OSG_Resource", "OSG_ResourceCatalog", "OSG_BatchSystems"],
    )
    return get_information_internal(ces)


def get_information_internal(ces):
    """Internal function to process collector ads and retrieve HTCondor-CE information.

    Args:
        ces (list): List of collector ads about HTCondor-CEs from the OSG collector.

    Returns:
        dict: A dictionary of resource information organized by resource and gatekeeper.
    """
    result = {}
    entry = "DEFAULT_ENTRY"
    for celem in ces:
        if "OSG_ResourceGroup" in celem:
            resource = celem["OSG_ResourceGroup"]
            site = celem["OSG_Resource"]
            batchsystem = celem.get("OSG_BatchSystems")
            gatekeeper = celem["Name"].lower()
            if resource:
                result.setdefault(resource, {})[gatekeeper] = {}
                if "OSG_ResourceCatalog" in celem:
                    pilot_entries = [
                        osg_catalog
                        for osg_catalog in celem["OSG_ResourceCatalog"]
                        if osg_catalog.get("IsPilotEntry") is True
                    ]
                    #                    requires_bestfit = pilot_entries == []
                    #                    if requires_bestfit:
                    result[resource][gatekeeper].setdefault(BEST_FIT_TAG, {})[entry] = get_bestfit_pilot(
                        celem, resource, site, batchsystem
                    )
                    #                    else:
                    for pentry in pilot_entries:
                        result[resource][gatekeeper].setdefault(pentry["Name"], {})[entry] = get_pilot(
                            resource, site, batchsystem, pentry
                        )
                else:
                    print(gatekeeper + " CE does not have OSG_ResourceCatalog attribute")
            else:
                print(gatekeeper + " CE does not have OSG_ResourceGroup attribute")

    return result


def get_entries_configuration(data):
    """Generate the factory XML configuration from a resource dictionary.

    Args:
        data (dict): A dictionary similar to that returned by `get_information`.

    Returns:
        str: The Factory XML configuration as a string.
    """
    entries_configuration = ""
    for _, site_information in sorted(data.items()):
        for celem, ce_information in sorted(site_information.items()):
            for _, q_information in sorted(ce_information.items()):
                for entry, entry_information in sorted(q_information.items()):
                    entry_configuration = copy.deepcopy(entry_information)
                    entry_configuration["entry_name"] = entry
                    # Can we get these information (next key)?
                    entry_configuration["attrs"]["GLIDEIN_REQUIRED_OS"] = {
                        "comment": "This value has been hardcoded",
                        "value": "any",
                    }
                    # Probably we can use port from attribute AddressV1 or CollectorHost
                    entry_configuration["gatekeeper"] = celem + " " + celem + ":9619"
                    entry_configuration["rsl"] = ""
                    entry_configuration["attrs"] = get_attr_str(entry_configuration["attrs"])
                    if "submit_attrs" in entry_configuration:
                        entry_configuration["submit_attrs"] = get_submit_attr_str(entry_configuration["submit_attrs"])
                    else:
                        entry_configuration["submit_attrs"] = ""
                    num_factories = entry_configuration.get("num_factories")
                    entry_configuration["num_factories"] = (
                        "" if num_factories is None else f'num_factories="{num_factories}"'
                    )
                    entry_configuration["limits"] = get_limits_str(entry_configuration["limits"])
                    entry_configuration["submission_speed"] = get_submission_speed(
                        entry_configuration["submission_speed"]
                    )
                    entries_configuration += ENTRY_STUB % entry_configuration

    return entries_configuration


# def backward_fix(out):
#    """ special backward compatibility case. Would like to remove this once configs are fixed.
#    """
#    for site, site_information in out.items():
#        if site_information is None: continue
#        for ce_hostname, ce_information in site_information.items():
#            if ce_information is None: continue
#            for qelem, q_information in ce_information.items():
#                if (q_information is None or
#                        set(['limits', 'attrs', 'submit_attrs']) & set(q_information.keys())):
#                    print("\033[91mMissing 'queue' level for site %s and CE %s. Fixing it up for you, but please add a '%s' layer!!\033[0m" %
#                          (site, ce_hostname, BEST_FIT_TAG))
#                    out[site][ce_hostname].setdefault(BEST_FIT_TAG, {})[qelem] = q_information
#                    del out[site][ce_hostname][qelem]
#


def sanitize(whitelist_info):
    """Sanitize the YAML file edited by Factory operators.

    Ensures that entry information is a dictionary and not None.
    The function will be expanded in the future with more checks.

    Args:
        whitelist_info (dict): Data from the whitelist file edited by operators.
    """
    for site, site_information in whitelist_info.items():
        for ce_hostname, ce_information in site_information.items():
            if ce_hostname == "common_entry_fields":
                continue
            for qelem, q_information in ce_information.items():
                for entry, entry_information in q_information.items():
                    if entry_information is None:
                        q_information[entry] = {}


def manage_common_entry_fields(whitelist_info):
    """Manage common entry fields.

    Iterates over the whitelist YAML file edited by Factory operators and expands the common entry fields
    found at the site level, copying them to all entries of the site.

    Args:
        whitelist_info (dict): Data from the whitelist file edited by operators.
    """
    for site, site_information in whitelist_info.items():
        if "common_entry_fields" in site_information:
            cef = site_information["common_entry_fields"]
            del site_information["common_entry_fields"]
            for ce_hostname, ce_information in site_information.items():
                for qelem, q_information in ce_information.items():
                    for entry, entry_information in q_information.items():
                        q_information[entry] = update(cef, entry_information)
            cef = None


def manage_append_values(whitelist_info, osg_info):
    """Manage attributes that use `append_value` instead of `value`.

    Iterate over the YAML whitelist file that factory operators manually edit, and if an
    attribute with an `append_value` is found, update the corresponding `value` by
    appending the values from the OSG collector data.

    Args:
        whitelist_info (dict): Data from the whitelist file edited by operators.
        osg_info (dict): Data from the OSG collector YAML file as returned by `get_information`.
    """
    for site, site_information in whitelist_info.items():
        for ce_hostname, ce_information in site_information.items():
            for qelem, q_information in ce_information.items():
                for entry, entry_information in q_information.items():
                    for attribute, attribute_information in entry_information.get("attrs", {}).items():
                        if attribute_information is not None and "append_value" in attribute_information:
                            attribute_information.setdefault("value", attribute_information["append_value"])
                            attribute_information["value"] += (
                                "," + osg_info[site][ce_hostname][qelem]["DEFAULT_ENTRY"]["attrs"][attribute]["value"]
                            )


def merge_yaml(config, white_list, args):
    """Merge different YAML files and return the corresponding resource dictionary.

    Three YAML files are merged:
      1. The factory whitelist/override file containing operator-specified entries, with the parameters
         they want to override.
      2. The YAML generated from the OSG collector.
      3. The default YAML file.

    For each entry, operator provided information are "updated" with collector information first,
    then with default file information.

    Args:
        config (dict): The configuration dictionary.
        white_list (str): Path to the whitelist YAML file.
        args (argparse.Namespace): Parsed command line arguments.

    Returns:
        dict: A dictionary similar to that returned by `get_information`, with defaults and overrides applied.
              Only whitelisted entries are returned.
    """
    out = get_yaml_file_info(white_list)
    sanitize(out)
    #    backward_fix(out)
    osg_info = get_yaml_file_info(config["OSG_YAML"])
    missing_info = get_yaml_file_info(config["MISSING_YAML"])
    update(osg_info, missing_info)
    manage_common_entry_fields(out)
    manage_append_values(out, osg_info)
    default_information = get_yaml_file_info(config["OSG_DEFAULT"])
    additional_yaml_files = config.get("ADDITIONAL_YAML_FILES", [])
    additional_information = []
    broken_sites = []
    broken_ces = []

    for additional_yaml_file in additional_yaml_files:
        additional_information.append(get_yaml_file_info(additional_yaml_file))
    # TODO remove this if once factory ops trims the default file
    if "DEFAULT_ENTRY" not in default_information:  # fixup default file, I'd like to trim it down
        default_information = default_information["DEFAULT_SITE"]["DEFAULT_GETEKEEPER"]
    for site, site_information in out.items():
        if site_information is None:
            print("There is no site information for %s site in white list file. Skipping it." % site)
            del out[site]
            continue
        print("Merging %s" % site)
        if site not in osg_info:
            print(
                "You put %s in the whitelist file, but the site is not present in the collector or the missing %s file"
                % (site, config["MISSING_YAML"])
            )
            if args.skip_broken:
                print("Will skip %s and continue normally" % site)
                broken_sites.append(site)
                continue
            else:
                raise ProgramError(2)
        for ce_hostname, ce_information in site_information.items():
            if ce_information is None:
                print("There is no CE information for %s CE in white list file. Skipping it." % ce_hostname)
                broken_ces.append((site, ce_hostname))
                continue
            if ce_hostname not in osg_info[site]:
                print(
                    "Working on whitelisted site %s: can't find ce %s in the generated %s or the missing %s files "
                    % (site, ce_hostname, config["OSG_YAML"], config["MISSING_YAML"])
                )
                if args.skip_broken:
                    print("Will skip %s and continue normally" % ce_hostname)
                    broken_ces.append((site, ce_hostname))
                    continue
                else:
                    raise ProgramError(3)
            for qelem, q_information in ce_information.items():
                if qelem not in osg_info[site][ce_hostname]:
                    print(
                        "Working on whitelisted site %s and CE %s: can't find queue %s in the generated %s or the missing %s files "
                        % (site, ce_hostname, qelem, config["OSG_YAML"], config["MISSING_YAML"])
                    )
                    if qelem == BEST_FIT_TAG:
                        print(
                            "It seems like you are using the best fit algorithm for this CE (%s), but the site admin specified one (or more) queue(s) in their CE config (called %s). Please, replace %s with one of the queue, and adjust the parameters in the whitelist file"
                            % (BEST_FIT_TAG, osg_info[site][ce_hostname].keys(), BEST_FIT_TAG)
                        )
                    raise ProgramError(4)
                for entry, entry_information in q_information.items():
                    update(entry_information, osg_info[site][ce_hostname][qelem]["DEFAULT_ENTRY"], overwrite=False)
                    if osg_info[site][ce_hostname][qelem]["DEFAULT_ENTRY"]["gridtype"] == "condor":
                        if "submit_attrs" in entry_information:
                            whole_node = False
                            if "+WantWholeNode" in entry_information["submit_attrs"]:
                                want_whole_node = entry_information["submit_attrs"]["+WantWholeNode"]
                                if is_true(want_whole_node):
                                    whole_node = True
                                    entry_information = set_whole_node_entry(entry_information)
                            if "Request_GPUs" in entry_information["submit_attrs"]:
                                entry_information = set_gpu_entry(entry_information, whole_node)
                    if "limits" in entry_information:
                        if "entry" in entry_information["limits"] and "frontend" not in entry_information["limits"]:
                            entry_information["limits"]["frontend"] = entry_information["limits"]["entry"]
                        elif "entry" not in entry_information["limits"] and "frontend" in entry_information["limits"]:
                            entry_information["limits"]["entry"] = entry_information["limits"]["frontend"]
                    update(entry_information, default_information["DEFAULT_ENTRY"], overwrite=False)
                    for additional_info in additional_information:
                        update(
                            entry_information,
                            additional_info.setdefault(site, {})
                            .setdefault(ce_hostname, {})
                            .setdefault(qelem, {})
                            .setdefault(entry, {}),
                            overwrite=False,
                        )

    for site in broken_sites:
        del out[site]
    for site, ce in broken_ces:
        del out[site][ce]
    return out


def set_gpu_entry(entry_information, want_whole_node):
    """Set GPU-specific entry attributes.

    Args:
        entry_information (dict): A dictionary of entry information from the whitelist file.
        want_whole_node (bool): Flag indicating whether whole node settings are desired.

    Returns:
        dict: Updated entry information dictionary with GPU settings.
    """
    if "attrs" not in entry_information:
        entry_information["attrs"] = {}
    if "GLIDEIN_Resource_Slots" not in entry_information["attrs"]:
        if want_whole_node:
            value = "GPUs,type=main"
        else:
            value = "GPUs," + str(entry_information["submit_attrs"]["Request_GPUs"]) + ",type=main"
        entry_information["attrs"]["GLIDEIN_Resource_Slots"] = {"value": value}

    return entry_information


def set_whole_node_entry(entry_information):
    """Configure an entry for whole node usage.

    Args:
        entry_information (dict): A dictionary of entry information from the whitelist file.

    Returns:
        dict: Updated entry information dictionary with whole node settings.
    """
    if "submit_attrs" in entry_information:
        if "+xcount" not in entry_information["submit_attrs"]:
            entry_information["submit_attrs"]["+xcount"] = None
        if "+maxMemory" not in entry_information["submit_attrs"]:
            entry_information["submit_attrs"]["+maxMemory"] = None

    if "attrs" not in entry_information:
        entry_information["attrs"] = {}
    if "GLIDEIN_CPUS" not in entry_information["attrs"]:
        entry_information["attrs"]["GLIDEIN_CPUS"] = {"value": "auto"}
    if "GLIDEIN_ESTIMATED_CPUS" not in entry_information["attrs"]:
        entry_information["attrs"]["GLIDEIN_ESTIMATED_CPUS"] = {"value": 32}
    if "GLIDEIN_MaxMemMBs" not in entry_information["attrs"]:
        entry_information["attrs"]["GLIDEIN_MaxMemMBs"] = {"type": "string", "value": ""}
    if "GLIDEIN_MaxMemMBs_Estimate" not in entry_information["attrs"]:
        entry_information["attrs"]["GLIDEIN_MaxMemMBs_Estimate"] = {"value": "True"}

    return entry_information


def update_submit_attrs(entry_information, attr, submit_attr):
    """Update the submit attribute based on a corresponding attribute if not already defined.

    Args:
        entry_information (dict): A dictionary of entry information from the whitelist file.
        attr (str): The attribute name.
        submit_attr (str): The submit attribute name.

    Returns:
        dict: Updated entry information dictionary with the possibly updated submit attribute.
    """
    if attr in entry_information["attrs"] and entry_information["attrs"][attr]:
        if "submit_attrs" not in entry_information:
            entry_information["submit_attrs"] = {}
        if attr == "GLIDEIN_Max_Walltime":
            entry_information["submit_attrs"][submit_attr] = int(entry_information["attrs"][attr]["value"] / 60) + 30
        else:
            entry_information["submit_attrs"][submit_attr] = entry_information["attrs"][attr]["value"]

    return entry_information


def create_missing_file(config, osg_collector_data):
    """Create the missing YAML file based on configuration and OSG collector data.

    Generates a YAML file containing information about missing sites and CEs.

    Args:
        config (dict): The configuration dictionary.
        osg_collector_data (dict): Data obtained from the OSG collector.
    """
    print("Generating the missing file")

    new_missing = {}
    try:
        osg_info = get_yaml_file_info(config["OSG_YAML"])
    except ProgramError:
        write_to_yaml_file(config["MISSING_YAML"], new_missing)
        print(
            "Skipping verification of missing files since OSG.yml does not exist. Is this the first time you run OSG_autoconf?"
        )
        return
    missing_info = get_yaml_file_info(config["MISSING_YAML"]) if os.path.isfile(config["MISSING_YAML"]) else {}

    print("Verifying missing sites and CEs")
    for white_list in sorted(config["OSG_WHITELISTS"]):
        print("Checking if any site or CE in %s is missing in the OSG collector" % white_list)
        whitelist_info = get_yaml_file_info(white_list)
        tmp = create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)
        update(new_missing, tmp)

    write_to_yaml_file(config["MISSING_YAML"], new_missing)


def create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data):
    """Internal function to create the missing YAML file.

    Args:
        missing_info (dict): Existing missing information.
        osg_info (dict): Data from the OSG collector YAML file.
        whitelist_info (dict): Data from the whitelist file edited by operators.
        osg_collector_data (dict): Data from the OSG collector.

    Returns:
        dict: Updated missing information dictionary.
    """
    new_missing = {}
    for site, site_information in whitelist_info.items():
        if site_information is None:
            continue
        if site not in osg_collector_data:  # Check if the site disappeared from the OSG collector
            if site in osg_info or site in missing_info:
                print(
                    "WARNING! Site %s is in the whitelist file, but not in the collector. Retrieving it from old data (old OSG YAML or MISSING YAML), and saving it to the MISSING YAML"
                    % site
                )
                new_missing[site] = osg_info.get(site) or missing_info[site]
            else:
                print(
                    "ERROR! Site %s is in the whitelist file, and I can't neither find it in the OSG YAML saved data, nor the MISSING YAML"
                    % site
                )
            continue
        for celem, ce_information in site_information.items():
            if ce_information is None:
                continue
            if celem not in osg_collector_data[site]:
                if celem in osg_info.get(site, {}) or celem in missing_info.get(site, {}):
                    print(
                        "WARNING! CE %s of site %s is in the whitelist file, but not in the collector. Retrieving it from old data (old OSG YAML or MISSING YAML), and saving it to the MISSING YAML"
                        % (celem, site)
                    )
                    new_missing.setdefault(site, {})
                    new_missing[site][celem] = osg_info.get(site, {}).get(celem, False) or missing_info[site][celem]
                else:
                    print(
                        "ERROR! CE %s of site %s is in the whitelist file, and I can't neither find it in the OSG YAML saved data, nor the MISSING YAML"
                        % (celem, site)
                    )

    # Add the new additional layer if it is missing
    # TODO Remove it once facotry ops is done with this (in 3.7.4)!
    for site, site_information in new_missing.items():
        for celem, ce_information in site_information.items():
            if "DEFAULT_ENTRY" in ce_information:
                new_missing[site][celem].setdefault(BEST_FIT_TAG, {})["DEFAULT_ENTRY"] = new_missing[site][celem][
                    "DEFAULT_ENTRY"
                ]
                del new_missing[site][celem]["DEFAULT_ENTRY"]

    # Returning for unit tests
    return new_missing


def main(args):
    """The main function.

    Reads configuration and OSG collector data to generate factory XML configuration files,
    merging information from multiple YAML sources and applying operator overrides.

    Args:
        args (argparse.Namespace): Parsed command line arguments.
    """
    config = get_yaml_file_info(args.config[0])
    xmloutdir = config.get("XML_OUTDIR", None)
    try:
        # Queries the OSG collector
        result = get_information(config["OSG_COLLECTOR"])
        # Create the file for the missing CEs
        create_missing_file(config, result)
        # Write the received information to the OSG.yml file
        write_to_yaml_file(config["OSG_YAML"], result)
    except htcondor.HTCondorIOError as e:
        print(
            "\033[91mWARNING!\033[0m The query to the collector %s returned the following error '%s'."
            % (config["OSG_COLLECTOR"], str(e))
        )
        if args.cache_fallback is True:
            print("Will continue and merge the yaml file using the old cached data in %s." % config["OSG_YAML"])
        else:
            raise ProgramError(5)
    # Merges different yaml files: the defaults, the generated one, and the factory overrides
    for white_list in sorted(config["OSG_WHITELISTS"]):
        result = merge_yaml(config, white_list, args)
        # Convert the resource dictionary obtained this way into a string (xml)
        entries_configuration = get_entries_configuration(result)
        # Write the factory configuration file on the disk
        xmloutdir = os.path.dirname(white_list) if xmloutdir is None else xmloutdir
        filename = os.path.basename(white_list.replace("yml", "xml"))
        write_to_xml_file(os.path.join(xmloutdir, filename), entries_configuration)


if __name__ == "__main__":
    # Argument parsing out of the try/except because it has its own error handling/exception throwing
    args = parse_opts()
    try:
        main(args)
    except ProgramError as merr:
        print("\033[91mError! \033[0m" + ProgramError.codes_map[merr.code])
        sys.exit(merr.code)
    except:
        logging.exception("")
        print("\033[91mUnexpected exception. Aborting automatic configuration generation!\033[0m")
        raise
    sys.exit(0)
