import importlib
import copy
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class MigrationBootstrapTests(unittest.TestCase):
    def test_migration_domain_imports(self):
        module = importlib.import_module("rvtools.migration")
        self.assertEqual(module.TARGET_IDS, ("ocvs", "avs", "gcve"))


class MigrationAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module("rvtools.migration")
        self.rows = {
            "vInfo": [
                {
                    "VM": "web-01",
                    "Powerstate": "poweredOn",
                    "Template": False,
                    "Cluster": "cluster-a",
                    "Host": "esx-intel",
                    "HW version": "vmx-19",
                    "FT State": "notConfigured",
                    "Consolidation Needed": False,
                },
                {
                    "VM": "db-01",
                    "Powerstate": "poweredOn",
                    "Template": False,
                    "Cluster": "cluster-a",
                    "Host": "esx-amd",
                    "HW version": "vmx-8",
                    "FT State": "running",
                    "Consolidation Needed": True,
                },
                {
                    "VM": "template-01",
                    "Powerstate": "poweredOff",
                    "Template": True,
                    "Cluster": "cluster-a",
                    "Host": "esx-intel",
                    "HW version": "vmx-19",
                },
            ],
            "vHost": [
                {"Host": "esx-intel", "CPU Model": "Intel Xeon", "ESX Version": "8.0.3"},
                {"Host": "esx-amd", "CPU Model": "AMD EPYC", "ESX Version": "7.0.3"},
            ],
            "vDisk": [
                {
                    "VM": "db-01",
                    "Template": False,
                    "Disk": "Hard disk 1",
                    "Raw": True,
                    "Raw Comp. Mode": "physicalMode",
                    "Disk Mode": "independent_persistent",
                    "Sharing mode": "sharingMultiWriter",
                }
            ],
            "vUSB": [{"VM": "db-01", "Template": False, "Connected": True}],
            "vCD": [{"VM": "db-01", "Template": False, "Connected": True}],
            "vTools": [
                {"VM": "web-01", "Template": False, "Powerstate": "poweredOn", "Tools": "toolsOk"},
                {"VM": "db-01", "Template": False, "Powerstate": "poweredOn", "Tools": "toolsNotRunning"},
            ],
            "vNetwork": [
                {
                    "VM": "db-01",
                    "Template": False,
                    "Network": "legacy-net",
                    "Switch": "vSwitch0",
                    "IPv6 Address": "2001:db8::10",
                }
            ],
            "vSnapshot": [],
        }

    def test_avs_assessment_is_per_vm_per_method_and_excludes_templates(self):
        result = self.migration.assess_migration(self.rows, "avs")

        self.assertEqual(result["target"]["id"], "avs")
        self.assertEqual(result["scope"]["workload_vms"], 2)
        self.assertEqual(result["scope"]["templates_excluded"], 1)
        by_vm = {row["vm"]: row for row in result["vm_methods"]}
        self.assertEqual(by_vm["web-01"]["methods"]["rav"]["status"], "eligible")
        self.assertEqual(by_vm["db-01"]["methods"]["rav"]["status"], "blocked")
        self.assertEqual(by_vm["db-01"]["methods"]["cold"]["status"], "conditional")
        self.assertIn("physical_rdm", by_vm["db-01"]["methods"]["rav"]["reason_ids"])
        self.assertIn("cross_vendor_cpu", by_vm["db-01"]["methods"]["rav"]["reason_ids"])

    def test_provider_profiles_include_catalogs_sources_and_manual_gates(self):
        avs = self.migration.assess_migration(self.rows, "avs")
        gcve = self.migration.assess_migration(self.rows, "gcve")

        self.assertIn("AV64", {node["id"] for node in avs["target"]["nodes"]})
        self.assertIn("ve2-standard-128", {node["id"] for node in gcve["target"]["nodes"]})
        self.assertTrue(any(node["storage_only"] for node in gcve["target"]["nodes"]))
        self.assertEqual(avs["target"]["cpu_vendor"], "Intel")
        self.assertEqual(gcve["target"]["cpu_vendor"], "Intel")
        self.assertIn("hcx_interoperability", {gate["id"] for gate in avs["manual_gates"]})
        self.assertIn("cidr_overlap", {gate["id"] for gate in gcve["manual_gates"]})
        self.assertTrue(all(source["url"].startswith("https://") for source in avs["sources"]))
        av64 = next(node for node in avs["target"]["nodes"] if node["id"] == "AV64")
        self.assertEqual(av64["cpu_model"], "Intel Xeon Platinum 8370C")
        self.assertIsNone(av64["raw_storage_tb"])
        self.assertEqual(av64["raw_storage_tb_osa"], 15.36)
        self.assertEqual(av64["raw_storage_tb_esa"], 19.25)

        sizing_gate = next(
            gate for gate in avs["manual_gates"] if gate["id"] == "performance_sizing"
        )
        for required in (
            "selected planning assumptions",
            "operating headroom",
            "one host unavailable",
            "largest-VM fit",
        ):
            self.assertIn(required, sizing_gate["evidence"])
        self.assertEqual(avs["target"]["sizing_constraints"]["primary_minimum_hosts"], 3)
        self.assertEqual(avs["target"]["sizing_constraints"]["workload_minimum_hosts"], 3)

        ocvs = self.migration.assess_migration(self.rows, "ocvs")
        self.assertEqual(
            ocvs["target"]["sizing_constraints"]["primary_minimum_hosts"], 3
        )
        self.assertEqual(
            ocvs["target"]["sizing_constraints"]["workload_minimum_hosts"], 2
        )

    def test_ocvs_can_apply_an_explicit_target_cpu_vendor(self):
        result = self.migration.assess_migration(
            self.rows, "ocvs", target_cpu_vendor="AMD"
        )
        by_vm = {row["vm"]: row for row in result["vm_methods"]}

        self.assertEqual(result["target"]["cpu_vendor"], "AMD")
        self.assertEqual(by_vm["web-01"]["methods"]["hcx_vmotion"]["status"], "blocked")
        self.assertIn(
            "cross_vendor_cpu",
            by_vm["web-01"]["methods"]["hcx_vmotion"]["reason_ids"],
        )

    def test_rejects_unknown_target_and_sku(self):
        with self.assertRaisesRegex(ValueError, "unknown migration target"):
            self.migration.assess_migration(self.rows, "unknown")
        with self.assertRaisesRegex(ValueError, "unknown avs target node"):
            self.migration.assess_migration(self.rows, "avs", target_node="not-real")

    def test_missing_core_compatibility_evidence_is_unknown_not_eligible(self):
        rows = copy.deepcopy(self.rows)
        rows["vInfo"][0]["HW version"] = ""
        rows["vInfo"][0]["Host"] = "missing-host"

        result = self.migration.assess_migration(rows, "avs")
        web = {row["vm"]: row for row in result["vm_methods"]}["web-01"]

        self.assertEqual(web["methods"]["rav"]["status"], "unknown")
        self.assertIn(
            "hardware_version_unknown",
            web["methods"]["rav"]["reason_ids"],
        )
        self.assertIn(
            "source_cpu_vendor_unknown",
            web["methods"]["hcx_vmotion"]["reason_ids"],
        )
    def test_fixed_vendor_target_rejects_an_impossible_override(self):
        with self.assertRaisesRegex(ValueError, "uses Intel hosts"):
            self.migration.assess_migration(
                self.rows, "avs", target_cpu_vendor="AMD"
            )

    def test_duplicate_vm_names_remain_distinct_across_vcenters(self):
        rows = copy.deepcopy(self.rows)
        rows["vInfo"][0]["VI SDK Server"] = "vc-a"
        duplicate = copy.deepcopy(rows["vInfo"][0])
        duplicate["VI SDK Server"] = "vc-b"
        duplicate["Host"] = "esx-amd"
        rows["vInfo"].append(duplicate)

        result = self.migration.assess_migration(rows, "avs")
        web_rows = [row for row in result["vm_methods"] if row["vm"] == "web-01"]

        self.assertEqual(result["scope"]["workload_vms"], 3)
        self.assertEqual(result["scope"]["duplicate_vm_names"], 1)
        self.assertEqual(len(result["vm_methods"]), 3)
        self.assertEqual(
            {row["vcenter"]: row["methods"]["rav"]["status"] for row in web_rows},
            {"vc-a": "eligible", "vc-b": "blocked"},
        )


if __name__ == "__main__":
    unittest.main()
