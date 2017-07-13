#!/usr/bin/env python
from __future__ import absolute_import
from builtins import str
import os
import sys
import unittest2 as unittest
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest

from glideinwms.lib import condorExe
from glideinwms.lib.condorExe import iexe_cmd
from glideinwms.lib.condorExe import exe_cmd
from glideinwms.lib.condorExe import exe_cmd_sbin
from glideinwms.lib.condorExe import ExeError

class TestCondorExe(unittest.TestCase):

    def setUp(self):
        # set the paths to the worker script directory for the purposes of our
        # unittests
        condorExe.condor_bin_path = os.path.join(sys.path[0], "worker_scripts")
        condorExe.condor_sbin_path = condorExe.condor_bin_path

        self.normal_exit_scripts = ['write_exit_0.sh', 'write_exit_0.py']
        self.abnormal_exit_scripts = ['write_exit_1.sh', 'write_exit_1.py']

        # exe_cmd and exe_cmd_sbin expect args but the worker scripts don't
        # nor do they care, so just add some dummy args to complete the calls
        self.dummy_args = "blah"

    def test_iexe_cmd(self):
        """
        Test the iexe_cmd function for errors.  There are two sets of worker
        functions that will be executed.  The first set writes 20k lines to
        stdout and exits normally (exit code: 0).  The second also writes 20k
        lines to stdout, but these exit abnormally (exit code: 1).  Both sets
        of scripts consist of one written in python and one written in shell
        script (bash).

        The original code for iexe_cmd would block if the buffer was filled and
        EOF wasn't in the buffer.  The code was re-written to handle that use
        case, but still blocked because the write side could still fill the
        buffer without appending EOF.  There are two solutions.  One, give the
        buffer read command a ridiculously small buffer size (but even that
        isn't a guarantee since the read side doesn't know hat the buffer size
        should be), or two, make the read buffers non-blocking.

        Option two was selected.  This unittest tests both the blocking
        condition and error handling in the function.
        """
        # Execution should proceed normally and exit with no exceptions.
        try:
            for script in self.normal_exit_scripts:
                cmd = os.path.join(condorExe.condor_bin_path, script)
                output = iexe_cmd(cmd)
        except Exception as e:
            self.fail("Exception Occurred: %s" % str(e))

        # Execution should exit with an exception.  If no exception, then fail
        for script in self.abnormal_exit_scripts:
            cmd = os.path.join(condorExe.condor_bin_path, script)
            self.failUnlessRaises(ExeError, iexe_cmd, cmd)

    def test_exe_cmd(self):
        """
        exe_cmd is a wrapper for iexe_cmd.  See test_iexe_cmd docstring for
        full details.
        """
        # Execution should proceed normally and exit with no exceptions.
        try:
            for script in self.normal_exit_scripts:
                output = exe_cmd(script, self.dummy_args)
        except Exception as e:
            self.fail("Exception Occurred: %s" % str(e))

        # Execution should exit with an exception.  If no exception, then fail
        for script in self.abnormal_exit_scripts:
            self.failUnlessRaises(ExeError, exe_cmd, script, self.dummy_args)

    def test_exe_cmd_sbin(self):
        """
        exe_cmd_sbin is a wrapper for iexe_cmd.  See test_iexe_cmd docstring
        for full details.
        """
        # Execution should proceed normally and exit with no exceptions.
        try:
            for script in self.normal_exit_scripts:
                output = exe_cmd_sbin(script, self.dummy_args)
        except Exception as e:
            self.fail("Exception Occurred: %s" % str(e))

        # Execution should exit with an exception.  If no exception, then fail
        for script in self.abnormal_exit_scripts:
            self.failUnlessRaises(ExeError, exe_cmd_sbin, script, self.dummy_args)


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
