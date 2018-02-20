#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import os
import unittest2 as unittest
import time
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.lib.timeConversion import getSeconds 
from glideinwms.lib.timeConversion import extractSeconds 
from glideinwms.lib.timeConversion import getHuman 
from glideinwms.lib.timeConversion import extractHuman 
from glideinwms.lib.timeConversion import getISO8601_UTC 
from glideinwms.lib.timeConversion import extractISO8601_UTC 
from glideinwms.lib.timeConversion import getISO8601_Local 
from glideinwms.lib.timeConversion import extractISO8601_Local 
from glideinwms.lib.timeConversion import getRFC2822_UTC 
from glideinwms.lib.timeConversion import extractRFC2822_UTC 
from glideinwms.lib.timeConversion import getRFC2822_Local 
from glideinwms.lib.timeConversion import extractRFC2822_Local 
from glideinwms.lib.timeConversion import get_time_in_format 
from glideinwms.lib.timeConversion import getTZval 


#
#define these globally for convenience
#
now=1518767040
now_dst=1521186240
expected=str(now)
human = 'Fri Feb 16 01:44:00 2018'
iso_utc = '2018-02-16T07:44:00Z'
iso_local = '2018-02-16T01:44:00-06:00'
iso_local_dst = '2018-03-16T01:44:00-06:00'
rfc_2822_utc = 'Fri, 16 Feb 2018 07:44:00 +0000'
rfc_2822_local = 'Fri, 16 Feb 2018 01:44:00 -0600'
tz='US/Central'
tzval = 21600
tzval_dst=18000
tz_wrong='US/Eastern'


class TestGetSeconds(unittest.TestCase):
    #@unittest.skip('for now')
    def test_get_seconds(self):
        self.assertEqual(expected, getSeconds(now))

class TestExtractSeconds(unittest.TestCase):
    #@unittest.skip('for now')
    def test_extract_seconds(self):
        self.assertEqual(now, extractSeconds(expected))

class TestGetHuman(unittest.TestCase):
    #@unittest.skip('for now')
    def test_get_human(self):
        self.assertEqual(human, getHuman(now))

class TestExtractHuman(unittest.TestCase):
    #@unittest.skip('for now')
    def test_extract_human(self):
        self.assertEqual(now, extractHuman(human))

class TestGetISO8601UTC(unittest.TestCase):
    #@unittest.skip('for now')
    def test_get_is_o8601__ut_c(self):
        self.assertEqual(iso_utc, getISO8601_UTC(now))

class TestExtractISO8601UTC(unittest.TestCase):
    #@unittest.skip('for now')
    def test_extract_is_o8601__ut_c(self):
        self.assertEqual(now, extractISO8601_UTC(iso_utc))

class TestGetISO8601Local(unittest.TestCase):
    #@unittest.skip('for now')
    def test_get_is_o8601__local(self):
        os.environ['TZ']=tz
        time.tzset()
        self.assertEqual(iso_local, getISO8601_Local(now))
        os.environ['TZ']=tz_wrong
        time.tzset()
        self.assertNotEqual(iso_local, getISO8601_Local(now))

class TestExtractISO8601Local(unittest.TestCase):
    #@unittest.skip('for now')
    def test_extract_is_o8601__local(self):
        os.environ['TZ']=tz
        time.tzset()
        self.assertEqual(now, extractISO8601_Local(iso_local))
        self.assertEqual(now_dst, extractISO8601_Local(iso_local_dst))

class TestGetRFC2822UTC(unittest.TestCase):
    #@unittest.skip('for now')
    def test_get_rf_c2822__ut_c(self):
        self.assertEqual(rfc_2822_utc, getRFC2822_UTC(now))

class TestExtractRFC2822UTC(unittest.TestCase):
    #@unittest.skip('for now')
    def test_extract_rf_c2822__ut_c(self):
        self.assertEqual(now, extractRFC2822_UTC(rfc_2822_utc))

class TestGetRFC2822Local(unittest.TestCase):
    #@unittest.skip('for now')
    def test_get_rf_c2822__local(self):
        os.environ['TZ']=tz
        time.tzset()
        self.assertEqual(rfc_2822_local, getRFC2822_Local(now))

class TestExtractRFC2822Local(unittest.TestCase):
    #@unittest.skip('for now')
    def test_extract_rf_c2822__local(self):
        self.assertEqual(now, extractRFC2822_Local(rfc_2822_local))

class TestGetTimeInFormat(unittest.TestCase):
    #@unittest.skip('for now')
    def test_get_time_in_format(self):
        os.environ['TZ']=tz
        time.tzset()
        time_format = "%a, %d %b %Y %H:%M:%S -0600"
        self.assertEqual(rfc_2822_local, get_time_in_format(now, time_format))

class TestGetTZval(unittest.TestCase):
    #@unittest.skip('for now')
    def test_get_t_zval(self):
        os.environ['TZ']=tz
        time.tzset()
        self.assertNotEqual(getTZval(now), getTZval(now_dst))
        self.assertEqual(tzval_dst, getTZval(now_dst))
        self.assertEqual(tzval, getTZval(now))
        os.environ['TZ']=tz_wrong
        time.tzset()
        self.assertNotEqual(tzval_dst, getTZval(now_dst))
        self.assertNotEqual(tzval, getTZval(now))

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
