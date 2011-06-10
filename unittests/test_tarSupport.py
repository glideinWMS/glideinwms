#!/usr/bin/env python
import os
import sys
import shutil
import tempfile
import tarfile
import random
import string
import unittest

# unittest_utils will handle putting the appropriate directories on the python
# path for us.
from unittest_utils import runTest
from unittest_utils import create_temp_file
from unittest_utils import create_random_string
from hashCrypto import extract_md5
from tarSupport import GlideinTar
from tarSupport import FileDoesNotExist

class TestTarSupport(unittest.TestCase):
    """
    Test the cleaners to ensure that only the files that we want to be deleted are.
    """
    def setUp(self):
        self.extract_dir = tempfile.mkdtemp()
        self.working_dir = tempfile.mkdtemp()
        self.number_of_files = 5
        self.files = []

    def tearDown(self):
        shutil.rmtree(self.extract_dir)
        shutil.rmtree(self.working_dir)

    def extract_archive(self, archive_file):
        tar = tarfile.open(archive_file, mode="r:gz")
        for tarinfo in tar:
            tar.extract(tarinfo, self.extract_dir)

    def create_archive(self):
        random_file_name = create_random_string()
        archive_file = "%s/%s.tar.gz" % (self.working_dir, random_file_name)
        tarball = GlideinTar()
        for file in self.files:
            tarball.add_file(file["path"], "/")
        tarball.create_tar_file(archive_file)
        self.assertTrue(tarball.is_tarfile(archive_file), "Tarball creation failed.  tarball.is_tarfile returned False")
        return archive_file

    def test_tarSupport(self):
        files_created = 0
        while not (files_created == self.number_of_files):
            path = create_temp_file(file_dir=self.working_dir)
            md5sum = extract_md5(path)
            self.files.append({"path": path, "md5sum" : md5sum})
            files_created += 1

        archive_file = self.create_archive()
        self.extract_archive(archive_file)
        files = os.listdir(self.extract_dir)
        msg = "The number of files in the extract directory does not equal the number of files add to the archive."
        self.assertTrue(len(files) == len(self.files), msg)

        extract_files = []
        for f in files:
            md5sum = extract_md5("%s/%s" % (self.extract_dir, f))
            extract_files.append({"path": "%s/%s" % (self.extract_dir, f), "md5sum" : md5sum})

        for file_dict in self.files:
            for extract_dict in extract_files:
                if (os.path.basename(file_dict["path"]) == os.path.basename(extract_dict["path"])) and \
                   (file_dict["md5sum"] == extract_dict["md5sum"]):
                    extract_files.remove(extract_dict)
                    break
        self.assertTrue(len(extract_files) == 0, "At least one original file's md5sum did not match the extracted file's md5sum")

def main():
    return runTest(TestTarSupport)

if __name__ == '__main__':
    sys.exit(main())
