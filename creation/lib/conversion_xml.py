#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#  These functions check the version of xml files
#  and perform the conversion if needed

import sys
import xml.etree.ElementTree as ET


def convert(type, input, output):
    with open(input, encoding="latin-1") as f:
        tree = ET.parse(f)
        parent_map = {c: p for p in tree.iter() for c in p}
        for elem in tree.findall(".//file"):
            try:
                print(elem)
                parent = parent_map[elem]
                if parent.tag != "xml":
                    grand_parent = parent_map[parent]
                else:
                    grand_parent = parent
                print(grand_parent)
                if grand_parent.tag == "entry":
                    print("entry")
                    elem.attrib["priority"] = "50"
                elif grand_parent.tag == "group":
                    if "after_entry" in elem.attrib:
                        if elem.attrib.get("after_entry") == "True":
                            print("group ae")
                            elem.attrib["priority"] = "70"
                        else:
                            print("group be")
                            elem.attrib["priority"] = "30"
                elif "after_entry" in elem.attrib or "after_group" in elem.attrib:
                    if elem.attrib.get("after_entry") == "True":
                        if type == "factory":
                            elem.attrib["priority"] = "90"
                        elif elem.attrib.get("after_group") == "True":
                            elem.attrib["priority"] = "80"
                        else:
                            elem.attrib["priority"] = "60"
                    else:
                        if type == "factory":
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
                    elem.attrib["type"] = "executable"
                    elem.attrib["time"] = "periodic:" + elem.attrib.get("period")
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
                        if child.tag == "untar_options":
                            elem.attrib["cond_attr"] = child.attrib["cond_attr"]
                            elem.attrib["absdir_outattr"] = child.attrib["absdir_outattr"]
                            elem.attrib["type"] = "untar:" + child.attrib["dir"]
                            elem.remove(child)

            except AttributeError:
                pass
        if output == "stdout":
            tree.write(sys.stdout.buffer)
        else:
            tree.write(output, encoding="latin-1")


def is_old_version(xml_file):
    with open(xml_file, encoding="latin-1") as f:
        tree = ET.parse(f)
        for elem in tree.findall("file"):
            if (
                "after_entry" in elem.attrib
                or "after_group" in elem.attrib
                or "period" in elem.attrib
                or "untar" in elem.attrib
                or "wrapper" in elem.attrib
                or "executable" in elem.attrib
            ):
                return True
            for child in elem:
                if child.tag == "untar_options":
                    return True
        return False


def main(type, input, output="stdout"):
    if is_old_version(input):
        convert(type, input, output)


def usage():
    print("Usage: python conversion_xml.py <options>")
    print("  <type>             : frontend/factory")
    print("  <input>            : input filename")
    print("  <output>           : (optional) output filename, stdout if not specified")
    print("  <-i>               : (optional) overwrite input file if present")


if __name__ == "__main__":
    if len(sys.argv) - 1 == 3:
        type = sys.argv[1]
        input = sys.argv[2]
        output = sys.argv[3]
        print(type, input, output)
        main(type, input, output)
    elif len(sys.argv) - 1 == 2:
        type = sys.argv[1]
        input = sys.argv[2]
        main(type, input)
    elif (len(sys.argv) - 1 == 4 or len(sys.argv) - 1 == 3) and sys.argv[len(sys.argv) - 1] == "-i":
        type = sys.argv[1]
        input = sys.argv[2]
        main(type, input, input)
    else:
        usage()
        exit(1)
    sys.exit(0)
