#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinwms
Purpose:
    unit test for glideinwms/factory/glideFactoryDowntimeLib.py
Author:
    Doug Strain <dstrain@fnal.gov>
"""

import os
import shutil
import sys
import tarfile
import tempfile
import time
import unittest

import xmlrunner

from glideinwms.factory import glideFactoryDowntimeLib
from glideinwms.lib import condorMonitor, logSupport

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import create_random_string, create_temp_file, FakeLogger, runTest

# from glideinwms.frontend.glideinFrontendInterface import Credential


class TestDowntimes(unittest.TestCase):
    """
    Test the downtimes library
    """

    def setUp(self):
        self.file_loc = "/tmp/downtimes.txt"
        self.downtime = glideFactoryDowntimeLib.DowntimeFile(self.file_loc)
        pass

    def tearDown(self):
        os.remove(self.file_loc)
        pass

    def test_downtimesfile(self):
        self.downtime.startDowntime(entry="All", comment="unittest downtime", create_if_empty=True)
        self.assertTrue(self.downtime.checkDowntime(entry="All", check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="James", check_time=None))
        # Test downtime comments
        self.assertEqual(self.downtime.downtime_comment, "unittest downtime")
        self.downtime.endDowntime(entry="All", comment="end unittest downtime")

        # Use now+1 since we just ended the downtime
        # The second counter may not have updated
        now = int(time.time())
        self.assertFalse(self.downtime.checkDowntime(entry="All", check_time=now + 1))

    def test_setperiodwithendtime(self):
        now = int(time.time())
        self.downtime.startDowntime(
            start_time=now - 60,
            end_time=now + 3600,
            entry="All",
            frontend="All",
            security_class="All",
            comment="unittest downtime",
            create_if_empty=True,
        )
        self.assertTrue(self.downtime.checkDowntime(entry="All", check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="James", check_time=None))
        self.downtime.endDowntime(entry="All", comment="end unittest downtime")
        # Make sure that is after the last downtime command
        now = int(time.time())
        self.assertFalse(self.downtime.checkDowntime(entry="All", check_time=now + 1))

    def test_entryonlydowntime(self):
        now = int(time.time())
        self.downtime.startDowntime(
            start_time=now - 60,
            end_time=now + 3600,
            entry="DougEntry",
            frontend="All",
            security_class="All",
            comment="unittest downtime",
            create_if_empty=True,
        )
        self.assertFalse(self.downtime.checkDowntime(entry="All", check_time=None))
        self.assertFalse(self.downtime.checkDowntime(entry="James", check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="DougEntry", check_time=None))
        self.downtime.endDowntime(entry="All", comment="end unittest downtime")
        # Make sure that is after the last downtime command
        now = int(time.time())
        self.assertFalse(self.downtime.checkDowntime(entry="All", check_time=now + 1))
        self.assertFalse(self.downtime.checkDowntime(entry="DougEntry", check_time=now + 1))

    def test_setdelayedperiod(self):
        now = int(time.time())
        self.downtime.startDowntime(
            start_time=now + 7200,
            end_time=now + 10800,
            entry="All",
            frontend="All",
            security_class="All",
            comment="unittest delayed downtime",
            create_if_empty=True,
        )
        self.assertFalse(self.downtime.checkDowntime(entry="All", check_time=None))
        self.assertTrue(self.downtime.checkDowntime(entry="All", check_time=now + 9600))
        self.downtime.endDowntime(entry="All", comment="end unittest downtime")
        # Make sure that is after the last downtime command
        now2 = int(time.time())
        self.assertFalse(self.downtime.checkDowntime(entry="All", check_time=now2 + 1))
        # Relative to the initial time (must be now2 < now + 7200)
        # Otherwise endDowntime() interrupts started downtime intervals
        if now2 < now + 7200:
            self.assertTrue(self.downtime.checkDowntime(entry="All", check_time=now + 9600))

    def test_setfrontendsecclass(self):
        now = int(time.time())
        self.downtime.startDowntime(
            start_time=now - 7200,
            end_time=now + 10800,
            entry="TestEntry",
            frontend="SampleFrontend",
            security_class="SecClass",
            comment="unittest frontend secclass",
            create_if_empty=True,
        )
        self.assertFalse(self.downtime.checkDowntime(entry="All", check_time=None))
        self.assertFalse(self.downtime.checkDowntime(entry="factory", check_time=None))
        self.assertFalse(self.downtime.checkDowntime(entry="TestEntry", check_time=None))
        self.assertTrue(
            self.downtime.checkDowntime(
                entry="TestEntry", frontend="SampleFrontend", security_class="SecClass", check_time=now + 9600
            )
        )
        self.assertFalse(
            self.downtime.checkDowntime(
                entry="TestEntry", frontend="OtherFrontend", security_class="SecClass", check_time=now + 9600
            )
        )
        self.assertFalse(
            self.downtime.checkDowntime(
                entry="TestEntry", frontend="OtherFrontend", security_class="OtherClass", check_time=now + 9600
            )
        )
        self.assertFalse(
            self.downtime.checkDowntime(
                entry="TestEntry", frontend="SampleFrontend", security_class="OtherClass", check_time=now + 9600
            )
        )
        self.downtime.endDowntime(entry="All", comment="end unittest downtime")
        # Test relative to initial time but must be in the future
        now = max(int(time.time()) + 1, now + 9600)
        self.assertFalse(
            self.downtime.checkDowntime(
                entry="TestEntry", frontend="SampleFrontend", security_class="SecClass", check_time=now
            )
        )


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
