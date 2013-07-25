#!/usr/bin/env python

import logging
import os
import shutil
import sys
import tempfile
import time
import unittest
import yaml

from unittest_utils import runTest
from unittest_utils import create_random_string

import logSupport

class TestLogSupport(unittest.TestCase):
    """
    Test the cleaners to ensure that only the files that we want to be deleted are.
    """
    def setUp(self):
        self.log_base_dir = tempfile.mkdtemp()
        self.format = "%Y-%m-%d_%H-%M"

        config_file = "%s/test_logSupport.yaml" % os.path.join(sys.path[0], "test_configurations")
        self.config = yaml.load(file(config_file, 'r'))

    def tearDown(self):
        shutil.rmtree(self.log_base_dir)

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
        except:
            pass # backup_count may not exist in all sections

        log_dir = "%s/%s" % (self.log_base_dir, log_name)
        os.makedirs(log_dir)

        logSupport.add_processlog_handler(log_name, log_dir, msg_types, 
                    extension, max_days, min_days, max_mbytes, 
                    backupCount=backupCount)

        return logging.getLogger(log_name), log_dir

    def rotated_log_tests(self, section, log_dir):
        log_file_name = "%s.%s.log" % (str(self.config[section]["log_name"]),
                                   str(self.config[section]["extension"]))
        # ls self.log_dir
        file_list = os.listdir(log_dir)
        # are there at least two files?
        self.assertTrue(len(file_list) > 1, "Log file did not rotate." )
        # check the extension of the file to make sure that the timestamp isn't in the future
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

        # we want to exceed the max size of the log but stop logging shortly after
        required_number_of_lines = (max_bytes / 100) + 100
        lines = 0
        while lines < required_number_of_lines:
            log.info(create_random_string(length=100))
            lines += 1

        self.rotated_log_tests(section, log_dir)

    def test_logSupport_time_rotate(self):
        section = "test_time_rotate"
        log, log_dir = self.load_log(section)
        max_lifetime_seconds = float(self.config[section]["max_days"]) * 24 * 3600
        sleep_time_seconds = float(self.config[section]["sleep"])

        # we want to log enough times to rotate the log and put a few lines into the new file
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

        # we want to exceed the max size of the log but stop logging shortly after
        required_number_of_lines = (max_bytes / 100) + 100

        # we are going to force a log rotate at least 7 times
        for _ in range(0, 8):
            lines = 0
            while lines < required_number_of_lines:
                log.info(create_random_string(length=100))
                lines += 1
            # sleep at least one minute so that we don't have name collisions on rollover
            time.sleep(62)

        self.rotated_log_tests(section, log_dir)

        # There should be 5 backups and the current log file
        file_list = os.listdir(log_dir)
        self.assertTrue(len(file_list) == 6, "Log file rotate didn't clean up properly." )

def main():
    return runTest(TestLogSupport)

if __name__ == '__main__':
    sys.exit(main())
