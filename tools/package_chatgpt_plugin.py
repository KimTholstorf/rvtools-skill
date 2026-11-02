#!/usr/bin/env python3
"""Build and smoke-test the ChatGPT distribution of the shared RVTools engine."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rvtools_package_runtime", ROOT / "scripts/run_rvtools.py")
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)
SKILL_PATH = "skills/rvtools-analyzer/"
WEBSITE = "https://analyzer.rvtools.help/"
VARIANTS = {
    "desktop": {
        "display_name": "RVTools Analyzer Desktop",
        "subtitle": "Analyze local RVTools files",
        "description": "Process local workbook paths on your computer. Workbook parsing, query indexes and report files stay in the local execution environment. Relevant findings may still be processed by OpenAI's models; this is not an offline AI service.",
    },
    "cloud": {
        "display_name": "RVTools Analyzer",
        "subtitle": "Analyze uploaded RVTools files",
        "description": "Process uploaded workbooks in ChatGPT's cloud workspace and return downloadable reports. Uploads and derived files are subject to the platform's data-handling and retention policies.",
    },
}
# An explicit allowlist, not a recursive archive of the repository. Add new
# runtime resources here deliberately, with a package test.
SHARED_FILES = (
    "agents/openai.yaml",
    "scripts/run_rvtools.py",
    "scripts/parse_rvtools.py",
    "scripts/query_rvtools.py",
    "scripts/rvtools/__init__.py",
    "scripts/rvtools/bom.py",
    "scripts/rvtools/licensing.py",
    "scripts/rvtools/migration.py",
    "scripts/rvtools/sizing.py",
    "scripts/rvtools/targets.py",
    "scripts/rvtools/pricing/__init__.py",
    "scripts/rvtools/pricing/base.py",
    "scripts/rvtools/pricing/oci.py",
    "scripts/rvtools/pricing/azure.py",
    "scripts/rvtools/pricing/google.py",
    "references/bom.md",
    "references/guest_os_lifecycle.md",
    "references/hardware_lifecycle.md",
    "references/hcx_avs.md",
    "references/hcx_common.md",
    "references/hcx_gcve.md",
    "references/hcx_ocvs.md",
    "references/hygiene.md",
    "references/querying.md",
    "references/sizing.md",
    "references/vcf_onprem.md",
    "assets/report-template.html",
)


def read_manifest(path):
    return json.loads(path.read_text(encoding="utf-8"))


def portable_manifest(root, variant):
    if variant not in VARIANTS:
        raise ValueError("unknown package variant; choose desktop or cloud")
    profile = VARIANTS[variant]
    codex = read_manifest(root / ".codex-plugin/plugin.json")
    claude = read_manifest(root / ".claude-plugin/plugin.json")
    if codex["version"] != claude["version"] or not re.fullmatch(r"\d+\.\d+\.\d+", codex["version"]):
        raise ValueError("both plugin manifests must have the same semantic release version")
    manifest = {key: codex[key] for key in (
        "name", "version", "description", "author", "homepage", "repository", "license", "keywords",
    )}
    manifest["name"] = codex["name"] + ("-desktop" if variant == "desktop" else "")
    manifest["homepage"] = WEBSITE
    interface = dict(codex["interface"])
    interface["displayName"] = profile["display_name"]
    interface["shortDescription"] = profile["subtitle"]
    interface["longDescription"] += " " + profile["description"]
    interface["websiteURL"] = WEBSITE
    interface["logo"] = "./assets/icon.png"
    interface["composerIcon"] = "./assets/icon.png"
    interface["capabilities"] = (["Instructions", "Local file analysis", "Reports"]
                                 if variant == "desktop" else ["Instructions", "Reports"])
    manifest["$schema"] = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    manifest["extensions"] = {"com.openai": {"interface": interface}}
    if variant == "desktop":
        manifest["extensions"]["com.openai"]["requires_local_executor"] = True
    return manifest


def source_bytes(root, relative):
    path = root / relative
    if any(part.is_symlink() for part in (path, *path.parents) if part != root.parent):
        raise ValueError(f"package sources must not be symlinks: {relative}")
    return path.read_bytes()


def build_package(root, wheel_dir, output, *, variant):
    root, wheel_dir, output = Path(root).resolve(), Path(wheel_dir), Path(output)
    manifest = portable_manifest(root, variant)
    if RUNTIME.bundled_wheels(wheel_dir) is None:
        raise RuntimeError("download the exact pinned wheels before building the plugin")
    files = {
        "plugin.json": (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        "LICENSE": source_bytes(root, "LICENSE"),
        "assets/icon.png": source_bytes(root, "web/favicon.png"),
        SKILL_PATH + "SKILL.md": source_bytes(root, f"packaging/chatgpt/{variant}/SKILL.md"),
        SKILL_PATH + "WORKFLOW.md": source_bytes(root, "SKILL.md"),
        SKILL_PATH + ".rvtools-offline": b"Bundled dependencies required; never use the package index.\n",
    }
    files.update((SKILL_PATH + name, source_bytes(root, name)) for name in SHARED_FILES)
    files.update((SKILL_PATH + "wheels/" + path.name, path.read_bytes()) for path in wheel_dir.iterdir())
    if output.suffix != ".zip":
        raise ValueError("the package output must be a .zip file")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Fixed timestamps, permissions and order make identical inputs reproducible.
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        staging = Path(temporary) / "plugin.zip"
        with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, payload in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, payload)
        os.replace(staging, output)
    return output


def download_wheels(output):
    output = Path(output)
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        lock = temporary / "requirements.lock"
        lock.write_text(RUNTIME.requirements_text(), encoding="utf-8")
        wheels = temporary / "wheels"
        subprocess.run([
            sys.executable, "-m", "pip", "--isolated", "download",
            "--disable-pip-version-check", "--no-cache-dir", "--require-hashes",
            "--only-binary=:all:", "--no-deps", "--dest", str(wheels), "-r", str(lock),
        ], check=True)
        RUNTIME.bundled_wheels(wheels)
        output.mkdir(parents=True, exist_ok=True)
        for wheel in wheels.iterdir():
            shutil.copyfile(wheel, output / wheel.name)
        RUNTIME.bundled_wheels(output)


def smoke_test(archive_path):
    """Exercise a clean, offline bootstrap, queries and sizing using synthetic data."""
    with tempfile.TemporaryDirectory(prefix="rvtools-chatgpt-smoke-") as temporary:
        base = Path(temporary)
        package = base / "package"
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                path = Path(info.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                    raise ValueError("unsafe path in plugin archive")
                if info.external_attr >> 16 & 0o170000 == 0o120000:
                    raise ValueError("symlinks are not allowed in plugin archives")
            archive.extractall(package)
        skill = package / SKILL_PATH
        RUNTIME.bundled_wheels(skill / "wheels")
        # An empty interpreter forces first-use bootstrap even when the machine
        # running the smoke test already has the pinned dependencies installed.
        import venv
        clean = base / "clean-python"
        venv.EnvBuilder(with_pip=False).create(clean)
        python = RUNTIME._venv_python(clean)
        environment = os.environ.copy()
        for name in ("PYTHONPATH", "PYTHONHOME", "PLUGIN_DATA", "CLAUDE_PLUGIN_DATA", "GOOGLE_CLOUD_API_KEY"):
            environment.pop(name, None)
        environment.update({
            "RVTOOLS_PLUGIN_DATA": str(base / "private-runtime"),
            "PYTHONDONTWRITEBYTECODE": "1", "PIP_NO_INDEX": "1",
            "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9", "NO_PROXY": "",
        })

        def run(arguments):
            result = subprocess.run(arguments, cwd=base, env=environment, capture_output=True,
                                    text=True, timeout=180)
            if result.returncode:
                raise RuntimeError(f"packaged smoke test failed:\n{result.stderr}")
            return result.stdout

        launcher = [str(python), "-I", str(skill / "scripts/run_rvtools.py")]
        help_output = run(launcher + ["parse", "--help"])
        if not help_output.startswith("usage:"):
            raise RuntimeError("first-use runtime setup contaminated command stdout")
        runtime = next((base / "private-runtime/python-runtime").glob("py*"))
        runtime_python = RUNTIME._venv_python(runtime)
        workbook = base / "synthetic.xlsx"
        run([str(runtime_python), "-c", (
            "from openpyxl import Workbook; import sys; w=Workbook(); "
            "v=w.active; v.title='vInfo'; "
            "v.append(['VM','Powerstate','Template','CPUs','Memory','Provisioned MiB','Cluster','Host']); "
            "v.append(['demo-linux','poweredOn',False,4,8192,102400,'demo','demo-esx']); "
            "v.append(['demo-off','poweredOff',False,8,16384,204800,'demo','demo-esx']); "
            "h=w.create_sheet('vHost'); "
            "h.append(['Host','Cluster','# CPU','Cores per CPU','# Cores','# Memory','CPU Model']); "
            "h.append(['demo-esx','demo',2,16,32,262144,'Intel Xeon']); w.save(sys.argv[1])"
        ), str(workbook)])
        sizing_args = [str(workbook), "--target", "ocvs", "--sizing-topology", "consolidated"]
        packaged = json.loads(run(launcher + ["parse", *sizing_args]))
        local = json.loads(run([str(runtime_python), str(ROOT / "scripts/parse_rvtools.py"), *sizing_args]))
        if packaged != local:
            raise RuntimeError("packaged analysis differs from the shared local engine")
        if packaged["sizing"]["totals"]["compute_vms"] != 1:
            raise RuntimeError("the package changed powered-on sizing defaults")
        query = json.loads(run(launcher + [
            "query", str(workbook), "--index", str(base / "session.sqlite"),
            "--entity", "vm", "--metric", "count", "--filter", "power_state=poweredOn",
        ]))
        local_query = json.loads(run([
            str(runtime_python), str(ROOT / "scripts/query_rvtools.py"), str(workbook),
            "--index", str(base / "local.sqlite"), "--entity", "vm", "--metric", "count",
            "--filter", "power_state=poweredOn",
        ]))
        # Index paths differ by design; compare the actual query rows.
        if query["rows"] != local_query["rows"]:
            raise RuntimeError("packaged query differs from the shared local engine")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download-wheels")
    download.add_argument("--output", type=Path, required=True)
    build = commands.add_parser("build")
    build.add_argument("--variant", choices=tuple(VARIANTS), required=True)
    build.add_argument("--wheel-dir", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    smoke = commands.add_parser("smoke-test")
    smoke.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "download-wheels":
            download_wheels(args.output)
        elif args.command == "build":
            print(build_package(ROOT, args.wheel_dir, args.output, variant=args.variant))
        else:
            smoke_test(args.archive)
            print("Packaged offline runtime, parsing, sizing and query smoke test passed.")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
