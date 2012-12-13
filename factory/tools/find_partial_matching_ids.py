#!/usr/bin/python

"""
Tool for maintaining the glideinWMS Factory configuration file.  All configuration file 
entries that have a partial match to the information system id.  No comparison is done on the content.

Usage: python config_update_tool.py [options]
Options:
     -x [filepath of config.xml, required]
     -d [skip_disabled entries, yes (default) or no, optional]
     -h, --help  show this help

"""

import os
import sys
import getopt 
import datetime
from xml.dom import minidom
import infosys_lib 
STARTUP_DIR = os.path.abspath(sys.path[0])
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))
from glideinwms.lib import condorExe

USAGE = "Usage: python config_update_tool.py [options]\n" \
        "Options: \n" \
        "  -x [filepath of config.xml, required]\n" \
        "  -d [skip_disabled entries, yes (default) or no, optional]\n" \
        "  -h, --help  show this help\n"

def main(argv):
    """
    Takes input configuration file and information system and finds entries where the id partially matches one published in 
    the given information system.
    """ 
    
    # Set defaults for the arguments
    config_xml = ""
    skip_disabled = 'yes'
    
    try:
        opts, args = getopt.getopt(argv, "hx:d:", ["help"])
    except getopt.GetoptError:
        print "Unrecognized or incomplete input arguments."
        print USAGE
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print USAGE
            sys.exit()
        else:
            if opt == '-x':
                config_xml = arg
            elif opt == '-d':
                skip_disabled = arg
            else:
                print "Unrecognized input arguments. "
                print USAGE
                sys.exit(2)
            
    # Validate arg exists
    if config_xml == '':
        print "No configuration file was provided. "
        print USAGE
        sys.exit(2)
    else: 
        if not os.path.isfile(config_xml):
            print "Config file '%s' does not exist." % config_xml
            sys.exit(2)

    if skip_disabled.lower() != 'yes' and skip_disabled.lower() != 'no':
        print "Skip disabled argument must be 'yes' or 'no'."
        print USAGE
        sys.exit(2)
    
    if skip_disabled == 'yes':
        skip_disabled = True
    else:
        skip_disabled = False
                 
    # Find entries with partial id matches      
    partial_bdii, partial_ress, partial_tg = find_entries_with_partial_id_match(config_xml, skip_disabled)
    
    # Format output
    datestamp = datetime.datetime.now().strftime("%Y-%m-%d %M:%S")
    output = "\nThis file contains entries that have <infosys_ref> information that is similar to " \
                "what is published in the information system.\n"
    output += "Script run on : %s \n" % datestamp
    output += "Number of entries: %i\n\n" % (len(partial_bdii) + len(partial_ress) + len(partial_tg))

    if len(partial_bdii) == 0 and len(partial_ress) == 0 and len(partial_tg) == 0:
        output += "No entries were found with partial matching ids.\n"
    else:
        output += infosys_lib.format_entry_pair_output(partial_bdii)
        output += infosys_lib.format_entry_pair_output(partial_ress)
        output += infosys_lib.format_entry_pair_output(partial_tg)
    
    # Output results
    print output
    
    
def find_entries_with_partial_id_match(config_xml, skip_disabled):
    """
    Finds the bdii, ress and TeraGrid entries with partial matches.
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
        print "Error parsing the the config file '%s', exiting the tool." % config_xml
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
            tg_entries.update(infosys_lib.query_teragrid(infosys))
            
    partial_match_bdii_entries = find_partial_id_match(bdii_entries, config_entries, 'bdii')
    partial_match_ress_entries = find_partial_id_match(ress_entries, config_entries, 'ress')
    partial_match_tg_entries = find_partial_id_match(tg_entries, config_entries, 'tg')
    
    return partial_match_bdii_entries, partial_match_ress_entries, partial_match_tg_entries


def find_partial_id_match(infosys_entries, config_entries, source_type):
    """
    Compares the information systems entries with entries in the config file that list a ref id.  
    Returns a list of a list of the config and info sys entries where there was a partial match of the ref ids.
    """
    id_partial_match = [] # list of lists
    
    for entry_name in config_entries.keys():
        entry_c = config_entries[entry_name]
        
        # Skip match if not from the same source, only compare apples to apples
        # TODO check source url too?
        if entry_c['source_type'].lower() != source_type.lower():
            continue
        
        for infosys_id in infosys_entries.keys():
            entry_i = infosys_entries[infosys_id]
            if ((entry_c['ref_id'] in entry_i['ref_id']) or (entry_i['ref_id'] in entry_c['ref_id'])) and (entry_i['ref_id'] != entry_c['ref_id']):
                id_partial_match.append([entry_c, infosys_entries[infosys_id]])
                break

    return id_partial_match


if __name__ == "__main__":
    main(sys.argv[1:])
