from __future__ import print_function

import sys
import logging
import argparse

from glideinwms.creation.lib.xmlConfig import DictElement, ListElement
from glideinwms.creation.lib.factoryXmlConfig import _parse, EntryElement, FactAttrElement, parse

tabs = 0
def count_tabs(function_to_decorate):
    def wrapper(*args, **kw):
        global tabs
        tabs += 1
        output = function_to_decorate(*args, **kw)
        tabs -= 1
    return wrapper

def check_list_diff(listA, listB):
    SKIP_TAGS = ['infosys_ref']
    for el in listA.children:
        if el.tag in SKIP_TAGS:
            continue
        if type(el)==DictElement:
            #print("\t"*tabs + "Checking %s" % el.tag)
            if len(listA.children) > 2:
                return
            #TODO what if B does not have it
            check_dict_diff(listA.children[0], listB.children[0],
                            lambda e: e.children.items())
        elif type(el)==FactAttrElement:
            #print("\t"*tabs + "Checking %s" % el['name'])
            elB = [ x for x in listB.children if x['name'] == el['name'] ]
            if len(elB) == 1:
                check_dict_diff(el, elB[0], FactAttrElement.items)
            elif len(elB) == 0:
                print("\t"*(tabs+1) + "%s: not present in %s" % (el['name'], entryB.getName()))
            else:
                print('More than one FactAttrElement')
        else:
            print('Element type not DictElement or FactAttrElement')
    for el in listB.children:
        if type(el)==FactAttrElement:
            elA = [ x for x in listA.children if x['name'] == el['name'] ]
            if len(elA) == 0:
                print("\t"*(tabs+1) + "%s: not present in %s" % (el['name'], entryA.getName()))


@count_tabs
def check_dict_diff(dictA, dictB, itemfunc=EntryElement.items, printName=True):
    tmpDictA = dict(itemfunc(dictA))
    tmpDictB = dict(itemfunc(dictB))
    SKIP_KEYS = ['name', 'comment']#, 'gatekeeper']
    for key, val in tmpDictA.items():
        #print("\t"*tabs + "Checking %s" % key)
        if key in SKIP_KEYS:
            continue
        if key not in tmpDictB:
            print("\t"*tabs + "Key %s(%s) not found in %s" % (key, val, entryB.getName()))
        elif type(val)==ListElement:
            check_list_diff(tmpDictA[key], tmpDictB[key])
        elif type(val)==DictElement:
            check_dict_diff(tmpDictA[key], tmpDictB[key], lambda e: e.children.items() if len(e.children)>0 else e.items())
        elif tmpDictA[key] != tmpDictB[key]:
            keystr = tmpDictA["name"] + ": " if printName else ""
            print("\t"*tabs + "%sKey %s is different: (%s vs %s)" %
                  (keystr, key, tmpDictA[key], tmpDictB[key]))
    for key, val in tmpDictB.items():
        if key in SKIP_KEYS:
            continue
        if key not in tmpDictA:
            print("\t"*tabs + "Key %s(%s) not found in %s" % (key, val, entryA.getName()))


def parse_opts():
    """ Parse the command line options for this command
    """
    description = 'Do a diff of two entries\n\n'

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        '--confA', type=str, action='store', dest='confA',
        default='/etc/gwms-factory/glideinWMS.xml',
        help='Configuration for the first entry')

    parser.add_argument(
        '--confB', type=str, action='store', dest='confB',
        default='/etc/gwms-factory/glideinWMS.xml',
        help='Configuration for the first entry')

    parser.add_argument(
        '--entryA', type=str, action='store', dest='entryA',
        help='Configuration for the first entry')

    parser.add_argument(
        '--entryB', type=str, action='store', dest='entryB',
        help='Configuration for the first entry')

    parser.add_argument(
        '--debug', action='store_true', dest='debug',
        default=False,
        help='Enable debug logging')

    options = parser.parse_args()

    #if options.entry_name is None:
    #    logging.error('Missing required option "--entry-name"')
    #    sys.exit(1)

    # Initialize logging
    if options.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

    return options


def main():
    """ The main
    """
    global entryA
    global entryB
    options = parse_opts()

    entryA = options.entryA
    entryB = options.entryB

    #conf = parse("/etc/gwms-factory/glideinWMS.xml")
    confA = _parse(options.confA)
    confB = _parse(options.confB)

    entryA = [ e for e in confA.get_entries() if e.getName()==entryA ]
    entryB = [ e for e in confB.get_entries() if e.getName()==entryB ]
    if len(entryA) != 1:
        print("Cannot find entry %s in the configuration file %s" % (options.entryA, options.confA))
        sys.exit(1)
    if len(entryB) != 1:
        print("Cannot find entry %s in the configuration file %s" % (options.entryB, options.confB))
        sys.exit(1)
    entryA = entryA[0]
    entryB = entryB[0]


    print("Checking entry attributes:")
    check_dict_diff(entryA, entryB, printName=False)
    print("Checking inner xml:")
    check_dict_diff(entryA.children, entryB.children, dict.items)


if __name__ == "__main__":
    main()
