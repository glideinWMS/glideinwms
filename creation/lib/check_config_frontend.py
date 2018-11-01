#!/usr/bin/python
# Script to check that /etc/gwms-frontend/frontend.xml is compatible w/ connected Factories

from __future__ import print_function
import xml.etree.ElementTree as ET
import htcondor
import sys

CONFIG_FILE="/etc/gwms-frontend/frontend.xml"


def mylog(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class ConfigFileError(RuntimeError):
    """Class to raise config verification error"""
    pass


def get_factory_version(node_name):
    htcondor.reload_config()
    collector = htcondor.Collector(node_name)
    adtype = htcondor.AdTypes.Any
    constraint = 'MyType == "glidefactoryglobal"'
    results = collector.query(adtype, constraint, ['GlideinWMSVersion'])
    return results[0]['GlideinWMSVersion']


def check_fail(msg):
    raise ConfigFileError(msg)


def check_attr(attr):
    # print ("MMDB: att %r (%s, %s)" % (attr,attr.attrib['name'],attr.attrib['value']))
    if attr.attrib['name'] == "GLIDEIN_Singularity_Use" and attr.attrib['value'] == "PREFERRED":
        check_fail("'PREFERRED' value for GLIDEIN_Singularity_Use")
    if attr.attrib['name'] == "SINGULARITY_IMAGES_DICT" or attr.attrib['name'] == "GLIDEIN_SINGULARITY_BINDPATH" or attr.attrib['name'] == "GLIDEIN_SINGULARITY_OPTS":
        check_fail("Using attribute %s" % attr.attrib['name'] )


def check_collector(coll_elem):
    # print ("MMDB: coll %r (%s, %s)" % (coll_elem,coll_elem.attrib,coll_elem.attrib['node']))
    coll = coll_elem.attrib['node']
    ind1 = coll.find("sock=")
    if ind1 > 0:
        ind2 = coll.find("-", ind1)
        if ind2 > ind1:
            check_fail("Sock ranges not supported in earlier versions")


def check_config(root):
    """Fail if there is something requiring 3.4.1"""
    # check Singularity attributes
    try:
        for attr in root.findall("./attrs/attr"):
            check_attr(attr)
        for attr in root.findall("./groups/group/attrs/attr"):
            check_attr(attr)
        for coll in root.findall("./collectors/collector"):
            check_collector(coll)
        for coll in root.findall("./groups/group/collectors/collector"):
            check_collector(coll)
        for coll in root.findall("./ccbs/ccb"):
            check_collector(coll)
        for coll in root.findall("./groups/group/ccbs/ccb"):
            check_collector(coll)
    except ConfigFileError as e:
        raise RuntimeError("At least one GWMS Factory connected is lower than v3.4.1\nYour configuration requires v3.4.1 Factories: %s" % e.message)
    return "Config file compatible w/ GWMS v3.4 Factories"


def main(config_file):
    """Parse and check the Frontend configuration in config_file"""
    try:
        tree = ET.parse(config_file)
    except IOError:
        return "Config file not readable: %s" % config_file
    except:
        return "Error parsing config file: %s" % config_file
    root = tree.getroot()
    fc_list = []
    for factory_collector in root.findall("./match/factory/collectors/collector"):
        fc_list.append(factory_collector.attrib['node'])
    all_3_4_1 = True
    for fc in fc_list:
        f_version = get_factory_version(fc)
        if f_version.startswith("glideinWMS 3.4-") or f_version.startswith("glideinWMS 3.2") or f_version.startswith("glideinWMS 3.3"):
            all_3_4_1 = False
            break
    if all_3_4_1:
        return "All connected Factories are at least v3.4.1"
    return check_config(root)


if __name__ == '__main__':
    config_file = CONFIG_FILE
    if len(sys.argv) == 1:
        config_file = sys.argv[0]
    try:
        msg = main(config_file)
    except RuntimeError as e:
        for line in str(e).split('\n'):
            mylog(line)
        sys.exit(1)
    mylog(msg)
    sys.exit(0)
