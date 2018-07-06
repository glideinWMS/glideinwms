#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import os
import copy
import unittest2 as unittest
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest
from glideinwms.unittests.unittest_utils import create_temp_file

from glideinwms.creation.lib.cWDictFile import DictFile
from glideinwms.creation.lib.cWDictFile import fileDicts


class TestDictFile(unittest.TestCase):
    """test class for DictFile from glideinwms/creation/lib/cWDictFile.py
    TODO  File cWDictFile.py is 1700 lines long and contains too
    many classes.  It should be split up
    """

    def test___getitem__(self):
        self.assertEqual("'True'",
                         self.dict_file.__getitem__('GLIDEIN_Expose_Grid_Env'))

    def setUp(self):
        self.dict_file = DictFile(dir="fixtures/frontend",
                                  fname="attrs.cfg",
                                  sort_keys=True,
                                  order_matters=None,
                                  fname_idx=None)
        self.dict_file.load()

    def test___init__(self):
        self.assertTrue(isinstance(self.dict_file, DictFile))

    def test_bad_init(self):
        try:
            df = DictFile(dir="fixtures/frontend",
                              fname="attrs.cfg",
                              sort_keys=True,
                              order_matters=True,
                              fname_idx=None)
            self.assertTrue(False, "DictFile init succeeded with " +
                            "sort_keys=True and order_matters=True")
        except RuntimeError:
            self.assertTrue(True,
                            "Raised exception when " +
                            "sort_keys=True and order_matters=True")

    def test_add(self):
        self.dict_file.add("foo", "bar", allow_overwrite=True)
        self.dict_file.add("foo", "bar", allow_overwrite=True)
        self.assertEqual("bar", self.dict_file["foo"])
        self.dict_file.add("foo", "foobar", allow_overwrite=True)
        try:
            self.dict_file.add("foo", "baz", allow_overwrite=False)
            assert False
        except RuntimeError:
            self.assertTrue(True,
                            "Raised exception when " +
                            "overwriting when allow_overwrite=False")
            return
        assert False

    def test_erase(self):
        self.assertTrue("GLIDEIN_Expose_Grid_Env" in self.dict_file)
        self.dict_file.erase()
        self.assertFalse("GLIDEIN_Expose_Grid_Env" in self.dict_file)

    def test_file_footer(self):
        self.assertEqual(None, self.dict_file.file_footer(want_comments=False))

    def test_file_header(self):
        self.assertEqual(None, self.dict_file.file_header(want_comments=False))
        self.assertEqual('# File: %s\n#' % self.dict_file.fname,
                         self.dict_file.file_header(want_comments=True))

    def test_format_val(self):
        key = 'GLIDEIN_Expose_Grid_Env'
        expected = "%s \t%s" % (key, "'True'")
        self.assertEqual(expected, self.dict_file.format_val(key, False))

    def test_get_dir(self):
        expected = 'fixtures/frontend'
        self.assertEqual(expected, self.dict_file.get_dir())

    def test_get_filepath(self):
        expected = os.path.join(self.dict_file.get_dir(), self.dict_file.fname)
        self.assertEqual(expected, self.dict_file.get_filepath())

    def test_get_fname(self):
        self.assertEqual(self.dict_file.fname, self.dict_file.get_fname())

    def test_has_key(self):
        expected = True
        key = 'GLIDEIN_Expose_Grid_Env'
        # TODO change this method name to has_key1()
        self.assertEqual(expected, self.dict_file.has_key(key))

    def test_is_compatible(self):
        old_val = 'foo'
        new_val = 'bar'
        self.assertEqual(True, self.dict_file.is_compatible(old_val, new_val))

    def test_is_equal(self):
        other = copy.deepcopy(self.dict_file)
        for cd in range(0, 2):
            for cf in range(0, 2):
                for ck in range(0, 2):
                    self.assertTrue(self.dict_file.is_equal(other,
                                                            compare_dir=cd,
                                                            compare_fname=cf,
                                                            compare_keys=ck))
        other.add("foo", "bar", allow_overwrite=True)
        for cd in range(0, 2):
            for cf in range(0, 2):
                for ck in range(0, 2):
                    self.assertFalse(self.dict_file.is_equal(other,
                                                             compare_dir=cd,
                                                             compare_fname=cf,
                                                             compare_keys=ck))
        other = copy.deepcopy(self.dict_file)
        other.dir = '/tmp'
        for cf in range(0, 2):
            for ck in range(0, 2):
                self.assertTrue(self.dict_file.is_equal(other,
                                                        compare_dir=False,
                                                        compare_fname=cf,
                                                        compare_keys=ck))
                self.assertFalse(self.dict_file.is_equal(other,
                                                         compare_dir=True,
                                                         compare_fname=cf,
                                                         compare_keys=ck))
        other = copy.deepcopy(self.dict_file)
        other.fname = 'foo'
        for cd in range(0, 2):
            for ck in range(0, 2):
                self.assertTrue(self.dict_file.is_equal(other,
                                                        compare_dir=cd,
                                                        compare_fname=False,
                                                        compare_keys=ck))
                self.assertFalse(self.dict_file.is_equal(other,
                                                         compare_dir=cd,
                                                         compare_fname=True,
                                                         compare_keys=ck))
        other = copy.deepcopy(self.dict_file)
        other.keys.sort()
        for cd in range(0, 2):
            for cf in range(0, 2):
                self.assertTrue(self.dict_file.is_equal(other,
                                                        compare_dir=cd,
                                                        compare_fname=cf,
                                                        compare_keys=False))
                self.assertFalse(self.dict_file.is_equal(other,
                                                         compare_dir=cd,
                                                         compare_fname=cf,
                                                         compare_keys=True))

    def test_parse_val(self):
        line = """foo    'bar'"""
        self.dict_file.parse_val(line)
        cpy = copy.deepcopy(self.dict_file)
        self.assertEqual("'bar'", self.dict_file["foo"])
        self.assertEqual(cpy.keys, self.dict_file.keys)
        # should not throw exception
        self.dict_file.parse_val("")
        self.assertEqual(cpy.keys, self.dict_file.keys)
        line = """#comment value"""
        self.dict_file.parse_val(line)
        self.assertFalse("comment" in self.dict_file)
        self.assertFalse("#comment" in self.dict_file)
        self.assertEqual(cpy.keys, self.dict_file.keys)

    def test_remove(self):
        # TODO: seems like fail_if_missing is exactly backwards
        #
        key = 'GLIDEIN_Expose_Grid_Env'
        self.dict_file.remove(key, fail_if_missing=False)
        self.dict_file.remove(key, fail_if_missing=True)
        self.assertFalse(key in self.dict_file.keys)
        try:
            self.dict_file.remove(key, fail_if_missing=False)
            assert False
        except Exception as err:
            self.assertTrue(isinstance(err, RuntimeError))

    def test_save(self):
        fnm = create_temp_file()
        os.remove(fnm)
        self.dict_file.save(fname=fnm, save_only_if_changed=False)
        self.assertTrue(os.path.exists(fnm))
        os.remove(fnm)

    def test_save_into_load_from_fd(self):
        other = copy.deepcopy(self.dict_file)
        fnm = create_temp_file()
        fd = open(fnm, "w")
        self.dict_file.save_into_fd(fd)
        fd.close()
        fd = open(fnm, "r")
        other.load_from_fd(fd, erase_first=True)
        fd.close()
        self.assertTrue(self.dict_file.is_equal(other))
        os.remove(fnm)

    def test_save_to_load_from_str(self):
        other = copy.deepcopy(self.dict_file)
        d_str = self.dict_file.save_into_str(sort_keys=False,
                                             set_readonly=False,
                                             reset_changed=False,
                                             want_comments=False)
        other.load_from_str(data=d_str,
                            erase_first=True,
                            set_not_changed=False)
        self.assertTrue(self.dict_file.is_equal(other))

    def test_set_readonly(self):
        self.dict_file.set_readonly(True)
        try:
            self.dict_file.add("foo", "bar", allow_overwrite=True)
            assert False
        except Exception as err:
            self.assertTrue(isinstance(err, RuntimeError))

        self.dict_file.set_readonly(False)
        self.dict_file.add("foo", "bar", allow_overwrite=True)


if __name__ == '__main__':
    ofl = 'unittests-reports'
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=ofl))
