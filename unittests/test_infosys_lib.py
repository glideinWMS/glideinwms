#!/usr/bin/python

"""
Unit tests for the infosys_lib module.
"""
from __future__ import absolute_import

from glideinwms.unittests import unittest_utils

import os
import sys
import re
from xml.dom import minidom
import unittest

from glideinwms.factory.tools.infosys_lib import query_bdii
from glideinwms.factory.tools.infosys_lib import query_ress
from glideinwms.factory.tools.infosys_lib import query_teragrid
from glideinwms.factory.tools.infosys_lib import parse_entries
from glideinwms.factory.tools.infosys_lib import parse_condor_path
from glideinwms.factory.tools.infosys_lib import parse_factory_schedds
from glideinwms.factory.tools.infosys_lib import parse_info_systems
from glideinwms.factory.tools.infosys_lib import generate_entry_xml
from glideinwms.factory.tools.infosys_lib import format_entry_pair_output

from glideinwms.lib import condorExe
from glideinwms.lib import ldapMonitor


class TestInfosysLib(unittest.TestCase):
    """
    Unit tests for the config update tool.
    """
    
    def test_query_bdii(self):
        """
        Test querying the BDII.  
        """       
        # Test that information is retrieved and is populated correctly
        infosys_entries = query_bdii("exp-bdii.cern.ch", "cms")
        self.assertNotEqual(infosys_entries, {})
        keys = list(infosys_entries.keys())
        entry = infosys_entries[keys[0]]
        self.assertTrue(entry['site_name'] != '')
        self.assertTrue(entry['gridtype'] != '')
        self.assertTrue(entry['gatekeeper'] != '')
        self.assertTrue(entry['wall_clocktime'] >= 0)
        self.assertTrue('GlueCEUniqueID' in entry['ref_id'])
        self.assertTrue(entry['ce_status'] != '')
        self.assertTrue(entry['glexec_bin'] != '')
        self.assertTrue(entry['work_dir'] != '')
        self.assertEqual(entry['source'], "exp-bdii.cern.ch")
        self.assertEqual(entry['source_type'], 'BDII')  
        self.assertTrue(entry['GlueCEUniqueID'] != '')   

        # Test bad bidd source
        self.assertRaises(ldapMonitor.ldap.LDAPError, query_bdii, "bad.url", "cms")
        
        # Test bad vo name
        infosys_entries = query_bdii("exp-bdii.cern.ch", "junk_testing_bad_vo_name_that_is_not_valid")
        self.assertEqual(infosys_entries, {})
                
        # Test empty vo name
        infosys_entries = query_bdii("exp-bdii.cern.ch", "")
        self.assertTrue(infosys_entries != {})
        
                
    def test_query_ress(self):
        """
        Test querying RESS
        """  
        # Condor path and config location
        # These will be set correctly as long as the test is run in the same environment
        # as what is needed to run the factory/wms collector
        if "CONDOR_CONFIG" not in os.environ:
            condor_config="/etc/condor/condor_config"
            
        condorExe.init()
        self.assertTrue(condorExe.condor_bin_path != None and condorExe.condor_sbin_path != None)
        condorExe.set_path(condorExe.condor_bin_path, condorExe.condor_sbin_path)
                           
        # Test that information is retrieved and is populated correctly
        infosys_entries = query_ress("osg-ress-1.fnal.gov", "engage")
        self.assertNotEqual(infosys_entries, {})
        keys = list(infosys_entries.keys())
        entry = infosys_entries[keys[0]]
        self.assertTrue(entry['site_name'] != '')
        self.assertTrue(entry['gridtype'] != '')
        self.assertTrue(entry['gatekeeper'] != '')
        self.assertTrue(entry['wall_clocktime'] != 0)
        self.assertTrue(entry['ref_id'] != '')
        self.assertTrue(entry['ce_status'] != '')
        self.assertTrue(entry['glexec_bin'] == 'OSG')
        self.assertTrue(entry['work_dir'] == 'OSG')
        self.assertEqual(entry['source'], "osg-ress-1.fnal.gov")
        self.assertEqual(entry['source_type'], 'RESS') 
        self.assertTrue(entry['GlueCEUniqueID'] != '') 

        # Test bad ress source
        self.assertRaises(Exception, query_ress, "bad.url", "cms")
        
        # Test bad vo name
        infosys_entries = query_ress("osg-ress-1.fnal.gov", "junk_testing_bad_vo_name_that_is_not_valid")
        self.assertEqual(infosys_entries, {})
        
        # Test empty vo name
        infosys_entries = query_ress("osg-ress-1.fnal.gov", "")
        self.assertTrue(infosys_entries != {})
        

    def test_query_teragrid(self):
        """
        Test querying TeraGrid information systems
        """
        
        # Test that information is retrieved and populated (most values are defaults since TG does not publish the info)
        # There is no input to the function since it is specific to the url requested
        infosys_entries = query_teragrid()
        self.assertNotEqual(infosys_entries, {})
        keys = list(infosys_entries.keys())
        entry = infosys_entries[keys[0]]
        self.assertTrue(entry['site_name'] != '')
        self.assertEqual(entry['gridtype'], 'gt5')
        self.assertTrue(entry['gatekeeper'] != '')
        self.assertTrue(entry['wall_clocktime'] != 0)
        self.assertTrue(entry['ref_id'] != '')
        self.assertEqual(entry['ce_status'], 'production')
        self.assertEqual(entry['glexec_bin'], 'NONE')
        self.assertEqual(entry['work_dir'], 'auto')
        self.assertEqual(entry['source'], 'info.teragrid.org')
        self.assertEqual(entry['source_type'], 'TGIS') 
        self.assertEqual(entry['GlueCEUniqueID'], 'N/A') 

       

    def test_parse_entries(self):
        """
        Verify entries are parsed correctly from the factory configuration file.
        """
        
        valid_file = open('valid.xml', 'w')
        valid_file.write('<glidein schedd_name="schedd_glideins1@test.gov,schedd_glideins2@test.fnal.gov">  \
                <entries> \
                    <entry name="valid_entry"  \
                            enabled="True"  gridtype="gt2" verbosity="std" work_dir="OSG"  \
                            gatekeeper="node.fnal.gov/jobmanager-condor"  \
                            rsl="(queue=default)"  \
                            schedd_name="schedd_glideins1@node.fnal.gov">  \
                        <attrs>  \
                            <attr name="CONDOR_ARCH" value="default"/>  \
                            <attr name="GLEXEC_BIN" value="NONE"/>  \
                            <attr name="GLIDEIN_Site" value="VE1"/>  \
                        </attrs>  \
                        <infosys_refs/>  \
                    </entry>  \
                    <entry name="valid_entry2"  \
                            enabled="False" gridtype="cream" verbosity="std" work_dir="."  \
                            gatekeeper="node2.fnal.gov/jobmanager-condor"  \
                            schedd_name="schedd_glideins2@node.fnal.gov">  \
                        <infosys_refs>  \
                            <infosys_ref ref="GlueCEUniqueID=node.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid"  \
                            server="exp-bdii.cern.ch" type="BDII"/>  \
                        </infosys_refs>  \
                    </entry>  \
                </entries>  \
                <condor_tarball arch="default" base_dir="/opt/glidecondor" os="default"  \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        valid_file.close()
        config_dom = minidom.parse('valid.xml')
        
        # Test valid entries - get all
        entries = parse_entries(config_dom, skip_missing_ref_id=False, skip_disabled=False)
        os.remove('valid.xml')
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries['valid_entry']['name'], 'valid_entry')
        self.assertEqual(entries['valid_entry']['enabled'], 'True')
        self.assertEqual(entries['valid_entry']['gatekeeper'], 'node.fnal.gov/jobmanager-condor')
        self.assertEqual(entries['valid_entry']['gridtype'], 'gt2')
        self.assertEqual(entries['valid_entry']['work_dir'], 'OSG')
        self.assertEqual(entries['valid_entry']['source'], '')
        self.assertEqual(entries['valid_entry']['source_type'], '')
        self.assertEqual(entries['valid_entry']['glidein_attrs'], {'CONDOR_ARCH':'default', 'GLEXEC_BIN':'NONE', 'GLIDEIN_Site':'VE1'})
        
        self.assertEqual(entries['valid_entry2']['name'], 'valid_entry2')
        self.assertEqual(entries['valid_entry2']['enabled'], 'False')
        self.assertEqual(entries['valid_entry2']['gatekeeper'], 'node2.fnal.gov/jobmanager-condor')
        self.assertEqual(entries['valid_entry2']['gridtype'], 'cream')
        self.assertEqual(entries['valid_entry2']['work_dir'], '.')
        self.assertEqual(entries['valid_entry2']['source'], 'exp-bdii.cern.ch')
        self.assertEqual(entries['valid_entry2']['source_type'], 'BDII')
        self.assertEqual(entries['valid_entry2']['glidein_attrs'], {})
        
        # Test with and without rsl
        self.assertEqual(entries['valid_entry']['rsl'], '(queue=default)')
        self.assertEqual(entries['valid_entry2']['rsl'], '')        
        
        # Test with ref id and without ref id
        self.assertEqual(entries['valid_entry']['ref_id'], '')
        self.assertEqual(entries['valid_entry2']['ref_id'], 'GlueCEUniqueID=node.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid')        
        
        # Test skip missing ref id
        missing_ref_id_entries = parse_entries(config_dom, skip_missing_ref_id=True, skip_disabled=False)
        self.assertEqual(len(missing_ref_id_entries), 1)
        
        # Test skip disabled
        disabled_entries = parse_entries(config_dom, skip_missing_ref_id=False, skip_disabled=True)
        self.assertEqual(len(disabled_entries), 1)    
        
        # Test skip disabled and missing ref id
        disabled_entries = parse_entries(config_dom, skip_missing_ref_id=True, skip_disabled=True)
        self.assertEqual(len(disabled_entries), 0)        
        
        # Test invalid entry (missing gatekeeper string)
        invalid_file = open('invalid.xml', 'w')
        invalid_file.write('<glidein schedd_name="schedd_glideins1@test.gov">  \
                <entries>  \
                    <entry name="valid_entry"  \
                            enabled="True"  \
                            gridtype="gt2"  \
                            schedd_name="schedd_glideins1@node.fnal.gov"  \
                            verbosity="std"  \
                            work_dir=".">  \
                        <infosys_refs>  \
                        </infosys_refs>  \
                    </entry>  \
                </entries>  \
                <condor_tarball arch="default" base_dir="/opt/glidecondor" os="default"   \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        invalid_file.close()
        config_dom = minidom.parse('invalid.xml')
        self.assertRaises(KeyError, parse_entries, config_dom, skip_missing_ref_id=False, skip_disabled=False)
        os.remove('invalid.xml')
        
        # Test missing entry  
        missing_entry_file = open('missing_entry.xml', 'w')
        missing_entry_file.write('<glidein schedd_name="schedd_glideins1@test.gov">  \
                <entries>  \
                </entries>  \
                <condor_tarball arch="default" base_dir="/opt/glidecondor" os="default"   \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        missing_entry_file.close()
        config_dom = minidom.parse('missing_entry.xml')
        self.assertRaises(KeyError, parse_entries, config_dom, skip_missing_ref_id=False, skip_disabled=False)
        os.remove('missing_entry.xml')     
                    
        # Test with multiple ref ids (only uses first ref id, for now)
        with_ref_ids_file = open('with_ref_ids.xml', 'w')
        with_ref_ids_file.write('<glidein schedd_name="schedd_glideins1@test.gov">  \
                <entries> \
                    <entry name="valid_entry"  \
                            enabled="True"  \
                            gatekeeper="node.fnal.gov/jobmanager-condor"  \
                            gridtype="gt2"  \
                            schedd_name="schedd_glideins1@node.fnal.gov"  \
                            verbosity="std"  \
                            work_dir=".">  \
                        <infosys_refs>  \
                            <infosys_ref ref="GlueCEUniqueID=node.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid" server="exp-bdii.cern.ch" type="BDII"/>  \
                            <infosys_ref ref="GlueCEUniqueID=node2.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid" server="exp-bdii.cern.ch" type="BDII"/>  \
                        </infosys_refs>  \
                    </entry>  \
                </entries>  \
                <condor_tarball arch="default" base_dir="/opt/glidecondor" os="default"  \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        with_ref_ids_file.close()
        config_dom = minidom.parse('with_ref_ids.xml')
        entries = parse_entries(config_dom)
        self.assertEqual(entries['valid_entry']['ref_id'], 'GlueCEUniqueID=node.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid')
        os.remove('with_ref_ids.xml')  
         
       
    def test_parse_condor_path(self):
        """
        Test that a valid condor path can be found in the factory config dom.
        """

        # Test valid entries 
        valid_file = open('valid.xml', 'w')
        valid_file.write('<glidein schedd_name="schedd_glideins1@test.gov,schedd_glideins2@test.fnal.gov">  \
                <entries> \
                    <entry name="valid_entry"  \
                            enabled="True"  \
                            gatekeeper="node.fnal.gov/jobmanager-condor"  \
                            gridtype="gt2"  \
                            rsl="(queue=default)"  \
                            schedd_name="schedd_glideins1@node.fnal.gov"  \
                            verbosity="std"  \
                            work_dir="OSG">  \
                        <attrs>  \
                        </attrs>  \
                        <infosys_refs>  \
                        </infosys_refs>  \
                    </entry>  \
                </entries>  \
                <condor_tarball arch="default" base_dir="/opt/glidecondor" os="default"  \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        valid_file.close()
        config_dom = minidom.parse('valid.xml')
        condor_path = parse_condor_path(config_dom)        
        self.assertEqual(condor_path, "/opt/glidecondor")
        os.remove('valid.xml')
               
        # Test missing condor path
        invalid_condor_file = open('invalid_condor.xml', 'w')
        invalid_condor_file.write('<glidein schedd_name="schedd_glideins1@test.gov">  \
                <entries>  \
                    <entry name="valid_entry"  \
                            enabled="True"  \
                            gridtype="gt2"  \
                            schedd_name="schedd_glideins1@node.fnal.gov"  \
                            verbosity="std"  \
                            work_dir=".">  \
                        <infosys_refs>  \
                        </infosys_refs>  \
                    </entry>  \
                </entries>  \
                <condor_tarball arch="default" os="default"   \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        invalid_condor_file.close()
        config_dom = minidom.parse('invalid_condor.xml')
        self.assertRaises(KeyError, parse_condor_path, config_dom)
        os.remove('invalid_condor.xml')

    def test_parse_factory_schedds(self):
        """
        Verify factory config dom contains a list of schedds
        """
        # Test valid entries 
        valid_file = open('valid.xml', 'w')
        valid_file.write('<glidein schedd_name="schedd_glideins1@test.gov,schedd_glideins2@test.fnal.gov">  \
                <entries> \
                    <entry name="valid_entry"  \
                            enabled="True"  \
                            gatekeeper="node.fnal.gov/jobmanager-condor"  \
                            gridtype="gt2"  \
                            rsl="(queue=default)"  \
                            schedd_name="schedd_glideins1@node.fnal.gov"  \
                            verbosity="std"  \
                            work_dir="OSG">  \
                        <attrs>  \
                        </attrs>  \
                        <infosys_refs>  \
                        </infosys_refs>  \
                    </entry>  \
                </entries>  \
                <condor_tarball arch="default" base_dir="/opt/glidecondor" os="default"  \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        valid_file.close()
        config_dom = minidom.parse('valid.xml')
        schedds = parse_factory_schedds(config_dom)
        
        self.assertEqual(len(schedds), 2)
        self.assertEqual(schedds, ['schedd_glideins1@test.gov', 'schedd_glideins2@test.fnal.gov'])
        os.remove('valid.xml')       

        # Test missing schedd name
        missing_schedds_file = open('missing_schedds.xml', 'w')
        missing_schedds_file.write('<glidein>  \
                <entries> \
                    <entry name="valid_entry"  \
                            enabled="True"  \
                            gatekeeper="node.fnal.gov/jobmanager-condor"  \
                            gridtype="gt2"  \
                            schedd_name="schedd_glideins1@node.fnal.gov"  \
                            verbosity="std"  \
                            work_dir=".">  \
                        <infosys_refs>  \
                            <infosys_ref ref="GlueCEUniqueID=node.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid" server="exp-bdii.cern.ch" type="BDII"/>  \
                        </infosys_refs>  \
                    </entry>  \
                </entries>  \
                <condor_tarball arch="default" base_dir="/opt/glidecondor" os="default"  \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        missing_schedds_file.close()
        config_dom = minidom.parse('missing_schedds.xml')
        self.assertRaises(KeyError, parse_factory_schedds, config_dom)
        os.remove('missing_schedds.xml') 
        
    
    def test_parse_info_systems(self):
        """
        Get a list of information systems listed in the entries for comparison
        """    
        # Test valid entries 
        valid_file = open('valid.xml', 'w')
        valid_file.write('<glidein schedd_name="schedd_glideins1@test.gov,schedd_glideins2@test.fnal.gov">  \
                <entries> \
                    <entry name="valid_entry"  \
                            enabled="True"  \
                            gatekeeper="node.fnal.gov/jobmanager-condor"  \
                            gridtype="gt2"  \
                            rsl="(queue=default)"  \
                            schedd_name="schedd_glideins1@node.fnal.gov"  \
                            verbosity="std"  \
                            work_dir="OSG">  \
                        <attrs>  \
                            <attr name="CONDOR_ARCH" value="default"/>  \
                            <attr name="GLEXEC_BIN" value="NONE"/>  \
                            <attr name="GLIDEIN_Site" value="VE1"/>  \
                        </attrs>  \
                        <infosys_refs>  \
                        </infosys_refs>  \
                    </entry>  \
                    <entry name="valid_entry2"  \
                            enabled="True"  \
                            gatekeeper="node2.fnal.gov/jobmanager-condor"  \
                            gridtype="cream"  \
                            schedd_name="schedd_glideins2@node.fnal.gov"  \
                            verbosity="std"  \
                            work_dir=".">  \
                        <infosys_refs>  \
                            <infosys_ref ref="GlueCEUniqueID=node.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid"  \
                            server="exp-bdii.cern.ch" type="BDII"/>  \
                        </infosys_refs>  \
                    </entry>  \
                </entries>  \
                <condor_tarball arch="default" base_dir="/opt/glidecondor" os="default"  \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        valid_file.close()
        config_dom = minidom.parse('valid.xml')
        infosystems = parse_info_systems(config_dom)
        self.assertEqual(infosystems, {'exp-bdii.cern.ch' : 'BDII'})  
        os.remove('valid.xml')
        
        # Test no info systems found
        valid_file = open('missing_infosys.xml', 'w')
        valid_file.write('<glidein schedd_name="schedd_glideins1@test.gov,schedd_glideins2@test.fnal.gov">  \
                <entries> \
                    <entry name="valid_entry"  \
                            enabled="True"  \
                            gatekeeper="node.fnal.gov/jobmanager-condor"  \
                            gridtype="gt2"  \
                            rsl="(queue=default)"  \
                            schedd_name="schedd_glideins1@node.fnal.gov"  \
                            verbosity="std"  \
                            work_dir="OSG">  \
                        <attrs>  \
                        </attrs>  \
                        <infosys_refs>  \
                        </infosys_refs>  \
                    </entry>  \
                </entries>  \
                <condor_tarball arch="default" base_dir="/opt/glidecondor" os="default"  \
                            tar_file="/var/www/html/glidefactory/stage/glidein_v2plus/condor.tgz" version="default"/>  \
            </glidein>')
        valid_file.close()
        config_dom = minidom.parse('missing_infosys.xml')
        infosystems = parse_info_systems(config_dom)
        self.assertEqual(infosystems, {})  
        os.remove('missing_infosys.xml')
              
      
    def test_generate_entry_xml(self):
        """
        Verify correct formatted xml string is generated.
        """
        
        # Test full xml correctly created
        entry = {'site_name' : 'has_rsl',
                         'gridtype' : 'cream',
                         'gatekeeper' : 'node2.fnal.gov/jobmanager-condor',
                         'rsl' : '(queue=default)',
                         'wall_clocktime' : 24,
                         'ref_id' : 'GlueCEUniqueID=has_rsl.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid',
                         'ce_status' : 'cestatus',
                         'glexec_bin' : 'NONE',
                         'work_dir' : 'OSG',
                         'source' : 'exp-bdii.cern.ch',
                         'source_type' : 'BDII'}
        schedd_name = 'schedd_glideins1@test.gov'
        expected = '\
      <entry name="has_rsl" enabled="True" gatekeeper="node2.fnal.gov/jobmanager-condor" gridtype="cream" rsl="(queue=default)" verbosity="std" work_dir="OSG" schedd_name="schedd_glideins1@test.gov">\n\
         <config>\n\
            <max_jobs held="100" idle="400" running="10000"/>\n\
            <release max_per_cycle="20" sleep="0.2"/>\n\
            <remove max_per_cycle="5" sleep="0.2"/>\n\
            <submit cluster_size="10" max_per_cycle="100" sleep="0.2"/>\n\
         </config>\n\
         <attrs>\n\
            <attr name="CONDOR_OS" const="True" glidein_publish="False" job_publish="False" parameter="True" publish="False" type="string" value="default"/>\n\
            <attr name="GLEXEC_BIN" const="True" glidein_publish="False" job_publish="False" parameter="True" publish="True" type="string" value="NONE"/>\n\
            <attr name="GLIDEIN_Max_Walltime" const="True" glidein_publish="False" job_publish="False" parameter="True" publish="False" type="int" value="1440"/>\n\
            <attr name="USE_CCB" const="True" glidein_publish="True" job_publish="False" parameter="True" publish="True" type="string" value="True"/>\n\
         </attrs>\n\
         <files>\n\
         </files>\n\
         <infosys_refs>\n\
            <infosys_ref ref="GlueCEUniqueID=has_rsl.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid" server="exp-bdii.cern.ch" type="BDII"/>\n\
         </infosys_refs>\n\
         <monitorgroups>\n\
         </monitorgroups>\n\
      </entry>\n'
        entry_xml = generate_entry_xml(entry, schedd_name)
        self.assertEqual(entry_xml, expected)
        
        # Test that correct xml is created with rsl
        has_rsl_entry = {'site_name' : 'has_rsl',
                         'gridtype' : 'cream',
                         'gatekeeper' : 'node2.fnal.gov/jobmanager-condor',
                         'rsl' : '(queue=default)',
                         'wall_clocktime' : 100,
                         'ref_id' : 'GlueCEUniqueID=has_rsl.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid',
                         'ce_status' : 'cestatus',
                         'glexec_bin' : 'NONE',
                         'work_dir' : 'OSG',
                         'source' : 'exp-bdii.cern.ch',
                         'source_type' : 'BDII'}
        has_rsl_xml_expected = '<entry name="has_rsl" enabled="True" gatekeeper="node2.fnal.gov/jobmanager-condor" gridtype="cream" rsl="(queue=default)" verbosity="std" work_dir="OSG" schedd_name="schedd_glideins1@test.gov">'
        has_rsl_xml = generate_entry_xml(has_rsl_entry, schedd_name)
        self.assertTrue(has_rsl_xml_expected in has_rsl_xml)
        
        # Test that correct xml is created without rsl
        without_rsl_entry = {'site_name' : 'without_rsl',
                         'gridtype' : 'cream',
                         'gatekeeper' : 'node2.fnal.gov/jobmanager-condor',
                         'rsl' : '',
                         'wall_clocktime' : 100,
                         'ref_id' : 'GlueCEUniqueID=without_rsl.fnal.gov:2119/jobmanager-condor_default,Mds-Vo-name=TEST,Mds-Vo-name=local,o=grid',
                         'ce_status' : 'cestatus',
                         'glexec_bin' : 'NONE',
                         'work_dir' : 'OSG',
                         'source' : 'exp-bdii.cern.ch',
                         'source_type' : 'BDII'}
        without_rsl_xml_expected = '<entry name="without_rsl" enabled="True" gatekeeper="node2.fnal.gov/jobmanager-condor" gridtype="cream" verbosity="std" work_dir="OSG" schedd_name="schedd_glideins1@test.gov">'
        without_rsl_xml = generate_entry_xml(without_rsl_entry, schedd_name)
        self.assertTrue(without_rsl_xml_expected in without_rsl_xml)

    def test_format_entry_pair_output(self):
        """
        Test formatting
        """
        
        config_entry = {'name' : 'config_entry',
                         'gridtype' : 'gt2',
                         'gatekeeper' : 'node1.fnal.gov/jobmanager-condor',
                         'rsl' : '(queue=default)',
                         'wall_clocktime' : 24,
                         'ref_id' : 'GlueCEUniqueID=config_entry.fnal.gov:2119/jobmanager-condor_default',
                         'ce_status' : 'cestatus',
                         'glexec_bin' : 'NONE',
                         'work_dir' : 'OSG',
                         'source' : 'exp-bdii.cern.ch',
                         'source_type' : 'BDII'}
        infosys_entry = {'site_name' : 'infosys_entry',
                         'gridtype' : 'cream',
                         'gatekeeper' : 'node2.fnal.gov/jobmanager-condor',
                         'rsl' : '(queue=default)',
                         'wall_clocktime' : 24,
                         'ref_id' : 'GlueCEUniqueID=infosys_entry.fnal.gov:2119/jobmanager-condor_default',
                         'ce_status' : 'cestatus',
                         'glexec_bin' : 'NONE',
                         'work_dir' : 'OSG',
                         'source' : 'exp-bdii.cern.ch',
                         'source_type' : 'BDII'}
        entry_pairs = [[config_entry, infosys_entry]]
        output = format_entry_pair_output(entry_pairs)
        expected = "Config Ref Id : GlueCEUniqueID=config_entry.fnal.gov:2119/jobmanager-condor_default\n" \
                    "Config entry Name : config_entry\n" \
                    "Config gatekeeper : node1.fnal.gov/jobmanager-condor\n" \
                    "Config rsl : (queue=default)\n" \
                    "Config gridtype : gt2\n" \
                    "Infosys BDII Id : GlueCEUniqueID=infosys_entry.fnal.gov:2119/jobmanager-condor_default\n" \
                    "Infosys source url: exp-bdii.cern.ch\n" \
                    "Infosys site name : infosys_entry\n" \
                    "Infosys gatekeeper : node2.fnal.gov/jobmanager-condor\n" \
                    "Infosys rsl : (queue=default)\n" \
                    "Infosys gridtype : cream\n\n"
        self.assertEqual(output, expected)


def main():
    return unittest_utils.runTest(TestInfosysLib)
        
if __name__ == "__main__":
    sys.exit(main())
