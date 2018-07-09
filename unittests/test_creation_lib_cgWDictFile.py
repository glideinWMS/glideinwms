#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner


# from glideinwms.creation.lib.cgWDictFile import MonitorGroupDictFile
# from glideinwms.creation.lib.cgWDictFile import InfoSysDictFile
from glideinwms.creation.lib.cgWDictFile import CondorJDLDictFile
from glideinwms.creation.lib.cgWDictFile import get_common_dicts
from glideinwms.creation.lib.cgWDictFile import get_main_dicts
from glideinwms.creation.lib.cgWDictFile import get_entry_dicts
from glideinwms.creation.lib.cgWDictFile import load_common_dicts
from glideinwms.creation.lib.cgWDictFile import load_main_dicts
from glideinwms.creation.lib.cgWDictFile import load_entry_dicts
# from glideinwms.creation.lib.cgWDictFile import refresh_description
# from glideinwms.creation.lib.cgWDictFile import refresh_file_list
# from glideinwms.creation.lib.cgWDictFile import refresh_signature
# from glideinwms.creation.lib.cgWDictFile import save_common_dicts
# from glideinwms.creation.lib.cgWDictFile import save_main_dicts
# from glideinwms.creation.lib.cgWDictFile import save_entry_dicts
# from glideinwms.creation.lib.cgWDictFile import reuse_simple_dict
# from glideinwms.creation.lib.cgWDictFile import reuse_file_dict
# from glideinwms.creation.lib.cgWDictFile import reuse_common_dicts
# from glideinwms.creation.lib.cgWDictFile import reuse_main_dicts
# from glideinwms.creation.lib.cgWDictFile import reuse_entry_dicts
# from glideinwms.creation.lib.cgWDictFile import clientDirSupport
# from glideinwms.creation.lib.cgWDictFile import chmodClientDirSupport
# from glideinwms.creation.lib.cgWDictFile import baseClientDirSupport
# from glideinwms.creation.lib.cgWDictFile import clientSymlinksSupport
# from glideinwms.creation.lib.cgWDictFile import clientLogDirSupport
# from glideinwms.creation.lib.cgWDictFile import clientProxiesDirSupport
from glideinwms.creation.lib.cgWDictFile import glideinMainDicts
# from glideinwms.creation.lib.cgWDictFile import glideinEntryDicts
# from glideinwms.creation.lib.cgWDictFile import glideinDicts

# import glideinwms.creation.lib.cWDictFile as cWDictFile


