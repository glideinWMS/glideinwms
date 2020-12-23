#!/usr/bin/env python
"""
Project:
    glideinWMS
Purpose:
    unit test for factory/tools/OSG_autoconf.py
Author:
    Marco Mascheroni, marco.mascheroni@cern.ch
"""

from __future__ import absolute_import
from __future__ import print_function

import copy
import xmlrunner
import unittest
#from unittest.mock import patch

try:
    from glideinwms.unittests.unittest_utils import TestImportError
except ImportError as err:
    class TestImportError(Exception):
        pass

try:
    from glideinwms.factory.tools.OSG_autoconf import create_missing_file_internal
except ImportError as err:
    raise TestImportError(str(err))


class TestOSGAutoconf(unittest.TestCase):
    def test_create_missing_file_internal(self):
        # 2 sites, three CEs
        info = \
            {'SITE_NAME': {
                'ce01.sitename.edu': {'DEFAULT_ENTRY': {'gridtype': 'condor',
                    'attrs': {
                        'GLIDEIN_Site': {'value': 'SITE_NAME'},
                        'GLIDEIN_CPUS': {'value': 8},
                        'GLIDEIN_ResourceName': {'value': 'SITE_NAME'},
                        'GLIDEIN_Supported_VOs': {'value': 'OSGVO,DUNE,CMS'},
                        'GLIDEIN_MaxMemMBs': {'value': 16000},
                        'GLIDEIN_Max_Walltime': {'value': 256200},
                    },
                    'submit_attrs': {'+maxMemory': 16000,
                                '+maxWallTime': 4300, '+xcount': 8}}},
                'ce02.sitename.edu': {'DEFAULT_ENTRY': {'gridtype': 'condor',
                    'attrs': {
                        'GLIDEIN_Site': {'value': 'SITE_NAME'},
                        'GLIDEIN_CPUS': {'value': 1},
                        'GLIDEIN_ResourceName': {'value': 'SITE_NAME'},
                        'GLIDEIN_Supported_VOs': {'value': 'CMS'},
                        'GLIDEIN_MaxMemMBs': {'value': 3968},
                        'GLIDEIN_Max_Walltime': {'value': 256200},
                    },
                    'submit_attrs': {'+maxMemory': 3968,
                                '+maxWallTime': 4300, '+xcount': 1}}}},
             'ANOTHER_SITE': {
                'ce01.othersite.edu': {'DEFAULT_ENTRY': {'gridtype': 'condor',
                    'attrs': {
                        'GLIDEIN_Site': {'value': 'OTHER_NAME'},
                        'GLIDEIN_CPUS': {'value': 4},
                        'GLIDEIN_ResourceName': {'value': 'OTHER_NAME'},
                        'GLIDEIN_Supported_VOs': {'value': 'OSGVO,DUNE,CMS'},
                        'GLIDEIN_MaxMemMBs': {'value': 8000},
                        'GLIDEIN_Max_Walltime': {'value': 84600},
                    },
                    'submit_attrs': {'+maxMemory': 8000,
                                '+maxWallTime': 4300, '+xcount': 4}}}}}

        missing_info = {} # Info from the old missing.yml file
        osg_info = copy.deepcopy(info) # Information as in the old OSG.yml file (old=from the previous run)
        whitelist_info = {'ANOTHER_SITE': {'ce01.othersite.edu': {}}} # The operator's override file
        osg_collector_data = copy.deepcopy(info) # Information from the OSG collector. Just fetched.
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # One of the site is now missing from the collector data
        del osg_collector_data['ANOTHER_SITE']
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)['ANOTHER_SITE'], info['ANOTHER_SITE'])

        # Now what happens if it is also missing from the old data?
        del osg_info['ANOTHER_SITE']
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # Now let's pretend it was in the missing yaml
        missing_info['ANOTHER_SITE'] = copy.deepcopy(info['ANOTHER_SITE'])
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)['ANOTHER_SITE'], info['ANOTHER_SITE'])

        # And if it is both in the missing file and the collector (CE is back up)? Missing should be empty.
        osg_collector_data = copy.deepcopy(info) # Information from the OSG collector. Just fetched.
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # Let's test a bit what happens when just a CE is missing
        missing_info = {}
        osg_info = copy.deepcopy(info) # Information as in the old OSG.yml file (old=from the previous run)
        whitelist_info = {'SITE_NAME': {'ce01.sitename.edu': {}}}
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # CE missing from the collector: Restored from old OSG YAML
        del osg_collector_data['SITE_NAME']['ce01.sitename.edu']
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)['SITE_NAME']['ce01.sitename.edu'], info['SITE_NAME']['ce01.sitename.edu'])

        # CE missing from the collector and can't be restored
        del osg_info['SITE_NAME']['ce01.sitename.edu']
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # Now let's pretend it was in the missing yaml
        missing_info.setdefault('SITE_NAME', {})['ce01.sitename.edu'] = copy.deepcopy(info['SITE_NAME']['ce01.sitename.edu'])
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)['SITE_NAME']['ce01.sitename.edu'], info['SITE_NAME']['ce01.sitename.edu'])

        # The WHITELIST YAML file is now containing ce02 as well, which is now missing from the OSG collector
        whitelist_info['SITE_NAME']['ce02.sitename.edu'] = {}
        del osg_collector_data['SITE_NAME']['ce02.sitename.edu']
        # restored from the OSG YAML
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)['SITE_NAME'], info['SITE_NAME'])
        # restored from the missing file
        del osg_info['SITE_NAME']['ce02.sitename.edu']
        missing_info['SITE_NAME']['ce02.sitename.edu'] = copy.deepcopy(info['SITE_NAME']['ce02.sitename.edu'])
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)['SITE_NAME'], info['SITE_NAME'])

        # The following lines need python3
 #       with patch('sys.stdout', new = StringIO()) as fake_out:
 #           self.assertEqual(fake_out.getvalue(), expected_out)


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
