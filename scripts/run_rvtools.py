#!/usr/bin/env python3
"""Launch RVTools commands with an isolated, pinned Python runtime."""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path


REQUIREMENTS = (
    (
        "openpyxl",
        "3.1.5",
        "5282c12b107bffeef825f4617dc029afaf41d0ea60823bbb665ef3079dc79de2",
    ),
    (
        "et_xmlfile",
        "2.0.0",
        "7a91720bc756843502c3b7504c77b8fe44217c85c537d85037f0f536151b2caa",
    ),
    (
        "defusedxml",
        "0.7.1",
        "a352e7e428770286cc899e2542b6cdaedb2b4953ff269a210103ec58f6198a61",
    ),
)
COMMANDS = {
    "parse": "parse_rvtools.py",
    "query": "query_rvtools.py",
}
LOCK_TIMEOUT_SECONDS = 120


def requirements_text():
    """Return a fully pinned, wheel-only pip requirements file."""
    return "".join(
        f"{name}=={version} --hash=sha256:{digest}\n"
        for name, version, digest in REQUIREMENTS
    )


def runtime_base(environ=None, temp_root=None):
    """Choose private persistent plugin data, falling back to OS temporary storage."""
    environ = os.environ if environ is None else environ
    temp_root = Path(tempfile.gettempdir()) if temp_root is None else Path(temp_root)
    for variable in ("RVTOOLS_PLUGIN_DATA", "PLUGIN_DATA", "CLAUDE_PLUGIN_DATA"):
        value = environ.get(variable)
        if value:
            return Path(value).expanduser() / "python-runtime"
    return temp_root / "rvtools-analyzer-python-runtime"


def _lock_digest():
    return hashlib.sha256(requirements_text().encode("utf-8")).hexdigest()[:16]


def _environment_matches_current_process():
    try:
        versions = {
            name: importlib.metadata.version(name)
            for name, _, _ in REQUIREMENTS
        }
        import openpyxl
    except (ImportError, importlib.metadata.PackageNotFoundError):
        return False
    return all(versions[name] == version for name, version, _ in REQUIREMENTS) and bool(
        openpyxl.DEFUSEDXML
    )


def _venv_python(runtime_dir):
    if os.name == "nt":
        return runtime_dir / "Scripts" / "python.exe"
    return runtime_dir / "bin" / "python"


def _environment_matches(python_executable):
    expected = {name: version for name, version, _ in REQUIREMENTS}
    probe = (
        "import importlib.metadata as m; import openpyxl; "
        f"expected={expected!r}; "
        "actual={name:m.version(name) for name in expected}; "
        "raise SystemExit(0 if actual == expected and openpyxl.DEFUSEDXML else 1)"
    )
    result = subprocess.run(
        [str(python_executable), "-c", probe],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _write_private(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if hasattr(os, "fchmod"):
        os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)


def _acquire_lock(lock_dir, ready_marker):
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_dir.mkdir()
            return True
        except FileExistsError:
            if ready_marker.exists():
                return False
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"timed out waiting for another RVTools runtime setup: {lock_dir}"
                )
            time.sleep(0.25)


def ensure_runtime():
    """Return a Python executable containing the exact pinned dependencies."""
    if sys.version_info < (3, 8):
        raise RuntimeError("RVTools Analyzer requires Python 3.8 or newer")
    if _environment_matches_current_process():
        return Path(sys.executable)

    base = runtime_base()
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        base.chmod(0o700)
    except OSError:
        pass

    digest = _lock_digest()
    runtime_dir = base / f"py{sys.version_info.major}.{sys.version_info.minor}-{digest}"
    ready_marker = runtime_dir / ".ready"
    python_executable = _venv_python(runtime_dir)
    if ready_marker.exists() and _environment_matches(python_executable):
        return python_executable

    lock_dir = base / f".{runtime_dir.name}.lock"
    owns_lock = _acquire_lock(lock_dir, ready_marker)
    if not owns_lock:
        if _environment_matches(python_executable):
            return python_executable
        raise RuntimeError("another process completed an invalid RVTools runtime setup")

    requirements_path = base / f"requirements-{digest}.lock"
    try:
        if ready_marker.exists() and _environment_matches(python_executable):
            return python_executable
        if runtime_dir.exists():
            shutil.rmtree(runtime_dir)
        _write_private(requirements_path, requirements_text())
        venv.EnvBuilder(with_pip=True, clear=False).create(runtime_dir)
        subprocess.run(
            [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--require-hashes",
                "--only-binary=:all:",
                "--no-deps",
                "-r",
                str(requirements_path),
            ],
            check=True,
        )
        if not _environment_matches(python_executable):
            raise RuntimeError("the private RVTools runtime failed dependency verification")
        _write_private(ready_marker, digest + "\n")
        return python_executable
    finally:
        try:
            lock_dir.rmdir()
        except OSError:
            pass


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        commands = "|".join(COMMANDS)
        sys.stderr.write(f"usage: {Path(sys.argv[0]).name} {{{commands}}} [arguments...]\n")
        return 2

    command = argv.pop(0)
    target = Path(__file__).with_name(COMMANDS[command])
    try:
        python_executable = ensure_runtime()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        sys.stderr.write(f"error: unable to prepare the private RVTools Python runtime: {exc}\n")
        return 2

    environment = os.environ.copy()
    environment["OPENPYXL_DEFUSEDXML"] = "True"
    arguments = [str(python_executable), str(target), *argv]
    os.execve(str(python_executable), arguments, environment)


if __name__ == "__main__":
    raise SystemExit(main())
