#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner
import os

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.creation.lib.cgWConsts import get_entry_submit_dir 
from glideinwms.creation.lib.cgWConsts import get_entry_name_from_entry_submit_dir 
from glideinwms.creation.lib.cgWConsts import get_entry_log_dir 
from glideinwms.creation.lib.cgWConsts import get_entry_userlog_dir 
from glideinwms.creation.lib.cgWConsts import get_entry_userproxies_dir 
from glideinwms.creation.lib.cgWConsts import get_entry_stage_dir 
from glideinwms.creation.lib.cgWConsts import get_entry_name_from_entry_stage_dir 
from glideinwms.creation.lib.cgWConsts import get_entry_monitor_dir 
from glideinwms.creation.lib.cgWConsts import get_entry_name_from_entry_monitor_dir 

entry_name = 'TEST_SITE_1'
entry_basedir = 'entry_%s' % entry_name
submit_dir = '/var/lib/submit'
entry_submit_dir = os.path.join(submit_dir,entry_basedir)
log_dir = '/var/log'
entry_log_dir = os.path.join(log_dir,entry_basedir)
proxies_dir = '/var/lib/proxies'
entry_proxies_dir = os.path.join(proxies_dir,entry_basedir)
stage_dir = '/var/stage'
entry_stage_dir = os.path.join(stage_dir,entry_basedir)
monitor_dir = '/var/monitor'
entry_monitor_dir = os.path.join(monitor_dir,entry_basedir)

class TestGetEntrySubmitDir(unittest.TestCase):
    def test_get_entry_submit_dir(self):
        self.assertEqual(entry_submit_dir, get_entry_submit_dir(submit_dir, entry_name))

class TestGetEntryNameFromEntrySubmitDir(unittest.TestCase):
    def test_get_entry_name_from_entry_submit_dir(self):
        self.assertEqual(entry_name, get_entry_name_from_entry_submit_dir(entry_submit_dir))
        try:
            get_entry_name_from_entry_submit_dir('/var/log/junk')
        except Exception as err:
            self.assertTrue(isinstance(err,ValueError))

class TestGetEntryLogDir(unittest.TestCase):
    def test_get_entry_log_dir(self):
        self.assertEqual(entry_log_dir, get_entry_log_dir(log_dir, entry_name))

class TestGetEntryUserlogDir(unittest.TestCase):
    def test_get_entry_userlog_dir(self):
        self.assertEqual(entry_log_dir, get_entry_userlog_dir(log_dir, entry_name))

class TestGetEntryUserproxiesDir(unittest.TestCase):
    def test_get_entry_userproxies_dir(self):
        self.assertEqual(entry_proxies_dir, get_entry_userproxies_dir(proxies_dir, entry_name))

class TestGetEntryStageDir(unittest.TestCase):
    def test_get_entry_stage_dir(self):
        self.assertEqual(entry_stage_dir, get_entry_stage_dir(stage_dir, entry_name))

class TestGetEntryNameFromEntryStageDir(unittest.TestCase):
    def test_get_entry_name_from_entry_stage_dir(self):
        self.assertEqual(entry_name, get_entry_name_from_entry_stage_dir(entry_stage_dir))
        try:
            get_entry_name_from_entry_stage_dir('/var/log/junk')
        except Exception as err:
            self.assertTrue(isinstance(err,ValueError))

class TestGetEntryMonitorDir(unittest.TestCase):
    def test_get_entry_monitor_dir(self):
        self.assertEqual(entry_monitor_dir, get_entry_monitor_dir(monitor_dir, entry_name))

class TestGetEntryNameFromEntryMonitorDir(unittest.TestCase):
    def test_get_entry_name_from_entry_monitor_dir(self):
        self.assertEqual(entry_name, get_entry_name_from_entry_monitor_dir(entry_monitor_dir))
        try:
            get_entry_name_from_entry_monitor_dir('/var/log/junk')
        except Exception as err:
            self.assertTrue(isinstance(err,ValueError))

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
