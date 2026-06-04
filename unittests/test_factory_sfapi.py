#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the SFAPI BLAHP prototype helpers."""

import io
import os
import socket
import subprocess
import sys
import tempfile
import types
import unittest

from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


def install_m2crypto_stub():
    """Allow importing Factory modules on systems without M2Crypto."""

    if "M2Crypto" in sys.modules:
        return

    m2crypto = types.ModuleType("M2Crypto")
    for submodule in ("BIO", "Err", "EVP", "RSA", "Rand", "X509"):
        module = types.ModuleType("M2Crypto.%s" % submodule)
        setattr(m2crypto, submodule, module)
        sys.modules["M2Crypto.%s" % submodule] = module

    m2crypto.RSA.no_padding = 0
    m2crypto.RSA.pkcs1_padding = 1
    m2crypto.RSA.pkcs1_oaep_padding = 2
    m2crypto.RSA.sslv23_padding = 3
    m2crypto.RSA.RSAError = Exception
    m2crypto.BIO.BIOError = Exception
    sys.modules["M2Crypto"] = m2crypto


class TestSfapiHelperPureFunctions(unittest.TestCase):
    def test_remote_workdir_uses_pscratch_user_bucket(self):
        from glideinwms.factory.sfapi import sfapi_helpers

        self.assertEqual(
            "/pscratch/sd/m/mmajumde/.gwms-sfapi/gwms_123",
            sfapi_helpers.build_remote_workdir("gwms_123", "mmajumde"),
        )

    def test_submit_script_preserves_shebang_before_sbatch_directives(self):
        from glideinwms.factory.sfapi import sfapi_helpers

        script = "#!/bin/bash\necho started\n"
        rendered = sfapi_helpers.build_submit_script(script, "/remote/work", "pilot")

        self.assertTrue(rendered.startswith("#!/bin/bash\n#SBATCH --output=/remote/work/pilot.out\n"))
        self.assertIn("#SBATCH --error=/remote/work/pilot.err\n", rendered)
        self.assertIn("#SBATCH --chdir=/remote/work\n", rendered)
        self.assertTrue(rendered.endswith("echo started\n"))

    def test_parse_blahp_job_id_accepts_sfapi_date_jobid(self):
        from glideinwms.factory.sfapi import sfapi_helpers

        self.assertEqual(("20260526", "12345"), sfapi_helpers.parse_blahp_job_id("sfapi/20260526/12345"))
        self.assertEqual(
            ("20260526", "12345"), sfapi_helpers.parse_blahp_job_id("BLAHP_JOBID_PREFIXsfapi/20260526/12345")
        )

    def test_resolve_auth_reads_frontend_auth_file_bundle(self):
        from glideinwms.factory.sfapi import sfapi_helpers

        authlib = types.ModuleType("authlib")
        jose = types.ModuleType("authlib.jose")

        class FakeJsonWebKey:
            @staticmethod
            def import_key(data):
                return {"imported": data}

        jose.JsonWebKey = FakeJsonWebKey
        sys.modules["authlib"] = authlib
        sys.modules["authlib.jose"] = jose

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / "sfapi-auth.json"
            auth_file.write_text(
                '{"client_id": "frontend-client", "private_key_jwk": {"kty": "RSA", "n": "abc", "e": "AQAB"}}'
            )

            client_id, key = sfapi_helpers.resolve_auth(
                {
                    "SFAPI_AUTH_MODE": "auth_file",
                    "SFAPI_AUTH_FILE": str(auth_file),
                    "SFAPI_CLIENT_ID_FILE": "/factory/local/clientid",
                    "SFAPI_PRIVATE_KEY_JWK_FILE": "/factory/local/key.jwk",
                }
            )

        self.assertEqual("frontend-client", client_id)
        self.assertEqual({"imported": {"kty": "RSA", "n": "abc", "e": "AQAB"}}, key)

    def test_resolve_auth_without_auth_file_does_not_use_factory_defaults(self):
        from glideinwms.factory.sfapi import sfapi_helpers

        with self.assertRaisesRegex(RuntimeError, "SFAPI_AUTH_FILE"):
            sfapi_helpers.resolve_auth({})

    def test_apply_job_metadata_overrides_ambient_auth_file(self):
        from glideinwms.factory.sfapi import sfapi_helpers

        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            jobstate = state_dir / "20260526_12345"
            jobstate.write_text(
                "meta::auth_mode:auth_file\n"
                "meta::auth_file:/factory/client-proxies/user_frontend/credential_client_sfapi\n"
                "meta::resource:perlmutter\n"
                "meta::python:/opt/gwms/sfapi/bin/python\n"
            )

            with mock.patch.dict(
                os.environ,
                {
                    "SFAPI_AUTH_FILE": "/factory-local/sfapi-auth.json",
                    "SFAPI_RESOURCE": "wrong-resource",
                },
                clear=False,
            ):
                sfapi_helpers.apply_job_metadata("sfapi/20260526/12345", state_dir=str(state_dir))

                self.assertEqual("auth_file", os.environ["SFAPI_AUTH_MODE"])
                self.assertEqual(
                    "/factory/client-proxies/user_frontend/credential_client_sfapi",
                    os.environ["SFAPI_AUTH_FILE"],
                )
                self.assertEqual("perlmutter", os.environ["SFAPI_RESOURCE"])
                self.assertEqual("/opt/gwms/sfapi/bin/python", os.environ["SFAPI_PYTHON"])


