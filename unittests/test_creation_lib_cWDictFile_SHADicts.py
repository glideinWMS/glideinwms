#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for SHA1DictFile and SummarySHA1DictFile classes in
   glideinwms/creation/lib/cWDictFile.py

 Author:
   Dennis Box dbox@fnal.gov
"""


from __future__ import absolute_import
from __future__ import print_function
import copy
import unittest2 as unittest
import xmlrunner


from glideinwms.creation.lib.cWDictFile import SHA1DictFile
from glideinwms.creation.lib.cWDictFile import SummarySHA1DictFile


class TestSHA1DictFile(unittest.TestCase):

    def setUp(self):
        self.dic = SHA1DictFile("fixtures/frontend", "signatures.sha1")
        self.dic.load()

    def test_init(self):
        self.assertTrue(isinstance(self.dic, SHA1DictFile))
        self.assertTrue('description.e98f4o.cfg  group_main' in self.dic.keys)
        self.assertTrue('description.e98f4o.cfg  group_main' in self.dic)

    def test_add_from_file(self):
        self.dic.add_from_file("fixtures/frontend/group_group1/params.cfg",
                               "params.cfg")
        self.assertTrue("params.cfg" in self.dic)

    def test_format_val(self):
        expected = 'ad0f57615c3df8bbb2130d96cfdf09363f4bd3ed  ' + \
                   'description.e98f4o.cfg  group_main'
        mykey = 'description.e98f4o.cfg  group_main'
        self.assertEqual(expected, self.dic.format_val(mykey, None))

    def test_parse_val(self):
        cpy = copy.deepcopy(self.dic)
        self.assertEqual(cpy.keys, self.dic.keys)
        self.dic.parse_val("# ignore this line")
        self.assertEqual(cpy.keys, self.dic.keys)
        self.dic.parse_val("")
        self.assertEqual(cpy.keys, self.dic.keys)
        try:
            self.dic.parse_val("this should throw RuntimeError")
        except RuntimeError:
            pass
        self.dic.parse_val("foo bar")
        self.assertTrue("bar" in self.dic.keys)
        self.assertNotEqual(cpy.keys, self.dic.keys)


class TestSummarySHA1DictFile(unittest.TestCase):

    def setUp(self):
        self.dic = SummarySHA1DictFile("fixtures/frontend", "signatures.sha1")
        self.dic.load()

    def test_init(self):
        self.assertTrue(isinstance(self.dic, SummarySHA1DictFile))
        self.assertTrue('group_main' in self.dic.keys)
        self.assertTrue('group_main' in self.dic)

    def test_add_from_file(self):
        self.dic.add_from_file("fixtures/frontend/group_group1/params.cfg",
                               "params.cfg")
        self.assertTrue("params.cfg" in self.dic)

    def test_format_val(self):
        expected = 'ad0f57615c3df8bbb2130d96cfdf09363f4bd3ed  ' + \
                   'description.e98f4o.cfg  group_main'
        self.assertEqual(expected, self.dic.format_val('group_main', None))

    def test_parse_val(self):
        cpy = copy.deepcopy(self.dic)
        self.assertEqual(cpy.keys, self.dic.keys)
        self.dic.parse_val("# ignore this line")
        self.assertEqual(cpy.keys, self.dic.keys)
        self.dic.parse_val("")
        self.assertEqual(cpy.keys, self.dic.keys)
        try:
            self.dic.parse_val("too short")
        except RuntimeError:
            pass
        self.dic.parse_val("foo bar baz")
        self.assertTrue("baz" in self.dic)
        self.assertNotEqual(cpy.keys, self.dic.keys)

    def test_add(self):
        self.dic.add('foo', ['7cea6e20d5a4e65e94689377771e3e44c72735',
                             'foo.e98f4o.cfg'])
        self.assertTrue("foo" in self.dic.keys)


if __name__ == '__main__':
    OFL = 'unittests-reports'
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=OFL))
