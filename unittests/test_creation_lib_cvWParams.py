#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import unittest2 as unittest
import xmlrunner
import mock
import copy
import tempfile

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.creation.lib.cvWParams import VOFrontendSubParams 
from glideinwms.creation.lib.cvWParams import VOFrontendParams 
from glideinwms.creation.lib.cvWParams import extract_attr_val 
from glideinwms.creation.lib.cWParams import Params
from glideinwms.creation.lib.cWParams import SubParams

argv=["fixtures/frontend.xml","fixtures/frontend.xml"]
frontendVersioning=""
src_dir="fixtures/frontend"
usage_prefix="create_frontend"


class TestVOFrontendSubParams(unittest.TestCase):

    def setUp(self):
        v_o_frontend_params = VOFrontendParams(usage_prefix,src_dir,argv)
        self.sub_params = VOFrontendSubParams(v_o_frontend_params.data)

    def test_init(self):
        self.assertTrue(isinstance(self.sub_params, SubParams))

    def test__eq__(self):
        cpy = copy.deepcopy(self.sub_params)
        self.assertEqual(cpy, self.sub_params)
        self.assertTrue(cpy == self.sub_params)
        self.assertFalse(self.sub_params ==  None)

    def test_extract_attr_val(self):
        monkey = mock.Mock()
        monkey.type = 'string'
        monkey.value = 'monkey'
        self.assertEqual("monkey", self.sub_params.extract_attr_val(monkey))

    def test_looks_like_dict(self):
        self.assertTrue(len(self.sub_params.keys()) > 0)
        for k in self.sub_params.keys():
            self.assertTrue(self.sub_params.has_key(k))
            val1 = self.sub_params.__getitem__(k)
            val2 = self.sub_params[k]
            self.assertEqual(val1,val2)

class TestVOFrontendParams(unittest.TestCase):

    def setUp(self):
        self.v_o_frontend_params = VOFrontendParams(usage_prefix,src_dir,argv)


    def test_init(self):
        self.assertTrue(isinstance(self.v_o_frontend_params, Params))


    def test_buildDir(self):
        self.assertEqual(src_dir, self.v_o_frontend_params.buildDir("", src_dir))

    def test_derive(self):
        try:
            self.v_o_frontend_params.derive()
        except RunTimeError as err:
            self.fail(err)

    def test_derive_match_attrs(self):
        try:
            self.v_o_frontend_params.derive_match_attrs()
        except RunTimeError as err:
            self.fail(err)

    def test_extract_attr_val(self):
        p = self.v_o_frontend_params
        self.assertEqual("1", p.extract_attr_val(p.attrs['GLIDECLIENT_Rank']))

    def test_get_subparams_class(self):
        sc = self.v_o_frontend_params.get_subparams_class()
        self.assertNotEqual(None, sc)

    def test_get_top_element(self):
        self.assertEqual('frontend', self.v_o_frontend_params.get_top_element())

    def test_get_xml_format(self):
        fmt_dict = self.v_o_frontend_params.get_xml_format()
        self.assertTrue('dicts_params' in fmt_dict)
        self.assertTrue('lists_params' in fmt_dict)

    def test_get_xml(self):
        self.assertTrue(len(self.v_o_frontend_params.get_xml().__repr__())>0)

    def test_get_description(self):
        self.assertTrue(len(self.v_o_frontend_params.get_description().__repr__())>0)

    def test_init_defaults(self):
        try:
            self.v_o_frontend_params.init_defaults()
        except RunTimeError as err:
            self.fail(err)

    def test_validate_names(self):
        try:
            self.v_o_frontend_params.validate_names()
        except RunTimeError as err:
            self.fail(err)


    def test_file_read_and_write(self):
        fn = tempfile.NamedTemporaryFile(prefix='/tmp/',delete=False)
        fn.close()
        self.v_o_frontend_params.save_into_file(fn.name)
        new_param_obj = VOFrontendParams("","",[fn.name,fn.name])
        new_param_obj.load_file(fn.name)

    def test__eq__(self):
        cpy = copy.deepcopy(self.v_o_frontend_params)
        self.assertTrue( cpy == self.v_o_frontend_params)


class TestExtractAttrVal(unittest.TestCase):
    def test_extract_attr_val(self):
        monkey = mock.Mock()
        monkey.type = 'string'
        monkey.value = 'monkey'
        self.assertEqual(monkey.value, extract_attr_val(monkey))

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
