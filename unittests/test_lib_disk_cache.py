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

import os
import tempfile
import time
import unittest

import xmlrunner

from glideinwms.lib.disk_cache import DiskCache


class TestDiskCache(unittest.TestCase):
    """Test the DiskCache class"""

    def setUp(self):
        self.obj = "I am the object to be saved"
        self.objid = "objid"
        self.cache = DiskCache(".")

    def tearDown(self):
        os.remove(self.objid)
        os.remove(self.objid + ".lock")

    def test_normal(self):
        """Test a few things"""
        # No cache file exists
        self.assertFalse(os.path.isfile(self.objid))

        # The cache is empty at the beginning
        cached_obj = self.cache.get(self.objid)
        self.assertIsNone(cached_obj)

        # Save the object and check the cache file exists now
        self.cache.save(self.objid, self.obj)
        self.assertTrue(os.path.isfile(self.objid))

        # Check we get the object from the cache
        cached_obj = self.cache.get(self.objid)
        self.assertEqual(self.obj, cached_obj)

        # Create a new cache (e.g., from another process) and verify we get the object from file
        cache = DiskCache(".")
        cached_obj = cache.get(self.objid)
        self.assertEqual(self.obj, cached_obj)

        # But from another directory we do not hit the cache
        new_location = tempfile.mkdtemp()
        cache = DiskCache(new_location)
        cached_obj = cache.get(self.objid)
        self.assertIsNone(cached_obj)
        os.rmdir(new_location)

        # And now what happens if we let the cache expire? We do not get the object!
        self.cache.cache_duration = 2  # 2 seconds
        time.sleep(2)
        cached_obj = self.cache.get(self.objid)
        self.assertIsNone(cached_obj)

        # But if I save it again it works (assuming this takes less than 2 seconds to be executes:
        # we are not running on potatoes)
        self.cache.save(self.objid, self.obj)
        cached_obj = self.cache.get(self.objid)
        self.assertEqual(self.obj, cached_obj)
        # It works also on another cache with empty memory cache
        cache = DiskCache(".")
        cached_obj = cache.get(self.objid)
        self.assertEqual(self.obj, cached_obj)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