# class TestMonitorGroupDictFile(unittest.TestCase):
class TestcgWDictFile(unittest.TestCase):

    def setUp(self):
        self.stage_dir = 'fixtures/factory/stage'
        self.submit_dir = 'fixtures/factory/work-dir'
        self.main_dicts = get_main_dicts(self.submit_dir, self.stage_dir)
        self.common_dicts = get_common_dicts(self.submit_dir, self.stage_dir)
        self.entry_dicts = get_entry_dicts(
            self.submit_dir, self.stage_dir, 'entry_el6_osg34')
        # self.main_dicts.load()
        # self.entry_dicts.load()

    def test__init__(self):
        self.assertTrue(isinstance(self.main_dicts, dict))
        self.assertTrue(isinstance(self.common_dicts, dict))
        self.assertTrue(isinstance(self.entry_dicts, dict))

    def test_add_MonitorGroupDictFile(self):
        monitor_group_dict_file = self.entry_dicts['mongroup']
        key = 'foo'
        val = 'bar'
        allow_overwrite = False
        accepts_non_tuples = True
        try:
            monitor_group_dict_file.add(key, val, allow_overwrite)
        except RuntimeError:
            accepts_non_tuples = False
        self.assertFalse(accepts_non_tuples)

        val = ['entry_el6_osg34']
        monitor_group_dict_file.add(key, val, allow_overwrite)
        self.assertTrue('foo' in monitor_group_dict_file)
        val = ['something_different']
        try:
            # should fail
            monitor_group_dict_file.add(key, val, allow_overwrite)
        except RuntimeError:
            allow_overwrite = True
        # should succeed
        monitor_group_dict_file.add(key, val, allow_overwrite)
        self.assertEqual(val, monitor_group_dict_file['foo'])
        self.assertTrue(allow_overwrite)

    def test_add_extended_MonitorGroupDictFile(self):
        monitor_group_dict_file = self.entry_dicts['mongroup']
        allow_overwrite = False
        group_name = 'entry_el6_osg34'
        monitor_group_dict_file.add_extended(group_name, allow_overwrite)
        try:
            # should fail
            monitor_group_dict_file.add_extended(group_name, allow_overwrite)
        except RuntimeError:
            allow_overwrite = True
        # should succeed
        monitor_group_dict_file.add_extended(group_name, allow_overwrite)
        self.assertTrue(group_name in monitor_group_dict_file)
        # FIXME
        # self.assertTrue(allow_overwrite)

    def test_file_footer_MonitorGroupDictFile(self):
        monitor_group_dict_file = self.entry_dicts['mongroup']
        expected = '</monitorgroups>'
        want_comments = False
        self.assertEqual(
            expected,
            monitor_group_dict_file.file_footer(want_comments))
        want_comments = True
        # FIXME
        # self.assertNotEqual(expected, monitor_group_dict_file.file_footer(want_comments))

    def test_file_header_MonitorGroupDictFile(self):
        monitor_group_dict_file = self.entry_dicts['mongroup']
        expected = '<monitorgroups>'
        want_comments = False
        self.assertEqual(
            expected,
            monitor_group_dict_file.file_header(want_comments))
        want_comments = True
        self.assertNotEqual(
            expected,
            monitor_group_dict_file.file_header(want_comments))

    def test_format_val_MonitorGroupDictFile(self):
        monitor_group_dict_file = self.entry_dicts['mongroup']
        val = ['entry_el6_osg34']
        key = 'foo'
        monitor_group_dict_file.add(key, val)
        no_c = monitor_group_dict_file.format_val(key, False)
        has_c = monitor_group_dict_file.format_val(key, True)
        expected = '  <monitorgroup group_name="entry_el6_osg34">'
        self.assertEqual(expected, no_c)
        self.assertEqual(expected, has_c)

    def test_parse_val_MonitorGroupDictFile(self):
        monitor_group_dict_file = self.entry_dicts['mongroup']
        monitor_group_dict_file.parse_val('')
        monitor_group_dict_file.parse_val('## hi there')

    def test_add_InfoSysDictFile(self):
        info_sys_dict_file = self.entry_dicts['infosys']
        key = 'foo'
        val = ['bar', 'baz', 'boo']
        allow_overwrite = False
        info_sys_dict_file.add(key, val, allow_overwrite)

    @unittest.skip('for now')
    def test_add_extended_InfoSysDictFile(self):
        # info_sys_dict_file = self.entry_dicts['infosys']
        # self.assertEqual(expected, info_sys_dict_file.add_extended(infosys_type, server_name, ref_str, allow_overwrite))
        assert False  # TODO: implement your test here

    def test_file_header_InfoSysDictFile(self):
        info_sys_dict_file = self.entry_dicts['infosys']
        want_comments = True
        self.assertTrue(
            '#######' in info_sys_dict_file.file_header(want_comments))
        want_comments = False
        self.assertEqual(None, info_sys_dict_file.file_header(want_comments))

    def test_format_val_InfoSysDictFile(self):
        info_sys_dict_file = self.entry_dicts['infosys']
        expected = 'bar \t                           baz \tboo \t\tfoo'
        want_comments = False
        key = 'foo'
        val = ['bar', 'baz', 'boo']
        allow_overwrite = False
        info_sys_dict_file.add(key, val, allow_overwrite)
        self.assertEqual(expected, info_sys_dict_file.format_val(key,
                                                                 want_comments))
        want_comments = True
        # want_comments is like the fake 'close door' button on an elevator
        self.assertEqual(expected, info_sys_dict_file.format_val(key,
                                                                 want_comments))

    def test_parse_val_InfoSysDictFile(self):
        info_sys_dict_file = self.entry_dicts['infosys']
        info_sys_dict_file.parse_val('')
        info_sys_dict_file.parse_val('###')

    def test_load_main_dicts(self):
        load_main_dicts(self.main_dicts)

    @unittest.skip('hmm')
    def test_load_common_dicts(self):
        load_common_dicts(self.common_dicts, self.common_dicts['description'])

    @unittest.skip('hmm')
    def test_load_entry_dicts(self):
        load_entry_dicts(
            self.entry_dicts,
            'el6_osg34',
            self.entry_dicts['signature'])


