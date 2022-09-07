#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#  These functions check the version of xml files
#  and perform the conversion if needed

import xml.etree.ElementTree as ET


def convert(xml_file):
    with open(xml_file, encoding="latin-1") as f:
        tree = ET.parse(f)
        for elem in tree.findall("file"):
            print(elem)
            try:
                if "after_entry" in elem.attrib or "after_group" in elem.attrib:
                    if elem.attrib.get("after_entry") == "True":
                        if not "after_group" in elem.attrib:
                            elem.attrib["priority"] = "90"
                        elif elem.attrib.get("after_group") == "True":
                            elem.attrib["priority"] = "80"
                        else:
                            elem.attrib["priority"] = "60"
                    elif elem.attrib.get("after_entry") == "False":
                        if not "after_group" in elem.attrib:
                            elem.attrib["priority"] = "10"
                        elif elem.attrib.get("after_group") == "True":
                            elem.attrib["priority"] = "40"
                        else:
                            elem.attrib["priority"] = "20"
                    if "after_entry" in elem.attrib:
                        elem.attrib.pop("after_entry")
                    if "after_group" in elem.attrib:
                        elem.attrib.pop("after_group")
                else:
                    continue

                if elem.attrib.get("executable") == "True":
                    elem.attrib.pop("executable")
                    elem.attrib["type"] = "exec"

                if "period" in elem.attrib:
                    elem.attrib["type"] = "periodic:" + elem.attrib.get("period")
                    elem.attrib.pop("period")

                if elem.attrib.get("wrapper") == "True":
                    elem.attrib.pop("wrapper")
                    elem.attrib["type"] = "wrapper"

                if elem.attrib.get("source") == "True":
                    elem.attrib.pop("source")
                    elem.attrib["type"] = "source"

                if elem.attrib.get("library") == "True":
                    elem.attrib.pop("library")
                    elem.attrib["type"] = "library"

                if elem.attrib.get("untar") == "True":
                    elem.attrib["type"] = "untar"
                    elem.attrib.pop("untar")

                if elem.attrib.get("type") == "untar":
                    for child in elem:
                        print(child)
                        if child.tag == "untar_options":
                            print("yes")
                            elem.attrib["cond_attr"] = child.attrib["cond_attr"]
                            elem.attrib["absdir_outattr"] = child.attrib["absdir_outattr"]
                            elem.attrib["type"] = "untar:" + child.attrib["dir"]
                            elem.remove(child)

            except AttributeError:
                pass
        tree.write("2" + xml_file, encoding="latin-1")


def is_old_version(xml_file):
    with open(xml_file, encoding="latin-1") as f:
        tree = ET.parse(f)
        for elem in tree.findall("file"):
            if "after_entry" in elem.attrib or "after_group" in elem.attrib or "period" in elem.attrib:
                return True
            for child in elem:
                if child.tag == "untar_options":
                    return True
        return False
