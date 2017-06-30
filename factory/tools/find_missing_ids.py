#!/usr/bin/python

"""
Tool for maintaining the glideinWMS Factory configuration file. Finds all the entries
in the Factory configuration file that do not contain an information systems id.  
    
Usage: python config_update_tool.py [options]
Options:
     -x [filepath of config.xml, required]
     -d [skip_disabled entries, yes (default) or no, optional]
     -h, --help  show this help

"""
from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import getopt 
import datetime
from xml.dom import minidom
from . import infosys_lib 

USAGE = "Usage: python config_update_tool.py [options]\n" \
        "Options: \n" \
        "  -x [filepath of config.xml, required]\n" \
        "  -d [skip_disabled entries, yes (default) or no, optional]\n" \
        "  -h, --help  show this help\n"
  
        
def main(argv):
    """
    For the given config, finds and prints the entries without an infosys id.
    """ 
    
    # Set defaults for the arguments
    config_xml = ""
    skip_disabled = 'yes'
    
    try:
        opts, args = getopt.getopt(argv, "hx:d:", ["help"])
    except getopt.GetoptError:
        print("Unrecognized or incomplete input arguments.")
        print(USAGE)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(USAGE)
            sys.exit()
        else:
            if opt == '-x':
                config_xml = arg
            elif opt == '-d':
                skip_disabled = arg
            else:
                print("Unrecognized input arguments.")
                print(USAGE)
                sys.exit(2)
            
    # Validate args
    if config_xml == '':
        print("No configuration file was provided.")
        print(USAGE)
        sys.exit(2)
    else: 
        if not os.path.isfile(config_xml):
            print("Config file '%s' does not exist." % config_xml)
            sys.exit(2)

    if skip_disabled.lower() != 'yes' and skip_disabled.lower() != 'no':
        print("Skip disabled argument must be 'yes' or 'no'.")
        print(USAGE)
        sys.exit(2)
    
    if skip_disabled == 'yes':
        skip_disabled = True
    else:
        skip_disabled = False
    
    # Find entries missing ids       
    config_entries = find_entries_missing_infosys_id(config_xml, skip_disabled)
    
    # Format output
    datestamp = datetime.datetime.now().strftime("%Y-%m-%d %M:%S")
    output = "\nThis file contains all the entries in the factory configuration file that " \
                "do not contain a ref identifier in <infosys_ref>.\nThese entries cannot be verified " \
                "with any information system.\nScript run on : %s \n\n" % datestamp

    if len(config_entries) == 0:
        output += "No entries were found with missing ref id.\n"
    else:
        for entry_id, entry_val in config_entries.iteritems():
            output += "Entry Name : %s\n" % entry_val["name"]
            output += "gatekeeper : %s\n" % entry_val["gatekeeper"]
            output += "rsl : %s\n" % entry_val["rsl"]
            output += "gridtype : %s\n" % entry_val["gridtype"]
            output += "\n"
      
    # Output results
    print(output)
    
    
def find_entries_missing_infosys_id(config_xml, skip_disabled=True):
    """
    Parses the config for any entries that don't have an infosys id.
    """
    # Find all enabled config entries without a ref id
    try:
        config_dom = minidom.parse(config_xml)
        config_entries = infosys_lib.parse_entries(config_dom, skip_missing_ref_id=False, skip_disabled=skip_disabled)
    except: 
        print("Error parsing the entries from the config file '%s', exiting the tool." % config_xml)
        sys.exit(2)  
    
    missing_ids = {}
    for entry_name in config_entries.keys():
        if config_entries[entry_name]['ref_id'] == '':
            missing_ids[entry_name] = config_entries[entry_name]
    
    return missing_ids

if __name__ == "__main__":
    main(sys.argv[1:])











   
