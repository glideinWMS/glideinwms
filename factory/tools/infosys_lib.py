#!/usr/bin/python

"""
Library for the information system comparisons.

"""
from __future__ import print_function

import os
import sys
import getopt 
import datetime
from xml.dom import minidom
import socket
import urllib2
import random
import re
import sys
from copy import deepcopy
STARTUP_DIR = os.path.abspath(sys.path[0])
sys.path.append(os.path.join(STARTUP_DIR, "../../.."))
from glideinwms.lib import ldapMonitor
from glideinwms.lib import condorMonitor
from glideinwms.lib import condorExe


def query_bdii(bdii_source, vo_name=''):
    ''' List all GlueCEUniqueIDs '''

    Bdii = ldapMonitor.BdiiLdap(bdii_source)
    
    # Query the bdii for entry info at the given source 
    if vo_name != '':
        filt = "(&(GlueCEUniqueID=*)(|(GlueCEAccessControlBaseRule=VO:" + vo_name + ")(GlueCEAccessControlBaseRule=VOMS:/" + vo_name + "/Role=pilot)))"
    else:
        filt = "'(GlueCEUniqueID=*)'"

    attrs = 'GlueCEUniqueID ' + \
            'GlueCEStateStatus ' + \
            'GlueCEPolicyMaxObtainableWallClockTime ' + \
            'GlueCECapability '  + \
            'GlueCEInfoContactString ' + \
            'GlueCEName ' + \
            'GlueCEInfoHostName ' + \
            'GlueCEInfoJobManager'

    result = Bdii.runldapquery(filt, attrs)

    ceList = {}
    for x in result:
        try:
            bdii_dn = x[0][0]
            bdii_entry = x[0][1]
            glue_id = bdii_entry['GlueCEUniqueID'][0]
            
            # Default values for an entry
            gridtype = gatekeeper = rsl = ''
            wall_clocktime = 36
            work_dir = '.'
            site_type = 'unknown'
            ce_status = 'unknown'
            
            if 'GlueCEStateStatus' in bdii_entry:
                ce_status = bdii_entry['GlueCEStateStatus'][0]            
                if ce_status == '' or ce_status is None:
                    ce_status = 'unknown'
            
            supported_vos = '' 
            if 'GlueCEAccessControlBaseRule' in bdii_entry:
                vos = bdii_entry['GlueCEAccessControlBaseRule']
                
            if 'Mds-Vo-name' in bdii_entry: 
                site_name = bdii_entry['Mds-Vo-name'][0]  
            else:
                site_name = bdii_entry['GlueCEInfoHostName'][0]
           
            # Time is used in creating the GLIDEIN_Retire_Time and GLIDEIN_Retire_Time_Spread for a entry
            if 'GlueCEPolicyMaxObtainableWallClockTime' in bdii_entry: 
                wall_clocktime = int(bdii_entry['GlueCEPolicyMaxObtainableWallClockTime'][0])
                # Adjust to max of 48 hours or default of 36 hours as needed
                if (wall_clocktime / 60) > 48:
                    wall_clocktime = 48 * 60
                if wall_clocktime == 0:
                    wall_clocktime = 36 * 60
            
            glexec = False
            if 'GlueCECapability' in bdii_entry:
                ceCapabilityList = bdii_entry['GlueCECapability']
                if 'glexec' in ceCapabilityList:
                    glexec = True

            contact_str = glue_id.split(',')[0]
            node, jobmgr_str = contact_str.split('/', 1) 
                        
            # Determine the gridtype, rsl, and jobmanager from the GlueCEUniqueID entry
            try:
                jobmgr_type, jobmgr_lrms, jobmgr_queue = jobmgr_str.split('-', 2)
            except ValueError:
                #print "Skipping bdii entry %s, can't parse format of GlueCEUniqueID" % jobmgr_str
                continue
            
            if jobmgr_type == 'cream':
                gridtype = 'cream'
                gatekeeper = 'https://%s/ce-cream/services/CREAM2 %s %s' % (node, jobmgr_lrms, jobmgr_queue)
                rsl = ''
            elif jobmgr_type == 'nordugrid':
                gridtype = 'nordugrid'
                gatekeeper = node
                rsl = "(queue=%s)(runtimeenvironment=ENV/GLITE)" % jobmgr_queue
            else:
                # TODO are there other grid types/rsl configurations?  what to do for new protocol - define a default?
                # all non-cream and nordugrid types default to gt2?
                gridtype = 'gt2'
                gatekeeper = '%s/%s-%s' % (node, jobmgr_type, jobmgr_lrms)
                if jobmgr_lrms == 'condor':
                    rsl = ''
                else:
                    rsl = '(queue=%s)(jobtype=single)' % jobmgr_queue

            ceEntry = {'site_name' : site_name + '_' + jobmgr_queue,
                'gridtype' : gridtype,
                'gatekeeper' : gatekeeper,
                'rsl' : rsl,
                'wall_clocktime' : wall_clocktime/60,
                'ref_id' : bdii_dn,
                'ce_status' : ce_status,
                'glexec_bin' : 'NONE',
                'work_dir' : work_dir,
                'source' : Bdii.bdii,
                'source_type' : 'BDII',
                'GlueCEUniqueID' : glue_id,
                'supported_vos': supported_vos,
                'site_type' : site_type,
                'glexec' : glexec}

            ceList[bdii_dn] = ceEntry
        
        except KeyError as e:
            # Bad BDII entry for a site.. Keep going
            continue

    ceListKeys = sorted(ceList.keys())
    ceType = siteType(ceListKeys, Bdii)

    # Update work dir and glexec bin according to site type
    for ce in ceListKeys:
        if ce in ceType:
            ceList[ce]['site_type'] = ceType[ce]
            if ceType[ce] == 'OSG':
                ceList[ce]['work_dir'] = 'OSG'
                if ceList[ce]['glexec']:
                    ceList[ce]['glexec_bin'] = 'OSG'
            elif ceType[ce] == 'EGI':
                ceList[ce]['work_dir'] = 'TMPDIR'
                if ceList[ce]['glexec']:
                    ceList[ce]['glexec_bin'] = 'ASK BURT'

    return ceList


