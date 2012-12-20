#!/usr/bin/python

"""
Tool for maintaining the glideinWMS Factory configuration file.

Finds all entries for a given information system that are not contained in the configuration   
file.  The entries will be formatted as the entry xml so that they can be pasted directly into the 
configuration file.

Usage: python config_update_tool.py [options]
Options:
     -x [filepath of config.xml, required]
     -s [information source url, required]
     -t [information source type:  bdii, ress, tg, required]
     -v [VO name, optional]
     -d [skip_disabled entries, yes (default) or no, optional]
     -h, --help  show this help


"""

import os
import sys
import getopt 
import datetime
import random
from xml.dom import minidom
import infosys_lib 
STARTUP_DIR = os.path.abspath(sys.path[0])
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))
from glideinwms.lib import condorExe

USAGE = "Usage: python config_update_tool.py [options] \n" \
        "Options:\n" \
        "  -x [filepath of config.xml, required]\n" \
        "  -s [information source url, required]\n" \
        "  -t [information source type:  bdii, ress, tg, required]\n" \
        "  -v [VO name, optional]\n" \
        "  -d [skip_disabled entries, yes (default) or no, optional]\n" \
        "  -h, --help  show this help\n" 


def main(argv):
    """
    Takes input configuration file and information system and finds new entries in the given information system. 
    """ 
    
    # Set defaults for the arguments
    config_xml = source = source_type = vo_name = ""
    skip_disabled = 'yes'
    
    try:
        opts, args = getopt.getopt(argv, "hx:s:t:v:d:", ["help"])
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
            elif opt == '-s': 
                source = arg
            elif opt == '-t':
                source_type = arg
            elif opt == '-v':
                vo_name = arg  #TODO do we want to accept a list of VOs?
            elif opt == '-d':
                skip_disabled = arg
            else:
                print "Unrecognized input arguments."
                print USAGE
                sys.exit(2)
               
    # Validate args
    err_msg = ""
    if config_xml == "":
        err_msg += "No configuration file was provided.\n"
    else: 
        if not os.path.isfile(config_xml):
            err_msg += "Config file '%s' does not exist.\n" % config_xml
    if source == '' or source_type == '':
        err_msg += "Source and source type must be defined.\n" 
    if err_msg:
        print err_msg
        print USAGE
        sys.exit(2)

    if skip_disabled.lower() != 'yes' and skip_disabled.lower() != 'no':
        print "Skip disabled argument must be 'yes' or 'no'."
        print USAGE
        sys.exit(2)  
    if skip_disabled == 'yes':
        skip_disabled = True
    else:
        skip_disabled = False
        
    # Find new entries       
    new_entries = find_new_entries_in_infosys(config_xml, source, source_type, skip_disabled, vo_name)
           
    # Format output
    datestamp = datetime.datetime.now().strftime("%Y-%m-%d %M:%S")
    output = "\nThis file contains all new entries published in the information system that are not identifiable in " \
                 "the config file.  They are formatted to be pasted directly into the config file.\n"
    output += "Script run on : %s \n" % datestamp
    output += "Number of new entries : %i\n\n" % len(new_entries)
        
    # Create formatted xml output
    if len(new_entries) > 0:
        
        # Get list of schedd
        try:
            # Find all config entries not disabled
            config_dom = minidom.parse(config_xml)
            schedds = infosys_lib.parse_factory_schedds(config_dom)
        except: 
            print "Error parsing the config file '%s' for the schedds, exiting the tool." % config_xml
            sys.exit(2)    
            
        for entry in new_entries:
            # Pick a random schedd to assign to this entry TODO - need to be able to assign to a specific schedd?
            random.shuffle(schedds)
            output += infosys_lib.generate_entry_xml(entry, schedds[0])  
    else:
        output = "No new entries were found.\n"  

    # Output results
    print output
    
    
def find_new_entries_in_infosys(config_xml, source, source_type, skip_disabled, vo_name=''):
    """
    For the given information system, find any new entries that are not already in the config.
    """
    try:
        # Find all config entries not disabled
        config_dom = minidom.parse(config_xml)
        config_entries = infosys_lib.parse_entries(config_dom, skip_missing_ref_id=True, skip_disabled=skip_disabled)
        
    except: 
        print "Error parsing the config file '%s' for entries, exiting the tool." % config_xml
        sys.exit(2)    
        
    # Query the given info system
    if source_type.lower() == 'bdii':
        infosys_entries = infosys_lib.query_bdii(source, vo_name)
            
    elif source_type.lower() == 'ress':
        # Update path with condor 
        condor_path = infosys_lib.parse_condor_path(config_dom)
        os.environ["CONDOR_CONFIG"] = condor_path + "/etc/condor_config"
        condorExe.set_path(condor_path + "/bin", condor_path + "/sbin")
            
        ress_entries = infosys_lib.query_ress(source, vo_name)
        
        # Remove duplicate entries
        infosys_entries = remove_duplicates(ress_entries)
            
    elif source_type.lower() == 'tg':
        infosys_entries = infosys_lib.query_teragrid()
        
    # Compare config entries with what is found in the information system
    new_entries = []
    
    for infosys_id in infosys_entries:
        entry_i = infosys_entries[infosys_id]
        
        found_match = False
        for config_entry in config_entries:
            entry_c = config_entries[config_entry]
            
            # Check if ids match
            if entry_i['ref_id'] == entry_c['ref_id']:
                # Check same source types between config and infosys entries
                # TODO do we need to check source url too?
                if entry_c['source_type'].lower() == source_type.lower():
                    found_match = True # already have this entry
                    break
            else:
                # Check if content matches for other infosys or manual entries
                if entry_i['gatekeeper'] == entry_c['gatekeeper'] and entry_i['gridtype'] == entry_c['gridtype'] and entry_i['rsl'] == entry_c['rsl']:
                    found_match = True # already have this entry
                    # TODO here could add ability to update ref_ids if find additional matching entry
                    # not sure if we want to for ress entries tho?
                    break
            
        if not found_match:
            new_entries.append(infosys_entries[infosys_id])

    return new_entries

def remove_duplicates(infosys_entries):
    """
    Removes duplicate entries found when querying an infosys.  
    """
    new_entries = {}
    site_list = []
    
    for id in infosys_entries.keys():
        entry = infosys_entries[id]
        site_def = [entry['gatekeeper'], entry['gridtype'], entry['rsl']]
        if site_def not in site_list:
            new_entries[id] = entry
            site_list.append(site_def)
    
    return new_entries

if __name__ == "__main__":
    main(sys.argv[1:])
