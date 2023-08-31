#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinwms
Purpose:
    test glideinwms/lib/logSupport.py
Author:
    Anthony Tiradani, tiradani@fnal.gov
"""


import logging
import os
import shutil
import sys
import tempfile
import time
import unittest

import xmlrunner

# pylint: disable=E0611,F0401
import yaml

# use tesfixtures.test_time to speed up clock so test takes less elapsed time
# TODO: test_time() deprecated in testfixtures 7.0.0, use mock_time() in the future
from testfixtures import Replacer, test_time

from glideinwms.lib import logSupport
from glideinwms.unittests.unittest_utils import create_random_string

# pylint: enable=E0611,F0401


class TestLogSupport(unittest.TestCase):
    """
    Test the cleaners to ensure that only the files that we want to be
    deleted are.
    """

    def setUp(self):
        self.log_base_dir = tempfile.mkdtemp()
        self.format = "%Y-%m-%d_%H-%M"

        config_file = "%s/test_logSupport.yaml" % os.path.join(sys.path[0], "test_configurations")
        self.config = yaml.load(open(config_file), Loader=yaml.FullLoader)
        self.replace = Replacer()
        # pylint: disable=redundant-keyword-arg; E1124, test_time is overloaded, OK to invoke that way
        self.replace(
            "glideinwms.lib.logSupport.time.time", test_time(2018, 6, 13, 16, 0, 1, delta=60, delta_type="seconds")
        )

    def tearDown(self):
        shutil.rmtree(self.log_base_dir)
        self.replace.restore()

    def load_log(self, section):
        # read these from config file
        log_name = str(self.config[section]["log_name"])
        extension = str(self.config[section]["extension"])
        msg_types = str(self.config[section]["msg_types"])
        max_days = float(self.config[section]["max_days"])
        min_days = float(self.config[section]["min_days"])
        max_mbytes = float(self.config[section]["max_mbytes"])

        backupCount = 5
        try:
            backupCount = int(self.config[section]["backup_count"])
        except BaseException:
            pass  # backup_count may not exist in all sections

        compression = ""
        try:
            compression = str(self.config[section]["compression"])
        except BaseException:
            pass  # compress may not exist in all sections

        log_dir = f"{self.log_base_dir}/{log_name}"
        os.makedirs(log_dir)

        logSupport.add_processlog_handler(
            log_name,
            log_dir,
            msg_types,
            extension,
            max_days,
            min_days,
            max_mbytes,
            backupCount=backupCount,
            compression=compression,
        )

        return logSupport.getLogger(log_name), log_dir

    def rotated_log_tests(self, section, log_dir):
        log_file_name = "{}.{}.log".format(
            str(self.config[section]["log_name"]), str(self.config[section]["extension"])
        )
        # ls self.log_dir
        file_list = os.listdir(log_dir)
        # are there at least two files?
        self.assertTrue(len(file_list) > 1, "Log file did not rotate.")
        # check the extension of the file to make sure that the timestamp isn't
        # in the future
        for log_file in file_list:
            if not (log_file == log_file_name):
                # we have a rotated log file
                extension = log_file.split(".")[-1]
                rotate_time = time.mktime(time.strptime(extension, self.format))
                self.assertTrue(rotate_time < time.time(), "The rotated log extension is in the future")

    def test_logSupport_size_rotate(self):
        section = "test_size_rotate"
        log, log_dir = self.load_log(section)
        max_bytes = float(self.config[section]["max_mbytes"]) * 1024.0 * 1024.0

        # we want to exceed the max size of the log but stop logging shortly
        # after
        required_number_of_lines = (max_bytes / 100) + 100
        lines = 0
        while lines < required_number_of_lines:
            log.info(create_random_string(length=100))
            lines += 1

        self.rotated_log_tests(section, log_dir)

    def test_logSupport_time_rotate(self):
        section = "test_time_rotate"
        self.replace.restore()
        log, log_dir = self.load_log(section)
        max_lifetime_seconds = float(self.config[section]["max_days"]) * 24 * 3600
        sleep_time_seconds = float(self.config[section]["sleep"])

        # we want to log enough times to rotate the log and put a few lines
        # into the new file
        required_number_log_attempts = (max_lifetime_seconds / sleep_time_seconds) + 5
        log_attempts = 0
        while log_attempts < required_number_log_attempts:
            log.info(create_random_string(length=100))
            log_attempts += 1
            time.sleep(sleep_time_seconds)

        self.rotated_log_tests(section, log_dir)

    def test_backup_count(self):
        section = "test_backup_count"
        log, log_dir = self.load_log(section)

        max_bytes = float(self.config[section]["max_mbytes"]) * 1024.0 * 1024.0

        # we want to exceed the max size of the log but stop logging shortly
        # after
        line_size_bytes = 100
        required_number_of_lines = (max_bytes / line_size_bytes) + 100

        # we are going to force a log rotate at least 7 times
        for _ in range(0, 8):
            lines = 0
            while lines < required_number_of_lines:
                log.info(create_random_string(length=line_size_bytes))
                lines += 1
            # sleep so that we don't have name collisions on rollover
            # time.sleep(30)

        self.rotated_log_tests(section, log_dir)

        # There should be 5 backups and the current log file
        file_list = os.listdir(log_dir)
        self.assertTrue(
            len(file_list) > 5,
            "Log file rotate didn't clean up properly. Got only %s rotation but expected 6. File list in %s: %s"
            % (len(file_list), self.log_base_dir, file_list),
        )

    def test_logSupport_compression(self):
        section = "test_compression"
        log, log_dir = self.load_log(section)

        max_bytes = float(self.config[section]["max_mbytes"]) * 1024.0 * 1024.0

        # we want to exceed the max size of the log but stop logging shortly
        # after
        required_number_of_lines = (max_bytes / 100) + 100

        # we are going to force a log rotate at least 7 times
        for _ in range(0, 8):
            lines = 0
            while lines < required_number_of_lines:
                log.info(create_random_string(length=100))
                lines += 1
            # sleep so that we don't have name collisions on rollover
            # time.sleep(30)

        # There should be 3 compressed backups
        file_list = os.listdir(log_dir)
        gzip_list = [i for i in file_list if i.endswith("gz")]
        # TODO:  Check more than the extension (size is smaller or check that file is a correct gzip - magic number?)
        # e.g.: file = open(f,'rb')
        # if (file.read(2) == b'\x1f\x8b'):
        self.assertTrue(len(file_list) == len(gzip_list) + 1, "Log file rotate didn't compress the files.")


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
