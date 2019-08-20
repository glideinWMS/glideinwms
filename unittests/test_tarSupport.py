#!/usr/bin/env python
"""
Project:
    glideinWMS
Purpose:
    unit test of glideinwms/lib/tarSupport.py
Author:
    Anthony Tiradani <tiradani@fnal.gov>
"""
from __future__ import absolute_import
import os
import sys
import shutil
import tempfile
import tarfile
import unittest2 as unittest
import xmlrunner

from glideinwms.unittests.unittest_utils import create_temp_file
from glideinwms.unittests.unittest_utils import create_random_string
from glideinwms.unittests.unittest_utils import TestImportError
try:
    from glideinwms.lib.hashCrypto import extract_md5
except ImportError as err:
    raise TestImportError(str(err))

from glideinwms.lib.tarSupport import GlideinTar
from glideinwms.lib.tarSupport import FileDoesNotExist


class TestTarSupport(unittest.TestCase):
    """
    Test the cleaners to ensure that only the files that we want to be deleted are.
    """

    def setUp(self):
        self.extract_dir = tempfile.mkdtemp()
        self.working_dir = tempfile.mkdtemp()
        self.number_of_files = 5
        self.files = []
        self.strings = {"string1": "Why did the chicken cross the road?",
                        "string2": "To get to the other side."}
        files_created = 0
        while not (files_created == self.number_of_files):
            path = create_temp_file(file_dir=self.working_dir)
            md5sum = extract_md5(path)
            self.files.append({"path": path, "md5sum": md5sum})
            files_created += 1

    def tearDown(self):
        shutil.rmtree(self.extract_dir)
        shutil.rmtree(self.working_dir)

    def extract_archive_file(self, archive_file):
        tar = tarfile.open(archive_file, mode="r:gz")
        for tarinfo in tar:
            tar.extract(tarinfo, self.extract_dir)

    def extract_archive_blob(self, blob):
        # handle the tarball
        temp_path = create_temp_file(
            file_dir=self.working_dir,
            write_path_to_file=False)
        with open(temp_path, 'w') as temp_file:
            temp_file.write(blob)
            temp_file.seek(0)
        shutil.move(temp_path, "%s.tar.gz" % temp_path)

        tarball = GlideinTar()
        self.assertTrue(
            tarball.is_tarfile(
                "%s.tar.gz" %
                temp_path),
            "Blob tarball fails tarball.is_tarfile test")

        self.extract_archive_file("%s.tar.gz" % temp_path)

    def create_archive_file(self):
        random_file_name = create_random_string()
        archive_file = "%s/%s.tar.gz" % (self.working_dir, random_file_name)
        tarball = GlideinTar()
        for f in self.files:
            tarball.add_file(f["path"], "/")
        tarball.create_tar_file(archive_file)
        self.assertTrue(
            tarball.is_tarfile(archive_file),
            "Tarball creation failed.  tarball.is_tarfile returned False")
        return archive_file

    def create_archive_blob(self):
        tarball = GlideinTar()
        for k in self.strings.keys():
            tarball.add_string(k, self.strings[k])

        binary_string = tarball.create_tar_blob()
        return binary_string

    def test_tarSupport_file(self):
        archive_file = self.create_archive_file()
        self.extract_archive_file(archive_file)
        files = os.listdir(self.extract_dir)
        msg = "The number of files in the extract directory does not equal the number of files add to the archive."
        self.assertTrue(len(files) == len(self.files), msg)

        extract_files = []
        for f in files:
            md5sum = extract_md5("%s/%s" % (self.extract_dir, f))
            extract_files.append({"path": "%s/%s" %
                                  (self.extract_dir, f), "md5sum": md5sum})

        for file_dict in self.files:
            for extract_dict in extract_files:
                if (os.path.basename(file_dict["path"]) == os.path.basename(extract_dict["path"])) and \
                   (file_dict["md5sum"] == extract_dict["md5sum"]):
                    extract_files.remove(extract_dict)
                    break
        self.assertTrue(
            len(extract_files) == 0,
            "At least one original file's md5sum did not match the extracted file's md5sum")
        # clean up for next test
        for f in files:
            os.remove("%s/%s" % (self.extract_dir, f))

    def test_tarSupport_blob(self):
        archive_blob = self.create_archive_blob()
        self.extract_archive_blob(archive_blob)
        extracted_files = os.listdir(self.extract_dir)
        msg = "The number of files in the extract directory does not equal the number of strings added to the archive."

        self.assertTrue(len(extracted_files) == len(self.strings.keys()), msg)

        for f in extracted_files:
            fd = open("%s/%s" % (self.extract_dir, f), 'r')
            file_contents = fd.read()
            self.assertTrue(
                f in self.strings.keys(),
                "a file was found that doesn't exist in the keys for the strings files")
            self.assertTrue(
                file_contents == self.strings[f],
                "a file was found that doesn't exist in the keys for the strings files")


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
