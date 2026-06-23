#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Helpers for the BLAHP-shaped Globus Compute batch adapter."""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


BLAHP_JOB_PREFIX = "BLAHP_JOBID_PREFIX"
GLOBUS_COMPUTE_JOB_PREFIX = "globuscompute"
DEFAULT_STATE_DIR = "~/.blah/globus_compute_jobs"
DEFAULT_RUNNER_NAME = "gwms-globuscompute-runner-v1"
GLOBUS_COMPUTE_ALL_SCOPE = "https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all"
SUBMIT_ENV_KEYS = ("GLIDEIN_ARGUMENTS",)
SAFE_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class GlobusComputeJobState:
    submit_date: str
    glidein_id: str
    endpoint_id: str
    function_id: str
    auth_mode: str = "delegated_user"
    auth_file: str = ""
    base_dir: str = ""
    stdout: str = ""
    stderr: str = ""
    outputs: list[str] | None = None


def _state_root(state_dir: str | Path | None = None) -> Path:
    return Path(os.path.expanduser(str(state_dir or os.environ.get("GLOBUS_COMPUTE_STATE_DIR", DEFAULT_STATE_DIR))))


def parse_blahp_job_id(blahp_job_id: str) -> tuple[str, str]:
    job_id = blahp_job_id
    if job_id.startswith(BLAHP_JOB_PREFIX):
        job_id = job_id[len(BLAHP_JOB_PREFIX):]

    parts = job_id.split("/", 2)
    if len(parts) != 3 or parts[0] != GLOBUS_COMPUTE_JOB_PREFIX or not parts[1] or not parts[2]:
        raise ValueError("expected globuscompute/<date>/<glidein_id>")

    return parts[1], parts[2]


def _state_path(submit_date: str, glidein_id: str, state_dir: str | Path | None = None) -> Path:
    return _state_root(state_dir) / f"{submit_date}_{glidein_id}"


def write_job_state(state: GlobusComputeJobState, state_dir: str | Path | None = None) -> Path:
    path = _state_path(state.submit_date, state.glidein_id, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), sort_keys=True), encoding="utf-8")
    return path