class TestCondorJDLDictFile(unittest.TestCase):

    def setUp(self):
        self.dir = 'fixtures/factory/work-dir/entry_el6_osg34'
        self.fname = 'job.condor'
        self.jdict = CondorJDLDictFile(self.dir, self.fname)
        self.jdict.load()

    def test__init__(self):
        self.assertTrue(isinstance(self.jdict, CondorJDLDictFile))
        self.assertNotEqual([], self.jdict.keys)

    def test_file_footer_CondorJDLDictFile(self):
        expected = 'Queue'
        self.assertNotEqual(
            expected, self.jdict.file_footer(
                want_comments=True))
        self.assertNotEqual(
            expected, self.jdict.file_footer(
                want_comments=False))

    def test_format_val_CondorJDLDictFile(self):
        want_comments = False
        for key in self.jdict.keys:
            not_expected = self.jdict[key]
            #self.assertEqual(expected, self.jdict.format_val(key, want_comments))
            self.assertNotEqual(
                not_expected, self.jdict.format_val(
                    key, want_comments))

    @unittest.skip('for now')
    def test_is_equal_CondorJDLDictFile(self):
        # condor_jdl_dict_file = CondorJDLDictFile(dir, fname, sort_keys, order_matters, jobs_in_cluster, fname_idx)
        # self.assertEqual(expected, condor_jdl_dict_file.is_equal(other, compare_dir, compare_fname, compare_keys))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_parse_val_CondorJDLDictFile(self):
        # condor_jdl_dict_file = CondorJDLDictFile(dir, fname, sort_keys, order_matters, jobs_in_cluster, fname_idx)
        # self.assertEqual(expected, condor_jdl_dict_file.parse_val(line))
        assert False  # TODO: implement your test here


# class TestRefreshDescription(unittest.TestCase):

    @unittest.skip('for now')
    def test_refresh_description(self):
        # self.assertEqual(expected, refresh_description(dicts))
        assert False  # TODO: implement your test here

# class TestRefreshFileList(unittest.TestCase):
    @unittest.skip('for now')
    def test_refresh_file_list(self):
        # self.assertEqual(expected, refresh_file_list(dicts, is_main, files_set_readonly, files_reset_changed))
        assert False  # TODO: implement your test here

# class TestRefreshSignature(unittest.TestCase):
    @unittest.skip('for now')
    def test_refresh_signature(self):
        # self.assertEqual(expected, refresh_signature(dicts))
        assert False  # TODO: implement your test here

# class TestSaveCommonDicts(unittest.TestCase):
    @unittest.skip('for now')
    def test_save_common_dicts(self):
        # self.assertEqual(expected, save_common_dicts(dicts, is_main, set_readonly))
        assert False  # TODO: implement your test here

# class TestSaveMainDicts(unittest.TestCase):
    @unittest.skip('for now')
    def test_save_main_dicts(self):
        # self.assertEqual(expected, save_main_dicts(main_dicts, set_readonly))
        assert False  # TODO: implement your test here

# class TestSaveEntryDicts(unittest.TestCase):
    @unittest.skip('for now')
    def test_save_entry_dicts(self):
        # self.assertEqual(expected, save_entry_dicts(entry_dicts, entry_name, summary_signature, set_readonly))
        assert False  # TODO: implement your test here

# class TestReuseSimpleDict(unittest.TestCase):
    @unittest.skip('for now')
    def test_reuse_simple_dict(self):
        # self.assertEqual(expected, reuse_simple_dict(dicts, other_dicts, key, compare_keys))
        assert False  # TODO: implement your test here

# class TestReuseFileDict(unittest.TestCase):
    @unittest.skip('for now')
    def test_reuse_file_dict(self):
        # self.assertEqual(expected, reuse_file_dict(dicts, other_dicts, key))
        assert False  # TODO: implement your test here

# class TestReuseCommonDicts(unittest.TestCase):
    @unittest.skip('for now')
    def test_reuse_common_dicts(self):
        # self.assertEqual(expected, reuse_common_dicts(dicts, other_dicts, is_main, all_reused))
        assert False  # TODO: implement your test here

# class TestReuseMainDicts(unittest.TestCase):
    @unittest.skip('for now')
    def test_reuse_main_dicts(self):
        # self.assertEqual(expected, reuse_main_dicts(main_dicts, other_main_dicts))
        assert False  # TODO: implement your test here

# class TestReuseEntryDicts(unittest.TestCase):
    @unittest.skip('for now')
    def test_reuse_entry_dicts(self):
        # self.assertEqual(expected, reuse_entry_dicts(entry_dicts, other_entry_dicts, entry_name))
        assert False  # TODO: implement your test here


