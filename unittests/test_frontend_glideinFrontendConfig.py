#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner
import string
import os

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.frontend.glideinFrontendConfig import FrontendConfig 
from glideinwms.frontend.glideinFrontendConfig import FrontendDescript
from glideinwms.frontend.glideinFrontendConfig import get_group_dir 
from glideinwms.frontend.glideinFrontendConfig import ConfigFile 
from glideinwms.frontend.glideinFrontendConfig import GroupConfigFile 
from glideinwms.frontend.glideinFrontendConfig import ElementDescript 
from glideinwms.frontend.glideinFrontendConfig import ParamsDescript 
from glideinwms.frontend.glideinFrontendConfig import AttrsDescript 
from glideinwms.frontend.glideinFrontendConfig import SignatureDescript 
from glideinwms.frontend.glideinFrontendConfig import ElementMergedDescript 
from glideinwms.frontend.glideinFrontendConfig import GroupSignatureDescript 
from glideinwms.frontend.glideinFrontendConfig import StageFiles 
from glideinwms.frontend.glideinFrontendConfig import ExtStageFiles 
from glideinwms.frontend.glideinFrontendConfig import MergeStageFiles 
from glideinwms.frontend.glideinFrontendConfig import HistoryFile 


class TestFrontendConfig(unittest.TestCase):


        
    def setUp(self):
        self.frontend_config = FrontendConfig()
        self.frontend_descript = FrontendDescript('fixtures/frontend')
        self.signature_descript = SignatureDescript('fixtures/frontend')
        self.group_descript = ElementDescript('fixtures/frontend','group1')
        self.params_descript = ParamsDescript('fixtures/frontend','group1')
        self.attrs_descript = AttrsDescript('fixtures/frontend','group1')
        self.signature_descript = SignatureDescript('fixtures/frontend')
        self.group_signature_descript = GroupSignatureDescript('fixtures/frontend', 'group1')
        self.element_descript = ElementDescript('fixtures/frontend','group1')
        self.element_merged_descript = ElementMergedDescript('fixtures/frontend','group1')
        self.debug_output = os.environ.get('DEBUG_OUTPUT')
        if self.debug_output:
            print('\nconfig = %s' % self.frontend_config)
            print('\ndescript = %s' % self.frontend_descript)
            print('\ngroup_descript = %s' % self.group_descript)
            print('\nparams_descript = %s' % self.params_descript)
            print('\nattrs_descript = %s' % self.attrs_descript)
            print('\nsignature_descript = %s' % self.signature_descript)
            print('group_signature_descript = %s' % self.group_signature_descript)
            print('\nelement_descript = %s' % self.element_descript)
            print('\nelement_merged_descript.merged_data = %s' % self.element_merged_descript.merged_data)
            print('\nelement_merged_descript.element_data = %s' % self.element_merged_descript.element_data)
            print('\nelement_merged_descript.frontend_data = %s' % self.element_merged_descript.frontend_data)
            print('\ndir element_merged_descript = %s' % dir(self.element_merged_descript))

    def test__init__(self):
        self.assertTrue(isinstance(self.frontend_descript, ConfigFile))
        self.assertTrue(isinstance(self.group_descript, ConfigFile))
        self.assertTrue(isinstance(self.element_merged_descript, ElementMergedDescript))
        self.assertTrue(isinstance(self.params_descript, ParamsDescript))
        self.assertTrue(isinstance(self.attrs_descript, AttrsDescript))
        self.assertTrue(isinstance(self.signature_descript, SignatureDescript))

    def test_get_group_dir(self):
        self.assertEqual('fixtures/frontend/group_group1', get_group_dir('fixtures/frontend', 'group1'))



    def test_split_func(self):
        line = "foo bar baz"
        self.signature_descript.split_func(line, None)
        self.assertEqual(self.signature_descript.data['baz'], ('foo', 'bar'))


class TestStageFiles(unittest.TestCase):
    def setUp(self):
        self.stage_files = StageFiles('fixtures/frontend/web-area/stage','nodes.blacklist',None,None)
    @unittest.skip('for now')
    def test___init__(self):
        stage_files = StageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_get_file_list(self):
        stage_files = StageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        self.assertEqual(expected, stage_files.get_file_list(list_type))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_get_stage_file(self):
        stage_files = StageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        self.assertEqual(expected, stage_files.get_stage_file(fname, repr))
        # assert False TODO: implement your test here

class TestExtStageFiles(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        ext_stage_files = ExtStageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_get_condor_vars(self):
        ext_stage_files = ExtStageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        self.assertEqual(expected, ext_stage_files.get_condor_vars())
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_get_constants(self):
        ext_stage_files = ExtStageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        self.assertEqual(expected, ext_stage_files.get_constants())
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_load_preentry_file_list(self):
        ext_stage_files = ExtStageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        self.assertEqual(expected, ext_stage_files.load_preentry_file_list())
        # assert False TODO: implement your test here

class TestMergeStageFiles(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        merge_stage_files = MergeStageFiles(base_URL, validate_algo, group1_descript_fname, group1_signature_hash, group_name, group_descript_fname, group_signature_hash)
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_get_condor_vars(self):
        merge_stage_files = MergeStageFiles(base_URL, validate_algo, group1_descript_fname, group1_signature_hash, group_name, group_descript_fname, group_signature_hash)
        self.assertEqual(expected, merge_stage_files.get_condor_vars())
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_get_constants(self):
        merge_stage_files = MergeStageFiles(base_URL, validate_algo, group1_descript_fname, group1_signature_hash, group_name, group_descript_fname, group_signature_hash)
        self.assertEqual(expected, merge_stage_files.get_constants())
        # assert False TODO: implement your test here

class TestHistoryFile(unittest.TestCase):
    @unittest.skip('for now')
    def test___contains__(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        self.assertEqual(expected, history_file.__contains__(keyid))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test___delitem__(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        self.assertEqual(expected, history_file.__delitem__(keyid))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test___getitem__(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        self.assertEqual(expected, history_file.__getitem__(keyid))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test___init__(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test___setitem__(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        self.assertEqual(expected, history_file.__setitem__(keyid, val))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_empty(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        self.assertEqual(expected, history_file.empty())
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_get(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        self.assertEqual(expected, history_file.get(keyid, defaultval))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_has_key(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        self.assertEqual(expected, history_file.has_key(keyid))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_load(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        self.assertEqual(expected, history_file.load(raise_on_error))
        # assert False TODO: implement your test here

    @unittest.skip('for now')
    def test_save(self):
        history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        self.assertEqual(expected, history_file.save(raise_on_error))
        # assert False TODO: implement your test here

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
