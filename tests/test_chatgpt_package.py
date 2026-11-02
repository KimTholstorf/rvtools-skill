import hashlib
import importlib.util
import io
import inspect
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "package_chatgpt_plugin.py"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BundledRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = load_module(ROOT / "scripts" / "run_rvtools.py", "bundle_runtime")
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.wheels = Path(self.tempdir.name) / "wheels"

    def check_bundle(self):
        self.assertTrue(callable(getattr(self.runtime, "bundled_wheels", None)),
                        "The shared launcher needs verified offline wheel support")
        return self.runtime.bundled_wheels(self.wheels)

    def test_local_install_without_bundle_keeps_existing_bootstrap(self):
        self.assertIsNone(self.check_bundle())

    def test_incomplete_bundle_fails_instead_of_downloading(self):
        self.wheels.mkdir()
        with self.assertRaisesRegex(RuntimeError, "wheel"):
            self.check_bundle()

    def test_bundle_checks_exact_pins_and_hashes(self):
        self.wheels.mkdir()
        data = b"synthetic wheel"
        wheel = self.wheels / "example-1.0-py3-none-any.whl"
        wheel.write_bytes(data)
        with patch.object(self.runtime, "REQUIREMENTS", (
            ("example", "1.0", hashlib.sha256(data).hexdigest()),
        )):
            self.assertEqual(self.check_bundle(), self.wheels)
            wheel.write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError, "hash"):
                self.check_bundle()

    def test_bundled_install_disables_index_and_dependency_resolution(self):
        self.assertTrue(callable(getattr(self.runtime, "pip_install_arguments", None)),
                        "Offline installation must explicitly disable the package index")
        command = self.runtime.pip_install_arguments(Path("python"), Path("lock"), self.wheels)
        self.assertIn("--no-index", command)
        self.assertIn("--no-deps", command)
        self.assertIn("--require-hashes", command)
        self.assertEqual(command[command.index("--find-links") + 1], str(self.wheels))
        online = self.runtime.pip_install_arguments(Path("python"), Path("lock"))
        self.assertNotIn("--no-index", online)
        self.assertNotIn("--isolated", online, "Preserve local package-index configuration")

    def test_cloud_bundle_with_missing_wheel_folder_fails_closed(self):
        (self.wheels.parent / ".rvtools-offline").touch()
        with self.assertRaisesRegex(RuntimeError, "wheel"):
            self.check_bundle()

    def test_universal_python2_python3_wheel_tag_is_supported(self):
        self.wheels.mkdir()
        data = b"universal wheel"
        (self.wheels / "example-1.0-py2.py3-none-any.whl").write_bytes(data)
        with patch.object(self.runtime, "REQUIREMENTS", (
            ("example", "1.0", hashlib.sha256(data).hexdigest()),
        )):
            self.assertEqual(self.check_bundle(), self.wheels)


class ChatGPTPackageTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(BUILDER.is_file(), "The ChatGPT ZIP builder must exist")
        self.builder = load_module(BUILDER, "chatgpt_builder")
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)
        self.wheels = self.base / "wheels"
        self.wheels.mkdir()
        # No downloads in unit tests. Real pinned wheels are exercised by the
        # packaged-runtime smoke test in CI and release packaging.
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("example-1.0.dist-info/LICENSE", "Synthetic test fixture")
        payload = data.getvalue()
        (self.wheels / "example-1.0-py3-none-any.whl").write_bytes(payload)
        self.pins = patch.object(self.builder.RUNTIME, "REQUIREMENTS", (
            ("example", "1.0", hashlib.sha256(payload).hexdigest()),
        ))
        self.pins.start()
        self.addCleanup(self.pins.stop)

    def build(self, root=ROOT, name="plugin.zip", variant="cloud"):
        self.assertIn("variant", inspect.signature(self.builder.build_package).parameters,
                      "Packages must explicitly select the Desktop or Cloud variant")
        return self.builder.build_package(root, self.wheels, self.base / name, variant=variant)

    def test_zip_is_self_contained_and_uses_the_shared_implementation(self):
        with zipfile.ZipFile(self.build()) as archive:
            names = set(archive.namelist())
            prefix = "skills/rvtools-analyzer/"
            manifest = json.loads(archive.read("plugin.json"))
            local = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
            self.assertEqual(manifest["version"], local["version"])
            self.assertEqual(manifest["name"], local["name"])
            self.assertIn("agent-plugins.org", manifest["$schema"])
            self.assertIn("com.openai", manifest["extensions"])
            self.assertNotIn("hooks", manifest["extensions"]["com.openai"])
            self.assertNotIn("mcp.json", names)
            self.assertEqual(archive.read(prefix + "WORKFLOW.md"), (ROOT / "SKILL.md").read_bytes())
            for source in self.builder.SHARED_FILES:
                self.assertEqual(archive.read(prefix + source), (ROOT / source).read_bytes())
            self.assertIn(prefix + "SKILL.md", names)
            self.assertIn(prefix + ".rvtools-offline", names)
            self.assertIn(prefix + "wheels/example-1.0-py3-none-any.whl", names)
            self.assertIn("LICENSE", names)
            self.assertTrue(all(name in {"plugin.json", "LICENSE", "assets/icon.png"} or name.startswith(prefix)
                                for name in names))
            self.assertFalse(any(part in {"samples", "outputs", "tests", ".git", "__pycache__"}
                                 for name in names for part in Path(name).parts))

    def test_build_is_reproducible(self):
        for variant in ("desktop", "cloud"):
            with self.subTest(variant=variant):
                first = self.build(name="first.zip", variant=variant).read_bytes()
                second = self.build(name="second.zip", variant=variant).read_bytes()
                self.assertEqual(first, second)

    def test_starter_prompts_meet_submission_limits_for_both_variants(self):
        local = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        for variant in ("desktop", "cloud"):
            with self.subTest(variant=variant), zipfile.ZipFile(self.build(variant=variant)) as archive:
                manifest = json.loads(archive.read("plugin.json"))
                prompts = manifest["extensions"]["com.openai"]["interface"]["defaultPrompt"]
                self.assertGreater(len(prompts), 0)
                self.assertLessEqual(len(prompts), 3, "Submission allows at most three starter prompts")
                self.assertEqual(prompts, local["interface"]["defaultPrompt"])
                for prompt in prompts:
                    self.assertTrue(prompt.strip())
                    self.assertLessEqual(len(prompt), 128)
                    self.assertEqual(len(prompt.splitlines()), 1)

    def test_variants_have_distinct_identities_and_local_executor_scope(self):
        for variant in ("desktop", "cloud"):
            with self.subTest(variant=variant), zipfile.ZipFile(self.build(variant=variant)) as archive:
                manifest = json.loads(archive.read("plugin.json"))
                extension = manifest["extensions"]["com.openai"]
                expected_name = "rvtools-analyzer-desktop" if variant == "desktop" else "rvtools-analyzer"
                expected_title = "RVTools Analyzer Desktop" if variant == "desktop" else "RVTools Analyzer"
                self.assertEqual(manifest["name"], expected_name)
                self.assertEqual(extension["interface"]["displayName"],
                                 expected_title)
                self.assertLessEqual(len(extension["interface"]["displayName"]), 30)
                self.assertLessEqual(len(extension["interface"]["shortDescription"]), 30)
                if variant == "desktop":
                    self.assertIs(extension["requires_local_executor"], True)
                else:
                    self.assertNotIn("requires_local_executor", extension)
                    entrypoint = archive.read("skills/rvtools-analyzer/SKILL.md").decode("utf-8")
                    self.assertIn("\nname: rvtools-analyzer\n", entrypoint)
                    self.assertIn("\n# RVTools Analyzer\n", entrypoint)
                    self.assertNotIn("RVTools Analyzer Cloud", entrypoint)

    def test_variants_share_all_calculations_but_have_separate_privacy_entrypoints(self):
        with zipfile.ZipFile(self.build(name="cloud.zip")) as cloud, zipfile.ZipFile(
            self.build(name="desktop.zip", variant="desktop")
        ) as desktop:
            self.assertEqual(set(desktop.namelist()), set(cloud.namelist()))
            for name in desktop.namelist():
                if name not in ("plugin.json", "skills/rvtools-analyzer/SKILL.md"):
                    self.assertEqual(desktop.read(name), cloud.read(name), name)
            entrypoint = desktop.read("skills/rvtools-analyzer/SKILL.md").decode("utf-8").casefold()
            self.assertIn("never request a workbook upload", entrypoint)
            self.assertIn("do not fall back to cloud execution", entrypoint)
            self.assertIn("does not mean offline", entrypoint)
            self.assertIn("cloud", cloud.read("skills/rvtools-analyzer/SKILL.md").decode("utf-8"))

    def test_packages_use_the_analyzer_website_and_bundled_website_icon(self):
        for variant in ("desktop", "cloud"):
            with self.subTest(variant=variant), zipfile.ZipFile(self.build(variant=variant)) as archive:
                manifest = json.loads(archive.read("plugin.json"))
                interface = manifest["extensions"]["com.openai"]["interface"]
                self.assertEqual(manifest["homepage"], "https://analyzer.rvtools.help/")
                self.assertEqual(interface.get("websiteURL"), "https://analyzer.rvtools.help/")
                self.assertEqual(interface.get("logo"), "./assets/icon.png")
                self.assertEqual(interface.get("composerIcon"), "./assets/icon.png")
                icon = archive.read("assets/icon.png")
                self.assertEqual(icon, (ROOT / "web/favicon.png").read_bytes())
                self.assertTrue(icon.startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertLessEqual(len(icon), 5 * 1024 * 1024)
                width, height = struct.unpack(">II", icon[16:24])
                self.assertEqual(width, height)
                self.assertGreaterEqual(width, 256)
                self.assertLessEqual(width, 4096)
                self.assertEqual(archive.read("skills/rvtools-analyzer/agents/openai.yaml"),
                                 (ROOT / "agents/openai.yaml").read_bytes())

    def test_unknown_variant_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "variant"):
            self.build(variant="unknown")

    def test_cli_requires_an_explicit_variant(self):
        result = subprocess.run([
            sys.executable, str(BUILDER), "build", "--wheel-dir", str(self.wheels),
            "--output", str(self.base / "ambiguous.zip"),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--variant", result.stderr)

    def test_private_and_unlisted_files_do_not_enter_the_bundle(self):
        root = self.base / "repo"
        root.mkdir()
        sources = (*self.builder.SHARED_FILES, "SKILL.md", "LICENSE", "web/favicon.png",
                   ".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
                   "packaging/chatgpt/cloud/SKILL.md", "packaging/chatgpt/desktop/SKILL.md")
        for name in sources:
            self.assertTrue((ROOT / name).is_file(), "Missing variant source: " + name)
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        for name in ("scripts/customer.xlsx", "scripts/secret.py", "references/customer.md",
                     "outputs/report.html", ".env"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("PRIVATE_SENTINEL")
        with zipfile.ZipFile(self.build(root)) as archive:
            self.assertNotIn(b"PRIVATE_SENTINEL", b"".join(archive.read(n) for n in archive.namelist()))

    def test_mismatched_plugin_versions_are_rejected(self):
        original = self.builder.read_manifest

        def mismatched(path):
            value = original(path)
            if path.parent.name == ".claude-plugin":
                value["version"] = "99.0.0"
            return value

        with patch.object(self.builder, "read_manifest", side_effect=mismatched):
            with self.assertRaisesRegex(ValueError, "version"):
                self.build()

    def test_missing_or_tampered_wheels_cannot_produce_a_package(self):
        wheel = next(self.wheels.iterdir())
        wheel.write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "hash"):
            self.build()
        wheel.unlink()
        with self.assertRaisesRegex(RuntimeError, "wheel"):
            self.build()

    def test_release_workflow_uses_successful_trusted_tagged_ci(self):
        workflow_path = ROOT / ".github/workflows/release-chatgpt-plugin.yml"
        self.assertTrue(workflow_path.is_file())
        workflow = workflow_path.read_text()
        for required in (
            "workflow_run:", 'workflows: ["CI"]',
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.event == 'push'",
            "github.event.workflow_run.head_repository.full_name == github.repository",
            "github.event.workflow_run.head_sha", "git tag --points-at",
            "download-wheels", "smoke-test", "gh release upload",
            "variant: [desktop, cloud]",
            "--variant", "rvtools-chatgpt-${variant}-${version}.zip",
        ):
            self.assertIn(required, workflow)


if __name__ == "__main__":
    unittest.main()
