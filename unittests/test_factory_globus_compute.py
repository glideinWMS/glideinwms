#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the Globus Compute factory submission scaffold."""

import unittest
import socket
import tempfile
import subprocess
import os
import time
import contextlib
import io
import base64
import hashlib
import json
import sys
from pathlib import Path
from unittest import mock

from glideinwms.creation.lib.cgWCreate import GlideinSubmitDictFile
from glideinwms.creation.lib.cgWParamDict import populate_job_descript
from glideinwms.creation.lib.factoryXmlConfig import parse
from glideinwms.creation.lib.cWDictFile import DictFile

socket.gethostbyname_ex = mock.Mock(return_value=("localhost", [], ["127.0.0.1"]))
from glideinwms.factory.glideFactoryLib import get_submit_environment, get_submit_environment_v3_11  # noqa: E402

TEST_DIR = Path(__file__).resolve().parent
XML = str(TEST_DIR / "fixtures/factory/glideinWMS.xml")


class EmptyCredentialCollection:
    def find(self, **_kwargs):
        return []

    def values(self):
        return []


class TextRequestCredentialCollection(EmptyCredentialCollection):
    def __init__(self, path):
        self.path = path

    def find(self, **kwargs):
        if str(kwargs.get("cred_type")) == "text" and str(kwargs.get("purpose")) == "request":
            return [self.path]
        return []


def make_globus_compute_entry(**overrides):
    conf = parse(XML)
    for entry in conf.get_entries():
        if entry.getName() == "TEST_SITE_1":
            gc_entry = entry
            break
    else:
        raise AssertionError("TEST_SITE_1 fixture entry not found")

    gc_entry["name"] = "TEST_GLOBUS_COMPUTE"
    gc_entry["gridtype"] = "batch globuscompute"
    gc_entry["gatekeeper"] = "globuscompute"
    gc_entry["auth_method"] = "auth_file"
    gc_entry["trust_domain"] = "globuscompute"
    gc_entry["globus_compute_endpoint"] = "29e26773-cf24-4574-b5d9-1e353fd4de72"
    gc_entry["globus_compute_function"] = "pilot-runner-function"
    gc_entry["globus_compute_glite_dir"] = "/opt/gwms/globuscompute/glite"
    gc_entry["globus_compute_python"] = "/opt/gwms/globus-compute-client/bin/python"
    gc_entry["globus_compute_user_dir"] = "/var/lib/gwms-factory/globus-compute-client"
    gc_entry["globus_compute_state_dir"] = "/var/lib/gwms-factory/globus-compute-state"
    for key, value in overrides.items():
        gc_entry[key] = value
    return conf, gc_entry


class TestGlobusComputeSubmitFileGeneration(unittest.TestCase):
    def test_batch_globuscompute_uses_globus_compute_glite_dir_without_bosco_username(self):
        conf, entry = make_globus_compute_entry()
        submit = GlideinSubmitDictFile(str(TEST_DIR / "fixtures/factory/work-dir"), entry["name"])

        submit.populate("glidein_startup.sh", entry["name"], conf, entry)

        self.assertEqual(
            "batch globuscompute",
            submit["Grid_Resource"],
        )
        self.assertNotIn("GLIDEIN_REMOTE_USERNAME", submit["Grid_Resource"])
        self.assertEqual('"batch globuscompute"', submit["+GlideinGridType"])
        self.assertIn("GLOBUS_COMPUTE_ENDPOINT=$ENV(GLOBUS_COMPUTE_ENDPOINT:)", submit["environment"])
        self.assertIn("GLOBUS_COMPUTE_FUNCTION=$ENV(GLOBUS_COMPUTE_FUNCTION:)", submit["environment"])
        self.assertIn("GLOBUS_COMPUTE_AUTH_FILE=$ENV(GLOBUS_COMPUTE_AUTH_FILE:)", submit["environment"])
        self.assertIn("GLOBUS_COMPUTE_PYTHON=$ENV(GLOBUS_COMPUTE_PYTHON:)", submit["environment"])
        self.assertIn("GLOBUS_COMPUTE_USER_DIR=$ENV(GLOBUS_COMPUTE_USER_DIR:)", submit["environment"])
        self.assertIn("GLOBUS_COMPUTE_STATE_DIR=$ENV(GLOBUS_COMPUTE_STATE_DIR:)", submit["environment"])
        self.assertEqual('"$ENV(GLOBUS_COMPUTE_ENDPOINT:)"', submit["+GlideinGlobusComputeEndpoint"])
        self.assertEqual("$ENV(IDENTITY_CREDENTIALS:)", submit["transfer_Input_files"])
        self.assertEqual("$ENV(IDENTITY_CREDENTIALS:)", submit["encrypt_Input_files"])


class TestGlobusComputeJobDescript(unittest.TestCase):
    def test_populate_job_descript_persists_globus_compute_metadata(self):
        conf, entry = make_globus_compute_entry()
        job_descript = DictFile(str(TEST_DIR / "fixtures/factory/work-dir"), "job.descript")
        attrs = DictFile(str(TEST_DIR / "fixtures/factory/work-dir"), "attributes.cfg")

        populate_job_descript(
            str(TEST_DIR / "fixtures/factory/work-dir/entry_TEST_GLOBUS_COMPUTE"),
            job_descript,
            1,
            entry["name"],
            entry,
            "schedd@example.org",
            attrs,
            False,
        )

        self.assertEqual("batch globuscompute", job_descript["GridType"])
        self.assertEqual("29e26773-cf24-4574-b5d9-1e353fd4de72", job_descript["GlobusComputeEndpoint"])
        self.assertEqual("pilot-runner-function", job_descript["GlobusComputeFunction"])
        self.assertEqual("/opt/gwms/globuscompute/glite", job_descript["GlobusComputeGliteDir"])
        self.assertEqual("/opt/gwms/globus-compute-client/bin/python", job_descript["GlobusComputePython"])
        self.assertEqual("/var/lib/gwms-factory/globus-compute-client", job_descript["GlobusComputeUserDir"])
        self.assertEqual("/var/lib/gwms-factory/globus-compute-state", job_descript["GlobusComputeStateDir"])

    def test_populate_job_descript_requires_globus_compute_endpoint(self):
        _conf, entry = make_globus_compute_entry(globus_compute_endpoint="")
        job_descript = DictFile(str(TEST_DIR / "fixtures/factory/work-dir"), "job.descript")
        attrs = DictFile(str(TEST_DIR / "fixtures/factory/work-dir"), "attributes.cfg")

        with self.assertRaisesRegex(RuntimeError, "globus_compute_endpoint"):
            populate_job_descript(
                str(TEST_DIR / "fixtures/factory/work-dir/entry_TEST_GLOBUS_COMPUTE"),
                job_descript,
                1,
                entry["name"],
                entry,
                "schedd@example.org",
                attrs,
                False,
            )

    def test_populate_job_descript_allows_missing_globus_compute_function(self):
        _conf, entry = make_globus_compute_entry(globus_compute_function="")
        job_descript = DictFile(str(TEST_DIR / "fixtures/factory/work-dir"), "job.descript")
        attrs = DictFile(str(TEST_DIR / "fixtures/factory/work-dir"), "attributes.cfg")

        populate_job_descript(
            str(TEST_DIR / "fixtures/factory/work-dir/entry_TEST_GLOBUS_COMPUTE"),
            job_descript,
            1,
            entry["name"],
            entry,
            "schedd@example.org",
            attrs,
            False,
        )

        self.assertNotIn("GlobusComputeFunction", job_descript)

    def test_populate_job_descript_requires_globus_compute_glite_dir(self):
        _conf, entry = make_globus_compute_entry(globus_compute_glite_dir="")
        job_descript = DictFile(str(TEST_DIR / "fixtures/factory/work-dir"), "job.descript")
        attrs = DictFile(str(TEST_DIR / "fixtures/factory/work-dir"), "attributes.cfg")

        with self.assertRaisesRegex(RuntimeError, "globus_compute_glite_dir"):
            populate_job_descript(
                str(TEST_DIR / "fixtures/factory/work-dir/entry_TEST_GLOBUS_COMPUTE"),
                job_descript,
                1,
                entry["name"],
                entry,
                "schedd@example.org",
                attrs,
                False,
            )