class FakeRemoteFile:
    def __init__(self, payload):
        self.payload = payload

    def is_dir(self):
        return False

    def download(self, binary=False):
        if binary:
            return io.BytesIO(self.payload)
        return io.StringIO(self.payload.decode())


class FakeRemotePath:
    files = {}
    return_text_for_binary = False

    def __init__(self, path=None, compute=None):
        self.path = path
        self.compute = compute

    def download(self, binary=False):
        if binary and self.return_text_for_binary:
            return io.StringIO(self.files[self.path].decode())
        return FakeRemoteFile(self.files[self.path]).download(binary=binary)


class TestSfapiDownload(unittest.TestCase):
    def test_download_job_outputs_creates_local_parents_and_removes_state(self):
        from glideinwms.factory.sfapi import sfapi_helpers

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            state_dir = tmp / "state"
            state_dir.mkdir()
            jobstate = state_dir / "20260526_12345"
            local_out = tmp / "nested" / "pilot.out"
            jobstate.write_text("stdout::%s:/remote/pilot.out\n" % local_out)
            FakeRemotePath.files = {"/remote/pilot.out": b"pilot output\n"}

            sfapi_helpers.download_job_outputs(
                "sfapi/20260526/12345",
                transfer_compute=object(),
                remote_path_cls=FakeRemotePath,
                state_dir=str(state_dir),
            )

            self.assertEqual(b"pilot output\n", local_out.read_bytes())
            self.assertFalse(jobstate.exists())

    def test_download_job_outputs_accepts_text_from_binary_download(self):
        from glideinwms.factory.sfapi import sfapi_helpers

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            state_dir = tmp / "state"
            state_dir.mkdir()
            jobstate = state_dir / "20260526_12345"
            local_out = tmp / "nested" / "pilot.out"
            jobstate.write_text("stdout::%s:/remote/pilot.out\n" % local_out)
            FakeRemotePath.files = {"/remote/pilot.out": b"pilot output\n"}
            FakeRemotePath.return_text_for_binary = True
            try:
                sfapi_helpers.download_job_outputs(
                    "sfapi/20260526/12345",
                    transfer_compute=object(),
                    remote_path_cls=FakeRemotePath,
                    state_dir=str(state_dir),
                )
            finally:
                FakeRemotePath.return_text_for_binary = False

            self.assertEqual(b"pilot output\n", local_out.read_bytes())
            self.assertFalse(jobstate.exists())


class FakeNode:
    def __init__(self, attrs=None, children=None, lists=None):
        self.attrs = attrs or {}
        self.children = children or {}
        self.lists = lists or {}

    def __getitem__(self, key):
        return self.attrs[key]

    def __contains__(self, key):
        return key in self.attrs

    def get(self, key, default=None):
        return self.attrs.get(key, default)

    def get_child(self, key):
        return self.children[key]

    def get_child_list(self, key):
        return self.lists.get(key, [])


def make_sfapi_entry(**overrides):
    attrs = {
        "auth_method": "auth_file",
        "enabled": "True",
        "gatekeeper": "api.nersc.gov",
        "gridtype": "batch sfapi",
        "sfapi_resource": "perlmutter",
        "verbosity": "std",
        "work_dir": "/tmp",
    }
    attrs.update(overrides)
    return FakeNode(
        attrs,
        children={
            "config": FakeNode(
                children={
                    "submit": FakeNode(lists={"submit_attrs": []}),
                }
            )
        },
        lists={"attrs": []},
    )


