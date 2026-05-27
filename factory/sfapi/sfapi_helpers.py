#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Standalone helper CLI for the prototype SFAPI BLAHP backend."""

import argparse
import getpass
import json
import os
import shlex
import sys

from contextlib import contextmanager
from pathlib import Path

BLAHP_JOBID_PREFIX = "BLAHP_JOBID_PREFIX"
DEFAULT_RESOURCE = "perlmutter"
DEFAULT_TRANSFER_MACHINE = "dtns"
DEFAULT_STATE_DIR = "~/.blah/sfapi_jobs"
DEFAULT_CLIENT_ID_FILE = "~/.superfacility/clientid.txt"
DEFAULT_PRIVATE_KEY_JWK_FILE = "~/.superfacility/priv_key.jwk"


def _read_text_file(path):
    return Path(path).expanduser().read_text().strip()


def _require_env(env, key):
    value = env.get(key)
    if not value:
        raise RuntimeError("%s is required for SFAPI authentication" % key)
    return value


def _import_jwk(jwk_data):
    from authlib.jose import JsonWebKey

    if isinstance(jwk_data, str):
        jwk_data = json.loads(jwk_data)
    return JsonWebKey.import_key(jwk_data)


def _read_auth_bundle(path):
    auth_data = json.loads(Path(path).expanduser().read_text())
    try:
        return auth_data["client_id"], auth_data["private_key_jwk"]
    except KeyError as err:
        raise RuntimeError("SFAPI_AUTH_FILE is missing required key %s" % err.args[0]) from err


def resolve_auth(env=None):
    """Resolve SFAPI client credentials from the prototype auth interface."""

    env = env or os.environ
    auth_mode = env.get("SFAPI_AUTH_MODE", "default").lower()

    if auth_mode == "auth_file":
        client_id, private_key_jwk = _read_auth_bundle(_require_env(env, "SFAPI_AUTH_FILE"))
    elif auth_mode == "env":
        client_id = _require_env(env, "SFAPI_CLIENT_ID")
        private_key_jwk = _require_env(env, "SFAPI_PRIVATE_KEY_JWK")
    elif auth_mode == "file":
        client_id = _read_text_file(_require_env(env, "SFAPI_CLIENT_ID_FILE"))
        private_key_jwk = _read_text_file(_require_env(env, "SFAPI_PRIVATE_KEY_JWK_FILE"))
    elif auth_mode in ("", "default"):
        client_id = _read_text_file(env.get("SFAPI_CLIENT_ID_FILE", DEFAULT_CLIENT_ID_FILE))
        private_key_jwk = _read_text_file(env.get("SFAPI_PRIVATE_KEY_JWK_FILE", DEFAULT_PRIVATE_KEY_JWK_FILE))
    else:
        raise RuntimeError("Unsupported SFAPI_AUTH_MODE=%s" % auth_mode)

    return client_id, _import_jwk(private_key_jwk)


def make_client(auth_required=True):
    from sfapi_client import Client

    if not auth_required:
        return Client()

    client_id, secret = resolve_auth()
    return Client(client_id, secret)


@contextmanager
def sfapi_client(auth_required=True):
    client = make_client(auth_required=auth_required)
    try:
        yield client
    finally:
        client.close()


def get_resource():
    return os.environ.get("SFAPI_RESOURCE", DEFAULT_RESOURCE)


def get_transfer_machine():
    return os.environ.get("SFAPI_TRANSFER_MACHINE", DEFAULT_TRANSFER_MACHINE)


def get_username():
    return os.environ.get("SFAPI_USERNAME") or os.environ.get("NERSC_USERNAME") or os.environ.get("USER") or getpass.getuser()


def get_state_dir(state_dir=None):
    return Path(state_dir or os.environ.get("SFAPI_STATE_DIR", DEFAULT_STATE_DIR)).expanduser()


def parse_input_files(input_files_csv):
    if not input_files_csv:
        return []
    return [item for item in (path.strip() for path in input_files_csv.split(",")) if item]


def build_remote_workdir(job_name, username=None):
    username = username or get_username()
    if not username:
        raise RuntimeError("Unable to determine SFAPI username")
    return "/pscratch/sd/%s/%s/.gwms-sfapi/%s" % (username[0], username, Path(job_name).name)


def build_submit_script(script_text, remote_dir, job_name):
    directives = [
        "#SBATCH --output=%s/%s.out" % (remote_dir, job_name),
        "#SBATCH --error=%s/%s.err" % (remote_dir, job_name),
        "#SBATCH --chdir=%s" % remote_dir,
    ]
    lines = script_text.splitlines(True)
    if lines and lines[0].startswith("#!"):
        return lines[0] + "\n".join(directives) + "\n" + "".join(lines[1:])
    return "#!/bin/bash\n" + "\n".join(directives) + "\n" + script_text


def parse_blahp_job_id(job_id):
    if job_id.startswith(BLAHP_JOBID_PREFIX):
        job_id = job_id[len(BLAHP_JOBID_PREFIX) :]
    parts = job_id.split("/")
    if len(parts) == 3 and parts[0] == "sfapi":
        return parts[1], parts[2]
    raise ValueError("Expected sfapi/<YYYYMMDD>/<jobid>, got %s" % job_id)


def bare_slurm_job_id(job_id):
    try:
        return parse_blahp_job_id(job_id)[1]
    except ValueError:
        return job_id


def jobstate_path(blahp_job_id, state_dir=None):
    date, job_id = parse_blahp_job_id(blahp_job_id)
    return get_state_dir(state_dir) / ("%s_%s" % (date, job_id))