class TestClientDirSupport(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        # client_dir_support = clientDirSupport(user, dir, dir_name, privsep_mkdir)
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_create_dir(self):
        # client_dir_support = clientDirSupport(user, dir, dir_name, privsep_mkdir)
        # self.assertEqual(expected, client_dir_support.create_dir(fail_if_exists))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_delete_dir(self):
        # client_dir_support = clientDirSupport(user, dir, dir_name, privsep_mkdir)
        # self.assertEqual(expected, client_dir_support.delete_dir())
        assert False  # TODO: implement your test here


class TestChmodClientDirSupport(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        # chmod_client_dir_support = chmodClientDirSupport(user, dir, chmod, dir_name)
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_create_dir(self):
        # chmod_client_dir_support = chmodClientDirSupport(user, dir, chmod, dir_name)
        # self.assertEqual(expected, chmod_client_dir_support.create_dir(fail_if_exists))
        assert False  # TODO: implement your test here


class TestBaseClientDirSupport(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        # base_client_dir_support = baseClientDirSupport(user, dir, dir_name)
        assert False  # TODO: implement your test here


class TestClientSymlinksSupport(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        # client_symlinks_support = clientSymlinksSupport(user_dirs, work_dir, symlink_base_subdir, dir_name)
        assert False  # TODO: implement your test here


class TestClientLogDirSupport(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        # client_log_dir_support = clientLogDirSupport(user, log_dir, dir_name)
        assert False  # TODO: implement your test here


class TestClientProxiesDirSupport(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        # client_proxies_dir_support = clientProxiesDirSupport(user, proxies_dir, proxiesdir_name)
        assert False  # TODO: implement your test here


class TestGlideinMainDicts(unittest.TestCase):

    def setUp(self):
        self.gmdicts = glideinMainDicts('fixtures/factory/work-dir',
                                        'fixtures/factory/stage',
                                        'work-dir',
                                        'fixtures/factory',
                                        {},
                                        {})

    def test___init__(self):
        self.assertTrue(isinstance(self.gmdicts, glideinMainDicts))

    def test_get_daemon_log_dir(self):
        self.assertEqual(
            'fixtures/factory',
            self.gmdicts.get_daemon_log_dir('fixtures'))

    def test_get_main_dicts(self):
        md = self.gmdicts.get_main_dicts()
        if md:
            assert True
        else:
            assert False

    def test_load(self):
        self.gmdicts.load()

    def test_reuse(self):
        other = glideinMainDicts('fixtures/factory/work-dir',
                                 'fixtures/factory/stage', 'work-dir',
                                 'fixtures/factory', {}, {})
        self.gmdicts.reuse(other)
        if other:
            assert True
        else:
            assert False

    def test_save(self):
        self.gmdicts.save(set_readonly=True)
        self.gmdicts.save(set_readonly=False)

    @unittest.skip('raised notimplemented')
    def test_populate(self):
        other = {}
        self.gmdicts.populate(other)
        if other:
            assert True
        else:
            assert False

    @unittest.skip('for now')
    def test_save_monitor(self):
        # glidein_main_dicts = glideinMainDicts(conf, workdir_name)
        # self.assertEqual(expected, glidein_main_dicts.save_monitor())
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_save_monitor_config(self):
        # glidein_main_dicts = glideinMainDicts(conf, workdir_name)
        # self.assertEqual(expected, glidein_main_dicts.save_monitor_config(work_dir, glidein_dict))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_save_pub_key(self):
        # glidein_main_dicts = glideinMainDicts(conf, workdir_name)
        # self.assertEqual(expected, glidein_main_dicts.save_pub_key())
        assert False  # TODO: implement your test here


    @unittest.skip('for now')
    def test_get_sub_dicts(self):
        # glidein_entry_dicts = glideinEntryDicts(base_work_dir, base_stage_dir, sub_name, summary_signature, workdir_name, base_log_dir, base_client_log_dirs, base_client_proxies_dirs)
        # self.assertEqual(expected, glidein_entry_dicts.get_sub_dicts())
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_get_sub_log_dir(self):
        # glidein_entry_dicts = glideinEntryDicts(base_work_dir, base_stage_dir, sub_name, summary_signature, workdir_name, base_log_dir, base_client_log_dirs, base_client_proxies_dirs)
        # self.assertEqual(expected, glidein_entry_dicts.get_sub_log_dir(base_dir))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_get_sub_stage_dir(self):
        # glidein_entry_dicts = glideinEntryDicts(base_work_dir, base_stage_dir, sub_name, summary_signature, workdir_name, base_log_dir, base_client_log_dirs, base_client_proxies_dirs)
        # self.assertEqual(expected, glidein_entry_dicts.get_sub_stage_dir(base_dir))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_get_sub_work_dir(self):
        # glidein_entry_dicts = glideinEntryDicts(base_work_dir, base_stage_dir, sub_name, summary_signature, workdir_name, base_log_dir, base_client_log_dirs, base_client_proxies_dirs)
        # self.assertEqual(expected, glidein_entry_dicts.get_sub_work_dir(base_dir))
        assert False  # TODO: implement your test here

    #@unittest.skip('for now')
    #def test_load(self):
        # glidein_entry_dicts = glideinEntryDicts(base_work_dir, base_stage_dir, sub_name, summary_signature, workdir_name, base_log_dir, base_client_log_dirs, base_client_proxies_dirs)
        # self.assertEqual(expected, glidein_entry_dicts.load())
    #    assert False  # TODO: implement your test here

    #@unittest.skip('for now')
    #def test_reuse(self):
        # glidein_entry_dicts = glideinEntryDicts(base_work_dir, base_stage_dir, sub_name, summary_signature, workdir_name, base_log_dir, base_client_log_dirs, base_client_proxies_dirs)
        # self.assertEqual(expected, glidein_entry_dicts.reuse(other))
    #    assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_reuse_nocheck(self):
        # glidein_entry_dicts = glideinEntryDicts(base_work_dir, base_stage_dir, sub_name, summary_signature, workdir_name, base_log_dir, base_client_log_dirs, base_client_proxies_dirs)
        # self.assertEqual(expected, glidein_entry_dicts.reuse_nocheck(other))
        assert False  # TODO: implement your test here

    #@unittest.skip('for now')
    #def test_save(self):
        # glidein_entry_dicts = glideinEntryDicts(base_work_dir, base_stage_dir, sub_name, summary_signature, workdir_name, base_log_dir, base_client_log_dirs, base_client_proxies_dirs)
        # self.assertEqual(expected, glidein_entry_dicts.save(set_readonly))
    #    assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_save_final(self):
        # glidein_entry_dicts = glideinEntryDicts(base_work_dir, base_stage_dir, sub_name, summary_signature, workdir_name, base_log_dir, base_client_log_dirs, base_client_proxies_dirs)
        # self.assertEqual(expected, glidein_entry_dicts.save_final(set_readonly))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_erase(self):
        # glidein_entry_dicts = glideinEntryDicts(conf, sub_name, summary_signature, workdir_name)
        # self.assertEqual(expected, glidein_entry_dicts.erase())
        assert False  # TODO: implement your test here

    #@unittest.skip('for now')
    #def test_populate(self):
        # glidein_entry_dicts = glideinEntryDicts(conf, sub_name, summary_signature, workdir_name)
        # self.assertEqual(expected, glidein_entry_dicts.populate(entry, schedd))
    #    assert False  # TODO: implement your test here

class TestGlideinDicts(unittest.TestCase):
    @unittest.skip('for now')
    def test___init__(self):
        # glidein_dicts = glideinDicts(work_dir, stage_dir, log_dir, client_log_dirs, client_proxies_dirs, entry_list, workdir_name)
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_get_sub_name_from_sub_stage_dir(self):
        # glidein_dicts = glideinDicts(work_dir, stage_dir, log_dir, client_log_dirs, client_proxies_dirs, entry_list, workdir_name)
        # self.assertEqual(expected, glidein_dicts.get_sub_name_from_sub_stage_dir(sign_key))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_new_MainDicts(self):
        # glidein_dicts = glideinDicts(work_dir, stage_dir, log_dir, client_log_dirs, client_proxies_dirs, entry_list, workdir_name)
        # self.assertEqual(expected, glidein_dicts.new_MainDicts())
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_new_SubDicts(self):
        # glidein_dicts = glideinDicts(work_dir, stage_dir, log_dir, client_log_dirs, client_proxies_dirs, entry_list, workdir_name)
        # self.assertEqual(expected, glidein_dicts.new_SubDicts(sub_name))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_populate(self):
        # glidein_dicts = glideinDicts(conf, sub_list)
        #  self.assertEqual(expected, glidein_dicts.populate(other))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_reuse(self):
        # glidein_dicts = glideinDicts(conf, sub_list)
        # self.assertEqual(expected, glidein_dicts.reuse(other))
        assert False  # TODO: implement your test here

    @unittest.skip('for now')
    def test_sortit(self):
        # glidein_dicts = glideinDicts(conf, sub_list)
        # self.assertEqual(expected, glidein_dicts.sortit(unsorted_dict))
        assert False  # TODO: implement your test here


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
