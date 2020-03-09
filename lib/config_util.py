"""This module contains a list of shared utility function used by the both OSG collector and CRIC
configuration generation helper tools
"""
from __future__ import division
from __future__ import print_function

import collections

import os
import yaml


# pylint: disable=line-too-long
ENTRY_STUB = """      <entry name="%(entry_name)s" auth_method="grid_proxy" comment="Entry automatically generated" enabled="%(enabled)s" gatekeeper="%(gatekeeper)s" gridtype="%(gridtype)s"%(rsl)s proxy_url="OSG" trust_domain="grid" verbosity="std" work_dir="%(work_dir)s">
         <config>
            <max_jobs>
               <default_per_frontend glideins="5000" held="50" idle="100"/>
               <per_entry glideins="10000" held="1000" idle="4000"/>
               <per_frontends>
               </per_frontends>
            </max_jobs>
            <release max_per_cycle="20" sleep="0.2"/>
            <remove max_per_cycle="5" sleep="0.2"/>
            <restrictions require_glidein_glexec_use="False" require_voms_proxy="False"/>
            <submit cluster_size="10" max_per_cycle="25" sleep="2" slots_layout="fixed">
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
    "type": "string"
}

GLIDEIN_SUPPORTED_VO_MAP = {
    "atlas": "ATLAS",
    "ATLAS": "ATLAS",
    "cdf": "CDF",
    "cigi": "CIGI",
    "cms": "CMS",
    "\"cms\"": "CMS",
    "CMS": "CMS",
    "engage": "EngageVO",
    "des": "DES",
    "dune": "DUNE",
    "fermilab": "Fermilab",
    "Fermilab": "Fermilab",
    "glow": "glowVO",
    "GLOW": "glowVO",
    "gluex": "GLUEX",
    "Gluex": "GLUEX",
    "hcc": "HCC",
    "HCC": "HCC",
    "icecube": "IceCube",
    "IceCube": "IceCube",
    "lbne": "LBNE",
    "ligo": "LIGO",
    "LIGO": "LIGO",
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
    "OSG": "OSGVO",
    "osgedu": "OSGEDU",
    "uc3": "UC3VO",
    "virgo": "VIRGO"
}


# Class to handle error in the merge script
class ProgramError(Exception):
    """Simple collection of program error codes and related short messages
    """
    codes_map = {
        1: "File not found",
        2: "Site not found",
        3: "CE not found",
    }

    def __init__(self, code):
        super(ProgramError, self).__init__(self.codes_map[code])
        self.code = code


def get_yaml_file_info(file_name):
    """Loads a yaml file into a dictionary

    Args:
        file_name (str): The file to load
        error_code (int): The error code to return if the file does not exist
    """
    if not os.path.isfile(file_name):
        print("Cannot find file %s" % file_name)
        raise ProgramError(1)
    with open(file_name) as fdesc:
        out = yaml.load(fdesc)

    return out


def write_to_yaml_file(file_name, information):
    """ Auxiliary function used to write a python dictionary into a yaml file

    Args:
        file_name (string): The yaml filename that will be written out
        information (dict):
    """
    with open(file_name, "w") as outfile:
        noalias_dumper = yaml.dumper.SafeDumper
        noalias_dumper.ignore_aliases = lambda self, information: True
        yaml.dump(information, outfile, default_flow_style=False, Dumper=noalias_dumper)


def get_attr_str(attrs):
    """Convert attributes from a dictionary form to the corresponding configuration string

    Args:
        attrs (dict): the dictionary containing the attributes

    Returns:
        string: the string representing the xml attributes section for a single entry
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
            data["comment"] = ' comment="' + data["comment"]  + '"'
        if "value" in data:
            # pylint: disable=line-too-long
            out += '            <attr name="%(name)s"%(comment)s const="%(const)s" glidein_publish="%(glidein_publish)s" job_publish="%(job_publish)s" parameter="%(parameter)s" publish="%(publish)s" type="%(type)s" value="%(value)s"/>\n' % data

    return out[:-1]


# Collect all submit attributes
def get_submit_attr_str(submit_attrs):
    """Convert submit attributes from a dictionary form to the corresponding configuration string

    Args:
        submit_attrs (dict): the dictionary containing the submit attributes

    Returns:
        string: the string representing the xml submit attributes section for a single entry
    """
    out = ""
    if submit_attrs:
        for name, value in sorted(submit_attrs.items()):
            if value is not None:
                out += '\n                  <submit_attr name="%s" value="%s"/>' % (name, value)

    return out


def update(data, update_data, overwrite=True):
    """Recursively update the information contained in a dictionary

    Args:
        data (dict): The starting dictionary
        update_data (dict): The dictionary that contains the new data
        overwrite (bool): wether existing keys are going to be overwritten
    """
    for key, value in update_data.items():
        if value is None:
            if key in data:
                del data[key]
        elif isinstance(value, collections.Mapping):
            sub_data = data.get(key, {})
            if sub_data is not None:
                data[key] = update(sub_data, value, overwrite)
        else:
            if overwrite or key not in data:
                data[key] = value

    return data


def write_to_xml_file(file_name, information):
    """Writes out on the disk entries xml adding the necessary top level tags

    Args:
        file_name (str): the filename where you want to write to.
        information (str): a string containing the xml for all the entries
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
    """Take a dictionary and writes it out to disk as a yaml file

    Args:
        file_name (str): the filename to write to disk
        information (dict): the dictionary to write out as yaml file
    """
    with open(file_name, "w") as outfile:
        yaml.safe_dump(information, outfile, default_flow_style=False)
