#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Globus Compute endpoint-side control function for factory-submitted glideins.

This mirrors the BLAHP submit/status/cancel model: the endpoint host plays the
role of the batch system. A `launch` op stages the glidein and starts it as a
detached process (returning a handle immediately), `status` reports whether that
process is still running or has finished, and `cancel` kills it. Each op is a
short Globus Compute task, so the service reports clean terminal status while the
glidein itself runs independently of the worker.
"""


def run_globus_compute_payload(payload: dict) -> dict:
    """Dispatch one BLAHP-style op (launch/status/cancel) for a GWMS glidein.

    The function is intentionally self-contained so it can be registered with
    Globus Compute and executed on an endpoint without importing GlideinWMS.
    """

    import base64
    import os
    import shutil
    import signal
    import socket
    import subprocess
    import sys

    from pathlib import Path

    op = payload.get("op", "launch")
    base_dir = Path(os.path.expanduser(payload.get("base_dir") or "~/.gwms-glideins"))
    glidein_id = str(payload.get("glidein_id") or "")
    if not glidein_id or "/" in glidein_id or ".." in glidein_id:
        raise ValueError(f"invalid glidein_id: {glidein_id!r}")
    workdir = base_dir / glidein_id

    default_cap = 1024 * 1024
    result_max_bytes = int(payload.get("result_max_bytes") or default_cap)
    output_max_bytes = int(payload.get("output_max_bytes") or result_max_bytes)

    def safe_name(name: str) -> str:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or not path.name:
            raise ValueError(f"unsafe payload filename: {name}")
        return path.name

    def bounded_text(path: Path, stream_name: str) -> str:
        if not path.exists():
            return ""
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > result_max_bytes:
                handle.seek(size - result_max_bytes)
            data = handle.read(result_max_bytes)
        text = data.decode("utf-8", errors="replace")
        if size <= result_max_bytes:
            return text
        return f"[Globus Compute {stream_name} truncated to last {result_max_bytes} bytes from {size} bytes]\n{text}"

    def collect_outputs(output_names):
        outputs = {}
        output_errors = {}
        for output_name in output_names or []:
            name = safe_name(str(output_name))
            output_path = workdir / name
            if output_path.exists() and output_path.is_file():
                output_size = output_path.stat().st_size
                if output_size > output_max_bytes:
                    output_errors[name] = (
                        f"output exceeded Globus Compute result cap: {output_size} bytes > {output_max_bytes} bytes"
                    )
                    continue
                outputs[name] = base64.b64encode(output_path.read_bytes()).decode("ascii")
        return outputs, output_errors

    if op == "launch":
        if workdir.exists():
            shutil.rmtree(workdir, ignore_errors=True)
        workdir.mkdir(parents=True, exist_ok=True)
        workdir.chmod(0o700)

        for staged_file in payload.get("files", []):
            path = workdir / safe_name(str(staged_file["name"]))
            path.write_bytes(base64.b64decode(staged_file.get("content_b64", "")))
            path.chmod(0o700 if staged_file.get("executable") else 0o600)

        (workdir / "payload.sh").write_text(str(payload.get("script", "")), encoding="utf-8")
        (workdir / "payload.sh").chmod(0o700)

        wrapper = (
            "#!/bin/bash\n"
            'cd "$(dirname "$0")" || exit 127\n'
            "/bin/bash payload.sh > .stdout 2> .stderr\n"
            "echo $? > .ec\n"
        )
        (workdir / "run.sh").write_text(wrapper, encoding="utf-8")
        (workdir / "run.sh").chmod(0o700)

        env = os.environ.copy()
        env.update({str(k): str(v) for k, v in payload.get("environment", {}).items()})

        import json as _json

        (workdir / ".meta").write_text(
            _json.dumps(
                {
                    "outputs": [safe_name(str(n)) for n in payload.get("outputs", [])],
                    "result_max_bytes": result_max_bytes,
                    "output_max_bytes": output_max_bytes,
                }
            ),
            encoding="utf-8",
        )

        launcher = (
            "import os, subprocess\n"
            "proc = subprocess.Popen("
            "['/bin/bash', 'run.sh'], "
            "cwd='.', env=os.environ.copy(), stdin=subprocess.DEVNULL, "
            "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True"
            ")\n"
            "with open('.pid', 'w', encoding='utf-8') as handle:\n"
            "    handle.write(str(proc.pid))\n"
            "os._exit(0)\n"
        )
        subprocess.run(
            [sys.executable, "-c", launcher],
            cwd=str(workdir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        pid = int((workdir / ".pid").read_text(encoding="utf-8").strip())
        return {"state": "launched", "glidein_id": glidein_id, "pid": pid, "host": socket.gethostname()}

    if op == "status":
        if not workdir.is_dir():
            return {"state": "unknown", "glidein_id": glidein_id}

        import json as _json

        meta = {}
        try:
            meta = _json.loads((workdir / ".meta").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        # Apply the caps recorded at launch (the status payload does not carry them).
        result_max_bytes = int(meta.get("result_max_bytes") or result_max_bytes)
        output_max_bytes = int(meta.get("output_max_bytes") or output_max_bytes)

        def finish(returncode):
            outputs, output_errors = collect_outputs(meta.get("outputs"))
            result = {
                "state": "completed",
                "glidein_id": glidein_id,
                "returncode": returncode,
                "stdout": bounded_text(workdir / ".stdout", "stdout"),
                "stderr": bounded_text(workdir / ".stderr", "stderr"),
                "outputs": outputs,
                "output_errors": output_errors,
            }
            shutil.rmtree(workdir, ignore_errors=True)
            return result

        ec_path = workdir / ".ec"
        if ec_path.exists():
            try:
                return finish(int(ec_path.read_text(encoding="utf-8").strip() or "0"))
            except ValueError:
                return finish(1)

        try:
            pid = int((workdir / ".pid").read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return finish(1)

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            if ec_path.exists():  # finished between the checks above
                try:
                    return finish(int(ec_path.read_text(encoding="utf-8").strip() or "0"))
                except ValueError:
                    return finish(1)
            return finish(1)  # died without recording an exit code
        except PermissionError:
            pass  # alive, owned by another uid

        return {"state": "running", "glidein_id": glidein_id, "pid": pid}

    if op == "cancel":
        if workdir.is_dir():
            try:
                pid = int((workdir / ".pid").read_text(encoding="utf-8").strip())
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (OSError, ValueError, ProcessLookupError):
                pass
            shutil.rmtree(workdir, ignore_errors=True)
        return {"state": "cancelled", "glidein_id": glidein_id}

    raise ValueError(f"unknown op: {op!r}")
