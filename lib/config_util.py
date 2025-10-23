# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module contains a list of shared utility functions used by both OSG collector and CRIC
configuration generation helper tools.
"""


import collections
import os

import yaml

BEST_FIT_TAG = "BEST_FIT"

# pylint: disable=line-too-long
ENTRY_STUB = """      <entry name="%(entry_name)s" auth_method="%(auth_method)s" comment="Entry automatically generated" enabled="%(enabled)s" gatekeeper="%(gatekeeper)s" gridtype="%(gridtype)s"%(rsl)s proxy_url="%(proxy_url)s" trust_domain="%(trust_domain)s" verbosity="%(verbosity)s" work_dir="%(work_dir)s">
         <config>
            <max_jobs %(num_factories)s>%(limits)s
               <per_frontends>
               </per_frontends>
            </max_jobs>
            <release max_per_cycle="20" sleep="0.2"/>
            <remove max_per_cycle="5" sleep="0.2"/>
            <restrictions require_voms_proxy="False"/>%(submission_speed)s
               <submit_attrs>%(submit_attrs)s
               </submit_attrs>
            </submit>
         </config>
         <allow_frontends>
         </allow_frontends>
         <attrs>
%(attrs)s
         </attrs>
         <files>
         </files>
         <infosys_refs>
         </infosys_refs>
         <monitorgroups>
         </monitorgroups>
      </entry>
