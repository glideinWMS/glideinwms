#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/creation/lib/cvWConsts.py

 Author:
   Dennis Box dbox@fnal.gov
"""


from __future__ import absolute_import
from __future__ import print_function
import os
import xmlrunner
import unittest2 as unittest

from glideinwms.creation.lib.cvWConsts import get_group_work_dir
from glideinwms.creation.lib.cvWConsts import get_group_name_from_group_work_dir
from glideinwms.creation.lib.cvWConsts import get_group_log_dir
from glideinwms.creation.lib.cvWConsts import get_group_stage_dir
from glideinwms.creation.lib.cvWConsts import get_group_name_from_group_stage_dir
from glideinwms.creation.lib.cvWConsts import get_group_monitor_dir
from glideinwms.creation.lib.cvWConsts import get_group_name_from_group_monitor_dir

#test fixtures defined globall here for convenience
work_dir = 'templates/frontend'
group_name = 'group_1'
group_basedir = 'group_group_1'
group_work_dir = os.path.join('templates/frontend', 'group_group_1')
log_dir = '/var/log'
stage_dir = '/var/stage'
monitor_dir = '/var/monitor'
group_log_dir = os.path.join(log_dir, group_basedir)
group_stage_dir = os.path.join(stage_dir, group_basedir)
group_monitor_dir = os.path.join(monitor_dir, group_basedir)

class TestGetGroupWorkDir(unittest.TestCase):

    def test_get_group_work_dir(self):
        self.assertEqual(group_work_dir, get_group_work_dir(work_dir, group_name))


class TestGetGroupNameFromGroupWorkDir(unittest.TestCase):

    def test_get_group_name_from_group_work_dir(self):
        self.assertEqual(group_name, get_group_name_from_group_work_dir(group_work_dir))
        try:
            get_group_name_from_group_work_dir('/var/log/junk')
        except Exception as err:
            self.assertTrue(isinstance(err, ValueError))


class TestGetGroupLogDir(unittest.TestCase):

    def test_get_group_log_dir(self):
        self.assertEqual(group_log_dir, get_group_log_dir(log_dir, group_name))


class TestGetGroupStageDir(unittest.TestCase):

    def test_get_group_stage_dir(self):
        self.assertEqual(group_stage_dir, get_group_stage_dir(stage_dir, group_name))


class TestGetGroupNameFromGroupStageDir(unittest.TestCase):

    def test_get_group_name_from_group_stage_dir(self):
        self.assertEqual(group_name, get_group_name_from_group_stage_dir(group_stage_dir))
        try:
            get_group_name_from_group_stage_dir('/var/log/junk')
        except Exception as err:
            self.assertTrue(isinstance(err, ValueError))


class TestGetGroupMonitorDir(unittest.TestCase):

    def test_get_group_monitor_dir(self):
        self.assertEqual(group_monitor_dir, get_group_monitor_dir(monitor_dir, group_name))


class TestGetGroupNameFromGroupMonitorDir(unittest.TestCase):

    def test_get_group_name_from_group_monitor_dir(self):
        self.assertEqual(group_name, get_group_name_from_group_monitor_dir(group_monitor_dir))
        try:
            get_group_name_from_group_monitor_dir('/var/log/junk')
        except Exception as err:
            self.assertTrue(isinstance(err, ValueError))

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
