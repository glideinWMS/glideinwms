#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import os
import tempfile
import unittest2 as unittest
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.creation.lib.cvWParamDict import populate_group_descript
from glideinwms.creation.lib.cvWParamDict import apply_group_glexec_policy
from glideinwms.creation.lib.cvWParamDict import apply_group_singularity_policy
from glideinwms.creation.lib.cvWParamDict import apply_multicore_policy
from glideinwms.creation.lib.cvWParamDict import get_pool_list
from glideinwms.creation.lib.cvWParamDict import populate_common_descript
from glideinwms.creation.lib.cvWParamDict import calc_glidein_collectors
from glideinwms.creation.lib.cvWParamDict import calc_glidein_ccbs
from glideinwms.creation.lib.cvWParamDict import populate_main_security
from glideinwms.creation.lib.cvWParamDict import populate_group_security
from glideinwms.creation.lib.cvWParamDict import populate_common_attrs
from glideinwms.creation.lib.cvWParamDict import frontendMainDicts
from glideinwms.creation.lib.cvWParamDict import frontendDicts
from glideinwms.creation.lib.cvWParams import VOFrontendSubParams
from glideinwms.creation.lib.cvWParams import VOFrontendParams
from glideinwms.creation.lib import xslt
from glideinwms.frontend import glideinFrontendLib
FRONTEND_DIR = os.path.dirname(glideinFrontendLib.__file__)
STARTUP_DIR = 'fixtures/frontend/web-base'

ARGV = ["fixtures/frontend/frontend.xml", "fixtures/frontend/frontend.xml"]
USAGE_PREFIX = "reconfig_frontend"


class TestFrontendMainDicts(unittest.TestCase):

    def setUp(self):
        transformed_xmlfile = tempfile.NamedTemporaryFile()
        xml = "fixtures/frontend/frontend.xml"
        transformed_xmlfile.write(
            xslt.xslt_xml(
                old_xmlfile=xml,
                xslt_plugin_dir=None))
        transformed_xmlfile.flush()
        args = ['/usr/sbin/reconfig_frontend', transformed_xmlfile.name]
        self.fe_params = VOFrontendParams(USAGE_PREFIX, STARTUP_DIR, args)
        self.sub_params = VOFrontendSubParams(self.fe_params.data)
        self.fed = frontendMainDicts(
            self.fe_params, 'fixtures/frontend/work-dir')

    def test__init__(self):
        self.assertTrue(isinstance(self.fed, frontendMainDicts))

    def test_populate(self):
        self.fed.populate(self.fe_params)

    def test_reuse(self):
        self.fed.reuse(self.fed)

    def test_populate_common_attrs(self):
        populate_common_attrs(self.fed)

    def test_find_parend_dir(self):
        pd = self.fed.find_parent_dir('fixtures/frontend', 'index.html')
        self.assertEqual(pd, 'fixtures/frontend/web-base/frontend')

    def test_save_monitor(self):
        self.fed.save_monitor()

    @unittest.skip('hmm')
    def test_apply_group_glexec_policy(self):
        apply_group_glexec_policy(
            self.fed.dicts['group_descript'],
            self.sub_params,
            self.params)

    @unittest.skip('hmm')
    def test_apply_group_singularity_policy(self):
        apply_group_singularity_policy(
            self.fed.dicts['group_descript'],
            self.sub_params,
            self.params)

    @unittest.skip('hmm')
    def test_apply_multicore_policy(self):
        apply_multicore_policy(self.fed.dicts['frontend_descript'])

    @unittest.skip('hmm')
    def test_save(self):
        self.fed.save()


class TestFrontendDicts(unittest.TestCase):

    def setUp(self):
        self.fe_params = VOFrontendParams(USAGE_PREFIX, STARTUP_DIR, ARGV)
        self.sub_params = VOFrontendSubParams(self.fe_params.data)
        self.fed = frontendDicts(self.fe_params)

    def test__init__(self):
        self.assertTrue(isinstance(self.fed, frontendDicts))

    def test_populate(self):
        self.fed.populate(self.fe_params)

    @unittest.skip('hmm')
    def test_save(self):
        self.fed.save()


class TestPopulateGroupDescript(unittest.TestCase):
    @unittest.skip('for now')
    def test_populate_group_descript(self):
        self.assertEqual(
            expected,
            populate_group_descript(
                work_dir,
                group_descript_dict,
                sub_name,
                sub_params))
        # assert False TODO: implement your test here


class TestGetPoolList(unittest.TestCase):
    @unittest.skip('for now')
    def test_get_pool_list(self):
        self.assertEqual(expected, get_pool_list(credential))
        # assert False TODO: implement your test here


class TestPopulateCommonDescript(unittest.TestCase):
    @unittest.skip('for now')
    def test_populate_common_descript(self):
        self.assertEqual(
            expected, populate_common_descript(
                descript_dict, params))
        # assert False TODO: implement your test here


class TestCalcGlideinCollectors(unittest.TestCase):
    @unittest.skip('for now')
    def test_calc_glidein_collectors(self):
        self.assertEqual(expected, calc_glidein_collectors(collectors))
        # assert False TODO: implement your test here


class TestCalcGlideinCcbs(unittest.TestCase):
    @unittest.skip('for now')
    def test_calc_glidein_ccbs(self):
        self.assertEqual(expected, calc_glidein_ccbs(collectors))
        # assert False TODO: implement your test here


class TestPopulateMainSecurity(unittest.TestCase):
    @unittest.skip('for now')
    def test_populate_main_security(self):
        self.assertEqual(
            expected, populate_main_security(
                client_security, params))
        # assert False TODO: implement your test here


class TestPopulateGroupSecurity(unittest.TestCase):
    @unittest.skip('for now')
    def test_populate_group_security(self):
        self.assertEqual(
            expected,
            populate_group_security(
                client_security,
                params,
                sub_params))
        # assert False TODO: implement your test here


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
