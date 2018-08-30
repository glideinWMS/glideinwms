#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/creation/lib/cgWParams.py

 Author:
   Dennis Box dbox@fnal.gov
"""


from __future__ import absolute_import
from __future__ import print_function
import tempfile
import copy
import os
import xmlrunner
import unittest2 as unittest

from glideinwms.creation.lib.cgWParams import GlideinParams
# from glideinwms.creation.lib.cgWParams import find_condor_base_dir
from glideinwms.creation.lib.cWParams import Params

# global definitions here for convenience. So sue me.
ARGV = ['fixtures/factory/glideinWMS.xml', 'fixtures/factory/glideinWMS.xml']
FACT_VERS = ""
SRC_DIR = "fixtures/factory"
USAGE_PREFIX = "create_factory"


class TestGlideinParams(unittest.TestCase):

    def setUp(self):
        self.glidein_params = GlideinParams(USAGE_PREFIX, SRC_DIR, ARGV)

    def test_init(self):
        self.assertTrue(isinstance(self.glidein_params, Params))

    def test_buildDir(self):
        self.assertEqual(
            SRC_DIR, self.glidein_params.buildDir(
                FACT_VERS, SRC_DIR))

    def test_derive(self):
        try:
            self.glidein_params.derive()
        except RuntimeError as err:
            self.fail(err)

    def test_get_top_element(self):
        self.assertEqual("glidein", self.glidein_params.get_top_element())

    def test_get_xml_format(self):
        fmt_dict = self.glidein_params.get_xml_format()
        self.assertTrue('dicts_params' in fmt_dict)
        self.assertTrue('lists_params' in fmt_dict)

    def test_get_xml(self):
        self.assertTrue(len(self.glidein_params.get_xml().__repr__()) > 0)

    def test_get_description(self):
        self.assertTrue(
            len(self.glidein_params.get_description().__repr__()) > 0)

    def test_file_read_and_write(self):
        fn = tempfile.NamedTemporaryFile(prefix='/tmp/', delete=False)
        fn.close()
        self.glidein_params.save_into_file(fn.name)
        new_param_obj = GlideinParams("", "", [fn.name, fn.name])
        new_param_obj.load_file(fn.name)
        os.remove(fn.name)

    def test_init_defaults(self):
        try:
            self.glidein_params.init_defaults()
        except RuntimeError as err:
            self.fail(err)

    @unittest.skip(
        'this test doesnt set up subparams so validate_names will fail')
    def test_validate_names(self):
        try:
            self.glidein_params.validate_names()
        except RuntimeError as err:
            self.fail(err)

    def test__eq__(self):
        cpy = copy.deepcopy(self.glidein_params)
        self.assertTrue(cpy == self.glidein_params)
        self.assertFalse(cpy is None)


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
