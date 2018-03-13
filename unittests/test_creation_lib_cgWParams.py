#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner
import tempfile
import copy
import os

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.creation.lib.cgWParams import GlideinParams 
from glideinwms.creation.lib.cgWParams import find_condor_base_dir 
from glideinwms.creation.lib.cWParams import Params

argv = ['fixtures/factory/glideinWMS.xml', 'fixtures/factory/glideinWMS.xml']
factoryVersioning=""
src_dir="fixtures/factory"
usage_prefix="create_factory"
expected=""

class TestGlideinParams(unittest.TestCase):

    def setUp(self):
        self.glidein_params = GlideinParams(usage_prefix, src_dir, argv)

    def test_init(self):
        self.assertTrue(isinstance(self.glidein_params, Params))

    def test_buildDir(self):
        self.assertEqual(src_dir, self.glidein_params.buildDir(factoryVersioning, src_dir))

    def test_derive(self):
        try:
            self.glidein_params.derive()
        except RuntimeError as err:
            self.fail(err)

    def test_get_top_element(self):
        self.assertEqual("glidein",self.glidein_params.get_top_element())

    def test_get_xml_format(self):
        fmt_dict = self.glidein_params.get_xml_format()
        self.assertTrue('dicts_params' in fmt_dict)
        self.assertTrue('lists_params' in fmt_dict)


    def test_get_xml(self):
        self.assertTrue(len(self.glidein_params.get_xml().__repr__())>0)

    def test_get_description(self):
        self.assertTrue(len(self.glidein_params.get_description().__repr__())>0)
    
    def test_file_read_and_write(self):
        fn = tempfile.NamedTemporaryFile(prefix='/tmp/',delete=False)
        fn.close()
        self.glidein_params.save_into_file(fn.name)
        new_param_obj = GlideinParams("","",[fn.name,fn.name])
        new_param_obj.load_file(fn.name)
        os.remove(fn.name)


    def test_init_defaults(self):
        try:
            self.glidein_params.init_defaults()
        except RuntimeError as err:
            self.fail(err)



    def test__eq__(self):
        cpy = copy.deepcopy(self.glidein_params)
        self.assertTrue(cpy == self.glidein_params)
        self.assertFalse(cpy == None)



if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
