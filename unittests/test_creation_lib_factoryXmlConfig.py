#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.creation.lib.factoryXmlConfig import FactAttrElement 
from glideinwms.creation.lib.factoryXmlConfig import FactFileElement 
from glideinwms.creation.lib.factoryXmlConfig import CondTarElement 
from glideinwms.creation.lib.factoryXmlConfig import FrontendElement 
from glideinwms.creation.lib.factoryXmlConfig import EntryElement 
from glideinwms.creation.lib.factoryXmlConfig import EntrySetElement 
from glideinwms.creation.lib.factoryXmlConfig import Config 
from glideinwms.creation.lib.factoryXmlConfig import parse 

XML='fixtures/factory/glideinWMS.xml'
XML_ENTRY='fixtures/factory/config.d/Dev_Sites.xml'

class TestFactAttrElement(unittest.TestCase):

    def setUp(self):
        self.conf = parse(XML)
        self.attr_el_list = self.conf.get_child_list(u'attrs')

    def test_validate(self):
        for fact_attr_element in self.attr_el_list:
            fact_attr_element.validate()

class TestFactFileElement(unittest.TestCase):
    
    def setUp(self):
        self.conf = parse(XML)
        self.files = self.conf.get_child_list(u'files')

    def test_validate(self):
        for fact_file_element in self.files:
            fact_file_element.validate()

class TestCondTarElement(unittest.TestCase):
    
    def setUp(self):
        self.conf = parse(XML)
        self.ctl = self.conf.get_child_list(u'condor_tarballs')

    def test_validate(self):
        for cte in self.ctl:
            cte.validate()
            self.assertTrue(u'arch' in cte)
            self.assertTrue(u'version' in cte)
            self.assertTrue(u'os' in cte)
            self.assertTrue(u'base_dir' in cte or u'tar_file' in cte)
            del cte[u'base_dir']
            try:
                cte.validate()
            except RuntimeError as err:
                pass

class TestFrontendElement(unittest.TestCase):

    def setUp(self):
        self.conf = parse(XML)
        self.sec = self.conf.get_child(u'security')
        self.frontends = self.sec.get_child_list(u'frontends')

    def test_validate(self):
        for frontend_element in self.frontends:
            frontend_element.validate()
            self.assertTrue(u'name' in frontend_element)
            self.assertTrue(u'identity' in frontend_element)

class TestEntryElement(unittest.TestCase):

    def setUp(self):
        self.conf = parse(XML)
        self.eel = self.conf.get_child_list('entries')

    def test_getName(self):
        for entry_element in self.eel:
            self.assertNotEqual('',entry_element.getName())
            self.assertNotEqual(None,entry_element.getName())

    def test_validate(self):
        for entry_element in self.eel:
            entry_element.validate()
            self.assertTrue(u'gridtype' in entry_element)
            self.assertTrue(u'gatekeeper' in entry_element)
            self.assertTrue(u'auth_method' in entry_element)
            self.assertTrue(u'enabled' in entry_element)

    def test_validate_sub_elements(self):
        for entry_element in self.eel:
            entry_element.validate_sub_elements()

class TestEntrySetElement(unittest.TestCase):
    
    def setUp(self):
        self.conf = parse(XML)
        self.esl = self.conf.get_child_list('entry_sets')
        self.assertTrue(len(self.esl) > 0)

    def test_validate(self):
        for entry_set_element in self.esl:
            entry_set_element.validate()

class TestConfig(unittest.TestCase):

    def setUp(self):
        self.config = parse(XML)

    def test___init__(self):
        self.assertTrue(isinstance(self.config, Config))

    def test_get_client_log_dirs(self):
        dirs = self.config.get_client_log_dirs()
        self.assertTrue(isinstance(dirs, dict))

    def test_get_client_proxy_dirs(self):
        dirs = self.config.get_client_proxy_dirs()
        self.assertTrue(isinstance(dirs, dict))

    def test_get_entries(self):
        entries = self.config.get_entries()
        self.assertTrue(isinstance(entries, list))

    def test_get_log_dir(self):
        log_dir = self.config.get_log_dir()
        self.assertEqual(u'/var/log/gwms-factory/server',log_dir)

    def test_get_monitor_dir(self):
        monitor_dir = self.config.get_monitor_dir()
        self.assertEqual(u'/var/lib/gwms-factory/web-area/monitor',monitor_dir)

    def test_get_stage_dir(self):
        stage_dir = self.config.get_stage_dir()
        self.assertEqual(u'/var/lib/gwms-factory/web-area/stage',stage_dir)

    def test_get_submit_dir(self):
        submit_dir = self.config.get_submit_dir()
        self.assertEqual(u'/var/lib/gwms-factory/work-dir',submit_dir)

    def test_get_web_url(self):
        url = self.config.get_web_url()
        self.assertEqual(u'http://fermicloud380.fnal.gov/factory/stage',url)

    def test_set_client_log_dirs(self):
        self.config.set_client_log_dirs()

    def test_set_client_proxy_dirs(self):
        self.config.set_client_proxy_dirs()

    def test_set_log_dir(self):
        self.config.set_log_dir()

    def test_set_monitor_dir(self):
        self.config.set_monitor_dir()

    def test_set_stage_dir(self):
        self.config.set_stage_dir()

    def test_set_submit_dir(self):
        self.config.set_submit_dir()

    def test_set_web_url(self):
        self.config.set_web_url()

    def test_validate(self):
        self.config.validate()

class TestParse(unittest.TestCase):
    def test_parse(self):
        conf = parse(XML)
        try:
            conf2 = parse(XML_ENTRY)
        except RuntimeError as err:
            pass

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