def siteType(ceList, Bdii):
   """
   Given a list of CEs, return a dict {ce: site type}
   where site type = OSG, LCG, etc.
   """

   Bdii.generateMaps()
   query = "(GlueSiteUniqueID=*)"
   pout = Bdii.runldapquery(query, 'GlueSiteUniqueID GlueSiteDescription GlueSiteOtherInfo')

   ceType = {}
   siteGridType = {}
   siteInfo = ''

   for x in pout:
       try:
           item = x[0][1]
           site = item['GlueSiteUniqueID'][0]
           siteDescr = item['GlueSiteDescription'][0]
           if 'GlueSiteOtherInfo' in item:
               siteInfo = item['GlueSiteOtherInfo']
           gridType = parseGridType(siteDescr, siteInfo)

           siteGridType[site] = gridType

       except KeyError:
           continue

   for ce in ceList:
       try:
           cluster = Bdii.ce_to_cluster_map[ce]
           site = Bdii.cluster_to_site_map[cluster]

           if site in siteGridType:
               ceType[ce] = siteGridType[site]

       except KeyError as e:
           #print 'KeyError in %s' % ce, e
           continue

   return ceType

def parseGridType(siteDescr, siteInfo):
   ''' Given a GlueSiteDescription and GlueSiteOtherInfo, determine the grid type '''
   ''' https://wiki.egi.eu/wiki/MAN1_How_to_publish_Site_Information '''

   if 'OSG' in siteDescr:
       return 'OSG'

   if 'GRID=NDGF' in siteInfo:
       return 'Nordugrid'

   if 'GRID=EGI' in siteInfo or 'GRID=EGEE' in siteInfo:
       return 'EGI'

   if 'GRID=EELA' in siteInfo:
       return 'EELA'

   if 'GRID=UKNGS' in siteInfo:
       return 'UKNGS'

   if 'GRID=SCOTGRID' in siteInfo:
       return 'SCOTGRID'

   if 'GRID=WLCG' in siteInfo:
       return 'WLCG-Unknown'

   return 'Unknown'


