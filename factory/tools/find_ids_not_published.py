#!/usr/bin/python

"""
Tool for maintaining the glideinWMS Factory configuration file.  Finds all the factory configuration entries that contain a ref id that is not published in the information system listed.

Usage: python config_update_tool.py [options]
Options:
     -x [filepath of config.xml, required]
     -d [skip_disabled entries, yes (default) or no, optional]
     -h, --help  show this help

"""
from __future__ import print_function

import os
import sys
import getopt 
import datetime
from xml.dom import minidom
STARTUP_DIR = os.path.abspath(sys.path[0])
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))
from glideinwms.factory.tools import infosys_lib 
from glideinwms.lib import condorExe

USAGE = "Usage: python config_update_tool.py [options]\n" \
        "Options: \n" \
        "  -x [filepath of config.xml, required]\n" \
        "  -d [skip_disabled entries, yes (default) or no, optional]\n" \
        "  -h, --help  show this help\n"
        

def main(argv):
    """
    Takes input configuration file and information system and finds entries where the id doesn't 
    exist in the given information system. 
    """ 
    
    # Set defaults for the arguments
    config_xml = ""
    skip_disabled = 'yes'

    try:
        opts, args = getopt.getopt(argv, "hx:d:", ["help"])
    except getopt.GetoptError:
        print("Unrecognized options or incorrect input.")
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
                print("Unrecognized options or incorrect input.")
                print(USAGE)
                sys.exit(2)
            
    # Validate arg exists
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
        
    # Find config entries not currently being published in the infosys              
    no_id_bdii, no_id_ress, no_id_tg = find_entries_with_ids_not_published(config_xml, skip_disabled)
                
    # Format output
    datestamp = datetime.datetime.now().strftime("%Y-%m-%d")
    output = "This file contains entries with information system ids that could not be identified " \
                "in the information system given.\n"
    output += "Script run on : %s \n" % datestamp
    output += "Number of entries : %i\n\n" % (len(no_id_bdii) + len(no_id_ress) + len(no_id_tg))
    
    if len(no_id_bdii) == 0 and len(no_id_ress) == 0 and len(no_id_tg) == 0:
        output += "No entries contained ref ids not found in the information system.\n"
    else:
        for entry in no_id_bdii:
            output += "BDII Id : %s\n" % entry["ref_id"]
            output += "source type: %s\n" % entry["source_type"]
            output += "source url: %s\n" % entry["source"]
            output += "entry name : %s\n" % entry["name"]
            output += "gatekeeper : %s\n" % entry["gatekeeper"]
            output += "rsl : %s\n" % entry["rsl"]
            output += "gridtype : %s\n" % entry["gridtype"]
            output += "\n"
        output += '\n'
                
        for entry in no_id_ress:
            output += "RESS Id : %s\n" % entry["ref_id"]
            output += "source type: %s\n" % entry["source_type"]
            output += "source url: %s\n" % entry["source"]
            output += "entry name : %s\n" % entry["name"]
            output += "gatekeeper : %s\n" % entry["gatekeeper"]
            output += "rsl : %s\n" % entry["rsl"]
            output += "gridtype : %s\n" % entry["gridtype"]
            output += "\n"
        output += '\n'
                
        for entry in no_id_tg:
            output += "TG Id : %s\n" % entry["ref_id"]
            output += "source type: %s\n" % entry["source_type"]
            output += "source url: %s\n" % entry["source"]
            output += "entry name : %s\n" % entry["name"]
            output += "gatekeeper : %s\n" % entry["gatekeeper"]
            output += "rsl : %s\n" % entry["rsl"]
            output += "gridtype : %s\n" % entry["gridtype"]
            output += "\n"            
            
    # Output results
    print(output)
    
    
def find_entries_with_ids_not_published(config_xml, skip_disabled):
    """
    Find config entries not published in the information systems.
    """
    try:
        # Find all enabled config entries with ref ids
        config_dom = minidom.parse(config_xml)
        config_entries = infosys_lib.parse_entries(config_dom, skip_missing_ref_id=True, skip_disabled=skip_disabled)
                    
        # Create an info systems list from factory config
        infosystems = infosys_lib.parse_info_systems(config_dom)
        
        has_ress = False
        for infosys in infosystems:
            if infosystems[infosys].lower() == 'ress':
                has_ress = True
                break
        if has_ress:  
            # Update path with condor 
            condor_path = infosys_lib.parse_condor_path(config_dom)
            os.environ["CONDOR_CONFIG"] = condor_path + "/etc/condor_config"
            condorExe.set_path(condor_path + "/bin", condor_path + "/sbin")
    except: 
        print("Error parsing the the config file '%s', exiting the tool." % config_xml)
        sys.exit(2) 

    # Retrieve info systems entries 
    bdii_entries = {}
    ress_entries = {}
    tg_entries = {}
    for infosys, type in infosystems.iteritems():
        if type.lower() == 'bdii':
            bdii_entries.update(infosys_lib.query_bdii(infosys))
                
        elif type.lower() == 'ress':
            ress_entries.update(infosys_lib.query_ress(infosys))
                
        elif type.lower() == 'tg':
            tg_entries.update(infosys_lib.query_teragrid())
            

    id_not_found_bdii_entries = find_entries_id_not_found(bdii_entries, config_entries, 'bdii')
    id_not_found_ress_entries = find_entries_id_not_found(ress_entries, config_entries, 'ress')
    id_not_found_tg_entries = find_entries_id_not_found(tg_entries, config_entries, 'tg')

    return id_not_found_bdii_entries, id_not_found_ress_entries, id_not_found_tg_entries


def find_entries_id_not_found(infosys_entries, config_entries, source_type):
    """
    Compares the information systems entries with entries in the config file that list a ref id.  
    Returns a list of entries in config the that have an ref id that was not found in the infosys.
    """
    id_not_found_entries = []
    print(source_type)
    
    for entry_name in config_entries.keys():
        entry_c = config_entries[entry_name]
        
        # Only compare entries that match the infosys
        if entry_c['source_type'].lower() == source_type.lower():
            # Check if ref id in infosys entries keys
            entry_found = False
            for info_id in infosys_entries.keys():
                entry_i = infosys_entries[info_id]
                if entry_c['ref_id'] == entry_i['ref_id']:
                    entry_found = True
                    break
            if not entry_found:
                id_not_found_entries.append(entry_c)
            # TODO do we need to check source url too?            
    
    return id_not_found_entries


if __name__ == "__main__":
    main(sys.argv[1:])
