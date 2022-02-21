#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/creation/lib/cvWParams.py

 Author:
   Dennis Box dbox@fnal.gov
"""


import copy
import os
import sys
import tempfile
import unittest

from unittest import mock

import xmlrunner

from glideinwms.creation.lib.cvWParams import extract_attr_val, VOFrontendParams, VOFrontendSubParams
from glideinwms.creation.lib.cWParams import Params, SubParams

ARGV = ["fixtures/frontend.xml", "fixtures/frontend.xml"]
SRC_DIR = "fixtures/frontend"
USAGE_PREFIX = "create_frontend"


class TestVOFrontendSubParams(unittest.TestCase):
    def setUp(self):
        v_o_frontend_params = VOFrontendParams(USAGE_PREFIX, SRC_DIR, ARGV)
        self.sub_params = VOFrontendSubParams(v_o_frontend_params.data)

    def test_init(self):
        self.assertTrue(isinstance(self.sub_params, SubParams))

    def test__eq__(self):
        cpy = copy.deepcopy(self.sub_params)
        self.assertEqual(cpy, self.sub_params)
        self.assertTrue(cpy == self.sub_params)
        self.assertFalse(self.sub_params is None)

    def test_extract_attr_val(self):
        monkey = mock.Mock()
        monkey.type = "string"
        monkey.value = "monkey"
        self.assertEqual("monkey", self.sub_params.extract_attr_val(monkey))

    def test_looks_like_dict(self):
        self.assertTrue(len(list(self.sub_params.keys())) > 0)
        # for k in self.sub_params: FAILS in the __getitem__ step
        # for k in self.sub_params.keys(): PASSES __getitem__
        for k in list(self.sub_params.keys()):
            self.assertTrue(k in self.sub_params)
            val1 = self.sub_params.__getitem__(k)
            val2 = self.sub_params[k]
            self.assertEqual(val1, val2)


class TestVOFrontendParams(unittest.TestCase):
    def setUp(self):
        self.v_o_frontend_params = VOFrontendParams(USAGE_PREFIX, SRC_DIR, ARGV)

    def test_init(self):
        self.assertTrue(isinstance(self.v_o_frontend_params, Params))

    def test_buildDir(self):
        self.assertEqual(SRC_DIR, self.v_o_frontend_params.buildDir("", SRC_DIR))

    def test_derive(self):
        try:
            self.v_o_frontend_params.derive()
        except RuntimeError as err:
            self.fail(err)

    def test_extract_attr_val(self):
        p = self.v_o_frontend_params
        self.assertEqual("1", p.extract_attr_val(p.attrs["GLIDECLIENT_Rank"]))

    def test_get_subparams_class(self):
        sc = self.v_o_frontend_params.get_subparams_class()
        self.assertNotEqual(None, sc)

    def test_get_top_element(self):
        self.assertEqual("frontend", self.v_o_frontend_params.get_top_element())

    def test_get_xml_format(self):
        fmt_dict = self.v_o_frontend_params.get_xml_format()
        self.assertTrue("dicts_params" in fmt_dict)
        self.assertTrue("lists_params" in fmt_dict)

    def test_get_xml(self):
        self.assertTrue(len(self.v_o_frontend_params.get_xml().__repr__()) > 0)

    def test_get_description(self):
        self.assertTrue(len(self.v_o_frontend_params.get_description().__repr__()) > 0)

    def test_init_defaults(self):
        try:
            self.v_o_frontend_params.init_defaults()
        except RuntimeError as err:
            self.fail(err)

    def test_validate_names(self):
        try:
            self.v_o_frontend_params.validate_names()
        except RuntimeError as err:
            self.fail(err)

    def test_file_read_and_write(self):
        fn = tempfile.NamedTemporaryFile(prefix="/tmp/", delete=False)
        fn.close()
        self.v_o_frontend_params.save_into_file(fn.name)
        new_param_obj = VOFrontendParams("", "", [fn.name, fn.name])
        new_param_obj.load_file(fn.name)

    def test__eq__(self):
        cpy = copy.deepcopy(self.v_o_frontend_params)
        self.assertTrue(cpy == self.v_o_frontend_params)


class TestExtractAttrVal(unittest.TestCase):
    def test_extract_attr_val(self):
        monkey = mock.Mock()
        monkey.type = "string"
        monkey.value = "monkey"
        self.assertEqual(monkey.value, extract_attr_val(monkey))


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