class TestGlobusComputeSubmitEnvironment(unittest.TestCase):
    @contextlib.contextmanager
    def _patch_factory_config(self, job_descript, job_attributes, glidein_descript, signatures):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                mock.patch("glideinwms.factory.glideFactoryConfig.JobDescript", return_value=job_descript)
            )
            stack.enter_context(
                mock.patch("glideinwms.factory.glideFactoryConfig.JobAttributes", return_value=job_attributes)
            )
            stack.enter_context(
                mock.patch("glideinwms.factory.glideFactoryConfig.GlideinDescript", return_value=glidein_descript)
            )
            stack.enter_context(
                mock.patch("glideinwms.factory.glideFactoryConfig.SignatureFile", return_value=signatures)
            )
            yield

    def _make_job_config(self):
        job_descript = mock.Mock()
        job_descript.data = {
            "Schedd": "schedd@example.org",
            "Verbosity": "std",
            "StartupDir": "OSG",
            "SubmitSlotsLayout": "fixed",
            "GridType": "batch globuscompute",
            "GlobusComputeEndpoint": "29e26773-cf24-4574-b5d9-1e353fd4de72",
            "GlobusComputeFunction": "pilot-runner-function",
            "GlobusComputePython": "/opt/gwms/globus-compute-client/bin/python",
            "GlobusComputeUserDir": "/var/lib/gwms-factory/globus-compute-client",
            "GlobusComputeStateDir": "/var/lib/gwms-factory/globus-compute-state",
        }
        job_attributes = mock.Mock()
        job_attributes.data = {}
        glidein_descript = mock.Mock()
        glidein_descript.data = {
            "GlideinName": "gfactory_instance",
            "FactoryName": "gfactory_service",
            "WebURL": "http://example.org/factory/stage",
        }
        signatures = mock.Mock()
        signatures.data = {
            "main_descript": "main.descript",
            "main_sign": "main.sign",
            "entry_TEST_GLOBUS_COMPUTE_descript": "entry.descript",
            "entry_TEST_GLOBUS_COMPUTE_sign": "entry.sign",
        }
        return job_descript, job_attributes, glidein_descript, signatures

    def _assert_globus_compute_submit_environment(self, env):
        env_dict = dict(item.split("=", 1) for item in env)
        self.assertEqual("29e26773-cf24-4574-b5d9-1e353fd4de72", env_dict["GLOBUS_COMPUTE_ENDPOINT"])
        self.assertEqual("pilot-runner-function", env_dict["GLOBUS_COMPUTE_FUNCTION"])
        self.assertEqual("/secure/frontend/globus-tokens.json", env_dict["GLOBUS_COMPUTE_AUTH_FILE"])
        self.assertEqual("/opt/gwms/globus-compute-client/bin/python", env_dict["GLOBUS_COMPUTE_PYTHON"])
        self.assertEqual("/var/lib/gwms-factory/globus-compute-client", env_dict["GLOBUS_COMPUTE_USER_DIR"])
        self.assertEqual("/var/lib/gwms-factory/globus-compute-state", env_dict["GLOBUS_COMPUTE_STATE_DIR"])
        self.assertIn("-cluster $(Cluster) -subcluster $(Process)", env_dict["GLIDEIN_ARGUMENTS"])
        self.assertNotIn("GRID_RESOURCE_OPTIONS", env_dict)
        self.assertNotIn("GLIDEIN_REMOTE_USERNAME", env_dict)
        self.assertNotIn("X509_USER_PROXY_BASENAME", env_dict)

    def test_batch_globuscompute_does_not_require_bosco_keypair_environment(self):
        submit_credentials = mock.Mock()
        submit_credentials.username = "frontend_user"
        submit_credentials.security_class = "frontend_sec_class"
        submit_credentials.id = "credential_id"
        submit_credentials.security_credentials = {
            "AuthFile": "/secure/frontend/globus-tokens.json",
        }
        submit_credentials.identity_credentials = {
            "frontend_scitoken": "/tmp/frontend.scitoken",
            "frontend_condortoken": "/tmp/frontend.idtoken",
        }

        job_descript, job_attributes, glidein_descript, signatures = self._make_job_config()

        with self._patch_factory_config(job_descript, job_attributes, glidein_descript, signatures):
            env = get_submit_environment(
                "TEST_GLOBUS_COMPUTE",
                "frontend.client",
                submit_credentials,
                None,
                {"GLIDEIN_CPUS": "1"},
                3600,
                log=mock.Mock(),
            )

        self._assert_globus_compute_submit_environment(env)

    def test_batch_globuscompute_v3_11_does_not_require_bosco_keypair_environment(self):
        empty_credentials = EmptyCredentialCollection()
        submit_credentials = mock.Mock()
        submit_credentials.username = "frontend_user"
        submit_credentials.security_class = "frontend_sec_class"
        submit_credentials.id = "credential_id"
        submit_credentials.security_credentials = TextRequestCredentialCollection(
            "/secure/frontend/globus-tokens.json"
        )
        submit_credentials.identity_credentials = empty_credentials

        job_descript, job_attributes, glidein_descript, signatures = self._make_job_config()

        with self._patch_factory_config(job_descript, job_attributes, glidein_descript, signatures):
            env = get_submit_environment_v3_11(
                "TEST_GLOBUS_COMPUTE",
                "frontend.client",
                submit_credentials,
                None,
                {"GLIDEIN_CPUS": "1"},
                3600,
                log=mock.Mock(),
            )

        self._assert_globus_compute_submit_environment(env)

    def test_batch_globuscompute_reports_missing_legacy_auth_file_credential(self):
        submit_credentials = mock.Mock()
        submit_credentials.username = "frontend_user"
        submit_credentials.security_class = "frontend_sec_class"
        submit_credentials.id = "credential_id"
        submit_credentials.security_credentials = {}
        submit_credentials.identity_credentials = {}

        job_descript, job_attributes, glidein_descript, signatures = self._make_job_config()

        with self._patch_factory_config(job_descript, job_attributes, glidein_descript, signatures):
            with self.assertRaisesRegex(RuntimeError, "AuthFile"):
                get_submit_environment(
                    "TEST_GLOBUS_COMPUTE",
                    "frontend.client",
                    submit_credentials,
                    None,
                    {"GLIDEIN_CPUS": "1"},
                    3600,
                    log=mock.Mock(),
                )

    def test_batch_globuscompute_reports_missing_v3_11_text_request_credential(self):
        submit_credentials = mock.Mock()
        submit_credentials.username = "frontend_user"
        submit_credentials.security_class = "frontend_sec_class"
        submit_credentials.id = "credential_id"
        submit_credentials.security_credentials = EmptyCredentialCollection()
        submit_credentials.identity_credentials = EmptyCredentialCollection()

        job_descript, job_attributes, glidein_descript, signatures = self._make_job_config()

        with self._patch_factory_config(job_descript, job_attributes, glidein_descript, signatures):
            with self.assertRaisesRegex(RuntimeError, "TEXT request credential"):
                get_submit_environment_v3_11(
                    "TEST_GLOBUS_COMPUTE",
                    "frontend.client",
                    submit_credentials,
                    None,
                    {"GLIDEIN_CPUS": "1"},
                    3600,
                    log=mock.Mock(),
                )