def query_ress(ress_source, vo=''):
    """
    Queries the specified RESS url source for information about the sites.

    Returns dictionary with RESS entries.  An entry is created for each classad (site can be listed multiple times).
    
    Can raise error
    """
    
    # TODO - there are multiple classads for an entry for each cluster/vo/etc.  Currently only the common information in all the classads for 
    # a site is used (gatekeeper, site and queue names) but if VO specific information is included in the future, this will require more 
    # complicated logic for building the entries dictionary
    
    ress_constraint = '(GlueCEInfoContactString=!=UNDEFINED)'
    if vo!='':
        ress_constraint = '(GlueCEInfoContactString=!=UNDEFINED)&&(StringlistMember("VO:%s",GlueCEAccessControlBaseRule))'%vo
    
    ress_ip = socket.gethostbyname(ress_source)

    # Get RESS info
    condor_obj = condorMonitor.CondorStatus(pool_name=ress_source)
    format_list=[('GlueCEInfoContactString', 's'), ('GlueCEName', 's'), ('GlueSiteName', 's'), ('GlueCEInfoJobManager', 's'), ('GlueCEUniqueID', 's'), ('GlueCEPolicyMaxObtainableWallClockTime', 'i'), ('GlueCEStateStatus', 's')]
    condor_data = condor_obj.fetch(constraint=ress_constraint, format_list=format_list)
    
    ress_entries = {}
    
    for condor_id in condor_data.keys():
        # Condor id is the value in the Name attribute of the classad.  The same entry may have multiple Names and therefore classads but each 
        # will have a unique Name/condor_id
        condor_el = condor_data[condor_id]

        # Default values for an entry
        gridtype = gatekeeper = rsl = wall_clocktime = ce_status = ''
        wall_clocktime = 0
        
        gatekeeper_name = condor_el['GlueCEInfoContactString'].encode('utf-8')
        queue_name = condor_el['GlueCEName'].encode('utf-8')
        site_name = condor_el['GlueSiteName'].encode('utf-8')
        
        # Determine rsl by jobmanager
        # OSG only supports gt2 (gt5 in near future?), do not need to create other rsl strings to support other grid types like cream
        if condor_el['GlueCEInfoJobManager'].encode('utf-8') == "condor":
            rsl = ""
        else:
            rsl = '(queue=%s)(jobtype=single)' % queue_name
        
        glue_id = condor_el['GlueCEUniqueID'].encode('utf-8')       
        
        wall_clocktime = int(condor_el['GlueCEPolicyMaxObtainableWallClockTime'])
        # Adjust to max of 48 hours or default of 36 hours as needed
        # This value is given in minutes
        if (wall_clocktime / 60) > 48:
            wall_clocktime = 48 * 60
        if wall_clocktime == 0:
            wall_clocktime = 36 * 60
        
        # TODO what to do with this?  New file of disabled entries?                  
        ce_status = condor_el['GlueCEStateStatus'].encode('utf-8')

        # Because RESS is specific to OSG, can default all entries to these values 
        glexec_bin = "OSG"
        work_dir ='OSG'
           
        # Could not find support for non-gt2 sites so defaulting gridtype to gt2.  Even if there are some sites, the overwhelming
        # majority is gt2.  May need to check GlueCEInfoGRAMVersion when sites start moving to gram5 (does gwms support gt5 yet?)
        gridtype = 'gt2'
        
        entry = {'site_name' : site_name + '_' + queue_name,
                'gridtype' : gridtype,
                'gatekeeper' : gatekeeper_name,
                'rsl' : rsl,
                'wall_clocktime' : wall_clocktime/60,
                'ref_id' : condor_id,
                'ce_status' : ce_status,
                'glexec_bin' : glexec_bin,
                'work_dir' : work_dir,
                'source' : ress_source,
                'source_type' : 'RESS',
                'GlueCEUniqueID' : glue_id}                      
        ress_entries[condor_id] = entry

    return ress_entries 

  