def make_factory_conf():
    return FakeNode(
        {"advertise_pilot_accounting": "False", "glidein_name": "gfactory"},
        children={"submit": FakeNode({"base_client_log_dir": "/tmp/client-log"})},
    )


class TestSfapiSubmitFileGeneration(unittest.TestCase):
    def test_batch_sfapi_submit_file_uses_sfapi_resource_without_bosco_assumptions(self):
        install_m2crypto_stub()
        from glideinwms.creation.lib.cgWCreate import GlideinSubmitDictFile

        submit_attrs = [FakeNode({"name": "+PrototypeAttr", "value": '"yes"'})]
        entry = make_sfapi_entry()
        entry.get_child("config").get_child("submit").lists["submit_attrs"] = submit_attrs
        conf = make_factory_conf()
        submit = GlideinSubmitDictFile(tempfile.gettempdir(), "job.condor")

        submit.populate("glidein_startup.sh", "SFAPI", conf, entry)

        self.assertEqual("batch sfapi", submit["Grid_Resource"])
        self.assertNotIn("GLIDEIN_REMOTE_USERNAME", submit["environment"])
        self.assertIn("X509_USER_PROXY=$ENV(X509_USER_PROXY_BASENAME:/dev/null)", submit["environment"])
        self.assertEqual('"yes"', submit["+PrototypeAttr"])
        self.assertEqual('"batch sfapi"', submit["+GlideinGridType"])
        self.assertEqual('"$ENV(SFAPI_RESOURCE:perlmutter)"', submit["+GlideinSFAPIResource"])
        self.assertEqual('"$ENV(SFAPI_TRANSFER_MACHINE:dtns)"', submit["+GlideinSFAPITransferMachine"])

    def test_batch_sfapi_grid_resource_uses_configured_glite_dir(self):
        install_m2crypto_stub()
        from glideinwms.creation.lib.cgWCreate import GlideinSubmitDictFile

        entry = make_sfapi_entry(sfapi_glite_dir="/opt/glite")
        conf = make_factory_conf()
        submit = GlideinSubmitDictFile(tempfile.gettempdir(), "job.condor")

        submit.populate("glidein_startup.sh", "SFAPI", conf, entry)

        self.assertEqual("batch sfapi --rgahp-glite /opt/glite api.nersc.gov", submit["Grid_Resource"])


class TestSfapiLocalSubmitAttributes(unittest.TestCase):
    def run_local_submit_attributes(self, extra_env):
        script = Path(__file__).resolve().parents[1] / "factory/sfapi/sfapi_local_submit_attributes.sh"
        env = os.environ.copy()
        env.update(extra_env)
        return subprocess.check_output(["bash", str(script)], env=env, text=True)

    def test_accepts_bosco_style_walltime_attribute(self):
        output = self.run_local_submit_attributes({"Walltime": "02:00:00"})

        self.assertIn("#SBATCH --time=02:00:00\n", output)

    def test_uppercase_walltime_still_works(self):
        output = self.run_local_submit_attributes({"WALLTIME": "02:00:00"})

        self.assertIn("#SBATCH --time=02:00:00\n", output)


