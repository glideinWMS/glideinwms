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
from glideinwms.creation.lib.cWDictFile import DictFileTwoKeys


class TestDictFileTwoKeys(unittest.TestCase):
    """test class for DictFileTwoKeys from
    glideinwms/creation/lib/cWDictFile.py
    TODO  File cWDictFile.py is 1700 lines long and contains too
    many classes.  It should be split up
    """

    def test___getitem__(self):
        self.assertEqual("'True'",
                         self.dict_file.__getitem__('GLIDECLIENT_Group_Start'))

    def setUp(self):
        self.dict_file = DictFileTwoKeys(dir="fixtures/frontend/group_group1",
                                         fname="attrs.cfg", sort_keys=True)
        self.dict_file.load()
        self.dict_file.add("a", "b")
        self.dict_file.add("c", "d")

    def test___init__(self):
        self.assertTrue(isinstance(self.dict_file, DictFileTwoKeys))

    def test_add_has_key2_get_val2(self):
        self.dict_file.add("foo", "baz", allow_overwrite=True)
        self.dict_file.add("foo", "baz", allow_overwrite=True)
        self.dict_file.add("foo", "bar", allow_overwrite=True)
        self.assertEqual("bar", self.dict_file["foo"])
        self.assertEqual("foo", self.dict_file.get_val2("bar"))
        self.assertTrue(self.dict_file.has_key2("bar"))

    def test_add_no_overwrite(self):
        self.dict_file.add("foo", "bar", allow_overwrite=False)
        try:
            self.dict_file.add("foo", "baz", allow_overwrite=False)
            assert False
        except RuntimeError:
            self.assertTrue(True, "raised correctly")
            return
        assert False

    def test_erase(self):
        self.assertTrue("GLIDECLIENT_Group_Start" in self.dict_file)
        self.dict_file.erase()
        self.assertFalse("GLIDECLIENT_Group_Start" in self.dict_file)

    def test_file_footer(self):
        self.assertEqual(None, self.dict_file.file_footer(want_comments=False))

    def test_file_header(self):
        self.assertEqual(None, self.dict_file.file_header(want_comments=False))
        self.assertEqual('# File: %s\n#' % self.dict_file.fname,
                         self.dict_file.file_header(want_comments=True))

    def test_format_val(self):
        key = 'GLIDECLIENT_Group_Start'
        expected = "%s \t%s" % (key, "'True'")
        self.assertEqual(expected, self.dict_file.format_val(key, False))
        # assert False TODO: implement your test here

    def test_get_dir(self):
        expected = 'fixtures/frontend/group_group1'
        self.assertEqual(expected, self.dict_file.get_dir())

    def test_get_filepath(self):
        expected = os.path.join(self.dict_file.get_dir(), self.dict_file.fname)
        self.assertEqual(expected, self.dict_file.get_filepath())

    def test_get_fname(self):
        self.assertEqual(self.dict_file.fname, self.dict_file.get_fname())

    def test_has_key(self):
        expected = True
        key = 'GLIDECLIENT_Group_Start'
        # has_key should be renamed has_key1
        self.assertEqual(expected, self.dict_file.has_key(key))

    def test_is_compatible2(self):
        self.assertTrue(self.dict_file.is_compatible2("foo", "bar"))

    def test_is_compatible(self):
        old_val = 'foo'
        new_val = 'bar'
        self.assertEqual(True, self.dict_file.is_compatible(old_val, new_val))

    def test_is_equal(self):
        other = copy.deepcopy(self.dict_file)
        for cd in range(0, 2):
            for cf in range(0, 2):
                for ck in range(0, 2):
                    cd = bool(cd)
                    cf = bool(cf)
                    ck = bool(ck)
                    self.assertTrue(self.dict_file.is_equal(other,
                                                            compare_dir=cd,
                                                            compare_fname=cf,
                                                            compare_keys=ck))
        other.add("foo", "bar", allow_overwrite=True)
        for cd in range(0, 2):
            for cf in range(0, 2):
                for ck in range(0, 2):
                    cd = bool(cd)
                    cf = bool(cf)
                    ck = bool(ck)
                    self.assertFalse(self.dict_file.is_equal(other,
                                                             compare_dir=cd,
                                                             compare_fname=cf,
                                                             compare_keys=ck))
        other = copy.deepcopy(self.dict_file)
        other.dir = '/tmp'
        for cf in range(0, 2):
            for ck in range(0, 2):
                cf = bool(cf)
                ck = bool(ck)
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
                cd = bool(cd)
                ck = bool(ck)
                self.assertTrue(self.dict_file.is_equal(other,
                                                        compare_dir=cd,
                                                        compare_fname=False,
                                                        compare_keys=ck))
                self.assertFalse(self.dict_file.is_equal(other,
                                                         compare_dir=cd,
                                                         compare_fname=True,
                                                         compare_keys=ck))
        other = copy.deepcopy(self.dict_file)
        other.remove("a")
        other.remove("c")
        other.add("c", "d")
        other.add("a", "b")

        sdf = self.dict_file
        fmt_str = "%s=%s self=\n%s other=\n%s"
        asck = 'assertTrue compare_keys'
        for cd in range(0, 2):
            for cf in range(0, 2):
                ck = False
                cd = bool(cd)
                cf = bool(cf)
                self.assertTrue(self.dict_file.is_equal(other,
                                                        compare_dir=cd,
                                                        compare_fname=cf,
                                                        compare_keys=ck),
                                fmt_str % (asck,
                                           ck,
                                           sdf.save_into_str(),
                                           other.save_into_str()))
                ck = True
                self.assertFalse(self.dict_file.is_equal(other,
                                                         compare_dir=cd,
                                                         compare_fname=cf,
                                                         compare_keys=ck),
                                 fmt_str % (asck,
                                            ck,
                                            sdf.save_into_str(),
                                            other.save_into_str()))

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
        # TODO: seems like fail_if_missing is correct unlike
        # this classes base class
        #
        key = 'GLIDECLIENT_Group_Start'
        self.dict_file.remove(key, fail_if_missing=False)
        self.dict_file.remove(key, fail_if_missing=False)
        self.assertFalse(key in self.dict_file.keys)
        try:
            self.dict_file.remove(key, fail_if_missing=True)
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