def query_teragrid():
    """
    Queries the TG information system using hardcoded values since this algorithm is specific to the xml retrieved.  There 
    are no VOs in TeraGrid.
    """
    
    # Get list of sites by ResourceID
    tg_infosys_xml = urllib2.urlopen('http://info.teragrid.org/web-apps/xml/ctss-resources-v1/')
    config_dom = minidom.parse(tg_infosys_xml)
    resource_elements = config_dom.getElementsByTagName('ResourceID')
    resource_ids = []
    for resource_element in resource_elements:
        resource_ids.append(resource_element.childNodes[0].nodeValue)     
    
    # Create list of TeraGrid entries
    tg_entries = {}
    for resource_id in resource_ids:
        # Find all the entries for a site
        try:
            resource_xml = urllib2.urlopen('http://info.teragrid.org/web-apps/xml/ctss-services-v1/ResourceID/' + resource_id)
        except:
            print("Skipping bad resource id %s" % resource_id)
            continue
        
        config_dom = minidom.parse(resource_xml)
        service_elements = config_dom.getElementsByTagName('Service')
        
        # Create an entry for each gram5 service
        # TODO validate xml or can just assume the format?
        for service_element in service_elements:
            type_element = service_element.getElementsByTagName('Type')[0]
            if type_element.childNodes[0].nodeValue == "gram5":
                
                gatekeeper = service_element.getElementsByTagName('Endpoint')[0].childNodes[0].nodeValue
                site_name = service_element.getElementsByTagName('ResourceID')[0].childNodes[0].nodeValue + "_" + service_element.getElementsByTagName('Name')[0].childNodes[0].nodeValue
     
                entry = {'site_name' : site_name,
                        'gridtype' : 'gt5',
                        'gatekeeper' : gatekeeper,
                        'rsl' : '(jobtype=single)(count=1)',
                        'wall_clocktime' : 24,
                        'ref_id' : 'ResourceID=' + site_name,
                        'ce_status' : 'production',
                        'glexec_bin' : 'NONE',
                        'work_dir' : 'auto',
                        'source' : 'info.teragrid.org',
                        'source_type' : 'TGIS',
                        'GlueCEUniqueID' : 'N/A'}                  
                                      
                tg_entries[site_name] = entry
            
            else:
                # TODO skipping, need to document somehow?
                pass
            
    return tg_entries

