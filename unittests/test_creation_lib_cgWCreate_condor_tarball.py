#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Tests for Condor tarball packaging in cgWCreate.py."""

import tarfile
import tempfile
import unittest

from pathlib import Path

from glideinwms.creation.lib.cgWCreate import create_condor_tar_fd


def make_minimal_condor_tree(base_dir):
    for dirname in ("sbin", "lib", "lib64/condor", "libexec/condor"):
        (base_dir / dirname).mkdir(parents=True, exist_ok=True)
    for exe in ("condor_master", "condor_startd", "condor_starter"):
        path = base_dir / "sbin" / exe
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    setup = base_dir / "libexec/condor/condor_ssh_to_job_sshd_setup"
    setup.write_text("#!/bin/sh\nexit 0\n")
    setup.chmod(0o755)


class TestCondorTarball(unittest.TestCase):
    def test_packages_ssh_to_job_files_from_rpm_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            make_minimal_condor_tree(tmp)
            template = tmp / "lib64/condor/condor_ssh_to_job_sshd_config_template"
            template.write_text("sshd config template\n")
            (tmp / "lib/condor_ssh_to_job_sshd_config_template").symlink_to(
                "../lib64/condor/condor_ssh_to_job_sshd_config_template"
            )
            libgetpwnam = tmp / "lib64/condor/libgetpwnam.so"
            libgetpwnam.write_bytes(b"libgetpwnam\n")
            (tmp / "lib/libgetpwnam.so").symlink_to("../lib64/condor/libgetpwnam.so")

            tar_fd = create_condor_tar_fd(str(tmp))

            with tarfile.open(fileobj=tar_fd, mode="r:gz") as tar:
                template_members = [
                    member for member in tar.getmembers() if member.name == "lib/condor_ssh_to_job_sshd_config_template"
                ]
                self.assertEqual(1, len(template_members))
                self.assertTrue(template_members[0].isreg(), template_members[0])
                self.assertEqual(
                    b"sshd config template\n",
                    tar.extractfile(template_members[0]).read(),
                )
                lib_members = [member for member in tar.getmembers() if member.name == "lib/libgetpwnam.so"]
                self.assertEqual(1, len(lib_members))
                self.assertTrue(lib_members[0].isreg(), lib_members[0])
                self.assertEqual(b"libgetpwnam\n", tar.extractfile(lib_members[0]).read())
                self.assertIn("libexec/condor_ssh_to_job_sshd_setup", tar.getnames())

    def test_rejects_ssh_to_job_symlink_outside_condor_base(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            outside = tmp / "outside"
            condor_base = tmp / "condor"
            make_minimal_condor_tree(condor_base)
            outside.write_text("external library\n")
            (condor_base / "lib/libgetpwnam.so").symlink_to(outside)

            with self.assertRaises(RuntimeError) as ctx:
                create_condor_tar_fd(str(condor_base))

            self.assertIn("resolves outside", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