class TestSfapiStatusScript(unittest.TestCase):
    def write_fake_python(self, path):
        path.write_text(
            "#!/bin/bash\n"
            'if [ "$1" = "-c" ]; then exit 0; fi\n'
            'case "$2" in\n'
            '  status) echo "SFAPI_STATUS:12345:${FAKE_SFAPI_STATE}"; exit 0 ;;\n'
            "  download) exit 0 ;;\n"
            "esac\n"
            "exit 1\n"
        )
        path.chmod(0o755)

    def write_setup_failing_python(self, path):
        path.write_text('#!/bin/bash\nif [ "$1" = "-c" ]; then exit 1; fi\nexit 1\n')
        path.chmod(0o755)

    def run_status_script_with_state(self, state):
        script = Path(__file__).resolve().parents[1] / "factory/sfapi/sfapi_status.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_python = Path(tmpdir) / "fake-python"
            self.write_fake_python(fake_python)
            env = os.environ.copy()
            env["SFAPI_PYTHON"] = str(fake_python)
            env["FAKE_SFAPI_STATE"] = state
            return subprocess.check_output(
                ["bash", str(script), "sfapi/20260526/12345"],
                env=env,
                text=True,
            )

    def test_failed_slurm_state_reports_terminal_nonzero_exit(self):
        output = self.run_status_script_with_state("FAILED")

        self.assertEqual('0[BatchJobId="12345";JobStatus=4;ExitCode=1;]\n', output)

    def test_status_preloads_python_from_job_metadata_before_setup_check(self):
        script = Path(__file__).resolve().parents[1] / "factory/sfapi/sfapi_status.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fake_python = tmp / "fake-python"
            self.write_fake_python(fake_python)
            state_dir = tmp / ".blah" / "sfapi_jobs"
            state_dir.mkdir(parents=True)
            (state_dir / "20260526_12345").write_text("meta::python:%s\n" % fake_python)

            env = os.environ.copy()
            env["SFAPI_PYTHON"] = "/bin/false"
            env["HOME"] = str(tmp)
            env["FAKE_SFAPI_STATE"] = "COMPLETED"
            output = subprocess.check_output(
                ["bash", str(script), "sfapi/20260526/12345"],
                env=env,
                text=True,
            )

        self.assertEqual('0[BatchJobId="12345";JobStatus=4;ExitCode=0;]\n', output)

    def test_setup_failure_reports_blahp_errors_for_status_and_cancel(self):
        status_script = Path(__file__).resolve().parents[1] / "factory/sfapi/sfapi_status.sh"
        cancel_script = Path(__file__).resolve().parents[1] / "factory/sfapi/sfapi_cancel.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_python = Path(tmpdir) / "fake-python"
            self.write_setup_failing_python(fake_python)
            env = os.environ.copy()
            env["SFAPI_PYTHON"] = str(fake_python)

            status_output = subprocess.check_output(
                ["bash", str(status_script), "sfapi/20260526/12345"],
                env=env,
                text=True,
            )
            cancel_output = subprocess.check_output(
                ["bash", str(cancel_script), "sfapi/20260526/12345"],
                env=env,
                text=True,
            )

        self.assertIn('1[BatchJobId="12345";Reason="SFAPI setup error:', status_output)
        self.assertIn("sfapi_client is not importable", status_output)
        self.assertIn(" 1 SFAPI\\ setup\\ error:", cancel_output)
        self.assertIn("sfapi_client\\ is\\ not\\ importable", cancel_output)


class TestSfapiHelperStatus(unittest.TestCase):
    def test_job_status_prints_structured_output_for_wrapper(self):
        from glideinwms.factory.sfapi import sfapi_helpers

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def compute(self, resource):
                return object()

        args = types.SimpleNamespace(type="job", value="sfapi/20260526/12345")
        stdout = io.StringIO()
        with mock.patch.object(sfapi_helpers, "apply_job_metadata"), mock.patch.object(
            sfapi_helpers, "sfapi_client", return_value=FakeClient()
        ), mock.patch.object(sfapi_helpers, "get_job_state", return_value="RUNNING"), redirect_stdout(stdout):
            retcode = sfapi_helpers.status(args)

        self.assertEqual(0, retcode)
        self.assertEqual("SFAPI_STATUS:12345:RUNNING\n", stdout.getvalue())


