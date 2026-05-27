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
        self.assertEqual(("20260526", "12345"), sfapi_helpers.parse_blahp_job_id("BLAHP_JOBID_PREFIXsfapi/20260526/12345"))

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

    def __init__(self, path=None, compute=None):
        self.path = path
        self.compute = compute

    def download(self, binary=False):
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


class TestSfapiSubmitFileGeneration(unittest.TestCase):
    def test_batch_sfapi_grid_resource_skips_bosco_username(self):
        install_m2crypto_stub()
        from glideinwms.creation.lib.cgWCreate import GlideinSubmitDictFile

        submit_attrs = [FakeNode({"name": "+PrototypeAttr", "value": '"yes"'})]
        entry = FakeNode(
            {
                "auth_method": "auth_file",
                "enabled": "True",
                "gatekeeper": "api.nersc.gov",
                "gridtype": "batch sfapi",
                "sfapi_resource": "perlmutter",
                "verbosity": "std",
                "work_dir": "/tmp",
            },
            children={
                "config": FakeNode(
                    children={
                        "submit": FakeNode(lists={"submit_attrs": submit_attrs}),
                    }
                )
            },
            lists={"attrs": []},
        )
        conf = FakeNode(
            {"advertise_pilot_accounting": "False", "glidein_name": "gfactory"},
            children={"submit": FakeNode({"base_client_log_dir": "/tmp/client-log"})},
        )
        submit = GlideinSubmitDictFile(tempfile.gettempdir(), "job.condor")

        submit.populate("glidein_startup.sh", "SFAPI", conf, entry)

        self.assertEqual("batch sfapi", submit["Grid_Resource"])
        self.assertNotIn("GLIDEIN_REMOTE_USERNAME", submit["environment"])
        self.assertIn("X509_USER_PROXY=$ENV(X509_USER_PROXY_BASENAME:/dev/null)", submit["environment"])
        self.assertEqual('"yes"', submit["+PrototypeAttr"])


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


if __name__ == "__main__":
    unittest.main()
