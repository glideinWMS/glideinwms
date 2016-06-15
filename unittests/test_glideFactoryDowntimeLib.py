#!/usr/bin/env python
import os
import sys
import shutil
import tempfile
import tarfile
import unittest2 as unittest
import time
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from unittest_utils import runTest
from unittest_utils import create_temp_file
from unittest_utils import create_random_string
from unittest_utils import FakeLogger

from glideinwms.lib import condorMonitor
from glideinwms.factory import glideFactoryDowntimeLib
from glideinwms.frontend.glideinFrontendInterface import Credential
from glideinwms.lib import logSupport

class TestDowntimes(unittest.TestCase):
    """
    Test the downtimes library
    """
    def setUp(self):
        self.file_loc="/tmp/downtimes.txt"
        self.downtime=glideFactoryDowntimeLib.DowntimeFile(self.file_loc)
        pass

    def tearDown(self):
        os.remove(self.file_loc)
        pass

    def test_downtimesfile(self):
        now=long(time.time())
        self.downtime.startDowntime(entry="All",comment="unittest downtime",create_if_empty=True)
        self.assertTrue(self.downtime.checkDowntime(entry="All",check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="James",check_time=None))
        #Test downtime comments
        self.assertEquals(self.downtime.downtime_comment,"unittest downtime")
        self.downtime.endDowntime(entry="All",comment="end unittest downtime")
  
        # Use now+1 since we just ended the downtime
        # The second counter may not have updated
        self.assertFalse(self.downtime.checkDowntime(entry="All",check_time=now+1))

    def test_setperiodwithendtime(self):
        now=long(time.time())
        self.downtime.startDowntime(start_time=now-60,end_time=now+3600,entry="All",frontend="All",security_class="All",comment="unittest downtime",create_if_empty=True)
        self.assertTrue(self.downtime.checkDowntime(entry="All",check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="James",check_time=None))
        self.downtime.endDowntime(entry="All",comment="end unittest downtime")
        self.assertFalse(self.downtime.checkDowntime(entry="All",check_time=now+1))
    
    def test_entryonlydowntime(self):
        now=long(time.time())
        self.downtime.startDowntime(start_time=now-60,end_time=now+3600,entry="DougEntry",frontend="All",security_class="All",comment="unittest downtime",create_if_empty=True)
        self.assertFalse(self.downtime.checkDowntime(entry="All",check_time=None))
        self.assertFalse(self.downtime.checkDowntime(entry="James",check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="DougEntry",check_time=None))
        self.downtime.endDowntime(entry="All",comment="end unittest downtime")
        self.assertFalse(self.downtime.checkDowntime(entry="All",check_time=now+1))
        self.assertFalse(self.downtime.checkDowntime(entry="DougEntry",check_time=now+1))


    def test_setdelayedperiod(self):
        now=long(time.time())
        self.downtime.startDowntime(start_time=now+7200,end_time=now+10800,entry="All",frontend="All",security_class="All",comment="unittest delayed downtime",create_if_empty=True)
        self.assertFalse(self.downtime.checkDowntime(entry="All",check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="All",check_time=now+9600))
        self.downtime.endDowntime(entry="All",comment="end unittest downtime")
        self.assertFalse(self.downtime.checkDowntime(entry="All",check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="All",check_time=now+9600))
    
    def test_setfrontendsecclass(self):
        now=long(time.time())
        self.downtime.startDowntime(start_time=now-7200,end_time=now+10800,entry="TestEntry",frontend="SampleFrontend",security_class="SecClass",comment="unittest frontend secclass",create_if_empty=True)
        self.assertFalse(self.downtime.checkDowntime(entry="All",check_time=None))
        self.assertFalse(self.downtime.checkDowntime(entry="factory",check_time=None))
        self.assertFalse(self.downtime.checkDowntime(entry="TestEntry",check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="TestEntry",frontend="SampleFrontend",security_class="SecClass",check_time=now+9600))
        self.assertFalse(self.downtime.checkDowntime(entry="TestEntry",frontend="OtherFrontend",security_class="SecClass",check_time=now+9600))
        self.assertFalse(self.downtime.checkDowntime(entry="TestEntry",frontend="OtherFrontend",security_class="OtherClass",check_time=now+9600))
        self.assertFalse(self.downtime.checkDowntime(entry="TestEntry",frontend="SampleFrontend",security_class="OtherClass",check_time=now+9600))
        self.downtime.endDowntime(entry="All",comment="end unittest downtime")
        self.assertFalse(self.downtime.checkDowntime(entry="TestEntry",frontend="SampleFrontend",security_class="SecClass",check_time=now+9600))

  

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