def parse_entries(config_dom, skip_missing_ref_id=True, skip_disabled=True):
    """
    Get dictionaries of entries from the factory config dom.  
    If contains_ref_id = True, only entries with a ref id will be returned. 
    If  skip_disabled = True, only enabled entries will be returned.
    
    Can raise KeyError if the dom has a bad configuration or was incorrectly parsed from the config file.
    """
    
    entries = {}
    entry_elements = config_dom.getElementsByTagName('entry')
    
    if len(entry_elements) == 0:
        raise KeyError, "Error, no entries listed in configuration file."
    
    for entry_element in entry_elements:
        
        if skip_disabled and entry_element.attributes['enabled'].value.encode('utf-8') == 'False':
            continue # skip disabled entries
        
        infosys_ref_elements = entry_element.getElementsByTagName('infosys_ref')
        if skip_missing_ref_id and len(infosys_ref_elements) == 0:
            continue # skip entries without ref_id
        
        entry = {}
        
        entry['name'] = entry_element.attributes['name'].value.encode('utf-8')
        entry['enabled'] = entry_element.attributes['enabled'].value.encode('utf-8')
        entry['gatekeeper'] = entry_element.attributes['gatekeeper'].value.encode('utf-8')
        entry['gridtype'] = entry_element.attributes['gridtype'].value.encode('utf-8')
        entry['work_dir'] = entry_element.attributes['work_dir'].value.encode('utf-8')
                
        if 'rsl' in entry_element.attributes:
            entry['rsl'] = entry_element.attributes["rsl"].value.encode('utf-8')
        else:
            entry['rsl'] = ""
                
        # Get the entry attrs and their values (we don't care about publishing here and ignoring global values)
        glidein_attrs = {}
        attr_elements = entry_element.getElementsByTagName('attr')
        for attr_element in attr_elements:
            name = attr_element.attributes['name'].value.encode('utf-8')
            value = attr_element.attributes['value'].value.encode('utf-8')
            glidein_attrs[name] = value
        entry['glidein_attrs'] = glidein_attrs

        
        # TODO How do we handle multiple infosys ref values?  Which one to choose for which infosys/parsing?
        # Assuming only one ref (if more than one, just uses the first one it finds)
        # We could add some configuration values to the factory config : can add ability to skip
        # entries, which info sys to compare to (or which to choose first), only update certain values, etc.
        if len(infosys_ref_elements) > 0:            
            entry['ref_id'] = infosys_ref_elements[0].attributes["ref"].value.encode('utf-8')
            entry['source'] = infosys_ref_elements[0].attributes["server"].value.encode('utf-8')
            entry['source_type'] = infosys_ref_elements[0].attributes["type"].value.encode('utf-8')
        else:
            entry['ref_id'] = ""
            entry['source'] = ""
            entry['source_type'] = ""       
            
        entries[entry_element.attributes["name"].value.encode('utf-8')] = entry   
    
    return entries


def parse_condor_path(config_dom):
    """
    Get a valid condor path from the factory config dom.
    
    Can raise KeyError if the dom has a bad configuration or was incorrectly parsed from the config file.
    """
    condor_element = config_dom.getElementsByTagName('condor_tarball')[0]
    condor_path = condor_element.attributes['base_dir'].value.encode('utf-8')
    
    return condor_path

def parse_factory_schedds(config_dom):
    """
    Get the list of factory schedds from the factory config dom.
    
    Can raise KeyError if the dom has a bad configuration or was incorrectly parsed from the config file.
    """
    glidein = config_dom.getElementsByTagName('glidein')[0]    
    schedds = glidein.attributes['schedd_name'].value.encode('utf-8').split(',')
    
    return schedds

def parse_info_systems(config_dom):
    """
    Get the list of information systems in the entries from the factory config dom.
    
    Can raise KeyError if the dom has a bad configuration or was incorrectly parsed from the config file.
    """
    infosystems = {}

    infosys_refs = config_dom.getElementsByTagName('infosys_ref')
    for infosys_ref in infosys_refs:
        source = infosys_ref.attributes["server"].value.encode('utf-8')
        source_type = infosys_ref.attributes["type"].value.encode('utf-8')
        infosystems[source] = source_type
        
    return infosystems


