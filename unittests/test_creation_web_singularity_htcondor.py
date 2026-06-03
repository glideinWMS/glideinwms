#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Tests for HTCondor-managed Singularity support in glideins."""

import shutil
import subprocess
import tempfile
import textwrap
import unittest

from pathlib import Path

CONDOR_STARTUP = Path("../creation/web_base/condor_startup.sh").resolve()
SINGULARITY_SETUP = Path("../creation/web_base/singularity_setup.sh").resolve()
CONFIG_ATTRIBUTES = Path("../creation/lib/config_attributes.txt").resolve()


class TestHtcondorManagedSingularity(unittest.TestCase):
    def test_condor_startup_writes_htcondor_singularity_config_from_flag(self):
        tmp = self.run_condor_startup_advertise_only(
            htcondor_managed=True,
            gwms_singularity_image="/cvmfs/example/default.sif",
            cvmfs_mount_dir="/custom/cvmfs",
        )
        condor_config = (tmp / "condor_config").read_text()

        self.assertIn("USER_JOB_WRAPPER =", condor_config)
        self.assertNotIn("USER_JOB_WRAPPER = $(LOCAL_DIR)/condor_job_wrapper.sh", condor_config)
        self.assertIn('GWMS_DEFAULT_SINGULARITY_IMAGE = "/cvmfs/example/default.sif"', condor_config)
        self.assertIn(
            'SINGULARITY_IMAGE_EXPR = ifThenElse(!isUndefined(TARGET.SingularityImage) '
            '&& TARGET.SingularityImage =!= "", TARGET.SingularityImage, $(GWMS_DEFAULT_SINGULARITY_IMAGE))',
            condor_config,
        )
        self.assertIn('SINGULARITY_JOB = $(SINGULARITY_IMAGE_EXPR) =!= ""', condor_config)
        self.assertNotIn("TARGET.REQUIRED_OS", condor_config)
        self.assertNotIn("SINGULARITY_IMAGES_DICT", condor_config)
        self.assertIn("SINGULARITY_TARGET_DIR = /srv", condor_config)
        self.assertIn("MOUNT_UNDER_SCRATCH = /tmp,/var/tmp", condor_config)
        self.assertIn("SINGULARITY_USE_LAUNCHER = True", condor_config)
        self.assertIn("SINGULARITY_USE_PID_NAMESPACES = False", condor_config)
        self.assertIn("/custom/cvmfs:/cvmfs", condor_config)
        self.assertNotIn("SINGULARITY_IS_SETUID", condor_config)
        self.assertIn("SINGULARITY = /opt/apptainer/bin/apptainer", condor_config)

    def test_condor_startup_leaves_native_ssh_to_job_shell_setup_in_place(self):
        condor_dir = self.make_condor_dir_with_ssh_to_job_shell_setup()
        tmp = self.run_condor_startup_advertise_only(htcondor_managed=True, condor_dir=condor_dir)
        shell_setup = condor_dir / "libexec/condor_ssh_to_job_shell_setup"
        original = condor_dir / "libexec/condor_ssh_to_job_shell_setup.gwms-orig"

        self.assertFalse(original.exists())
        self.assertIn("ORIGINAL_SHELL_SETUP", shell_setup.read_text())
        self.assertNotIn("GWMS_SINGULARITY_USE_HTCONDOR", (tmp / "condor_job_wrapper.sh").read_text())

    def test_condor_startup_maps_bind_paths_and_extra_args_to_htcondor(self):
        tmp = self.run_condor_startup_advertise_only(
            htcondor_managed=True,
            bindpath="/scratch:/srv/scratch,/data",
            bindpath_default="/project",
            bind_cvmfs=False,
            cvmfs_mount_dir="/cvmfs",
            singularity_opts="--no-home --fakeroot",
        )
        condor_config = (tmp / "condor_config").read_text()

        self.assertIn(
            'SINGULARITY_BIND_EXPR = "/scratch:/srv/scratch /data /project"',
            condor_config,
        )
        self.assertNotIn(" /cvmfs", condor_config)
        self.assertIn('SINGULARITY_EXTRA_ARGUMENTS = "--no-home --fakeroot"', condor_config)

    def test_condor_startup_warns_when_no_default_image_was_selected(self):
        tmp = self.run_condor_startup_advertise_only(htcondor_managed=True)
        condor_config = (tmp / "condor_config").read_text()
        stderr = (tmp / "condor_startup.stderr").read_text()

        self.assertIn('GWMS_DEFAULT_SINGULARITY_IMAGE = ""', condor_config)
        self.assertIn("WARNING: GLIDEIN_SINGULARITY_USE_HTCONDOR is enabled", stderr)
        self.assertIn("no default Singularity image was selected by setup", stderr)
        self.assertIn("jobs without +SingularityImage will run without Singularity", stderr)

    def test_condor_startup_warns_when_container_env_policy_is_not_translated(self):
        tmp = self.run_condor_startup_advertise_only(
            htcondor_managed=True,
            container_env="BEARER_TOKEN_FILE,SCITOKEN_FILE",
            container_env_clearlist="BEARER_TOKEN_FILE,SCITOKEN_FILE",
        )
        stderr = (tmp / "condor_startup.stderr").read_text()

        self.assertIn("WARNING: GLIDEIN_CONTAINER_ENV or GLIDEIN_CONTAINER_ENV_CLEARLIST is set", stderr)
        self.assertIn("does not translate GWMS container environment policies", stderr)

    def test_condor_startup_falls_back_without_flag_or_binary(self):
        for kwargs in ({"htcondor_managed": True, "singularity_path": ""}, {"htcondor_managed": False}):
            with self.subTest(kwargs=kwargs):
                tmp = self.run_condor_startup_advertise_only(**kwargs)
                condor_config = (tmp / "condor_config").read_text()
                condor_job_wrapper = (tmp / "condor_job_wrapper.sh").read_text()

                self.assertNotIn("GWMS_DEFAULT_SINGULARITY_IMAGE", condor_config)
                self.assertNotIn("SINGULARITY_IMAGE_EXPR =", condor_config)
                self.assertNotIn("SINGULARITY_TARGET_DIR = /srv", condor_config)
                self.assertIn("USER_JOB_WRAPPER = $(LOCAL_DIR)/condor_job_wrapper.sh", condor_config)
                self.assertNotIn("GWMS_SINGULARITY_USE_HTCONDOR", condor_job_wrapper)

    def test_htcondor_singularity_flag_is_registered_as_config_attribute(self):
        config_attributes = CONFIG_ATTRIBUTES.read_text()

        self.assertIn("GLIDEIN_SINGULARITY_USE_HTCONDOR", config_attributes)
        self.assertNotIn("GLIDEIN_SINGULARITY_SSH_REENTER", config_attributes)

    def test_singularity_setup_does_not_require_empty_default_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            setup = tmp / "singularity_setup.sh"
            shutil.copy(SINGULARITY_SETUP, setup)
            setup.chmod(0o755)
            (tmp / "singularity_lib.sh").write_text(textwrap.dedent("""\
                    info_stdout() { echo "$*"; }
                    info() { echo "$*" >&2; }
                    info_dbg() { :; }
                    warn() { echo "$*" >&2; }
                    singularity_get_image() { return 1; }
                    cvmfs_resolve_path() { echo "$1"; }
                    uri_is_valid_file_or_remote() { return 1; }
                    singularity_get_image_default() { echo "/tmp/test-image.sif"; }
                    singularity_locate_bin() {
                        HAS_SINGULARITY=True
                        GWMS_SINGULARITY_PATH=/usr/bin/apptainer
                        GWMS_SINGULARITY_VERSION=1.0
                        GWMS_CONTAINERSW_PATH=/usr/bin/apptainer
                        GWMS_CONTAINERSW_VERSION=1.0
                        GWMS_CONTAINERSW_FULL_VERSION="apptainer version 1.0"
                        GWMS_SINGULARITY_MODE=unprivileged
                        GWMS_CONTAINERSW_MODE=unprivileged
                    }
                    advertise() {
                        gconfig_add "$1" "$2"
                        condor_vars_file=$(gconfig_get CONDOR_VARS_FILE "$glidein_config")
                        add_condor_vars_line "$1" "$3" "-" "+" "Y" "Y" "+"
                    }
                    """))
            (tmp / "add_config_line.source").write_text(textwrap.dedent("""\
                    gconfig_get() {
                        grep -i "^$1 " "$2" 2>/dev/null | tail -1 | cut -d ' ' -f 2-
                    }
                    gconfig_get_tolower() {
                        gconfig_get "$@" | tr '[:upper:]' '[:lower:]'
                    }
                    gconfig_add() {
                        echo "$1 $2" >> "$glidein_config"
                    }
                    add_condor_vars_line() {
                        echo "$@" >> "$condor_vars_file"
                    }
                    """))
            (tmp / "error_gen.sh").write_text("#!/bin/sh\nexit 0\n")
            (tmp / "error_gen.sh").chmod(0o755)
            condor_vars = tmp / "condor_vars.lst"
            condor_vars.write_text("")
            config = tmp / "glidein_config"
            config.write_text(
                "ADD_CONFIG_LINE_SOURCE %s\n"
                "ERROR_GEN_PATH %s\n"
                "CONDOR_VARS_FILE %s\n"
                "GLIDEIN_Singularity_Use PREFERRED\n"
                "GLIDEIN_SINGULARITY_REQUIRE PREFERRED\n"
                "SINGULARITY_IMAGE_REQUIRED false\n"
                "SINGULARITY_IMAGE_RESTRICTIONS cvmfs\n"
                "SINGULARITY_IMAGES_DICT rhel9:/cvmfs/example/rhel9.sif\n"
                % (tmp / "add_config_line.source", tmp / "error_gen.sh", condor_vars)
            )

            result = subprocess.run(
                ["bash", str(setup), str(config)],
                cwd=str(tmp),
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.assertEqual(0, result.returncode, "stdout:\n%s\nstderr:\n%s" % (result.stdout, result.stderr))
            self.assertNotIn("GWMS_SINGULARITY_IMAGE S - + Y Y +", condor_vars.read_text())

    def run_condor_startup_advertise_only(
        self,
        htcondor_managed,
        gwms_singularity_image="",
        singularity_path="/opt/apptainer/bin/apptainer",
        condor_dir=None,
        bindpath="",
        bindpath_default="",
        bind_cvmfs=None,
        cvmfs_mount_dir="",
        singularity_opts="",
        container_env="",
        container_env_clearlist="",
    ):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        main = tmp / "main"
        main.mkdir()
        (main / "description.cfg").write_text(
            "condor_config \tcondor_config\n"
            "condor_config_main_include \tcondor_config.dedicated_starter.include\n"
            "condor_config_monitor_include \tcondor_config.monitor.include\n"
            "condor_config_multi_include \tcondor_config.multi_schedd.include\n"
            "condor_config_check_include \tcondor_config.check.include\n"
        )
        (main / "condor_config").write_text("SINGULARITY_JOB = false\n")
        for include_file in (
            "condor_config.dedicated_starter.include",
            "condor_config.monitor.include",
            "condor_config.multi_schedd.include",
            "condor_config.check.include",
        ):
            (main / include_file).write_text("")
        (main / "advertise_failure.helper").write_text("#!/bin/sh\nexit 0\n")
        (main / "advertise_failure.helper").chmod(0o755)
        (tmp / "wrapper_list.lst").write_text("")
        (tmp / "logging_utils.source").write_text("glog_setup() { :; }\n")
        (tmp / "error_gen.sh").write_text("#!/bin/sh\nexit 0\n")
        (tmp / "error_gen.sh").chmod(0o755)
        (tmp / "add_config_line.source").write_text(textwrap.dedent("""\
                gconfig_get() {
                    grep -i "^$1 " "$2" 2>/dev/null | tail -1 | cut -d ' ' -f 2-
                }
                """))
        (tmp / "condor_vars.lst").write_text(
            'GLIDEIN_WRAPPER_EXEC S \\"\\\\\\$@\\" + N N -\n' "X509_EXPIRE I 4102444800 + N Y -\n"
        )
        config_lines = [
            "ADD_CONFIG_LINE_SOURCE %s" % (tmp / "add_config_line.source"),
            "ERROR_GEN_PATH %s" % (tmp / "error_gen.sh"),
            "GLIDEIN_WORK_DIR %s" % main,
            "DESCRIPTION_FILE description.cfg",
            "WRAPPER_LIST %s" % (tmp / "wrapper_list.lst"),
            "DEBUG_MODE 0",
            "GLIDEIN_ADVERTISE_ONLY 1",
            "GLIDEIN_ADVERTISE_DESTINATION VO",
            "GLIDEIN_ADVERTISE_TYPE UPDATE_STARTD_AD",
            "GLIDEIN_STARTUP_PID 12345",
            "CONDOR_VARS_FILE %s" % (tmp / "condor_vars.lst"),
            "LOGGING_UTILS_SOURCE %s" % (tmp / "logging_utils.source"),
            "GLIDEIN_Retire_Time 21600",
            "GLIDEIN_Job_Max_Time 3600",
            "GLIDEIN_Graceful_Shutdown 120",
            "GLIDEIN_Ignore_X509_Duration true",
            "GLIDEIN_Expose_X509 false",
            "X509_EXPIRE 4102444800",
        ]
        if condor_dir:
            config_lines.append("CONDOR_DIR %s" % condor_dir)
        if bindpath:
            config_lines.append("GLIDEIN_SINGULARITY_BINDPATH %s" % bindpath)
        if bindpath_default:
            config_lines.append("GLIDEIN_SINGULARITY_BINDPATH_DEFAULT %s" % bindpath_default)
        if bind_cvmfs is not None:
            config_lines.append("GWMS_SINGULARITY_BIND_CVMFS %s" % ("1" if bind_cvmfs else "0"))
        if cvmfs_mount_dir:
            config_lines.append("CVMFS_MOUNT_DIR %s" % cvmfs_mount_dir)
        if singularity_opts:
            config_lines.append("GLIDEIN_SINGULARITY_OPTS %s" % singularity_opts)
        if container_env:
            config_lines.append("GLIDEIN_CONTAINER_ENV %s" % container_env)
        if container_env_clearlist:
            config_lines.append("GLIDEIN_CONTAINER_ENV_CLEARLIST %s" % container_env_clearlist)
        if singularity_path:
            config_lines.append("SINGULARITY_PATH %s" % singularity_path)
        if htcondor_managed:
            config_lines.append("GLIDEIN_SINGULARITY_USE_HTCONDOR 'True'")
        if gwms_singularity_image:
            config_lines.append("GWMS_SINGULARITY_IMAGE %s" % gwms_singularity_image)
        config = tmp / "glidein_config"
        config.write_text("\n".join(config_lines) + "\n")

        result = subprocess.run(
            ["bash", str(CONDOR_STARTUP), str(config)],
            cwd=str(tmp),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        (tmp / "condor_startup.stdout").write_text(result.stdout)
        (tmp / "condor_startup.stderr").write_text(result.stderr)
        self.assertEqual(0, result.returncode, "stdout:\n%s\nstderr:\n%s" % (result.stdout, result.stderr))
        return tmp

    def make_condor_dir_with_ssh_to_job_shell_setup(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "bin").mkdir()
        (tmp / "libexec").mkdir()
        shell_setup = tmp / "libexec/condor_ssh_to_job_shell_setup"
        shell_setup.write_text("#!/bin/sh\necho ORIGINAL_SHELL_SETUP\n")
        shell_setup.chmod(0o755)
        return tmp

if __name__ == "__main__":
    unittest.main()
