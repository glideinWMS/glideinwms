#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/lib/fork.py

 Author:
   Dennis Box dbox@fnal.gov
"""

import os
import sys

# import select
import time
import unittest

import xmlrunner

import glideinwms.lib.logSupport

# needed to manipulate the select seen by the functions in fork
from glideinwms.lib import fork
from glideinwms.lib.fork import (
    fetch_fork_result,
    fetch_fork_result_list,
    fetch_ready_fork_result_list,
    fork_in_bg,
    ForkManager,
    ForkResultError,
    wait_for_pids,
)
from glideinwms.unittests.unittest_utils import create_temp_file, FakeLogger

LOG_FILE = create_temp_file()


def global_log_setup():
    fd = open(LOG_FILE, "w")
    glideinwms.lib.logSupport.log = FakeLogger(fd)


def global_log_cleanup():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)


def sleep_fn(sleep_tm=None):
    if not sleep_tm:
        sleep_tm = 1
    time.sleep(float(sleep_tm))
    return str(sleep_tm)


class TestForkResultError(unittest.TestCase):
    def test___init__(self):
        try:
            fork_result_error = ForkResultError(nr_errors=1, good_results=None, failed=1)
        except ForkResultError as err:
            self.assertEqual("", str(err))
            self.assertEqual("", str(fork_result_error))

        return


class TestForkInBg(unittest.TestCase):
    def test_fork_in_bg(self):
        global_log_setup()
        results = fork_in_bg(sleep_fn, 1)
        self.assertTrue("r" in results)
        self.assertTrue("pid" in results)
        global_log_cleanup()


class TestFetchForkResult(unittest.TestCase):
    def test_fetch_fork_result(self):
        global_log_setup()
        sleep_arg = "1"
        results = fork_in_bg(sleep_fn, sleep_arg)
        expected = fetch_fork_result(results["r"], results["pid"])
        self.assertEqual(expected, sleep_arg)
        global_log_cleanup()


class TestFetchForkResultList(unittest.TestCase):
    def test_fetch_fork_result_list(self):
        global_log_setup()
        pipe_ids = {}
        expected = {}
        svl = 10
        for key in range(1, 5):
            pipe_ids[key] = fork_in_bg(sleep_fn, svl)
            expected[key] = str(svl)

        result = fetch_fork_result_list(pipe_ids)
        self.assertTrue(expected, result)
        global_log_cleanup()


class TestFetchReadyForkResultList(unittest.TestCase):
    def test_fetch_ready_fork_result_list(self):
        global_log_setup()
        pipe_ids = {}
        expected = {}
        svl = 10
        for key in range(1, 5):
            pipe_ids[key] = fork_in_bg(sleep_fn, svl)
            expected[key] = str(svl)

        result = fetch_ready_fork_result_list(pipe_ids)
        self.assertTrue(expected, result)
        global_log_cleanup()


class TestWaitForPids(unittest.TestCase):
    def test_wait_for_pids(self):
        global_log_setup()
        pid_list = []
        for i in range(1, 5):
            pid_list.append(fork_in_bg(sleep_fn, 10))

        wait_for_pids(pid_list)
        global_log_cleanup()


class TestForkManager(unittest.TestCase):
    def setUp(self):
        # import select
        global_log_setup()
        self.fork_manager = ForkManager()
        self.default_forks = 100
        self.default_sleep = 5

    def tear_down(self):
        global_log_cleanup()

    def load_forks(self, num_forks=None, sleep_val=None):
        if not num_forks:
            num_forks = self.default_forks
        if not sleep_val:
            sleep_val = self.default_sleep
        expected = {}
        for i in range(0, num_forks):
            expected[i] = str(sleep_val)
            self.fork_manager.add_fork(i, sleep_fn, sleep_val)
        return expected

    def test___init__(self):
        self.assertTrue(isinstance(self.fork_manager, ForkManager))

    def test_add_fork_and_len(self):
        num_forks = 10
        self.load_forks(num_forks)
        self.assertEqual(num_forks, len(self.fork_manager))

    def test_fork_and_collect(self):
        expected = self.load_forks()
        results = self.fork_manager.fork_and_collect()
        self.assertEqual(expected, results)

    def test_fork_and_wait(self):
        expected = self.load_forks()
        results = self.fork_manager.fork_and_wait()  # pylint: disable=assignment-from-no-return
        self.assertEqual(None, results)
        return

    @unittest.skipUnless(sys.platform.lower().startswith("linux"), "epoll available only on Linux")
    def test_bounded_fork_and_collect_use_epoll(self):
        #
        # the following 3 tests are better if run in order
        # which may be an artifact of different test runners
        #
        # This test will fail on Darwin or other platforms w/o epoll
        # if platform.system() != 'Linux':
        #    return
        expected = self.load_forks()
        results = self.fork_manager.bounded_fork_and_collect(max_forks=50, log_progress=True, sleep_time=0.1)
        self.assertEqual(expected, results)
        fd = open(LOG_FILE)
        log_contents = fd.read()
        self.assertTrue(log_contents)  # False if Fakelogger is not working correctly
        self.assertTrue("Active forks =" in log_contents)
        self.assertTrue("Forks to finish =" in log_contents)
        # The error messages changed in python 3:
        # Failed to load select.epoll(): module 'select' has no attribute 'epoll'
        # Failed to load select.poll(): module 'select' has no attribute 'poll'
        self.assertFalse("module 'select' has no attribute 'epoll'" in log_contents)
        self.assertFalse("module 'select' has no attribute 'poll'" in log_contents)

    def test_bounded_fork_and_collect_use_poll(self):
        # force select.epoll to throw in import error so select.poll is used
        if hasattr(fork.select, "epoll"):
            del fork.select.epoll
        expected = self.load_forks()
        results = self.fork_manager.bounded_fork_and_collect(max_forks=50, log_progress=True, sleep_time=0.1)
        # restore select (fork.select) after running the test
        del sys.modules["select"]
        import select

        fork.select = select
        # check results
        self.assertEqual(expected, results)
        fd = open(LOG_FILE)
        log_contents = fd.read()
        self.assertTrue(log_contents)  # False if Fakelogger is not working correctly
        self.assertTrue("Active forks = " in log_contents)
        self.assertTrue("Forks to finish =" in log_contents)
        self.assertTrue("module 'select' has no attribute 'epoll'" in log_contents)
        self.assertFalse("module 'select' has no attribute 'poll'" in log_contents)

    def test_bounded_fork_and_collect_use_select(self):
        # force select.epoll and select.poll to throw an import error so select is used
        if hasattr(fork.select, "epoll"):
            del fork.select.epoll
        if hasattr(fork.select, "poll"):
            del fork.select.poll
        expected = self.load_forks()
        results = self.fork_manager.bounded_fork_and_collect(max_forks=50, log_progress=True, sleep_time=0.1)
        # restore select (fork.select) after running the test
        del sys.modules["select"]
        import select

        fork.select = select
        # check results
        self.assertEqual(expected, results)
        fd = open(LOG_FILE)
        log_contents = fd.read()
        self.assertTrue(log_contents)  # False if Fakelogger is not working correctly
        self.assertTrue("Active forks = " in log_contents)
        self.assertTrue("Forks to finish =" in log_contents)
        self.assertTrue("module 'select' has no attribute 'epoll'" in log_contents)
        self.assertTrue("module 'select' has no attribute 'poll'" in log_contents)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
