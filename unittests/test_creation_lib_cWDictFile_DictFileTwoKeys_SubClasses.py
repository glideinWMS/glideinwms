#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
   glideinWMS

 Description:
   unit test for subclasses of DictFileTwoKeys in
   glideinwms/creation/lib/cWDictFile.py

 Author:
   Dennis Box dbox@fnal.gov
"""


import unittest

import xmlrunner

from glideinwms.unittests.unittest_utils import TestImportError

# from glideinwms.creation.lib.cWDictFile import DictFile

try:
    from glideinwms.creation.lib.cWDictFile import DescriptionDictFile, GridMapDict
except ImportError as err:
    raise TestImportError(str(err))


class TestDescriptionDictFile(unittest.TestCase):
    def setUp(self):
        self.description_dict_file = DescriptionDictFile("fixtures", "description.cfg")
        self.description_dict_file.load()

    def test_format_val(self):
        key = "signature.i2cmtV.sha1"
        expected = "{} \t{}.i2cmtV.sha1".format("signature", "signature")
        self.assertEqual(expected, self.description_dict_file.format_val(key, False))

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
        self.assertEqual(None, self.grid_map_dict.file_header(want_comments=False))

    def test_format_val(self):
        key = "/DC=org/DC=opensciencegrid/O=Open Science " + "Grid/OU=Services/CN=fermicloud308.fnal.gov"
        expected = '"/DC=org/DC=opensciencegrid/O=Open Science ' + 'Grid/OU=Services/CN=fermicloud308.fnal.gov" factory'
        self.assertEqual(expected, self.grid_map_dict.format_val(key, want_comments=False))

    def test_parse_val(self):
        mykey = "/DC=org/DC=opensciencegrid/O=Open Science Grid" + "/OU=Services/CN=fermicloud204.fnal.gov"
        line = """"%s" osg""" % mykey
        self.grid_map_dict.parse_val(line)
        self.assertTrue(mykey in self.grid_map_dict)
        self.grid_map_dict.parse_val("")


if __name__ == "__main__":
    OFL = "unittests-reports"
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=OFL))
