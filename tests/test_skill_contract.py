import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
RUNTIME_PATH = ROOT / "scripts" / "run_rvtools.py"


def load_runtime_module():
    spec = importlib.util.spec_from_file_location("rvtools_runtime", RUNTIME_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SkillContractTests(unittest.TestCase):
    def test_runtime_launcher_imports_for_dependency_bootstrap_tests(self):
        runtime = load_runtime_module()
        self.assertEqual(runtime.__doc__, "Launch RVTools commands with an isolated, pinned Python runtime.")

    def test_runtime_launcher_pins_hashed_security_hardened_dependencies(self):
        runtime = load_runtime_module()
        requirements = runtime.requirements_text()

        self.assertIn("openpyxl==3.1.5 --hash=sha256:", requirements)
        self.assertIn("et_xmlfile==2.0.0 --hash=sha256:", requirements)
        self.assertIn("defusedxml==0.7.1 --hash=sha256:", requirements)
        self.assertEqual(requirements.count("--hash=sha256:"), 3)

    def test_runtime_launcher_uses_private_plugin_data_or_a_temp_fallback(self):
        runtime = load_runtime_module()
        temp_root = Path("/private/tmp/example")

        self.assertEqual(
            runtime.runtime_base({"PLUGIN_DATA": "/plugin-data"}, temp_root),
            Path("/plugin-data/python-runtime"),
        )
        self.assertEqual(
            runtime.runtime_base({"CLAUDE_PLUGIN_DATA": "/claude-data"}, temp_root),
            Path("/claude-data/python-runtime"),
        )
        self.assertEqual(
            runtime.runtime_base({}, temp_root),
            temp_root / "rvtools-analyzer-python-runtime",
        )

    def test_codex_git_marketplace_contract(self):
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["name"], "rvtools-analyzer")
        self.assertEqual(manifest["version"], "0.3.0")
        self.assertEqual(manifest["repository"], "https://github.com/KimTholstorf/rvtools-skill")
        self.assertEqual(manifest["license"], "MIT")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(marketplace["name"], "rvtools-analyzer")
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "rvtools-analyzer")
        self.assertEqual(entry["source"], {"source": "local", "path": "./"})
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")

    def test_claude_and_codex_plugins_share_version_and_implementation(self):
        codex_manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude_manifest = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude_marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )

        self.assertEqual(claude_manifest["name"], "rvtools")
        self.assertEqual(claude_manifest["version"], codex_manifest["version"])
        self.assertEqual(claude_manifest["repository"], codex_manifest["repository"])
        self.assertEqual(claude_manifest["license"], codex_manifest["license"])
        self.assertEqual(claude_marketplace["name"], "rvtools-analyzer")
        entry = claude_marketplace["plugins"][0]
        self.assertEqual(entry["name"], "rvtools")
        self.assertEqual(entry["source"], "./")

        skill = (ROOT / "skills" / "rvtools-analyzer" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("$rvtools-analyzer", skill)
        self.assertIn("/rvtools:analyze", skill)
        self.assertIn("CLAUDE_PLUGIN_DATA", skill)
        command = (ROOT / "commands" / "analyze.md").read_text(encoding="utf-8")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/rvtools-analyzer/SKILL.md", command)
        self.assertIn("$ARGUMENTS", command)
        root_skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Use when an agent receives", root_skill)
        self.assertNotIn("Use when Codex receives", root_skill)

    def test_public_repository_contract(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for private_path in (
            "samples/",
            "PROJECT_HANDOFF.md",
            ".claude/settings.local.json",
            "*.sqlite",
        ):
            self.assertIn(private_path, ignore)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Install and update", readme)
        self.assertIn("### Claude Code", readme)
        self.assertIn("### Claude Desktop", readme)
        self.assertIn("### Codex", readme)
        self.assertIn("### Updating", readme)
        self.assertIn("claude plugin marketplace add KimTholstorf/rvtools-skill", readme)
        self.assertIn("claude plugin install rvtools@rvtools-analyzer", readme)
        self.assertIn("rvtools-skill-<version>.zip", readme)
        self.assertIn("Settings → Customize → Skills → Add → Upload a skill", readme)
        self.assertIn("Do not use GitHub's automatically generated source-code ZIP", readme)
        self.assertIn("codex plugin marketplace add KimTholstorf/rvtools-skill", readme)
        self.assertIn("claude plugin update rvtools@rvtools-analyzer", readme)
        self.assertIn("codex plugin marketplace upgrade rvtools-analyzer", readme)
        self.assertIn("## What it can do", readme)
        self.assertIn("Estimate required VCF cores", readme)
        self.assertIn("$rvtools-analyzer", readme)
        self.assertIn("/rvtools:analyze", readme)
        self.assertIn("Python 3.8", readme)
        self.assertIn("pdf/health-check-report-sample.pdf", readme)
        self.assertIn("pdf/ocvs-migration-analysis-sample.pdf", readme)
        self.assertIn("fully synthetic data", readme)
        self.assertNotIn("/Users/", readme)

        for sample_name in (
            "health-check-report-sample.pdf",
            "ocvs-migration-analysis-sample.pdf",
        ):
            sample = ROOT / "pdf" / sample_name
            self.assertTrue(sample.is_file())
            self.assertTrue(sample.read_bytes().startswith(b"%PDF-"))

        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Kim Tholstorf", license_text)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [0.3.0] - 2026-08-11", changelog)
        self.assertNotIn("beta", changelog.casefold())

    def test_claude_desktop_zip_is_released_only_after_successful_tagged_ci(self):
        workflow_path = ROOT / ".github" / "workflows" / "release-claude-skill.yml"

        self.assertTrue(workflow_path.is_file())
        workflow = workflow_path.read_text(encoding="utf-8")
        for required in (
            "workflow_run:",
            'workflows: ["CI"]',
            "types: [completed]",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.event == 'push'",
            "github.event.workflow_run.head_sha",
            "git tag --points-at",
            "contents: write",
            "--prefix=rvtools-analyzer/",
            "SKILL.md",
            "assets/report-template.html",
            "references",
            "scripts",
            "rvtools-skill-${version}.zip",
            "gh release create",
            "gh release upload",
        ):
            self.assertIn(required, workflow)

    def test_skill_routes_commands_through_runtime_launcher(self):
        skill = (ROOT / "skills" / "rvtools-analyzer" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/run_rvtools.py parse", skill)
        self.assertIn("scripts/run_rvtools.py query", skill)
        self.assertNotIn("python3 scripts/parse_rvtools.py", skill)
        self.assertNotIn("python3 scripts/query_rvtools.py", skill)

    def test_report_template_uses_flat_oracle_inspired_design_system(self):
        template = (ROOT / "assets" / "report-template.html").read_text(
            encoding="utf-8"
        ).casefold()

        self.assertIn("--oracle-red: #c74634;", template)
        self.assertIn("--bark: #312d2a;", template)
        self.assertIn("--sand: #f1efed;", template)
        self.assertIn("background: var(--oracle-red);", template)
        self.assertNotIn("linear-gradient", template)
        self.assertNotIn("box-shadow", template)
        self.assertNotIn("#4f46e5", template)
        self.assertNotIn("#3730a3", template)

    def test_report_template_is_responsive_and_print_ready(self):
        template = (ROOT / "assets" / "report-template.html").read_text(
            encoding="utf-8"
        ).casefold()

        self.assertIn("@media (max-width: 700px)", template)
        self.assertIn("@media print", template)
        self.assertIn("@page", template)
        self.assertIn("thead { display: table-header-group; }", template)
        self.assertIn("break-inside: avoid", template)

    def test_report_template_preserves_content_slots_in_semantic_sections(self):
        template = (ROOT / "assets" / "report-template.html").read_text(
            encoding="utf-8"
        )

        self.assertEqual(template.count('class="report-section'), 7)
        for slot in (
            "REPORT_TITLE",
            "LENS_LABEL",
            "ASSESSMENT_DATE",
            "EXECUTIVE_SUMMARY",
            "KPI_CARDS",
            "FINDING_CARDS",
            "INVENTORY_TABLE",
            "OVERCOMMIT_TABLE",
            "REMEDIATION_STEPS",
            "COVERAGE_GAPS",
            "METHOD_AND_SOURCES",
            "SOURCE_IDENTITY",
        ):
            expected_count = 2 if slot == "REPORT_TITLE" else 1
            self.assertEqual(template.count("{{" + slot + "}}"), expected_count)

    def test_hygiene_requires_vendor_lifecycle_research(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        hygiene = (ROOT / "references" / "hygiene.md").read_text(encoding="utf-8")
        lifecycle_path = ROOT / "references" / "hardware_lifecycle.md"

        self.assertTrue(lifecycle_path.exists())
        lifecycle = lifecycle_path.read_text(encoding="utf-8")
        self.assertIn("references/hardware_lifecycle.md", skill)
        self.assertIn("hardware_lifecycle.md", hygiene)
        for required in (
            "distinct vendor/model",
            "primary vendor",
            "Last Date of Support",
            "as-of date",
            "coverage gap",
            "End-of-Sale",
            "HT Available",
            "HT Active",
        ):
            self.assertIn(required, lifecycle)

    def test_query_reference_documents_host_hardware_fields(self):
        querying = (ROOT / "references" / "querying.md").read_text(encoding="utf-8")
        for field in (
            "vendor",
            "model",
            "cpu_vendor",
            "cpu_model",
            "ht_available",
            "ht_active",
            "cpu_sockets",
            "cores_per_cpu",
            "cpu_speed_mhz",
            "bios_vendor",
            "bios_version",
            "bios_date",
        ):
            self.assertIn(f"`{field}`", querying)

    def test_skill_routes_all_cloud_vmware_migration_targets_through_shared_hcx_rules(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        querying = (ROOT / "references" / "querying.md").read_text(encoding="utf-8")

        for reference in ("hcx_common.md", "hcx_ocvs.md", "hcx_avs.md", "hcx_gcve.md"):
            self.assertTrue((ROOT / "references" / reference).is_file())
            self.assertIn(f"references/{reference}", skill)
        for target in ("ocvs", "avs", "gcve"):
            self.assertIn(f"--target {target}", skill)
        for entity in ("migration_method", "migration_finding", "target_node"):
            self.assertIn(f"`{entity}`", querying)
        self.assertNotIn("each detection's `lenses`", skill)

    def test_public_readme_mentions_avs_and_gcve_migration_analysis(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Azure VMware Solution (AVS)", readme)
        self.assertIn("Google Cloud VMware Engine (GCVE)", readme)


if __name__ == "__main__":
    unittest.main()