def load_job_state(blahp_job_id: str, state_dir: str | Path | None = None) -> GlobusComputeJobState:
    submit_date, glidein_id = parse_blahp_job_id(blahp_job_id)
    path = _state_path(submit_date, glidein_id, state_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    return GlobusComputeJobState(**data)


def delete_job_state(blahp_job_id: str, state_dir: str | Path | None = None) -> None:
    submit_date, glidein_id = parse_blahp_job_id(blahp_job_id)
    _state_path(submit_date, glidein_id, state_dir).unlink(missing_ok=True)


def is_task_execution_failed(exc: Exception) -> bool:
    try:
        from globus_compute_sdk.errors import TaskExecutionFailed
    except ImportError:
        TaskExecutionFailed = ()  # type: ignore[assignment]
    return isinstance(exc, TaskExecutionFailed) or exc.__class__.__name__ == "TaskExecutionFailed"


def _is_task_pending(exc: Exception) -> bool:
    return exc.__class__.__name__ == "TaskPending" or "pending" in str(exc).lower()


def run_control_op(
    client: Any,
    *,
    endpoint_id: str,
    function_id: str,
    payload: dict[str, Any],
    timeout: float = 120.0,
    interval: float = 2.0,
) -> dict[str, Any]:
    """Run one short control-function task (launch/status/cancel) and return its result.

    Each op is a brief Globus Compute task, so we submit it and wait for its result;
    the glidein it manages runs detached, independent of this task.
    """
    task_id = client.run(payload, endpoint_id=endpoint_id, function_id=function_id)
    deadline = time.time() + timeout
    while True:
        try:
            return client.get_result(task_id)
        except Exception as exc:
            if not _is_task_pending(exc):
                raise
            if time.time() >= deadline:
                raise TimeoutError(f"Globus Compute control task {task_id} did not return within {timeout:g}s") from exc
            time.sleep(interval)


def format_blahp_job_id(submit_date: str, glidein_id: str) -> str:
    return f"{BLAHP_JOB_PREFIX}{GLOBUS_COMPUTE_JOB_PREFIX}/{submit_date}/{glidein_id}"


def _safe_environment(environ: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in environ.items()
        if key in SUBMIT_ENV_KEYS and SAFE_ENV_RE.match(key) and not key.startswith("GLOBUS_COMPUTE_")
    }


def _stage_file(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    return {
        "name": source.name,
        "content_b64": base64.b64encode(source.read_bytes()).decode("ascii"),
        "executable": os.access(source, os.X_OK),
    }


def build_payload_from_script(
    *,
    job_name: str,
    script_path: str | Path,
    environment: dict[str, str] | None = None,
    input_files: list[str] | None = None,
    output_files: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "job_name": job_name,
        "script": Path(script_path).read_text(encoding="utf-8"),
        "environment": _safe_environment(environment or {}),
        "files": [_stage_file(path) for path in input_files or [] if path],
        "outputs": [Path(path).name for path in output_files or []],
    }


def launch_glidein(
    client: Any,
    *,
    endpoint_id: str,
    function_id: str,
    payload: dict[str, Any],
    glidein_id: str,
    auth_mode: str = "delegated_user",
    auth_file: str = "",
    base_dir: str = "",
    stdout: str = "",
    stderr: str = "",
    outputs: list[str] | None = None,
    submit_date: str | None = None,
    state_dir: str | Path | None = None,
    timeout: float = 120.0,
) -> str:
    submit_date = submit_date or time.strftime("%Y%m%d")
    launch_payload = dict(payload)
    launch_payload["op"] = "launch"
    launch_payload["glidein_id"] = glidein_id
    if base_dir:
        launch_payload["base_dir"] = base_dir
    run_control_op(
        client, endpoint_id=endpoint_id, function_id=function_id, payload=launch_payload, timeout=timeout
    )
    state = GlobusComputeJobState(
        submit_date=submit_date,
        glidein_id=glidein_id,
        endpoint_id=endpoint_id,
        function_id=function_id,
        auth_mode=auth_mode,
        auth_file=auth_file,
        base_dir=base_dir,
        stdout=stdout,
        stderr=stderr,
        outputs=outputs or [],
    )
    write_job_state(state, state_dir=state_dir)
    return format_blahp_job_id(submit_date, glidein_id)


def format_status_classad_with_exit_code(task_id: str, blahp_status: int, exit_code: int | None) -> str:
    attrs = [f'BatchJobId="{task_id}"', f"JobStatus={blahp_status}"]
    if exit_code is not None:
        attrs.append(f"ExitCode={exit_code}")
    return f"0[{';'.join(attrs)};]"


def _write_text_result(path: str, content: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _append_output_error_diagnostics(stderr: str, output_errors: dict[str, str]) -> str:
    if not output_errors:
        return stderr
    lines = []
    if stderr and not stderr.endswith("\n"):
        lines.append("")
    lines.extend(f"{name}: {reason}" for name, reason in sorted(output_errors.items()))
    return stderr + "\n".join(lines) + "\n"


def _write_failure_diagnostics(state: GlobusComputeJobState, reason: str) -> None:
    """Write the empty stdout and diagnostic stderr expected for a task that failed without a fetchable result."""
    _write_text_result(state.stdout, "")
    _write_text_result(state.stderr, reason if reason.endswith("\n") else reason + "\n")


def _write_output_results(output_paths: list[str], encoded_outputs: dict[str, str]) -> None:
    outputs_by_name = {Path(path).name: path for path in output_paths}
    for name, content_b64 in encoded_outputs.items():
        if name not in outputs_by_name:
            continue
        target = Path(outputs_by_name[name])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(content_b64))


def status_for_job(
    blahp_job_id: str,
    *,
    client: Any | None = None,
    state_dir: str | Path | None = None,
) -> str:
    state = load_job_state(blahp_job_id, state_dir=state_dir)
    client = client or create_client(auth_file=state.auth_file)
    _submit_date, glidein_id = parse_blahp_job_id(blahp_job_id)

    result = run_control_op(
        client,
        endpoint_id=state.endpoint_id,
        function_id=state.function_id,
        payload={"op": "status", "glidein_id": glidein_id, "base_dir": state.base_dir},
    )
    glidein_state = str(result.get("state", "")).lower()

    if glidein_state == "running":
        return format_status_classad_with_exit_code(glidein_id, 2, None)

    if glidein_state == "completed":
        exit_code = int(result.get("returncode", 0))
        _write_text_result(state.stdout, str(result.get("stdout", "")))
        _write_text_result(
            state.stderr,
            _append_output_error_diagnostics(str(result.get("stderr", "")), result.get("output_errors", {})),
        )
        _write_output_results(state.outputs or [], result.get("outputs", {}))
        delete_job_state(blahp_job_id, state_dir=state_dir)
        return format_status_classad_with_exit_code(glidein_id, 4, exit_code)

    # "unknown": the glidein workdir is gone without a recorded exit code.
    _write_failure_diagnostics(state, f"Globus Compute glidein {glidein_id} ended without an exit code")
    delete_job_state(blahp_job_id, state_dir=state_dir)
    return format_status_classad_with_exit_code(glidein_id, 4, 1)


def cancel_job(
    blahp_job_id: str,
    *,
    client: Any | None = None,
    state_dir: str | Path | None = None,
) -> int:
    _, glidein_id = parse_blahp_job_id(blahp_job_id)
    try:
        state = load_job_state(blahp_job_id, state_dir=state_dir)
    except FileNotFoundError:
        return 0  # nothing tracked locally; treat as already cancelled
    client = client or create_client(auth_file=state.auth_file)
    run_control_op(
        client,
        endpoint_id=state.endpoint_id,
        function_id=state.function_id,
        payload={"op": "cancel", "glidein_id": glidein_id, "base_dir": state.base_dir},
    )
    delete_job_state(blahp_job_id, state_dir=state_dir)
    return 0


def _read_json_credential(auth_file: str) -> dict:
    try:
        data = json.loads(Path(os.path.expanduser(auth_file)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def create_client(*, auth_file: str = "") -> Any:
    if not auth_file:
        raise RuntimeError("GLOBUS_COMPUTE_AUTH_FILE is required for delegated authentication")

    credential = _read_json_credential(auth_file)

    # Confidential client credential: grab a token in-process via client-credentials.
    if credential.get("client_id") and credential.get("client_secret"):
        from globus_compute_sdk import Client
        from globus_sdk import ClientApp, GlobusAppConfig
        from globus_sdk.token_storage import MemoryTokenStorage

        app = ClientApp(
            "glideinwms-globus-compute",
            client_id=credential["client_id"],
            client_secret=credential["client_secret"],
            config=GlobusAppConfig(token_storage=MemoryTokenStorage()),
        )
        return Client(app=app)

    # Pre-minted access token (e.g. from the generator or mint-token).
    if isinstance(credential.get("access_token"), str):
        from globus_compute_sdk import Client
        from globus_sdk import AccessTokenAuthorizer

        return Client(authorizer=AccessTokenAuthorizer(credential["access_token"]))

    raise RuntimeError(
        "GLOBUS_COMPUTE_AUTH_FILE must hold a confidential {client_id, client_secret} credential "
        "or a minted Globus Compute access token"
    )


def create_registration_client(*, auth_file: str = "") -> Any:
    return create_client(auth_file=auth_file)


def mint_access_token(
    *,
    client_id: str,
    client_secret: str,
    scope: str = GLOBUS_COMPUTE_ALL_SCOPE,
    resource_server: str = "funcx_service",
) -> dict:
    """Mint a Globus Compute access token with the OAuth2 client-credentials grant."""
    if not client_id or not client_secret:
        raise RuntimeError("client_id and client_secret are required to mint a Globus Compute token")

    from globus_sdk import ConfidentialAppAuthClient

    response = ConfidentialAppAuthClient(client_id, client_secret).oauth2_client_credentials_tokens(
        requested_scopes=[scope]
    )
    token = response.by_resource_server[resource_server]
    return {
        "access_token": token["access_token"],
        "expires_at_seconds": token["expires_at_seconds"],
        "scope": token.get("scope", scope),
        "resource_server": resource_server,
    }


def load_runner_source() -> str:
    runner_path = Path(__file__).with_name("globus_compute_runner.py")
    return runner_path.read_text(encoding="utf-8")


def _register_runner_source(client: Any, function_name: str, runner_source: str | None = None) -> str:
    source = runner_source if runner_source is not None else load_runner_source()
    return client.register_source_code(
        source,
        "run_globus_compute_payload",
        description=function_name,
        public=False,
    )


def _auth_cache_key(auth_file: str) -> str:
    credential = _read_json_credential(auth_file)
    if credential.get("client_id") and credential.get("client_secret"):
        return f"client_id:{str(credential['client_id']).strip()}"

    path = Path(os.path.expanduser(auth_file))
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    metadata: dict[str, Any] = {"path": str(resolved)}
    try:
        stat_info = path.stat()
    except OSError:
        pass
    else:
        metadata["uid"] = stat_info.st_uid
        metadata["gid"] = stat_info.st_gid

    key_json = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return f"auth_file:{hashlib.sha256(key_json.encode('utf-8')).hexdigest()}"


def _function_cache_key_material(endpoint_id: str, auth_key: str, runner_sha256: str) -> dict[str, str]:
    return {
        "endpoint_id": endpoint_id,
        "auth_key": auth_key,
        "runner_sha256": runner_sha256,
    }


def _function_cache_path(
    endpoint_id: str,
    auth_key: str,
    runner_sha256: str,
    state_dir: str | Path | None = None,
) -> Path:
    key_json = json.dumps(
        _function_cache_key_material(endpoint_id, auth_key, runner_sha256),
        sort_keys=True,
        separators=(",", ":"),
    )
    return _state_root(state_dir) / "functions" / f"{hashlib.sha256(key_json.encode('utf-8')).hexdigest()}.json"


def _read_function_cache_record(
    cache_path: Path,
    *,
    endpoint_id: str,
    auth_key: str,
    runner_sha256: str,
) -> dict[str, Any] | None:
    try:
        record = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    if record.get("schema_version") != 1:
        return None
    if record.get("endpoint_id") != endpoint_id:
        return None
    if record.get("auth_key") != auth_key:
        return None
    if record.get("runner_sha256") != runner_sha256:
        return None
    if record.get("function_name") != DEFAULT_RUNNER_NAME:
        return None
    if not isinstance(record.get("registered_at"), (int, float)):
        return None
    if not isinstance(record.get("last_used_at"), (int, float)):
        return None
    if not str(record.get("function_id", "")).strip():
        return None
    return record


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _function_cache_context(
    endpoint_id: str,
    auth_file: str,
    state_dir: str | Path | None = None,
) -> tuple[str, str, str, Path]:
    runner_source = load_runner_source()
    runner_sha256 = hashlib.sha256(runner_source.encode("utf-8")).hexdigest()
    auth_key = _auth_cache_key(auth_file)
    return runner_source, runner_sha256, auth_key, _function_cache_path(endpoint_id, auth_key, runner_sha256, state_dir)


def _write_function_cache_record(
    cache_path: Path,
    *,
    endpoint_id: str,
    auth_key: str,
    runner_sha256: str,
    function_id: str,
    function_name: str,
) -> None:
    now = time.time()
    _write_json_atomic(
        cache_path,
        {
            "schema_version": 1,
            "endpoint_id": endpoint_id,
            "auth_key": auth_key,
            "runner_sha256": runner_sha256,
            "function_id": function_id,
            "function_name": function_name,
            "registered_at": now,
            "last_used_at": now,
        },
    )


def _register_and_write_function_cache(
    client: Any,
    *,
    endpoint_id: str,
    auth_key: str,
    runner_sha256: str,
    runner_source: str,
    cache_path: Path,
    function_name: str = DEFAULT_RUNNER_NAME,
) -> str:
    function_id = _register_runner_source(client, function_name, runner_source=runner_source)
    _write_function_cache_record(
        cache_path,
        endpoint_id=endpoint_id,
        auth_key=auth_key,
        runner_sha256=runner_sha256,
        function_id=function_id,
        function_name=function_name,
    )
    return function_id


def resolve_cached_or_register_function(
    client: Any,
    endpoint_id: str,
    auth_file: str,
    state_dir: str | Path | None = None,
) -> tuple[str, bool]:
    runner_source, runner_sha256, auth_key, cache_path = _function_cache_context(endpoint_id, auth_file, state_dir)
    lock_path = cache_path.with_name(f"{cache_path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            record = _read_function_cache_record(
                cache_path,
                endpoint_id=endpoint_id,
                auth_key=auth_key,
                runner_sha256=runner_sha256,
            )
            if record is not None:
                record["last_used_at"] = time.time()
                _write_json_atomic(cache_path, record)
                return str(record["function_id"]), True
            return (
                _register_and_write_function_cache(
                    client,
                    endpoint_id=endpoint_id,
                    auth_key=auth_key,
                    runner_sha256=runner_sha256,
                    runner_source=runner_source,
                    cache_path=cache_path,
                ),
                False,
            )
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def register_and_update_function_cache(
    client: Any,
    endpoint_id: str,
    auth_file: str,
    state_dir: str | Path | None = None,
    failed_function_id: str = "",
) -> str:
    runner_source, runner_sha256, auth_key, cache_path = _function_cache_context(endpoint_id, auth_file, state_dir)
    lock_path = cache_path.with_name(f"{cache_path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            record = _read_function_cache_record(
                cache_path,
                endpoint_id=endpoint_id,
                auth_key=auth_key,
                runner_sha256=runner_sha256,
            )
            if failed_function_id and record is not None and record.get("function_id") != failed_function_id:
                return str(record["function_id"])
            return _register_and_write_function_cache(
                client,
                endpoint_id=endpoint_id,
                auth_key=auth_key,
                runner_sha256=runner_sha256,
                runner_source=runner_source,
                cache_path=cache_path,
            )
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def is_repairable_function_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError) or is_task_execution_failed(exc):
        return False

    class_name = exc.__class__.__name__.lower()
    if "function" in class_name and any(term in class_name for term in ("notfound", "not_found", "missing")):
        return True

    status = getattr(exc, "http_status", None) or getattr(exc, "status_code", None)
    message = str(exc).lower()
    if status == 404 and "function" in message:
        return True

    codes = [str(getattr(exc, attr, "")).lower() for attr in ("code", "error_code")]
    if any(
        code
        for code in codes
        if "function" in code and any(term in code for term in ("not_found", "notfound", "missing", "invalid"))
    ):
        return True

    if "invalid function" in message or "function id invalid" in message or "function_id invalid" in message:
        return True

    return any(
        phrase in message
        for phrase in (
            "function id not found",
            "function_id not found",
            "function not found",
            "function does not exist",
            "function has been deleted",
            "registered function not found",
        )
    )


def register_runner(function_name: str, *, auth_file: str = "") -> str:
    return _register_runner_source(create_registration_client(auth_file=auth_file), function_name)


def _cmd_parse_job_id(args: argparse.Namespace) -> int:
    submit_date, task_id = parse_blahp_job_id(args.job_id)
    print(f"{submit_date} {task_id}")
    return 0


def _cmd_submit(args: argparse.Namespace) -> int:
    input_files = [item for item in (args.input_files or "").split(",") if item]
    outputs = [item for item in (args.output_files or "").split(",") if item]
    payload = build_payload_from_script(
        job_name=args.job_name,
        script_path=args.script,
        environment=os.environ,
        input_files=input_files,
        output_files=outputs,
    )
    stdout = args.stdout or ""
    stderr = args.stderr or ""
    auth_file = os.environ.get("GLOBUS_COMPUTE_AUTH_FILE", "")
    endpoint_id = os.environ["GLOBUS_COMPUTE_ENDPOINT"]

    client = create_client(auth_file=auth_file)
    function_id = os.environ.get("GLOBUS_COMPUTE_FUNCTION", "").strip()
    function_is_configured = bool(function_id)
    function_from_cache = False
    if not function_id:
        function_id, function_from_cache = resolve_cached_or_register_function(client, endpoint_id, auth_file)

    glidein_id = uuid.uuid4().hex
    endpoint_base_dir = os.environ.get("GLOBUS_COMPUTE_ENDPOINT_WORK_DIR", "").strip()
    launch_kwargs = {
        "client": client,
        "endpoint_id": endpoint_id,
        "payload": payload,
        "glidein_id": glidein_id,
        "auth_mode": "delegated_user",
        "auth_file": auth_file,
        "base_dir": endpoint_base_dir,
        "stdout": stdout,
        "stderr": stderr,
        "outputs": outputs,
    }
    try:
        blahp_job_id = launch_glidein(function_id=function_id, **launch_kwargs)
    except Exception as exc:
        if function_is_configured or not function_from_cache or not is_repairable_function_error(exc):
            raise
        function_id = register_and_update_function_cache(
            client,
            endpoint_id,
            auth_file,
            failed_function_id=function_id,
        )
        try:
            blahp_job_id = launch_glidein(function_id=function_id, **launch_kwargs)
        except Exception as retry_exc:
            raise RuntimeError(
                f"Globus Compute submit failed after repairing function {function_id} for endpoint {endpoint_id}: "
                f"{retry_exc}"
            ) from retry_exc
    print(blahp_job_id)
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    print(status_for_job(args.job_id))
    return 0


def _cmd_cancel(args: argparse.Namespace) -> int:
    cancel_job(args.job_id)
    return 0


def _cmd_register_runner(args: argparse.Namespace) -> int:
    print(register_runner(args.name, auth_file=os.environ.get("GLOBUS_COMPUTE_AUTH_FILE", "")))
    return 0


def _cmd_mint_token(args: argparse.Namespace) -> int:
    client_id = args.client_id or os.environ.get("GLOBUS_COMPUTE_CLIENT_ID", "")
    client_secret = ""
    if args.credential_file:
        creds = json.loads(Path(os.path.expanduser(args.credential_file)).read_text(encoding="utf-8"))
        client_id = client_id or creds.get("client_id", "")
        client_secret = creds.get("client_secret", "")
    if not client_secret:
        secret_file = args.client_secret_file or os.environ.get("GLOBUS_COMPUTE_CLIENT_SECRET_FILE", "")
        if secret_file:
            client_secret = Path(os.path.expanduser(secret_file)).read_text(encoding="utf-8").strip()

    token_doc = mint_access_token(client_id=client_id, client_secret=client_secret, scope=args.scope)

    output = args.output or os.environ.get("GLOBUS_COMPUTE_AUTH_FILE", "")
    if not output:
        raise RuntimeError("mint-token requires --output or GLOBUS_COMPUTE_AUTH_FILE (refusing to print the token)")
    path = Path(os.path.expanduser(output))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token_doc), encoding="utf-8")
    path.chmod(0o600)
    print(str(path))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_job_id = subparsers.add_parser("parse-job-id")
    parse_job_id.add_argument("job_id")
    parse_job_id.set_defaults(func=_cmd_parse_job_id)

    submit = subparsers.add_parser("submit")
    submit.add_argument("--job-name", default="")
    submit.add_argument("--script", required=True)
    submit.add_argument("--input-files", default="")
    submit.add_argument("--stdout", default="")
    submit.add_argument("--stderr", default="")
    submit.add_argument("--output-files", default="")
    submit.set_defaults(func=_cmd_submit)

    status = subparsers.add_parser("status")
    status.add_argument("job_id")
    status.set_defaults(func=_cmd_status)

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("job_id")
    cancel.set_defaults(func=_cmd_cancel)

    register = subparsers.add_parser("register-runner")
    register.add_argument("--name", default="gwms-globuscompute-runner-v1")
    register.set_defaults(func=_cmd_register_runner)

    mint = subparsers.add_parser("mint-token")
    mint.add_argument("--credential-file", default="")
    mint.add_argument("--client-id", default="")
    mint.add_argument("--client-secret-file", default="")
    mint.add_argument("--scope", default=GLOBUS_COMPUTE_ALL_SCOPE)
    mint.add_argument("--output", default="")
    mint.set_defaults(func=_cmd_mint_token)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