"""

# Default values of parameters attributes
DEFAULT_ATTRS = {
    "const": "True",
    "glidein_publish": "True",
    "job_publish": "False",
    "parameter": "True",
    "publish": "True",
    "type": "string",
}

GLIDEIN_SUPPORTED_VO_MAP = {
    "atlas": "ATLAS",
    "cdf": "CDF",
    "cigi": "CIGI",
    "cms": "CMS",
    "engage": "EngageVO",
    "des": "DES",
    "dune": "DUNE",
    "fermilab": "Fermilab",
    "glow": "glowVO",
    "gluex": "GLUEX",
    "hcc": "HCC",
    "icecube": "IceCube",
    "lbne": "LBNE",
    "ligo": "LIGO",
    "lsst": "LSST",
    "minos": "MINOS",
    "mis": "MIS",
    "nanohub": "nanoHUB",
    "nebiogrid": "NEBioGrid",
    "nees": "NEES",
    "nova": "Nova",
    "nwicg": "NWICG",
    "sbgrid": "SBGrid",
    "osg": "OSGVO",
    "osgedu": "OSGEDU",
    "uc3": "UC3VO",
    "virgo": "VIRGO",
    "eic": "EIC",
    "clas12": "CLAS12",
}

GLIDEIN_SUPPORTED_VO_MAP_GPU = {
    "cms": "CMSGPU",
    "dune": "DUNEGPU",
    "fermilab": "FermilabGPU",
    "glow": "glowGPU",
    "hcc": "HCCGPU",
    "icecube": "IceCubeGPU",
    "ligo": "LIGOGPU",
    "nova": "NovaGPU",
    "sbgrid": "SBGridGPU",
    "osg": "OSGVOGPU",
    "virgo": "VIRGOGPU",
}

SUBMISSION_SPEED_MAP = {
    "super slow": {"cluster_size": 1, "max_per_cycle": 1, "sleep": 2, "slots_layout": "fixed"},
    "slow": {"cluster_size": 5, "max_per_cycle": 5, "sleep": 2, "slots_layout": "fixed"},
    "normal": {"cluster_size": 10, "max_per_cycle": 10, "sleep": 2, "slots_layout": "fixed"},
    "fast": {"cluster_size": 15, "max_per_cycle": 15, "sleep": 2, "slots_layout": "fixed"},
    "super fast": {"cluster_size": 20, "max_per_cycle": 20, "sleep": 2, "slots_layout": "fixed"},
}


# Class to handle error in the merge script
class ProgramError(Exception):
    """Simple collection of program error codes and related short messages.

    Args:
        code (int): Error code.

    Attributes:
        code (int): Exception error code.
    """

    codes_map = {
        1: "File not found",
        2: "Site not found",
        3: "CE not found",
        4: "Do not use BEST_FIT",
        5: "Collector error",
    }

    def __init__(self, code):
        super().__init__(self.codes_map[code])
        self.code = code


def get_yaml_file_info(file_name):
    """Loads a yaml file into a dictionary.

    Args:
        file_name (str): The file to load.

    Returns:
        dict: The loaded yaml file content.

    Raises:
        ProgramError: If the file is not found.
    """
    if not os.path.isfile(file_name):
        print("Cannot find file %s" % file_name)
        raise ProgramError(1)
    with open(file_name) as fdesc:
        out = yaml.load(fdesc, Loader=yaml.FullLoader)

    return out


def write_to_yaml_file(file_name, information):
    """Auxiliary function used to write a python dictionary into a yaml file.

    Args:
        file_name (str): The yaml filename that will be written out.
        information (dict): The dictionary to write.
    """
    with open(file_name, "w") as outfile:
        noalias_dumper = yaml.dumper.SafeDumper
        noalias_dumper.ignore_aliases = lambda self, information: True
        yaml.dump(information, outfile, default_flow_style=False, Dumper=noalias_dumper)


def get_attr_str(attrs):
    """Convert attributes from a dictionary form to the corresponding configuration string.

    Args:
        attrs (dict): The dictionary containing the attributes.

    Returns:
        str: The string representing the xml attributes section for a single entry.
    """
    out = ""
    for name, data in sorted(attrs.items()):
        if data is None:
            continue
        data["name"] = name
        update(data, DEFAULT_ATTRS, overwrite=False)
        if "comment" not in data:
            data["comment"] = ""
        else:
            data["comment"] = ' comment="' + data["comment"] + '"'
        if "value" in data:
            # pylint: disable=line-too-long
            out += (
                '            <attr name="%(name)s"%(comment)s const="%(const)s" glidein_publish="%(glidein_publish)s" job_publish="%(job_publish)s" parameter="%(parameter)s" publish="%(publish)s" type="%(type)s" value="%(value)s"/>\n'
                % data
            )

    return out[:-1]


# Collect all submit attributes
def get_submit_attr_str(submit_attrs):
    """Convert submit attributes from a dictionary form to the corresponding configuration string.

    Args:
        submit_attrs (dict): The dictionary containing the submit attributes.

    Returns:
        str: The string representing the xml submit attributes section for a single entry.
    """
    out = ""
    if submit_attrs:
        for name, value in sorted(submit_attrs.items()):
            if value is not None:
                out += f'\n                  <submit_attr name="{name}" value="{value}"/>'

    return out


# Collect all pilots limits
def get_limits_str(limits):
    """Convert pilots limits from a dictionary form to the corresponding configuration string.

    Args:
        limits (dict): The dictionary containing the pilots limits.

    Returns:
        str: The string representing the xml pilots limits section for a single entry.
    """
    out = ""
    if limits is not None:
        for name, value in reversed(sorted(limits.items())):
            if (
                value is not None
                and value.get("glideins") is not None
                and value.get("held") is not None
                and value.get("idle") is not None
            ):
                glideins = value["glideins"]
                held = min(max(int(glideins * value["held"] / 100), 5), glideins)
                idle = min(max(int(glideins * value["idle"] / 100), 10), glideins)
                if name == "entry":
                    out += f'\n               <per_entry glideins="{glideins}" held="{held}" idle="{idle}"/>'
                elif name == "frontend":
                    out += '\n               <default_per_frontend glideins="{}" held="{}" idle="{}"/>'.format(
                        glideins,
                        held,
                        idle,
                    )

    return out


# Collect submission speed
def get_submission_speed(submission_speed):
    """Convert submission speed from a name to the corresponding configuration string.

    Args:
        submission_speed (str): The string containing the submission speed name.

    Returns:
        str: The string representing the xml submission speed section for a single entry.
    """
    out = ""
    if submission_speed:
        if submission_speed in SUBMISSION_SPEED_MAP:
            submission_speed_dictionary = SUBMISSION_SPEED_MAP[submission_speed]
        else:
            submission_speed_dictionary = SUBMISSION_SPEED_MAP["normal"]
            print(
                "Submission speed with name "
                + submission_speed
                + " is not in SUBMISSION_SPEED_MAP, therefore submission speed is set to normal."
            )
        out += (
            '\n            <submit cluster_size="%(cluster_size)s" max_per_cycle="%(max_per_cycle)s" sleep="%(sleep)s" slots_layout="%(slots_layout)s">'
            % submission_speed_dictionary
        )

    return out


def update(data, update_data, overwrite=True):
    """Recursively update the information contained in a dictionary.

    Args:
        data (dict): The starting dictionary.
        update_data (dict): The dictionary that contains the new data.
        overwrite (bool): Whether existing keys are going to be overwritten.

    Returns:
        dict: The updated dictionary.
    """
    for key, value in list(update_data.items()):
        if value is None:
            if key in data:
                del data[key]
        elif isinstance(value, collections.abc.Mapping):
            sub_data = data.get(key, {})
            if sub_data is not None:
                data[key] = update(sub_data, value, overwrite)
        else:
            if overwrite or key not in data:
                data[key] = value

    return data


def write_to_xml_file(file_name, information):
    """Writes out on the disk entries xml adding the necessary top level tags.

    Args:
        file_name (str): The filename where you want to write to.
        information (str): A string containing the xml for all the entries.
    """
    with open(file_name, "w") as outfile:
        outfile.write("<glidein>\n")
        outfile.write("   <entries>\n")
        outfile.write(information)
        outfile.write("   </entries>\n")
        outfile.write("   <entry_sets>\n")
        outfile.write("   </entry_sets>\n")
        outfile.write("</glidein>\n")


# Write collected information to file
def write_to_file(file_name, information):
    """Take a dictionary and writes it out to disk as a yaml file.

    Args:
        file_name (str): The filename to write to disk.
        information (dict): The dictionary to write out as yaml file.
    """
    with open(file_name, "w") as outfile:
        yaml.safe_dump(information, outfile, default_flow_style=False)