def iter_jobstate_entries(path):
    with open(path) as jobstate:
        for line in jobstate:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            kind, payload = line.split("::", 1)
            if kind == "meta":
                continue
            local_path, remote_path = payload.split(":", 1)
            yield kind, local_path, remote_path


def read_job_metadata(path):
    metadata = {}
    try:
        with open(path) as jobstate:
            for line in jobstate:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                kind, payload = line.split("::", 1)
                if kind != "meta":
                    continue
                key, value = payload.split(":", 1)
                if value:
                    metadata[key] = value
    except FileNotFoundError:
        pass
    return metadata


def apply_job_metadata(blahp_job_id, state_dir=None):
    try:
        metadata = read_job_metadata(jobstate_path(blahp_job_id, state_dir=state_dir))
    except ValueError:
        return

    env_map = {
        "auth_mode": "SFAPI_AUTH_MODE",
        "auth_file": "SFAPI_AUTH_FILE",
        "resource": "SFAPI_RESOURCE",
        "transfer_machine": "SFAPI_TRANSFER_MACHINE",
        "venv": "SFAPI_VENV",
        "username": "SFAPI_USERNAME",
        "nersc_username": "NERSC_USERNAME",
    }
    for key, env_key in env_map.items():
        value = metadata.get(key)
        if value and not os.environ.get(env_key):
            os.environ[env_key] = value


def upload_input_file(transfer_compute, remote_path_cls, local_path, remote_dir):
    remote_path = "%s/%s" % (remote_dir, Path(local_path).name)
    with open(local_path, "rb") as input_file:
        remote_path_cls(path=remote_path, compute=transfer_compute).upload(input_file)
    return remote_path


def download_job_outputs(blahp_job_id, transfer_compute, remote_path_cls=None, state_dir=None):
    if remote_path_cls is None:
        from sfapi_client._sync.paths import RemotePath as remote_path_cls

    state_path = jobstate_path(blahp_job_id, state_dir=state_dir)
    for _kind, local_path, remote_path in iter_jobstate_entries(state_path):
        local = Path(local_path)
        local.parent.mkdir(parents=True, exist_ok=True)
        with remote_path_cls(path=remote_path, compute=transfer_compute).download(binary=True) as remote_file:
            local.write_bytes(remote_file.read())
    state_path.unlink()


def submit(args):
    from sfapi_client._sync.paths import RemotePath

    job_name = Path(args.job_name).name
    remote_dir = build_remote_workdir(job_name)
    remote_stdout = "%s/%s.out" % (remote_dir, job_name)
    remote_stderr = "%s/%s.err" % (remote_dir, job_name)

    script_text = Path(args.script).read_text()
    submit_script = build_submit_script(script_text, remote_dir, job_name)

    with sfapi_client(auth_required=True) as client:
        compute = client.compute(get_resource())
        transfer = client.compute(get_transfer_machine())
        transfer.run("mkdir -p %s" % shlex.quote(remote_dir))
        for input_file in parse_input_files(args.input_files):
            upload_input_file(transfer, RemotePath, input_file, remote_dir)
        job = compute.submit_job(submit_script)

    print("SFAPI_RESULT:%s:%s:%s" % (job.jobid, remote_stdout, remote_stderr))


def get_job_state(compute, job_id):
    from sfapi_client._jobs import JobCommand

    for command in (JobCommand.squeue, JobCommand.sacct):
        try:
            job = compute.job(job_id, command=command)
            state = job.state
            return getattr(state, "value", str(state))
        except Exception as err:
            if "not found" not in str(err).lower() and command == JobCommand.sacct:
                raise
    return "UNKNOWN"


def status(args):
    if args.type == "resource":
        with sfapi_client(auth_required=False) as client:
            status_obj = client.resources.status(args.value)
        value = getattr(status_obj.status, "value", str(status_obj.status))
        print("Resource %s status: %s" % (args.value, value))
        if value != "active":
            return 1
        return 0

    apply_job_metadata(args.value)
    job_id = bare_slurm_job_id(args.value)
    with sfapi_client(auth_required=True) as client:
        compute = client.compute(get_resource())
        state = get_job_state(compute, job_id)
    print("Job %s state: %s" % (job_id, state))
    return 0


def download(args):
    apply_job_metadata(args.blahp_job_id)
    with sfapi_client(auth_required=True) as client:
        transfer = client.compute(get_transfer_machine())
        download_job_outputs(args.blahp_job_id, transfer)


def cancel(args):
    apply_job_metadata(args.job_id)
    job_id = bare_slurm_job_id(args.job_id)
    with sfapi_client(auth_required=True) as client:
        compute = client.compute(get_resource())
        try:
            compute.client.delete("compute/jobs/%s/%s" % (compute.name, job_id))
        except Exception as err:
            if "not found" not in str(err).lower() and "404" not in str(err):
                raise


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("--job-name", required=True)
    submit_parser.add_argument("--input-files", default="")
    submit_parser.add_argument("--script", required=True)
    submit_parser.set_defaults(func=submit)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--type", required=True, choices=("resource", "job"))
    status_parser.add_argument("--value", required=True)
    status_parser.set_defaults(func=status)

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("blahp_job_id")
    download_parser.set_defaults(func=download)

    cancel_parser = subparsers.add_parser("cancel")
    cancel_parser.add_argument("job_id")
    cancel_parser.set_defaults(func=cancel)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
        return 0 if result is None else result
    except Exception as err:
        print("SFAPI_ERROR:%s" % err, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