class TestGlobusComputeHelpers(unittest.TestCase):
    def test_create_client_uses_access_token_authorizer_for_generated_token(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_authorizer = mock.Mock(name="authorizer")
        fake_client = mock.Mock(name="compute-client")
        globus_sdk = mock.Mock()
        globus_sdk.AccessTokenAuthorizer.return_value = fake_authorizer
        compute_sdk = mock.Mock()
        compute_sdk.Client.return_value = fake_client

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / "gc-token.json"
            auth_file.write_text(
                json.dumps({"access_token": "minted-token", "expires_at_seconds": 99999999999}),
                encoding="utf-8",
            )
            with mock.patch.dict(
                sys.modules,
                {"globus_sdk": globus_sdk, "globus_compute_sdk": compute_sdk},
            ):
                client = globus_compute_helpers.create_client(auth_file=str(auth_file))

        self.assertIs(fake_client, client)
        globus_sdk.AccessTokenAuthorizer.assert_called_once_with("minted-token")
        compute_sdk.Client.assert_called_once_with(authorizer=fake_authorizer)

    def test_create_client_mints_in_process_from_confidential_credential(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_app = mock.Mock(name="client-app")
        fake_client = mock.Mock(name="compute-client")
        globus_sdk = mock.Mock()
        globus_sdk.ClientApp.return_value = fake_app
        token_storage = mock.Mock()
        compute_sdk = mock.Mock()
        compute_sdk.Client.return_value = fake_client

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / "confidential.json"
            auth_file.write_text(json.dumps({"client_id": "cid", "client_secret": "sec"}), encoding="utf-8")
            with mock.patch.dict(
                sys.modules,
                {
                    "globus_sdk": globus_sdk,
                    "globus_sdk.token_storage": token_storage,
                    "globus_compute_sdk": compute_sdk,
                },
            ):
                client = globus_compute_helpers.create_client(auth_file=str(auth_file))

        self.assertIs(fake_client, client)
        _, kwargs = globus_sdk.ClientApp.call_args
        self.assertEqual("cid", kwargs["client_id"])
        self.assertEqual("sec", kwargs["client_secret"])
        compute_sdk.Client.assert_called_once_with(app=fake_app)

    def test_mint_access_token_uses_client_credentials_grant(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        globus_sdk = mock.Mock()
        auth_client = globus_sdk.ConfidentialAppAuthClient.return_value
        auth_client.oauth2_client_credentials_tokens.return_value.by_resource_server = {
            "funcx_service": {"access_token": "minted", "expires_at_seconds": 123, "scope": "all"}
        }
        with mock.patch.dict(sys.modules, {"globus_sdk": globus_sdk}):
            doc = globus_compute_helpers.mint_access_token(client_id="cid", client_secret="sec")

        self.assertEqual("minted", doc["access_token"])
        self.assertEqual(123, doc["expires_at_seconds"])
        self.assertEqual("funcx_service", doc["resource_server"])
        globus_sdk.ConfidentialAppAuthClient.assert_called_once_with("cid", "sec")
        auth_client.oauth2_client_credentials_tokens.assert_called_once_with(
            requested_scopes=[globus_compute_helpers.GLOBUS_COMPUTE_ALL_SCOPE]
        )

    def test_mint_access_token_requires_client_id_and_secret(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        with self.assertRaisesRegex(RuntimeError, "client_id and client_secret"):
            globus_compute_helpers.mint_access_token(client_id="", client_secret="sec")

    def test_mint_token_cli_writes_token_file_from_credential_file(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        minted = {"access_token": "tok", "expires_at_seconds": 123, "scope": "all", "resource_server": "funcx_service"}
        with tempfile.TemporaryDirectory() as tmpdir:
            cred_file = Path(tmpdir) / "cred.json"
            cred_file.write_text(json.dumps({"client_id": "cid", "client_secret": "sec"}), encoding="utf-8")
            out = Path(tmpdir) / "auth.globuscompute"
            with mock.patch.object(globus_compute_helpers, "mint_access_token", return_value=minted) as mint:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = globus_compute_helpers.main(
                        ["mint-token", "--credential-file", str(cred_file), "--output", str(out)]
                    )
            self.assertEqual(0, rc)
            self.assertEqual(minted, json.loads(out.read_text(encoding="utf-8")))
            self.assertEqual(0o600, out.stat().st_mode & 0o777)
            mint.assert_called_once_with(
                client_id="cid", client_secret="sec", scope=globus_compute_helpers.GLOBUS_COMPUTE_ALL_SCOPE
            )

    def test_create_client_requires_delegated_auth(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        with self.assertRaisesRegex(RuntimeError, "GLOBUS_COMPUTE_AUTH_FILE"):
            globus_compute_helpers.create_client(auth_file="")
        with self.assertRaisesRegex(RuntimeError, "confidential .* credential or a minted"):
            globus_compute_helpers.create_client(auth_file="/secure/tokens.json")

    def test_parse_blahp_job_id_accepts_globuscompute_date_task_id(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        self.assertEqual(
            ("20260616", "task-123"),
            globus_compute_helpers.parse_blahp_job_id("globuscompute/20260616/task-123"),
        )
        self.assertEqual(
            ("20260616", "task-123"),
            globus_compute_helpers.parse_blahp_job_id("BLAHP_JOBID_PREFIXglobuscompute/20260616/task-123"),
        )

    def test_state_file_round_trip_restores_glidein_metadata(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        with tempfile.TemporaryDirectory() as tmpdir:
            state = globus_compute_helpers.GlobusComputeJobState(
                submit_date="20260616",
                glidein_id="glidein-123",
                endpoint_id="endpoint-uuid",
                function_id="function-uuid",
                stdout="/tmp/stdout",
                stderr="/tmp/stderr",
                outputs=["/tmp/out"],
            )

            globus_compute_helpers.write_job_state(state, state_dir=tmpdir)
            loaded = globus_compute_helpers.load_job_state("globuscompute/20260616/glidein-123", state_dir=tmpdir)

            self.assertEqual(state, loaded)

    def test_launch_glidein_runs_launch_op_and_writes_state(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "launched", "glidein_id": "glidein-123", "pid": 4242}

        with tempfile.TemporaryDirectory() as tmpdir:
            blahp_job_id = globus_compute_helpers.launch_glidein(
                fake_client,
                endpoint_id="endpoint-uuid",
                function_id="function-uuid",
                payload={"script": "./glidein_startup.sh\n"},
                glidein_id="glidein-123",
                auth_file="/secure/frontend/globus-tokens.json",
                base_dir="/endpoint/glideins",
                stdout="/tmp/stdout",
                stderr="/tmp/stderr",
                outputs=["/tmp/out"],
                submit_date="20260616",
                state_dir=tmpdir,
            )

            self.assertEqual("BLAHP_JOBID_PREFIXglobuscompute/20260616/glidein-123", blahp_job_id)
            sent_payload = fake_client.run.call_args.args[0]
            self.assertEqual("launch", sent_payload["op"])
            self.assertEqual("glidein-123", sent_payload["glidein_id"])
            self.assertEqual("/endpoint/glideins", sent_payload["base_dir"])
            self.assertEqual("./glidein_startup.sh\n", sent_payload["script"])
            loaded = globus_compute_helpers.load_job_state(blahp_job_id, state_dir=tmpdir)
            self.assertEqual("glidein-123", loaded.glidein_id)
            self.assertEqual("endpoint-uuid", loaded.endpoint_id)
            self.assertEqual("function-uuid", loaded.function_id)
            self.assertEqual("/secure/frontend/globus-tokens.json", loaded.auth_file)
            self.assertEqual("/endpoint/glideins", loaded.base_dir)

    def test_register_runner_registers_source_code_without_module_dependency(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.register_source_code.return_value = "function-id"

        with mock.patch(
            "glideinwms.factory.globus_compute.globus_compute_helpers.create_registration_client",
            return_value=fake_client,
        ):
            function_id = globus_compute_helpers.register_runner("runner-name")

        self.assertEqual("function-id", function_id)
        source = fake_client.register_source_code.call_args.args[0]
        namespace = {}
        exec(compile(source, "globus_compute_runner.py", "exec"), namespace)
        self.assertIn("run_globus_compute_payload", namespace)
        fake_client.register_source_code.assert_called_once_with(
            source,
            "run_globus_compute_payload",
            description="runner-name",
            public=False,
        )

    def test_register_runner_uses_delegated_credential(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.register_source_code.return_value = "function-id"

        with mock.patch(
            "glideinwms.factory.globus_compute.globus_compute_helpers.create_client",
            return_value=fake_client,
        ) as create_client:
            function_id = globus_compute_helpers.register_runner(
                "runner-name",
                auth_file="/secure/frontend/globus-tokens.json",
            )

        self.assertEqual("function-id", function_id)
        create_client.assert_called_once_with(auth_file="/secure/frontend/globus-tokens.json")

    def test_repairable_function_error_requires_function_registration_failure(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        class MissingFunctionError(Exception):
            http_status = 404

        class TaskExecutionFailed(Exception):
            pass

        self.assertTrue(globus_compute_helpers.is_repairable_function_error(MissingFunctionError("function not found")))
        self.assertTrue(globus_compute_helpers.is_repairable_function_error(RuntimeError("invalid function id")))
        self.assertFalse(
            globus_compute_helpers.is_repairable_function_error(
                RuntimeError("remote control function returned invalid payload")
            )
        )
        self.assertFalse(
            globus_compute_helpers.is_repairable_function_error(TaskExecutionFailed("function not found"))
        )

    def _write_state(self, helpers, tmpdir):
        tmp = Path(tmpdir)
        state = helpers.GlobusComputeJobState(
            submit_date="20260616",
            glidein_id="glidein-123",
            endpoint_id="endpoint-uuid",
            function_id="function-uuid",
            auth_file="/secure/frontend/globus-tokens.json",
            base_dir="/endpoint/glideins",
            stdout=str(tmp / "stdout"),
            stderr=str(tmp / "stderr"),
            outputs=[str(tmp / "result.txt")],
        )
        helpers.write_job_state(state, state_dir=tmpdir)
        return "globuscompute/20260616/glidein-123"

    def test_status_reports_running_and_keeps_state(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "running", "glidein_id": "glidein-123"}

        with tempfile.TemporaryDirectory() as tmpdir:
            job_id = self._write_state(globus_compute_helpers, tmpdir)
            classad = globus_compute_helpers.status_for_job(job_id, client=fake_client, state_dir=tmpdir)

            self.assertEqual('0[BatchJobId="glidein-123";JobStatus=2;]', classad)
            self.assertTrue((Path(tmpdir) / "20260616_glidein-123").exists())
            sent = fake_client.run.call_args.args[0]
            self.assertEqual("status", sent["op"])
            self.assertEqual("glidein-123", sent["glidein_id"])
            self.assertEqual("/endpoint/glideins", sent["base_dir"])

    def test_status_completed_writes_outputs_and_deletes_state(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {
            "state": "completed",
            "returncode": 3,
            "stdout": "remote stdout\n",
            "stderr": "remote stderr\n",
            "outputs": {"result.txt": base64.b64encode(b"remote output\n").decode("ascii")},
            "output_errors": {},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            job_id = self._write_state(globus_compute_helpers, tmpdir)
            classad = globus_compute_helpers.status_for_job(job_id, client=fake_client, state_dir=tmpdir)

            self.assertEqual('0[BatchJobId="glidein-123";JobStatus=4;ExitCode=3;]', classad)
            self.assertEqual("remote stdout\n", (tmp / "stdout").read_text(encoding="utf-8"))
            self.assertEqual("remote stderr\n", (tmp / "stderr").read_text(encoding="utf-8"))
            self.assertEqual(b"remote output\n", (tmp / "result.txt").read_bytes())
            self.assertFalse((tmp / "20260616_glidein-123").exists())

    def test_status_completed_appends_output_error_diagnostics(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {
            "state": "completed",
            "returncode": 0,
            "stderr": "remote stderr\n",
            "outputs": {},
            "output_errors": {"result.txt": "output exceeded Globus Compute result cap"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            job_id = self._write_state(globus_compute_helpers, tmpdir)
            globus_compute_helpers.status_for_job(job_id, client=fake_client, state_dir=tmpdir)

            stderr = (tmp / "stderr").read_text(encoding="utf-8")
            self.assertIn("remote stderr\n", stderr)
            self.assertIn("result.txt: output exceeded Globus Compute result cap", stderr)

    def test_status_unknown_reports_terminal_failure(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "unknown", "glidein_id": "glidein-123"}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            job_id = self._write_state(globus_compute_helpers, tmpdir)
            classad = globus_compute_helpers.status_for_job(job_id, client=fake_client, state_dir=tmpdir)

            self.assertEqual('0[BatchJobId="glidein-123";JobStatus=4;ExitCode=1;]', classad)
            self.assertIn("without an exit code", (tmp / "stderr").read_text(encoding="utf-8"))
            self.assertFalse((tmp / "20260616_glidein-123").exists())

    def test_cancel_runs_cancel_op_and_removes_state(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "cancelled", "glidein_id": "glidein-123"}

        with tempfile.TemporaryDirectory() as tmpdir:
            job_id = self._write_state(globus_compute_helpers, tmpdir)
            rc = globus_compute_helpers.cancel_job(job_id, client=fake_client, state_dir=tmpdir)

            self.assertEqual(0, rc)
            self.assertEqual("cancel", fake_client.run.call_args.args[0]["op"])
            self.assertEqual("/endpoint/glideins", fake_client.run.call_args.args[0]["base_dir"])
            self.assertFalse((Path(tmpdir) / "20260616_glidein-123").exists())

    def test_cancel_treats_missing_state_as_already_cancelled(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = globus_compute_helpers.cancel_job(
                "globuscompute/20260616/gone", client=fake_client, state_dir=tmpdir
            )
            self.assertEqual(0, rc)
            fake_client.run.assert_not_called()

    def test_cancel_keeps_state_when_control_op_fails(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.side_effect = RuntimeError("endpoint unreachable")

        with tempfile.TemporaryDirectory() as tmpdir:
            job_id = self._write_state(globus_compute_helpers, tmpdir)
            with self.assertRaises(RuntimeError):
                globus_compute_helpers.cancel_job(job_id, client=fake_client, state_dir=tmpdir)
            self.assertTrue((Path(tmpdir) / "20260616_glidein-123").exists())


class TestGlobusComputeRunner(unittest.TestCase):
    def _write_gc_auth_file(self, directory, name="auth.json", client_id="client-a", client_secret="secret"):
        path = Path(directory) / name
        path.write_text(
            json.dumps({"client_id": client_id, "client_secret": client_secret}),
            encoding="utf-8",
        )
        return path

    def _write_gc_token_file(self, directory, name="token.json", access_token="secret-token"):
        path = Path(directory) / name
        path.write_text(json.dumps({"access_token": access_token}), encoding="utf-8")
        return path

    def _token_auth_key(self, path):
        path = Path(path)
        metadata = {
            "path": str(path.resolve()),
            "uid": path.stat().st_uid,
            "gid": path.stat().st_gid,
        }
        key_json = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        return f"auth_file:{hashlib.sha256(key_json.encode('utf-8')).hexdigest()}"

    def _cache_key_material(self, endpoint_id, auth_key, runner_source):
        return {
            "endpoint_id": endpoint_id,
            "auth_key": auth_key,
            "runner_sha256": hashlib.sha256(runner_source.encode("utf-8")).hexdigest(),
        }

    def _expected_cache_path(self, state_dir, endpoint_id, auth_key, runner_source):
        key_json = json.dumps(
            self._cache_key_material(endpoint_id, auth_key, runner_source),
            sort_keys=True,
            separators=(",", ":"),
        )
        return Path(state_dir) / "functions" / f"{hashlib.sha256(key_json.encode('utf-8')).hexdigest()}.json"

    def _function_cache_records(self, state_dir):
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((Path(state_dir) / "functions").glob("*.json"))
        ]

    def _run_submit_cli(
        self,
        globus_compute_helpers,
        fake_client,
        tmpdir,
        *,
        auth_file,
        endpoint_id="endpoint-uuid",
        runner_source="runner-source-v1",
        configured_function=None,
        glidein_id="gid",
    ):
        script = Path(tmpdir) / f"{glidein_id}.sh"
        script.write_text("printf ok\n", encoding="utf-8")
        env = {
            "GLOBUS_COMPUTE_ENDPOINT": endpoint_id,
            "GLOBUS_COMPUTE_AUTH_FILE": str(auth_file),
            "GLOBUS_COMPUTE_STATE_DIR": str(tmpdir),
        }
        if configured_function is not None:
            env["GLOBUS_COMPUTE_FUNCTION"] = configured_function

        with mock.patch(
            "glideinwms.factory.globus_compute.globus_compute_helpers.create_client",
            return_value=fake_client,
        ):
            with mock.patch.object(globus_compute_helpers, "load_runner_source", return_value=runner_source):
                with mock.patch.dict(os.environ, env, clear=True):
                    with mock.patch("time.strftime", return_value="20260616"):
                        with mock.patch.object(globus_compute_helpers.uuid, "uuid4") as uuid4:
                            uuid4.return_value.hex = glidein_id
                            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                                rc = globus_compute_helpers.main(["submit", "--script", str(script)])

        return rc, stdout.getvalue().strip()

    def _runner(self):
        from glideinwms.factory.globus_compute.globus_compute_runner import run_globus_compute_payload

        return run_globus_compute_payload

    def _wait_completed(self, run, base, glidein_id, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = run({"op": "status", "glidein_id": glidein_id, "base_dir": base})
            if result["state"] != "running":
                return result
            time.sleep(0.05)
        self.fail("glidein did not finish in time")

    def test_launch_returns_immediately_and_status_completes_with_outputs(self):
        run = self._runner()
        with tempfile.TemporaryDirectory() as base:
            launched = run(
                {
                    "op": "launch",
                    "glidein_id": "g1",
                    "base_dir": base,
                    "script": (
                        "printf 'hello stdout\\n'; printf 'hello stderr\\n' >&2; printf data > result.txt; exit 5"
                    ),
                    "outputs": ["result.txt"],
                }
            )
            self.assertEqual("launched", launched["state"])
            self.assertEqual("g1", launched["glidein_id"])
            self.assertIsInstance(launched["pid"], int)

            result = self._wait_completed(run, base, "g1")
            self.assertEqual("completed", result["state"])
            self.assertEqual(5, result["returncode"])
            self.assertEqual("hello stdout\n", result["stdout"])
            self.assertEqual("hello stderr\n", result["stderr"])
            self.assertEqual(b"data", base64.b64decode(result["outputs"]["result.txt"]))

            # workdir is cleaned after a completed status; polling again reports unknown
            self.assertEqual("unknown", run({"op": "status", "glidein_id": "g1", "base_dir": base})["state"])

    def test_status_reports_running_then_cancel_removes_glidein(self):
        run = self._runner()
        with tempfile.TemporaryDirectory() as base:
            run({"op": "launch", "glidein_id": "g2", "base_dir": base, "script": "sleep 30"})
            self.assertEqual("running", run({"op": "status", "glidein_id": "g2", "base_dir": base})["state"])

            self.assertEqual("cancelled", run({"op": "cancel", "glidein_id": "g2", "base_dir": base})["state"])
            self.assertEqual("unknown", run({"op": "status", "glidein_id": "g2", "base_dir": base})["state"])

    def test_launch_does_not_warn_about_unreaped_python_child(self):
        import gc
        import warnings

        run = self._runner()
        with tempfile.TemporaryDirectory() as base:
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always", ResourceWarning)
                    run({"op": "launch", "glidein_id": "gwarn", "base_dir": base, "script": "sleep 30"})
                    gc.collect()
            finally:
                run({"op": "cancel", "glidein_id": "gwarn", "base_dir": base})

        resource_warnings = [warning for warning in caught if issubclass(warning.category, ResourceWarning)]
        self.assertEqual([], resource_warnings)

    def test_launch_stages_files_with_restricted_permissions(self):
        import stat

        run = self._runner()
        with tempfile.TemporaryDirectory() as base:
            run(
                {
                    "op": "launch",
                    "glidein_id": "g3",
                    "base_dir": base,
                    "script": "sleep 5",
                    "files": [
                        {"name": "token.idtoken", "content_b64": base64.b64encode(b"t\n").decode("ascii")},
                        {
                            "name": "run.bin",
                            "content_b64": base64.b64encode(b"x\n").decode("ascii"),
                            "executable": True,
                        },
                    ],
                }
            )
            workdir = Path(base) / "g3"
            self.assertEqual(0o600, stat.S_IMODE((workdir / "token.idtoken").stat().st_mode))
            self.assertEqual(0o700, stat.S_IMODE((workdir / "run.bin").stat().st_mode))
            run({"op": "cancel", "glidein_id": "g3", "base_dir": base})

    def test_status_bounds_stdout_and_declared_outputs(self):
        run = self._runner()
        with tempfile.TemporaryDirectory() as base:
            run(
                {
                    "op": "launch",
                    "glidein_id": "g4",
                    "base_dir": base,
                    "script": "printf 'stdout-start-stdout-end'; printf 'output-start-output-end' > result.txt; exit 0",
                    "outputs": ["result.txt"],
                    "result_max_bytes": 10,
                    "output_max_bytes": 10,
                }
            )
            result = self._wait_completed(run, base, "g4")
            self.assertEqual("completed", result["state"])
            self.assertIn("truncated to last 10 bytes", result["stdout"])
            self.assertTrue(result["stdout"].endswith("tdout-end"))
            self.assertEqual({}, result["outputs"])
            self.assertIn("result.txt", result["output_errors"])

    def test_runner_runs_from_its_registered_source(self):
        src = (TEST_DIR.parent / "factory/globus_compute/globus_compute_runner.py").read_text(encoding="utf-8")
        namespace = {}
        exec(compile(src, "globus_compute_runner.py", "exec"), namespace)
        run = namespace["run_globus_compute_payload"]

        with tempfile.TemporaryDirectory() as base:
            run(
                {
                    "op": "launch",
                    "glidein_id": "gsrc",
                    "base_dir": base,
                    "script": "printf ok > out.txt",
                    "outputs": ["out.txt"],
                }
            )
            result = self._wait_completed(run, base, "gsrc")
            self.assertEqual("completed", result["state"])
            self.assertEqual(0, result["returncode"])
            self.assertEqual(b"ok", base64.b64decode(result["outputs"]["out.txt"]))

    def test_format_status_classad_with_exit_code(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        self.assertEqual(
            '0[BatchJobId="g";JobStatus=4;ExitCode=0;]',
            globus_compute_helpers.format_status_classad_with_exit_code("g", 4, 0),
        )
        self.assertEqual(
            '0[BatchJobId="g";JobStatus=2;]',
            globus_compute_helpers.format_status_classad_with_exit_code("g", 2, None),
        )

    def test_submit_cli_requires_script_payload(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch(
                "glideinwms.factory.globus_compute.globus_compute_helpers.create_client",
                return_value=fake_client,
            ):
                with mock.patch.dict(
                    os.environ,
                    {
                        "GLOBUS_COMPUTE_ENDPOINT": "endpoint-uuid",
                        "GLOBUS_COMPUTE_FUNCTION": "function-uuid",
                        "GLOBUS_COMPUTE_AUTH_FILE": "/secure/frontend/globus-tokens.json",
                        "GLOBUS_COMPUTE_STATE_DIR": tmpdir,
                    },
                ):
                    with contextlib.redirect_stderr(io.StringIO()) as stderr:
                        with self.assertRaises(SystemExit) as raised:
                            globus_compute_helpers.main(["submit", "--", "./glidein_startup.sh"])

        self.assertEqual(2, raised.exception.code)
        self.assertIn("--script", stderr.getvalue())
        fake_client.run.assert_not_called()

    def test_submit_cli_launches_glidein_from_script_and_staged_files(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "launched", "glidein_id": "fixed-glidein", "pid": 99}

        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch(
                "glideinwms.factory.globus_compute.globus_compute_helpers.create_client",
                return_value=fake_client,
            ) as create_client:
                with mock.patch.dict(
                    os.environ,
                    {
                        "GLOBUS_COMPUTE_ENDPOINT": "endpoint-uuid",
                        "GLOBUS_COMPUTE_FUNCTION": "function-uuid",
                        "GLOBUS_COMPUTE_AUTH_FILE": "/secure/frontend/globus-tokens.json",
                        "GLOBUS_COMPUTE_STATE_DIR": tmpdir,
                        "GLOBUS_COMPUTE_USER_DIR": "/factory/sdk-user-dir",
                        "GLIDEIN_ARGUMENTS": "-cluster 7 -subcluster 0",
                        "PATH": "/not/staged",
                    },
                    clear=True,
                ):
                    with mock.patch("time.strftime", return_value="20260616"):
                        with mock.patch.object(globus_compute_helpers.uuid, "uuid4") as uuid4:
                            uuid4.return_value.hex = "fixed-glidein"
                            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                                tmp = Path(tmpdir)
                                (tmp / "payload.sh").write_text("./pilot.sh\n", encoding="utf-8")
                                pilot = tmp / "pilot.sh"
                                pilot.write_text("#!/usr/bin/env bash\necho pilot\n", encoding="utf-8")
                                pilot.chmod(0o755)
                                rc = globus_compute_helpers.main(
                                    [
                                        "submit",
                                        "--job-name",
                                        "unit-job",
                                        "--script",
                                        str(tmp / "payload.sh"),
                                        "--input-files",
                                        str(pilot),
                                        "--stdout",
                                        str(tmp / "stdout"),
                                        "--stderr",
                                        str(tmp / "stderr"),
                                        "--output-files",
                                        str(tmp / "result.txt"),
                                    ]
                                )

            self.assertEqual(0, rc)
            self.assertEqual("BLAHP_JOBID_PREFIXglobuscompute/20260616/fixed-glidein", stdout.getvalue().strip())
            payload = fake_client.run.call_args.args[0]
            self.assertEqual("launch", payload["op"])
            self.assertEqual("fixed-glidein", payload["glidein_id"])
            self.assertNotIn("base_dir", payload)
            self.assertEqual("unit-job", payload["job_name"])
            self.assertEqual("./pilot.sh\n", payload["script"])
            self.assertEqual({"GLIDEIN_ARGUMENTS": "-cluster 7 -subcluster 0"}, payload["environment"])
            self.assertEqual(["pilot.sh"], [item["name"] for item in payload["files"]])
            self.assertEqual(["result.txt"], payload["outputs"])
            state = globus_compute_helpers.load_job_state(
                "BLAHP_JOBID_PREFIXglobuscompute/20260616/fixed-glidein", state_dir=tmpdir
            )
            self.assertEqual("fixed-glidein", state.glidein_id)
            self.assertEqual("", state.base_dir)
            self.assertEqual([str(Path(tmpdir) / "result.txt")], state.outputs)
            self.assertEqual("/secure/frontend/globus-tokens.json", state.auth_file)
            self.assertFalse((Path(tmpdir) / "functions").exists())
        create_client.assert_called_once_with(auth_file="/secure/frontend/globus-tokens.json")
        fake_client.register_source_code.assert_not_called()

    def test_submit_cli_registers_runner_and_writes_function_cache_when_function_not_configured(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.register_source_code.return_value = "auto-fn-id"
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "launched", "glidein_id": "gid", "pid": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = self._write_gc_auth_file(tmpdir)
            rc, _stdout = self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                runner_source="runner-source-v1",
            )

            self.assertEqual(0, rc)
            self.assertEqual("auto-fn-id", fake_client.run.call_args.kwargs["function_id"])
            self.assertEqual(1, fake_client.register_source_code.call_count)
            self.assertFalse(fake_client.register_source_code.call_args.kwargs["public"])
            records = self._function_cache_records(tmpdir)
            self.assertEqual(1, len(records))
            self.assertEqual("endpoint-uuid", records[0]["endpoint_id"])
            self.assertEqual("client_id:client-a", records[0]["auth_key"])
            self.assertEqual(hashlib.sha256(b"runner-source-v1").hexdigest(), records[0]["runner_sha256"])
            self.assertEqual("auto-fn-id", records[0]["function_id"])
            self.assertEqual("gwms-globuscompute-runner-v1", records[0]["function_name"])

    def test_submit_cli_reuses_cached_function_for_same_endpoint_auth_and_runner(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.register_source_code.return_value = "auto-fn-id"
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "launched", "pid": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = self._write_gc_auth_file(tmpdir)
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                runner_source="runner-source-v1",
                glidein_id="gid1",
            )
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                runner_source="runner-source-v1",
                glidein_id="gid2",
            )

            self.assertEqual(1, fake_client.register_source_code.call_count)
            self.assertEqual(
                ["auto-fn-id", "auto-fn-id"],
                [call.kwargs["function_id"] for call in fake_client.run.call_args_list],
            )
            self.assertEqual(1, len(self._function_cache_records(tmpdir)))

    def test_submit_cli_uses_different_cache_entry_for_different_endpoint(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.register_source_code.side_effect = ["fn-endpoint-a", "fn-endpoint-b"]
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "launched", "pid": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = self._write_gc_auth_file(tmpdir)
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                endpoint_id="endpoint-a",
                glidein_id="gid1",
            )
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                endpoint_id="endpoint-b",
                glidein_id="gid2",
            )

            self.assertEqual(2, fake_client.register_source_code.call_count)
            self.assertEqual(
                ["fn-endpoint-a", "fn-endpoint-b"],
                [call.kwargs["function_id"] for call in fake_client.run.call_args_list],
            )
            self.assertEqual(
                {"endpoint-a", "endpoint-b"},
                {record["endpoint_id"] for record in self._function_cache_records(tmpdir)},
            )

    def test_submit_cli_uses_different_cache_entry_for_different_client_id(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.register_source_code.side_effect = ["fn-client-a", "fn-client-b"]
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "launched", "pid": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_a = self._write_gc_auth_file(tmpdir, name="auth-a.json", client_id="client-a")
            auth_b = self._write_gc_auth_file(tmpdir, name="auth-b.json", client_id="client-b")
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_a,
                glidein_id="gid1",
            )
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_b,
                glidein_id="gid2",
            )

            self.assertEqual(2, fake_client.register_source_code.call_count)
            self.assertEqual(
                {"client_id:client-a", "client_id:client-b"},
                {record["auth_key"] for record in self._function_cache_records(tmpdir)},
            )

    def test_submit_cli_token_auth_cache_key_uses_file_identity_not_token_value(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.register_source_code.side_effect = ["fn-token-a", "fn-token-b"]
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "launched", "pid": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            token_a = self._write_gc_token_file(tmpdir, name="token-a.json", access_token="secret-a")
            token_b = self._write_gc_token_file(tmpdir, name="token-b.json", access_token="secret-b")
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=token_a,
                glidein_id="gid1",
            )
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=token_b,
                glidein_id="gid2",
            )

            records = self._function_cache_records(tmpdir)
            self.assertEqual(
                {self._token_auth_key(token_a), self._token_auth_key(token_b)},
                {record["auth_key"] for record in records},
            )
            self.assertFalse(any("secret" in record["auth_key"] for record in records))

    def test_submit_cli_uses_different_cache_entry_for_different_runner_source_hash(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.register_source_code.side_effect = ["fn-runner-v1", "fn-runner-v2"]
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "launched", "pid": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = self._write_gc_auth_file(tmpdir)
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                runner_source="runner-source-v1",
                glidein_id="gid1",
            )
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                runner_source="runner-source-v2",
                glidein_id="gid2",
            )

            self.assertEqual(2, fake_client.register_source_code.call_count)
            self.assertEqual(
                {
                    hashlib.sha256(b"runner-source-v1").hexdigest(),
                    hashlib.sha256(b"runner-source-v2").hexdigest(),
                },
                {record["runner_sha256"] for record in self._function_cache_records(tmpdir)},
            )

    def test_submit_cli_repairable_cached_function_failure_updates_cache_and_retries_once(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        class MissingFunctionError(Exception):
            http_status = 404

        fake_client = mock.Mock()
        fake_client.register_source_code.side_effect = ["cached-fn-id", "repaired-fn-id"]
        fake_client.run.side_effect = ["control-task-1", MissingFunctionError("function not found"), "control-task-2"]
        fake_client.get_result.return_value = {"state": "launched", "pid": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = self._write_gc_auth_file(tmpdir)
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                glidein_id="gid1",
            )
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                glidein_id="gid2",
            )

            self.assertEqual(2, fake_client.register_source_code.call_count)
            self.assertEqual(
                ["cached-fn-id", "cached-fn-id", "repaired-fn-id"],
                [call.kwargs["function_id"] for call in fake_client.run.call_args_list],
            )
            self.assertEqual("repaired-fn-id", self._function_cache_records(tmpdir)[0]["function_id"])

    def test_submit_cli_does_not_repair_fresh_auto_registered_function_failure(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        class MissingFunctionError(Exception):
            http_status = 404

        fake_client = mock.Mock()
        fake_client.register_source_code.return_value = "fresh-fn-id"
        fake_client.run.side_effect = MissingFunctionError("function not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = self._write_gc_auth_file(tmpdir)
            with self.assertRaisesRegex(MissingFunctionError, "function not found"):
                self._run_submit_cli(
                    globus_compute_helpers,
                    fake_client,
                    tmpdir,
                    auth_file=auth_file,
                )

            self.assertEqual(1, fake_client.register_source_code.call_count)
            self.assertEqual("fresh-fn-id", self._function_cache_records(tmpdir)[0]["function_id"])

    def test_submit_cli_non_repairable_submit_failure_does_not_register_again(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.register_source_code.return_value = "cached-fn-id"
        fake_client.run.side_effect = ["control-task-1", RuntimeError("endpoint unavailable")]
        fake_client.get_result.return_value = {"state": "launched", "pid": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = self._write_gc_auth_file(tmpdir)
            self._run_submit_cli(
                globus_compute_helpers,
                fake_client,
                tmpdir,
                auth_file=auth_file,
                glidein_id="gid1",
            )
            with self.assertRaisesRegex(RuntimeError, "endpoint unavailable"):
                self._run_submit_cli(
                    globus_compute_helpers,
                    fake_client,
                    tmpdir,
                    auth_file=auth_file,
                    glidein_id="gid2",
                )

            self.assertEqual(1, fake_client.register_source_code.call_count)
            self.assertEqual("cached-fn-id", self._function_cache_records(tmpdir)[0]["function_id"])

    def test_submit_cli_replaces_corrupt_or_mismatched_function_cache(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        runner_source = "runner-source-v1"
        fake_client = mock.Mock()
        fake_client.register_source_code.side_effect = ["from-corrupt", "from-mismatch", "from-incomplete"]
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "launched", "pid": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            auth_file = self._write_gc_auth_file(tmpdir)
            cache_path = self._expected_cache_path(tmpdir, "endpoint-uuid", "client_id:client-a", runner_source)
            cache_path.parent.mkdir(parents=True)

            with self.subTest("corrupt json"):
                cache_path.write_text("{not json", encoding="utf-8")
                self._run_submit_cli(
                    globus_compute_helpers,
                    fake_client,
                    tmpdir,
                    auth_file=auth_file,
                    runner_source=runner_source,
                    glidein_id="gid1",
                )
                self.assertEqual("from-corrupt", json.loads(cache_path.read_text(encoding="utf-8"))["function_id"])

            with self.subTest("mismatched record"):
                cache_path.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "endpoint_id": "other-endpoint",
                            "auth_key": "client_id:client-a",
                            "runner_sha256": hashlib.sha256(runner_source.encode("utf-8")).hexdigest(),
                            "function_id": "stale-fn",
                            "function_name": "gwms-globuscompute-runner-v1",
                        }
                    ),
                    encoding="utf-8",
                )
                self._run_submit_cli(
                    globus_compute_helpers,
                    fake_client,
                    tmpdir,
                    auth_file=auth_file,
                    runner_source=runner_source,
                    glidein_id="gid2",
                )
                self.assertEqual("from-mismatch", json.loads(cache_path.read_text(encoding="utf-8"))["function_id"])

            with self.subTest("incomplete record"):
                cache_path.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "endpoint_id": "endpoint-uuid",
                            "auth_key": "client_id:client-a",
                            "runner_sha256": hashlib.sha256(runner_source.encode("utf-8")).hexdigest(),
                            "function_id": "incomplete-fn",
                        }
                    ),
                    encoding="utf-8",
                )
                self._run_submit_cli(
                    globus_compute_helpers,
                    fake_client,
                    tmpdir,
                    auth_file=auth_file,
                    runner_source=runner_source,
                    glidein_id="gid3",
                )
                self.assertEqual("from-incomplete", json.loads(cache_path.read_text(encoding="utf-8"))["function_id"])

    def test_status_cli_prints_blahp_classad(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "completed", "returncode": 0}

        with tempfile.TemporaryDirectory() as tmpdir:
            state = globus_compute_helpers.GlobusComputeJobState(
                submit_date="20260616",
                glidein_id="glidein-123",
                endpoint_id="endpoint-uuid",
                function_id="function-uuid",
                auth_file="/secure/frontend/globus-tokens.json",
            )
            globus_compute_helpers.write_job_state(state, state_dir=tmpdir)
            with mock.patch.dict(os.environ, {"GLOBUS_COMPUTE_STATE_DIR": tmpdir}):
                with mock.patch(
                    "glideinwms.factory.globus_compute.globus_compute_helpers.create_client",
                    return_value=fake_client,
                ):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        rc = globus_compute_helpers.main(
                            ["status", "BLAHP_JOBID_PREFIXglobuscompute/20260616/glidein-123"]
                        )

        self.assertEqual(0, rc)
        self.assertEqual('0[BatchJobId="glidein-123";JobStatus=4;ExitCode=0;]', stdout.getvalue().strip())
        self.assertEqual("status", fake_client.run.call_args.args[0]["op"])

    def test_cancel_cli_runs_cancel_op(self):
        from glideinwms.factory.globus_compute import globus_compute_helpers

        fake_client = mock.Mock()
        fake_client.run.return_value = "control-task"
        fake_client.get_result.return_value = {"state": "cancelled"}

        with tempfile.TemporaryDirectory() as tmpdir:
            state = globus_compute_helpers.GlobusComputeJobState(
                submit_date="20260616",
                glidein_id="glidein-123",
                endpoint_id="endpoint-uuid",
                function_id="function-uuid",
                auth_file="/secure/frontend/globus-tokens.json",
            )
            globus_compute_helpers.write_job_state(state, state_dir=tmpdir)
            with mock.patch.dict(os.environ, {"GLOBUS_COMPUTE_STATE_DIR": tmpdir}):
                with mock.patch(
                    "glideinwms.factory.globus_compute.globus_compute_helpers.create_client",
                    return_value=fake_client,
                ):
                    rc = globus_compute_helpers.main(["cancel", "BLAHP_JOBID_PREFIXglobuscompute/20260616/glidein-123"])

        self.assertEqual(0, rc)
        self.assertEqual("cancel", fake_client.run.call_args.args[0]["op"])


class TestGlobusComputeShellEntryPoints(unittest.TestCase):
    def write_fake_python(self, path):
        path.write_text(
            "#!/usr/bin/env bash\n"
            'if [ "$1" = "-c" ]; then exit 0; fi\n'
            'case "$2" in\n'
            '  status) echo "0[BatchJobId=\\"task-123\\";JobStatus=4;ExitCode=0;]"; exit 0 ;;\n'
            "  cancel) exit 0 ;;\n"
            "esac\n"
            "exit 1\n"
        )
        path.chmod(0o755)

    def test_blahp_shell_entry_points_exist_and_are_executable(self):
        helper_dir = TEST_DIR.parent / "factory/globus_compute"

        for script_name in (
            "globuscompute_submit.sh",
            "globuscompute_status.sh",
            "globuscompute_cancel.sh",
            "globuscompute_ping.sh",
            "globuscompute_local_submit_attributes.sh",
            "globus_compute_setup.sh",
        ):
            script = helper_dir / script_name
            self.assertTrue(script.exists(), f"{script} is missing")
            self.assertTrue(os.access(script, os.X_OK), f"{script} is not executable")

    def test_setup_reports_missing_globus_compute_sdk(self):
        setup = TEST_DIR.parent / "factory/globus_compute/globus_compute_setup.sh"

        result = subprocess.run(
            ["bash", str(setup)],
            check=False,
            env={
                "PATH": os.environ["PATH"],
                "GLOBUS_COMPUTE_PYTHON": "/bin/false",
            },
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Globus Compute setup error", result.stderr)

    def test_setup_sources_glite_runtime_env_file(self):
        setup = TEST_DIR.parent / "factory/globus_compute/globus_compute_setup.sh"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            script_dir = tmpdir_path / "glite"
            script_dir.mkdir()
            setup_copy = script_dir / "globus_compute_setup.sh"
            setup_copy.write_text(setup.read_text(encoding="utf-8"), encoding="utf-8")
            setup_copy.chmod(0o755)

            bin_dir = tmpdir_path / "bin"
            bin_dir.mkdir()
            bad_python = bin_dir / "python3"
            bad_python.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
            bad_python.chmod(0o755)

            fake_python = tmpdir_path / "fake-python"
            fake_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_python.chmod(0o755)
            (script_dir / "globus_compute_env.sh").write_text(
                "export GLOBUS_COMPUTE_PYTHON=%s\n" % fake_python,
                encoding="utf-8",
            )

            result = subprocess.run(
                ["bash", str(setup_copy)],
                check=False,
                env={
                    "PATH": "%s:%s" % (bin_dir, os.environ["PATH"]),
                    "GLOBUS_COMPUTE_BLAHP_JOB_ID": "ping",
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(0, result.returncode, result.stderr)

    def test_setup_env_file_does_not_override_existing_runtime_environment(self):
        setup = TEST_DIR.parent / "factory/globus_compute/globus_compute_setup.sh"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            script_dir = tmpdir_path / "glite"
            script_dir.mkdir()
            setup_copy = script_dir / "globus_compute_setup.sh"
            setup_copy.write_text(setup.read_text(encoding="utf-8"), encoding="utf-8")
            setup_copy.chmod(0o755)

            fake_python = tmpdir_path / "fake-python"
            fake_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_python.chmod(0o755)
            (script_dir / "globus_compute_env.sh").write_text(
                "export GLOBUS_COMPUTE_PYTHON=/bin/false\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["bash", str(setup_copy)],
                check=False,
                env={
                    "PATH": os.environ["PATH"],
                    "GLOBUS_COMPUTE_PYTHON": str(fake_python),
                    "GLOBUS_COMPUTE_BLAHP_JOB_ID": "ping",
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(0, result.returncode, result.stderr)

    def test_setup_env_file_does_not_override_delegated_auth_environment(self):
        setup = TEST_DIR.parent / "factory/globus_compute/globus_compute_setup.sh"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            script_dir = tmpdir_path / "glite"
            script_dir.mkdir()
            setup_copy = script_dir / "globus_compute_setup.sh"
            setup_copy.write_text(setup.read_text(encoding="utf-8"), encoding="utf-8")
            setup_copy.chmod(0o755)

            fake_python = tmpdir_path / "fake-python"
            fake_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_python.chmod(0o755)
            (script_dir / "globus_compute_env.sh").write_text(
                "export GLOBUS_COMPUTE_PYTHON=%s\n"
                "export GLOBUS_COMPUTE_AUTH_FILE=/static/globus-compute-auth.json\n" % fake_python,
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    '. "$1"; printf "%s" "$GLOBUS_COMPUTE_AUTH_FILE"',
                    "bash",
                    str(setup_copy),
                ],
                check=False,
                env={
                    "PATH": os.environ["PATH"],
                    "GLOBUS_COMPUTE_PYTHON": str(fake_python),
                    "GLOBUS_COMPUTE_BLAHP_JOB_ID": "ping",
                    "GLOBUS_COMPUTE_AUTH_FILE": "/delegated/frontend/globus-tokens.json",
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("/delegated/frontend/globus-tokens.json", result.stdout)

    def test_setup_env_file_replaces_empty_runtime_override(self):
        setup = TEST_DIR.parent / "factory/globus_compute/globus_compute_setup.sh"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            script_dir = tmpdir_path / "glite"
            script_dir.mkdir()
            setup_copy = script_dir / "globus_compute_setup.sh"
            setup_copy.write_text(setup.read_text(encoding="utf-8"), encoding="utf-8")
            setup_copy.chmod(0o755)

            fake_python = tmpdir_path / "fake-python"
            fake_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_python.chmod(0o755)
            configured_state_dir = tmpdir_path / "configured-state"
            (script_dir / "globus_compute_env.sh").write_text(
                "export GLOBUS_COMPUTE_PYTHON=%s\nexport GLOBUS_COMPUTE_STATE_DIR=%s\n"
                % (fake_python, configured_state_dir),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    '. "$1"; printf "%s" "$GLOBUS_COMPUTE_STATE_DIR"',
                    "bash",
                    str(setup_copy),
                ],
                check=False,
                env={
                    "PATH": os.environ["PATH"],
                    "GLOBUS_COMPUTE_BLAHP_JOB_ID": "ping",
                    "GLOBUS_COMPUTE_STATE_DIR": "",
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(configured_state_dir), result.stdout)

    def test_status_script_emits_failure_when_setup_fails(self):
        status = TEST_DIR.parent / "factory/globus_compute/globuscompute_status.sh"

        result = subprocess.run(
            ["bash", str(status), "globuscompute/20260616/task-123"],
            check=False,
            env={
                "PATH": os.environ["PATH"],
                "GLOBUS_COMPUTE_PYTHON": "/bin/false",
            },
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(0, result.returncode)
        self.assertIn('1[BatchJobId="task-123";Reason="Globus Compute setup error', result.stdout)

    def test_status_script_does_not_require_submit_endpoint_environment(self):
        status = TEST_DIR.parent / "factory/globus_compute/globuscompute_status.sh"

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_python = Path(tmpdir) / "fake-python"
            self.write_fake_python(fake_python)
            result = subprocess.run(
                ["bash", str(status), "globuscompute/20260616/task-123"],
                check=False,
                env={
                    "PATH": os.environ["PATH"],
                    "GLOBUS_COMPUTE_PYTHON": str(fake_python),
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual('0[BatchJobId="task-123";JobStatus=4;ExitCode=0;]\n', result.stdout)

    def test_cancel_script_uses_blahp_result_line(self):
        cancel = TEST_DIR.parent / "factory/globus_compute/globuscompute_cancel.sh"

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_python = Path(tmpdir) / "fake-python"
            self.write_fake_python(fake_python)
            result = subprocess.run(
                ["bash", str(cancel), "globuscompute/20260616/task-123"],
                check=False,
                env={
                    "PATH": os.environ["PATH"],
                    "GLOBUS_COMPUTE_PYTHON": str(fake_python),
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(" 0 No\\ error\n", result.stdout)

    def test_submit_wrapper_uses_blahp_stage_in_files_and_emits_job_id(self):
        submit = TEST_DIR.parent / "factory/globus_compute/globuscompute_submit.sh"
        setup = TEST_DIR.parent / "factory/globus_compute/globus_compute_setup.sh"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            script_dir = tmp / "glite"
            script_dir.mkdir()
            (script_dir / "globuscompute_submit.sh").write_text(submit.read_text(encoding="utf-8"), encoding="utf-8")
            (script_dir / "globuscompute_submit.sh").chmod(0o755)
            (script_dir / "globus_compute_setup.sh").write_text(setup.read_text(encoding="utf-8"), encoding="utf-8")
            (script_dir / "globus_compute_setup.sh").chmod(0o755)
            (script_dir / "globus_compute_helpers.py").write_text("# unused by fake python\n", encoding="utf-8")

            command = tmp / "pilot.sh"
            command.write_text("#!/usr/bin/env bash\necho pilot\n", encoding="utf-8")
            command.chmod(0o755)
            input_file = tmp / "input.txt"
            input_file.write_text("input\n", encoding="utf-8")
            credential = tmp / "credential.idtoken"
            credential.write_text("idtoken\n", encoding="utf-8")
            transfer_input = tmp / "transfer.idtoken"
            transfer_input.write_text("transfer idtoken\n", encoding="utf-8")
            factory_credential_dir = tmp / "client-proxies"
            factory_credential_subdir = factory_credential_dir / "user_frontend" / "glidein_gfactory_instance"
            factory_credential_subdir.mkdir(parents=True)
            factory_credential = factory_credential_subdir / (
                "credential_callback_IdTokenGenerator_ABC"
                ".globuscompute-smoke.idtoken.idtoken"
            )
            factory_credential.write_text("factory idtoken\n", encoding="utf-8")
            output_file = tmp / "result.txt"

            (script_dir / "blah_common_submit_functions.sh").write_text(
                "#!/usr/bin/env bash\n"
                "bls_parse_submit_options() {\n"
                "  bls_opt_job_name='unit-job'\n"
                f"  bls_opt_cmd='{command}'\n"
                "  bls_arguments='-entry globuscompute-smoke --flag two_words'\n"
                "  bls_opt_environment='\"GLOBUS_COMPUTE_ENDPOINT=endpoint-uuid\""
                " \"GLOBUS_COMPUTE_FUNCTION=function-uuid\"'\n"
                f"  bls_opt_workdir='{tmp}'\n"
                f"  bls_opt_stdin='{input_file}'\n"
                f"  bls_opt_stdout='{tmp / 'stdout.txt'}'\n"
                f"  bls_opt_stderr='{tmp / 'stderr.txt'}'\n"
                "}\n"
                "bls_setup_all_files() {\n"
                "  if [ -z \"${bls_opt_temp_dir:-}\" ]; then echo missing temp dir >&2; return 1; fi\n"
                "  if [ ! -d \"$bls_opt_temp_dir\" ] || [ ! -w \"$bls_opt_temp_dir\" ];"
                " then echo bad temp dir >&2; return 1; fi\n"
                "  if [[ \"$bls_opt_workdir\" != */ ]]; then \"$bls_opt_workdir=${bls_opt_workdir}/\"; fi\n"
                "  bls_inputsand_counter=0\n"
                "  let bls_inputsand_counter++\n"
                f"  bls_inputsand_local_0='{input_file}'\n"
                "  bls_inputsand_counter=1\n"
                f"  bls_inputcopy_local_0='{credential}'\n"
                "  bls_inputcopy_counter=1\n"
                f"  bls_outputsand_local_0='{output_file}'\n"
                "  bls_outputsand_counter=1\n"
                "  bls_arguments=\"$bls_arguments < \\\"$bls_opt_stdin\\\""
                " > \\\"$bls_opt_stdout\\\" 2> \\\"$bls_opt_stderr\\\"\"\n"
                "}\n",
                encoding="utf-8",
            )

            fake_python = tmp / "fake-python"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "$1" = "-c" ]; then exit 0; fi\n'
                "prev=''\n"
                'for arg in "$@"; do\n'
                '  if [ "$prev" = "--script" ]; then cp "$arg" "$FAKE_SCRIPT_COPY"; fi\n'
                "  prev=\"$arg\"\n"
                "done\n"
                'printf "%s\\n" "$@" > "$FAKE_PYTHON_ARGS"\n'
                'echo "BLAHP_JOBID_PREFIXglobuscompute/20260616/task-123"\n',
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            result = subprocess.run(
                ["bash", str(script_dir / "globuscompute_submit.sh"), "--ignored"],
                check=False,
                env={
                    "PATH": os.environ["PATH"],
                    "GLOBUS_COMPUTE_PYTHON": str(fake_python),
                    "GLOBUS_COMPUTE_AUTH_FILE": str(credential),
                    "GLIDEIN_ARGUMENTS": "-cluster 7 -subcluster 0",
                    "TransferInput": str(transfer_input),
                    "GLOBUS_COMPUTE_FACTORY_CREDENTIAL_DIR": str(factory_credential_dir),
                    "FAKE_PYTHON_ARGS": str(tmp / "helper-args.txt"),
                    "FAKE_SCRIPT_COPY": str(tmp / "generated-script.txt"),
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            helper_args = (tmp / "helper-args.txt").read_text(encoding="utf-8")
            generated_script = (tmp / "generated-script.txt").read_text(encoding="utf-8")

        self.assertEqual("BLAHP_JOBID_PREFIXglobuscompute/20260616/task-123\n", result.stdout)
        self.assertIn("--job-name\nunit-job\n", helper_args)
        self.assertIn("--input-files\n", helper_args)
        self.assertIn("--stdout\n", helper_args)
        self.assertIn("--stderr\n", helper_args)
        self.assertIn("--output-files\n", helper_args)
        self.assertIn(str(credential), helper_args)
        self.assertIn(str(transfer_input), helper_args)
        self.assertNotIn(str(factory_credential), helper_args)
        self.assertIn(str(output_file), helper_args)
        self.assertIn("export GLIDEIN_ARGUMENTS=", generated_script)
        self.assertIn("umask 077\n", generated_script)
        self.assertIn("replace(b\"umask 0022\", b\"umask 0077\", 1)", generated_script)
        self.assertIn("./pilot.sh -entry globuscompute-smoke --flag two_words < ./input.txt", generated_script)
        self.assertNotIn("\\<", generated_script)
        self.assertNotIn("\\>", generated_script)

    def test_submit_wrapper_does_not_use_eval(self):
        submit = TEST_DIR.parent / "factory/globus_compute/globuscompute_submit.sh"

        self.assertNotIn("eval", submit.read_text(encoding="utf-8"))
        self.assertNotIn("GLOBUS_COMPUTE_FACTORY_CREDENTIAL_DIR", submit.read_text(encoding="utf-8"))


class TestGlobusComputeTokenGenerator(unittest.TestCase):
    def _load_plugin(self):
        import importlib.util

        path = TEST_DIR.parent / "plugins/GlobusComputeTokenGenerator.py"
        spec = importlib.util.spec_from_file_location("gwms_test_gc_token_generator", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_generate_reads_secret_and_wraps_minted_token(self):
        module = self._load_plugin()
        minted = {
            "access_token": "minted-token",
            "expires_at_seconds": 99999999999,
            "scope": "all",
            "resource_server": "funcx_service",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            secret_file = Path(tmpdir) / "client_secret"
            secret_file.write_text("super-secret\n", encoding="utf-8")
            generator = module.GlobusComputeTokenGenerator(
                context={
                    "client_id": "confidential-client-id",
                    "client_secret_file": str(secret_file),
                    "tkn_dir": tmpdir,
                }
            )
            with mock.patch.object(module, "mint_access_token", return_value=minted) as mint:
                credential = generator._generate(logger=mock.Mock())

        self.assertEqual("minted-token", credential.access_token)
        self.assertTrue(credential.valid)
        mint.assert_called_once_with(
            client_id="confidential-client-id",
            client_secret="super-secret",
            scope=module.GLOBUS_COMPUTE_ALL_SCOPE,
            resource_server="funcx_service",
        )


if __name__ == "__main__":
    unittest.main()
