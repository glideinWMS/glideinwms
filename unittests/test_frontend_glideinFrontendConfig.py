#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
   glideinWMS

Description:
   unit test for glideinwms/frontend/glideinFrontendConfig

Author:
   Dennis Box <dbox@fnal.gov>
"""


import os
import string
import unittest

import xmlrunner

from glideinwms.frontend.glideinFrontendConfig import (
    AttrsDescript,
    ConfigFile,
    ElementDescript,
    ElementMergedDescript,
    ExtStageFiles,
    FrontendConfig,
    FrontendDescript,
    get_group_dir,
    GroupConfigFile,
    GroupSignatureDescript,
    HistoryFile,
    MergeStageFiles,
    ParamsDescript,
    SignatureDescript,
    StageFiles,
)


class TestFrontendConfig(unittest.TestCase):
    def setUp(self):
        self.frontend_config = FrontendConfig()
        self.frontend_descript = FrontendDescript("fixtures/frontend")
        self.signature_descript = SignatureDescript("fixtures/frontend")
        self.group_descript = ElementDescript("fixtures/frontend", "group1")
        self.params_descript = ParamsDescript("fixtures/frontend", "group1")
        self.attrs_descript = AttrsDescript("fixtures/frontend", "group1")
        self.signature_descript = SignatureDescript("fixtures/frontend")
        self.group_signature_descript = GroupSignatureDescript("fixtures/frontend", "group1")
        self.element_descript = ElementDescript("fixtures/frontend", "group1")
        self.element_merged_descript = ElementMergedDescript("fixtures/frontend", "group1")
        self.debug_output = os.environ.get("DEBUG_OUTPUT")
        if self.debug_output:
            print("\nconfig = %s" % self.frontend_config)
            print("\ndescript = %s" % self.frontend_descript)
            print("\ngroup_descript = %s" % self.group_descript)
            print("\nparams_descript = %s" % self.params_descript)
            print("\nattrs_descript = %s" % self.attrs_descript)
            print("\nsignature_descript = %s" % self.signature_descript)
            print("group_signature_descript = %s" % self.group_signature_descript)
            print("\nelement_descript = %s" % self.element_descript)
            print("\nelement_merged_descript.merged_data = %s" % self.element_merged_descript.merged_data)
            print("\nelement_merged_descript.element_data = %s" % self.element_merged_descript.element_data)
            print("\nelement_merged_descript.frontend_data = %s" % self.element_merged_descript.frontend_data)
            print("\ndir element_merged_descript = %s" % dir(self.element_merged_descript))

    def test__init__(self):
        self.assertTrue(isinstance(self.frontend_descript, ConfigFile))
        self.assertTrue(isinstance(self.group_descript, ConfigFile))
        self.assertTrue(isinstance(self.element_merged_descript, ElementMergedDescript))
        self.assertTrue(isinstance(self.params_descript, ParamsDescript))
        self.assertTrue(isinstance(self.attrs_descript, AttrsDescript))
        self.assertTrue(isinstance(self.signature_descript, SignatureDescript))

    def test_get_group_dir(self):
        self.assertEqual("fixtures/frontend/group_group1", get_group_dir("fixtures/frontend", "group1"))

    def test_split_func(self):
        line = "foo bar baz"
        self.signature_descript.split_func(line, None)
        self.assertEqual(self.signature_descript.data["baz"], ("foo", "bar"))


class TestStageFiles(unittest.TestCase):
    def setUp(self):
        sum = "03265fccd0599cdcd41011ffb9db5c1688e5e241"
        self.stage_files = StageFiles("fixtures/frontend/web-area/stage", "description.e98f4o.cfg", "sha1", sum)

    def test___init__(self):
        self.assertTrue(isinstance(self.stage_files, StageFiles))

    def test_get_file_list(self):
        try:
            fll = self.stage_files.get_file_list("schmoo")
            assert False  # raise error if found schmoo files
        except KeyError as ker:
            # print('%s' % ker)
            pass
        fll = self.stage_files.get_file_list("file_list")
        self.assertTrue(isinstance(fll, ConfigFile))

    @unittest.skip("for now")
    def test_get_stage_file(self):
        # stage_files = StageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        # self.assertEqual(expected, stage_files.get_stage_file(fname, repr))
        assert False  # TODO: implement your test here


class TestExtStageFiles(unittest.TestCase):
    @unittest.skip("for now")
    def test___init__(self):
        # ext_stage_files = ExtStageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_get_condor_vars(self):
        # ext_stage_files = ExtStageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        # self.assertEqual(expected, ext_stage_files.get_condor_vars())
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_get_constants(self):
        # ext_stage_files = ExtStageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        # self.assertEqual(expected, ext_stage_files.get_constants())
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_load_preentry_file_list(self):
        # ext_stage_files = ExtStageFiles(base_URL, descript_fname, validate_algo, signature_hash)
        # self.assertEqual(expected, ext_stage_files.load_preentry_file_list())
        assert False  # TODO: implement your test here


class TestMergeStageFiles(unittest.TestCase):
    @unittest.skip("for now")
    def test___init__(self):
        # merge_stage_files = MergeStageFiles(base_URL, validate_algo, group1_descript_fname, group1_signature_hash, group_name, group_descript_fname, group_signature_hash)
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_get_condor_vars(self):
        # merge_stage_files = MergeStageFiles(base_URL, validate_algo, group1_descript_fname, group1_signature_hash, group_name, group_descript_fname, group_signature_hash)
        # self.assertEqual(expected, merge_stage_files.get_condor_vars())
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_get_constants(self):
        # merge_stage_files = MergeStageFiles(base_URL, validate_algo, group1_descript_fname, group1_signature_hash, group_name, group_descript_fname, group_signature_hash)
        # self.assertEqual(expected, merge_stage_files.get_constants())
        assert False  # TODO: implement your test here


class TestHistoryFile(unittest.TestCase):
    @unittest.skip("for now")
    def test___contains__(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # self.assertEqual(expected, history_file.__contains__(keyid))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test___delitem__(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # self.assertEqual(expected, history_file.__delitem__(keyid))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test___getitem__(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # self.assertEqual(expected, history_file.__getitem__(keyid))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test___init__(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test___setitem__(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # self.assertEqual(expected, history_file.__setitem__(keyid, val))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_empty(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # self.assertEqual(expected, history_file.empty())
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_get(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # self.assertEqual(expected, history_file.get(keyid, defaultval))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_has_key(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # self.assertEqual(expected, history_file.has_key(keyid))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_load(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # self.assertEqual(expected, history_file.load(raise_on_error))
        assert False  # TODO: implement your test here

    @unittest.skip("for now")
    def test_save(self):
        # history_file = HistoryFile(base_dir, group_name, load_on_init, default_factory)
        # self.assertEqual(expected, history_file.save(raise_on_error))
        assert False  # TODO: implement your test here


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