class TestSfapiFactoryEnvironment(unittest.TestCase):
    def test_append_sfapi_environment_uses_frontend_auth_file_credential(self):
        install_m2crypto_stub()
        socket.gethostbyname_ex = lambda name: (name, [], ["127.0.0.1"])
        from glideinwms.factory import glideFactoryLib

        job_descript = types.SimpleNamespace(data={"SfapiResource": "perlmutter", "SfapiGliteDir": "/opt/glite"})
        submit_credentials = types.SimpleNamespace(
            security_credentials={
                "AuthFile": "/factory/client-proxies/user_frontend/glidein_test/credential_client_sfapi",
                "GlideinProxy": "/factory/client-proxies/user_frontend/glidein_test/credential_client_pilot",
            }
        )
        with mock.patch.dict(
            os.environ,
            {
                "SFAPI_CLIENT_ID_FILE": "/factory-local/clientid",
                "SFAPI_PRIVATE_KEY_JWK_FILE": "/factory-local/key.jwk",
            },
            clear=False,
        ):
            env = glideFactoryLib.append_sfapi_environment(
                [],
                {
                    "SFAPI_AUTH_MODE": "env",
                    "SFAPI_CLIENT_ID": "factory-local-client",
                    "SFAPI_PRIVATE_KEY_JWK": "factory-local-key",
                    "SFAPI_TRANSFER_MACHINE": "dtns",
                },
                job_descript,
                submit_credentials,
            )

        self.assertIn("SFAPI_RESOURCE=perlmutter", env)
        self.assertIn("SFAPI_AUTH_MODE=auth_file", env)
        self.assertIn("SFAPI_AUTH_FILE=/factory/client-proxies/user_frontend/glidein_test/credential_client_sfapi", env)
        self.assertIn("SFAPI_TRANSFER_MACHINE=dtns", env)
        self.assertFalse(any(item.startswith("SFAPI_CLIENT_ID=") for item in env))
        self.assertFalse(any(item.startswith("SFAPI_PRIVATE_KEY_JWK=") for item in env))
        self.assertFalse(any(item.startswith("SFAPI_CLIENT_ID_FILE=") for item in env))
        self.assertFalse(any(item.startswith("SFAPI_PRIVATE_KEY_JWK_FILE=") for item in env))
        self.assertFalse(any(item.startswith("GLIDEIN_REMOTE_USERNAME=") for item in env))

    def test_v3_11_submit_environment_includes_sfapi_auth_file(self):
        install_m2crypto_stub()
        socket.gethostbyname_ex = lambda name: (name, [], ["127.0.0.1"])
        from glideinwms.factory import glideFactoryLib
        from glideinwms.lib.credentials import CredentialDict, CredentialPurpose
        from glideinwms.lib.credentials.text import TextCredential

        auth_file = TextCredential(string=b"{}", purpose=CredentialPurpose.REQUEST)
        auth_file.path = "/factory/client-proxies/user_frontend/glidein_test/credential_client_sfapi"
        security_credentials = CredentialDict()
        security_credentials.add(auth_file, "auth_file")
        submit_credentials = types.SimpleNamespace(
            username="frontend",
            security_class="frontend",
            id="credential-id",
            security_credentials=security_credentials,
            identity_credentials=CredentialDict(),
            parameters={},
        )

        glidein_descript = types.SimpleNamespace(
            data={
                "GlideinName": "gfactory_instance",
                "FactoryName": "gfactory_service",
                "WebURL": "http://factory/stage",
            }
        )
        job_descript = types.SimpleNamespace(
            data={
                "GridType": "batch sfapi",
                "Schedd": "factory.example.org",
                "Verbosity": "std",
                "StartupDir": "AUTO",
                "SubmitSlotsLayout": "fixed",
                "SfapiResource": "perlmutter",
            }
        )
        job_attributes = types.SimpleNamespace(data={})
        signatures = types.SimpleNamespace(
            data={
                "main_descript": "description.cfg",
                "main_sign": "main-sign",
                "entry_entry_descript": "description.entry.cfg",
                "entry_entry_sign": "entry-sign",
            }
        )

        with mock.patch.object(glideFactoryLib.glideFactoryConfig, "GlideinDescript", return_value=glidein_descript), mock.patch.object(
            glideFactoryLib.glideFactoryConfig, "JobDescript", return_value=job_descript
        ), mock.patch.object(glideFactoryLib.glideFactoryConfig, "JobAttributes", return_value=job_attributes), mock.patch.object(
            glideFactoryLib.glideFactoryConfig, "SignatureFile", return_value=signatures
        ), mock.patch.object(
            glideFactoryLib.timeConversion, "get_time_in_format", return_value="20260603"
        ):
            env = glideFactoryLib.get_submit_environment_v3_11(
                "entry",
                "frontend-workspace.main",
                submit_credentials,
                None,
                {"SFAPI_TRANSFER_MACHINE": "dtns"},
                1200,
                log=types.SimpleNamespace(debug=lambda *args: None, warning=lambda *args: None, exception=lambda *args: None),
            )

        self.assertIn("SFAPI_RESOURCE=perlmutter", env)
        self.assertIn("SFAPI_AUTH_MODE=auth_file", env)
        self.assertIn(
            "SFAPI_AUTH_FILE=/factory/client-proxies/user_frontend/glidein_test/credential_client_sfapi",
            env,
        )
        self.assertIn("SFAPI_TRANSFER_MACHINE=dtns", env)


if __name__ == "__main__":
    unittest.main()