def generate_entry_xml(entry, schedd_name):
    """
    Creates an xml string for an entry in the glideinwms entry config xml format. 
    Input is a infosys entry.
    """  
                  
    # Entry wall clock time is given in minutes but the GLIDEIN attrs are provided in secs
    GLIDEIN_Max_Walltime = entry['wall_clocktime'] * 60
    
    # TODO what attributes to include?  What defaults to use for each? 
    # Do we need to add some kind of VO info using the other database? 
    entry_xml = ""         
    if entry['rsl']:            
        entry_xml += "      <entry name=\"%s\" enabled=\"True\" gatekeeper=\"%s\" gridtype=\"%s\" rsl=\"%s\" verbosity=\"std\" work_dir=\"%s\" schedd_name=\"%s\">\n" % ((entry['site_name']), entry['gatekeeper'], entry['gridtype'], entry['rsl'], entry['work_dir'], schedd_name)
    else:
        entry_xml += "      <entry name=\"%s\" enabled=\"True\" gatekeeper=\"%s\" gridtype=\"%s\" verbosity=\"std\" work_dir=\"%s\" schedd_name=\"%s\">\n" % ((entry['site_name']), entry['gatekeeper'], entry['gridtype'], entry['work_dir'], schedd_name)
    entry_xml += "         <config>\n"
    entry_xml += "            <max_jobs held=\"100\" idle=\"400\" running=\"10000\"/>\n"
    entry_xml += "            <release max_per_cycle=\"20\" sleep=\"0.2\"/>\n"
    entry_xml += "            <remove max_per_cycle=\"5\" sleep=\"0.2\"/>\n"
    entry_xml += "            <submit cluster_size=\"10\" max_per_cycle=\"100\" sleep=\"0.2\"/>\n"
    entry_xml += "         </config>\n"
    entry_xml += "         <downtimes/>\n"
    entry_xml += "         <attrs>\n"
    entry_xml += "            <attr name=\"CONDOR_OS\" const=\"True\" glidein_publish=\"False\" job_publish=\"False\" parameter=\"True\" publish=\"False\" type=\"string\" value=\"default\"/>\n"
    entry_xml += "            <attr name=\"GLEXEC_BIN\" const=\"True\" glidein_publish=\"False\" job_publish=\"False\" parameter=\"True\" publish=\"True\" type=\"string\" value=\"%s\"/>\n" % entry['glexec_bin']
    entry_xml += "            <attr name=\"GLIDEIN_Max_Walltime\" const=\"True\" glidein_publish=\"False\" job_publish=\"False\" parameter=\"True\" publish=\"False\" type=\"int\" value=\"%i\"/>\n" % GLIDEIN_Max_Walltime
    entry_xml += "            <attr name=\"USE_CCB\" const=\"True\" glidein_publish=\"True\" job_publish=\"False\" parameter=\"True\" publish=\"True\" type=\"string\" value=\"True\"/>\n"
    entry_xml += "         </attrs>\n"
    entry_xml += "         <files>\n"
    entry_xml += "         </files>\n"
    entry_xml += "         <infosys_refs>\n"
    entry_xml += "            <infosys_ref ref=\"%s\" server=\"%s\" type=\"%s\"/>\n" % (entry['ref_id'], entry['source'], entry['source_type'])
    entry_xml += "         </infosys_refs>\n"
    entry_xml += "         <monitorgroups>\n"
    entry_xml += "         </monitorgroups>\n"
    entry_xml += "      </entry>\n"

    return entry_xml


def format_entry_pair_output(entry_pairs):
    """
    Format entry pairs into an output string
    """
    output = ''
    for entry_pair in entry_pairs:
        config_e = entry_pair[0]
        output += "Config Ref Id : %s\n" % config_e["ref_id"]
        output += "Config entry Name : %s\n" % config_e["name"]
        output += "Config gatekeeper : %s\n" % config_e["gatekeeper"]
        output += "Config rsl : %s\n" % config_e["rsl"]
        output += "Config gridtype : %s\n" % config_e["gridtype"]
                    
        infosys_e = entry_pair[1]                   
        output += "Infosys %s Id : %s\n" % (infosys_e["source_type"], infosys_e["ref_id"])
        output += "Infosys source url: %s\n" % infosys_e["source"]
        output += "Infosys site name : %s\n" % infosys_e["site_name"]
        output += "Infosys gatekeeper : %s\n" % infosys_e["gatekeeper"]
        output += "Infosys rsl : %s\n" % infosys_e["rsl"]
        output += "Infosys gridtype : %s\n" % infosys_e["gridtype"]
        output += "\n"

    return output




