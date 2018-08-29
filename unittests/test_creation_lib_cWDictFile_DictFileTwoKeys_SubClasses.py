#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for subclasses of DictFileTwoKeys in
   glideinwms/creation/lib/cWDictFile.py

 Author:
   Dennis Box dbox@fnal.gov
"""


from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner


# from glideinwms.creation.lib.cWDictFile import DictFile
from glideinwms.creation.lib.cWDictFile import DescriptionDictFile
from glideinwms.creation.lib.cWDictFile import GridMapDict


class TestDescriptionDictFile(unittest.TestCase):

    def setUp(self):
        self.description_dict_file = DescriptionDictFile("fixtures",
                                                         "description.cfg")
        self.description_dict_file.load()

    def test_format_val(self):
        key = 'signature.i2cmtV.sha1'
        expected = "%s \t%s.i2cmtV.sha1" % ('signature', 'signature')
        self.assertEqual(expected,
                         self.description_dict_file.format_val(key, False))

    def test_parse_val(self):
        line = """dohicky     doohicky.i2cmtV.sha1"""
        self.description_dict_file.parse_val(line)
        self.assertTrue("doohicky.i2cmtV.sha1" in self.description_dict_file)
        self.description_dict_file.parse_val("")


class TestGridMapDict(unittest.TestCase):

    def setUp(self):
        self.grid_map_dict = GridMapDict("fixtures", "condor_mapfile")
        self.grid_map_dict.load()

    def test_file_header(self):
        self.assertEqual(None,
                         self.grid_map_dict.file_header(want_comments=False))

    def test_format_val(self):
        key = "/DC=org/DC=opensciencegrid/O=Open Science " + \
              "Grid/OU=Services/CN=fermicloud308.fnal.gov"
        expected = '"/DC=org/DC=opensciencegrid/O=Open Science ' + \
                   'Grid/OU=Services/CN=fermicloud308.fnal.gov" factory'
        self.assertEqual(expected,
                         self.grid_map_dict.format_val(key,
                                                       want_comments=False))

    def test_parse_val(self):
        mykey = "/DC=org/DC=opensciencegrid/O=Open Science Grid" + \
                "/OU=Services/CN=fermicloud204.fnal.gov"
        line = """"%s" osg""" % mykey
        self.grid_map_dict.parse_val(line)
        self.assertTrue(mykey in self.grid_map_dict)
        self.grid_map_dict.parse_val("")


if __name__ == '__main__':
    OFL = 'unittests-reports'
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=OFL))
