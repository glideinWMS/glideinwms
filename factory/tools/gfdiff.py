""" This script allows to compare two different entries
"""

from __future__ import print_function

import re
import sys
import uuid
import base64
import hashlib
import argparse
import requests

from glideinwms.creation.lib.xmlConfig import DictElement, ListElement
from glideinwms.creation.lib.factoryXmlConfig import _parse, EntryElement, FactAttrElement #, parse


g_entry_a = None
g_entry_b = None
last_key = []
tabs = 0

def count_tabs(function_to_decorate):
    """ Decorator function that keeps track of how many intentation level are required.
    In other words, the decorator counts how many times the decorated function is called
    """
    def wrapper(*args, **kw):
        """The wrapper function
        """
        global tabs
        tabs += 1
        _ = function_to_decorate(*args, **kw)
        tabs -= 1
    return wrapper


def check_list_diff(list_a, list_b):
    """Scan the two list for differences
    """
    SKIP_TAGS = ['infosys_ref']
    for elem in list_a.children:
        if elem.tag in SKIP_TAGS:
            continue
        if isinstance(elem, DictElement):
            #print("\t"*tabs + "Checking %s" % elem.tag)
            if len(list_a.children) > 2:
                return
            #TODO what if B does not have it
            check_dict_diff(list_a.children[0], list_b.children[0],
                            lambda e: e.children.items())
        elif isinstance(elem, FactAttrElement):
            #print("\t"*tabs + "Checking %s" % elem['name'])
            elem_b = [x for x in list_b.children if x['name'] == elem['name']]
            if len(elem_b) == 1:
                check_dict_diff(elem, elem_b[0], FactAttrElement.items)
            elif len(elem_b) == 0:
                print("\t"*(tabs+1) + "%s: not present in %s" % (elem['name'], g_entry_b.getName()))
            else:
                print('More than one FactAttrElement')
        else:
            print('Element type not DictElement or FactAttrElement')
    for elem in list_b.children:
        if isinstance(elem, FactAttrElement):
            elem_a = [x for x in list_a.children if x['name'] == elem['name']]
            if len(elem_a) == 0:
                print("\t"*(tabs+1) + "%s: not present in %s" % (elem['name'], g_entry_a.getName()))


@count_tabs
def check_dict_diff(dict_a, dict_b, itemfunc=EntryElement.items, print_name=True):
    """Check differences between two dictionaries
    """
    tmp_dict_a = dict(itemfunc(dict_a))
    tmp_dict_b = dict(itemfunc(dict_b))
    SKIP_KEYS = ['name', 'comment']  #, 'gatekeeper']
    for key, val in tmp_dict_a.items():
        last_key.append(key)
        #print("\t"*tabs + "Checking %s" % key)
        if key in SKIP_KEYS:
            continue
        if key not in tmp_dict_b:
            print("\t"*tabs + "Key %s(%s) not found in %s" % (key, val, g_entry_b.getName()))
        elif isinstance(val, ListElement):
            check_list_diff(tmp_dict_a[key], tmp_dict_b[key])
        elif isinstance(val, DictElement):
            check_dict_diff(tmp_dict_a[key], tmp_dict_b[key],
                            lambda e: e.children.items() if len(e.children) > 0 else e.items())
        elif tmp_dict_a[key] != tmp_dict_b[key]:
            keystr = (tmp_dict_a["name"] + ": " if print_name and "name" in tmp_dict_a
                      else last_key[-2] + ": ")
            print("\t"*tabs + "%sKey %s is different: (%s vs %s)" %
                  (keystr, key, tmp_dict_a[key], tmp_dict_b[key]))
        last_key.pop()
    for key, val in tmp_dict_b.items():
        if key in SKIP_KEYS:
            continue
        if key not in tmp_dict_a:
            print("\t"*tabs + "Key %s(%s) not found in %s" % (key, val, g_entry_a.getName()))


def parse_opts():
    """ Parse the command line options for this command
    """
    description = 'Do a diff of two entries\n\n'

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        '--confA', type=str, action='store', dest='conf_a',
        default='/etc/gwms-factory/glideinWMS.xml',
        help='Configuration for the first entry')

    parser.add_argument(
        '--confB', type=str, action='store', dest='conf_b',
        default='/etc/gwms-factory/glideinWMS.xml',
        help='Configuration for the first entry')

    parser.add_argument(
        '--entryA', type=str, action='store', dest='entry_a',
        help='Configuration for the first entry')

    parser.add_argument(
        '--entryB', type=str, action='store', dest='entry_b',
        help='Configuration for the first entry')

    parser.add_argument(
        '--mergely', action='count',
        help='Only print the mergely link')

    options = parser.parse_args()

    return options


def get_entry_text(entry, conf):
    """Get an entry text from the xml configuration file
    """
    with open(conf) as fdesc:
        text = fdesc.read()
        return re.search(".*( +<entry name=\"%s\".*?</entry>)" % entry, text, re.DOTALL).group(1)


def handle_mergely(entry_a, conf_a, entry_b, conf_b, mergely_only):
    """Function that prints the link to the mergely website
    """
    url = 'http://www.mergely.com/ajax/handle_file.php'

    # get a unique 8char key
    unique_id = uuid.uuid4()
    myhash = hashlib.sha1(str(unique_id).encode("UTF-8"))
    key = base64.b32encode(myhash.digest())[0:8]

    payload = {
        "key": key,
        "name": "lhs",
        "content": get_entry_text(entry_a, conf_a)
    }
    requests.post(url, data=payload)
    payload["name"] = "rhs"
    payload["content"] = get_entry_text(entry_b, conf_b)
    requests.post(url, data=payload)
    requests.get("http://www.mergely.com/ajax/handle_save.php?key=" + key)
    if mergely_only:
        print("http://www.mergely.com/" + key)
    else:
        print("Visualize differences at: http://www.mergely.com/" + key)
        print()


def main():
    """ The main
    """
    global g_entry_a
    global g_entry_b
    options = parse_opts()

    if options.mergely:
        handle_mergely(options.entry_a, options.conf_a, options.entry_b,
                       options.conf_b, options.mergely)
        return

    entry_a = options.entry_a
    entry_b = options.entry_b

    #conf = parse("/etc/gwms-factory/glideinWMS.xml")
    conf_a = _parse(options.conf_a)
    conf_b = _parse(options.conf_b)

    # pylint: disable=no-member
    entry_a = [e for e in conf_a.get_entries() if e.getName() == entry_a]
    # pylint: disable=no-member
    entry_b = [e for e in conf_b.get_entries() if e.getName() == entry_b]
    if len(entry_a) != 1:
        print("Cannot find entry %s in the configuration file %s" %
              (options.entry_a, options.conf_a))
        sys.exit(1)
    if len(entry_b) != 1:
        print("Cannot find entry %s in the configuration file %s" %
              (options.entry_b, options.conf_b))
        sys.exit(1)
    g_entry_a = entry_a[0]
    g_entry_b = entry_b[0]

    print("Checking entry attributes:")
    check_dict_diff(g_entry_a, g_entry_b, print_name=False)
    print("Checking inner xml:")
    check_dict_diff(entry_a.children, entry_b.children, dict.items)


if __name__ == "__main__":
    main()
