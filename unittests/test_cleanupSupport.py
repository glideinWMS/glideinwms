#!/usr/bin/env python
from __future__ import absolute_import
import os
import sys
import shutil
import tempfile
import unittest2 as unittest
import xmlrunner

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from glideinwms.unittests.unittest_utils import runTest
from glideinwms.unittests.unittest_utils import FakeLogger
from glideinwms.unittests.unittest_utils import create_temp_file
from glideinwms.lib import logSupport
from glideinwms.lib import cleanupSupport

class TestCleanupSupport(unittest.TestCase):
    """
    Test the cleaners to ensure that only the files that we want to be deleted are.
    """
    def setUp(self):
        """
        The cleanupSupport module logs so implement the FakeLogger so that things
        don't break.  We will create a bunch of files to cleanup and a bunch to 
        keep around.
        """
        logSupport.log = FakeLogger()
        self.num_cleanup_files_wanted = 10
        self.num_noncleanup_files_wanted = 5
        self.cleanup_extension = '.cleanup'
        self.keep_extension = '.dont_cleanup'

        # mkdir tempdir
        self.cleanup_dir = tempfile.mkdtemp()
        # make non cleanup temp files
        self.create_noncleanup_tempfiles()
        # make cleanup temp files
        self.create_cleanup_tempfiles()

    def tearDown(self):
        """
        remove all remaining files created by tests
        """
        shutil.rmtree(self.cleanup_dir)

    def create_files(self, number_of_files, suffix=""):
        """
        Create temporary files using the tempfile module.  The absolute path toThe file extension to place on the temporary file
        the file is written to the file for content.
        
        @type number_of_files: int
        @param number_of_files: The number of temporary files to create
        @type file_suffix: string
        @param file_suffix: The file extension to place on the temporary file
        """
        files_created = 0
        while not (files_created == number_of_files):
            path = create_temp_file(file_suffix=suffix, file_dir=self.cleanup_dir)
            files_created += 1

    def create_cleanup_tempfiles(self):
        """
        Call the create_files function with the appropriate suffix to denote
        files that should be cleaned up.
        """
        self.create_files(self.num_cleanup_files_wanted, self.cleanup_extension)

    def create_noncleanup_tempfiles(self):
        """
        Call the create_files function with the appropriate suffix to denote
        files that should not be cleaned up.
        """
        self.create_files(self.num_noncleanup_files_wanted, self.keep_extension)

    def check_for_cleanup_files(self):
        """
        Get a directory listing of the reference directory excluding all files
        except the cleanup files.
        
        @return: Number in cleanup files found
        """
        files = os.listdir(self.cleanup_dir)
        files = [filename for filename in files if filename.endswith(self.cleanup_extension)]
        return len(files)

    def check_for_noncleanup_files(self):
        """
        Get a directory listing of the cleanup directory excluding all files
        except the non-cleanup files.
        
        @return: Number in non-cleanup files found
        """
        files = os.listdir(self.cleanup_dir)
        files = [filename for filename in files if filename.endswith(self.keep_extension)]
        return len(files)

    def test_PrivsepDirCleanupWSpace(self):
        """
        Instantiate the directory cleaner and direct it to clean all cleanup files with
        the cleanup extension.  After teh cleanup method has been called, check for the
        presence of cleanup files.  Fail if any exist.  Also check for the presence of
        the other files created.  Fail if any were deleted. 
        """
        cleaner = cleanupSupport.PrivsepDirCleanupWSpace(None, self.cleanup_dir, ".*\%s" % self.cleanup_extension, 0, 0, 0)
        cleaner.cleanup()
        num_cleanup_files_left = self.check_for_cleanup_files()
        num_noncleanup_files_left = self.check_for_noncleanup_files()
        self.assertEqual(num_cleanup_files_left, 0,
                         "The cleaner left %s files that should have been deleted." % str(num_cleanup_files_left))
        self.assertEqual(num_noncleanup_files_left, self.num_noncleanup_files_wanted,
                         "The cleaner deleted %s files that should not have been deleted." % \
                         str(self.num_noncleanup_files_wanted - num_cleanup_files_left))


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='unittests-reports'))
