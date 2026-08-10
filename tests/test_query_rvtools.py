import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "query_rvtools.py"
SPEC = importlib.util.spec_from_file_location("query_rvtools", MODULE_PATH)
QUERY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(QUERY)


def add_sheet(workbook, name, headers, rows):
    worksheet = workbook.create_sheet(name)
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)


class QueryRVToolsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "query-rvtools.xlsx"
        workbook = Workbook()
        workbook.remove(workbook.active)
        add_sheet(
            workbook,
            "vInfo",
            [
                "VM",
                "Powerstate",
                "Template",
                "CPUs",
                "Memory",
                "Provisioned MiB",
                "In Use MiB",
                "Cluster",
                "Host",
                "HW version",
                "Consolidation Needed",
                "OS according to the configuration file",
                "OS according to the VMware Tools",
            ],
            [
                ["linux-on", "poweredOn", False, 4, 8192, 102400, 51200, "cluster-a", "esx-01", "vmx-19", False, "Other Linux", "Ubuntu Linux 24.04"],
                ["windows-off", "poweredOff", False, 2, 4096, 51200, 20480, "cluster-a", "esx-02", "vmx-15", False, "Microsoft Windows Server 2022", ""],
                ["bsd-on", "poweredOn", False, 2, 2048, 20480, 10240, "cluster-b", "esx-03", "vmx-19", False, "FreeBSD 13", ""],
                ["linux-template", "poweredOff", True, 8, 16384, 204800, 102400, "cluster-a", "esx-01", "vmx-19", False, "Ubuntu Linux", ""],
            ],
        )
        add_sheet(
            workbook,
            "vHost",
            [
                "Host",
                "Cluster",
                "CPU Model",
                "ESX Version",
                "# Cores",
                "# Memory",
                "Vendor",
                "Model",
                "HT Available",
                "HT Active",
                "# CPU",
                "Cores per CPU",
                "Speed",
                "BIOS Vendor",
                "BIOS Version",
                "BIOS Date",
            ],
            [
                ["esx-01", "cluster-a", "Intel(R) Xeon Gold 6248", "8.0.3", 16, 65536, "Cisco Systems Inc", "HXAF240C-M5SX", True, True, 2, 8, 2500, "Cisco Systems, Inc.", "C240M5.4.1.3m", "2022-07-08"],
                ["esx-02", "cluster-a", "AMD EPYC 7543", "8.0.3", 16, 65536, "Dell Inc.", "PowerEdge R7525", True, False, 2, 8, 2800, "Dell Inc.", "2.19.1", "2024-01-15"],
                ["esx-03", "cluster-b", "Intel Xeon", "8.0.3", 8, 32768, "", "", "", "", 1, 8, 2200, "", "", ""],
            ],
        )
        add_sheet(
            workbook,
            "vTools",
            ["VM", "Template", "Tools", "Powerstate"],
            [
                ["linux-on", False, "toolsOk", "poweredOn"],
                ["windows-off", False, "toolsNotRunning", "poweredOff"],
                ["linux-template", True, "toolsNotRunning", "poweredOff"],
            ],
        )
        add_sheet(
            workbook,
            "vDatastore",
            ["Name", "Capacity MiB", "Provisioned MiB", "In Use MiB", "Free MiB", "Free %", "Accessible"],
            [["ds-01", 1000000, 700000, 600000, 400000, 40, True]],
        )
        add_sheet(
            workbook,
            "vDisk",
            ["VM", "Template", "Disk", "Capacity MiB", "Raw", "Disk Mode", "Sharing mode", "Raw Comp. Mode"],
            [["linux-on", False, "Hard disk 1", 102400, False, "persistent", "sharingNone", ""]],
        )
        add_sheet(
            workbook,
            "vNetwork",
            ["VM", "Template", "Network", "Switch", "Connected", "Cluster", "Host"],
            [["linux-on", False, "production", "dvSwitch-01", True, "cluster-a", "esx-01"]],
        )
        add_sheet(
            workbook,
            "vSnapshot",
            ["VM", "Template", "Date / time", "Size MiB (total)", "Powerstate"],
            [["linux-on", False, "2026-01-01T00:00:00", 1024, "poweredOn"]],
        )
        add_sheet(
            workbook,
            "dvPort",
            ["Port", "Switch", "VLAN", "Allow Promiscuous", "Mac Changes", "Forged Transmits", "Type"],
            [["production", "dvSwitch-01", 100, False, False, False, "earlyBinding"]],
        )
        add_sheet(
            workbook,
            "vCD",
            ["VM", "Template", "Powerstate", "Connected", "Starts Connected", "Device Type"],
            [
                ["linux-on", False, "poweredOn", True, True, "ISO image"],
                ["linux-template", True, "poweredOff", True, True, "ISO image"],
            ],
        )
        add_sheet(
            workbook,
            "vUSB",
            ["VM", "Template", "Powerstate", "Connected", "Device Type"],
            [["windows-off", False, "poweredOff", False, "USB device"]],
        )
        workbook.save(self.path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_aggregates_filtered_inventory_and_excludes_templates_by_default(self):
        self.assertTrue(hasattr(QUERY, "run_query"))
        result = QUERY.run_query(
            self.path,
            {
                "entity": "vm",
                "metrics": ["count", "sum:cpus"],
                "filters": ["guest_os_family=linux"],
                "group_by": ["cluster"],
            },
        )

        self.assertEqual(result["rows"], [{"cluster": "cluster-a", "count": 1, "sum_cpus": 4}])
        self.assertTrue(result["scope"]["templates_excluded"])

    def test_queries_cluster_overcommit_fields(self):
        self.assertTrue(hasattr(QUERY, "run_query"))
        result = QUERY.run_query(
            self.path,
            {
                "entity": "cluster",
                "select": ["cluster", "cpu_ratio", "memory_ratio"],
                "filters": ["cluster=cluster-a"],
            },
        )

        self.assertEqual(
            result["rows"],
            [{"cluster": "cluster-a", "cpu_ratio": 0.12, "memory_ratio": 0.06}],
        )

    def test_queries_host_vendor_model_cpu_topology_hyperthreading_and_bios(self):
        expected_fields = {
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
        }
        self.assertTrue(expected_fields.issubset(QUERY.ENTITY_SCHEMAS["host"]))

        result = QUERY.run_query(
            self.path,
            {
                "entity": "host",
                "select": ["host", *sorted(expected_fields)],
                "filters": ["host=esx-01"],
            },
        )

        self.assertEqual(
            result["rows"],
            [
                {
                    "host": "esx-01",
                    "bios_date": "2022-07-08",
                    "bios_vendor": "Cisco Systems, Inc.",
                    "bios_version": "C240M5.4.1.3m",
                    "cores_per_cpu": 8.0,
                    "cpu_model": "Intel(R) Xeon Gold 6248",
                    "cpu_sockets": 2.0,
                    "cpu_speed_mhz": 2500.0,
                    "cpu_vendor": "Intel",
                    "ht_active": 1,
                    "ht_available": 1,
                    "model": "HXAF240C-M5SX",
                    "vendor": "Cisco Systems Inc",
                }
            ],
        )

        unknown_ht = QUERY.run_query(
            self.path,
            {
                "entity": "host",
                "select": ["host", "ht_available", "ht_active"],
                "filters": ["host=esx-03"],
            },
        )
        self.assertEqual(
            unknown_ht["rows"],
            [{"host": "esx-03", "ht_available": None, "ht_active": None}],
        )

    def test_filters_vm_linked_entities_by_vm_cluster_context(self):
        self.assertTrue(hasattr(QUERY, "run_query"))
        self.assertIn("cluster", QUERY.ENTITY_SCHEMAS["disk"])
        result = QUERY.run_query(
            self.path,
            {
                "entity": "disk",
                "metrics": ["count", "sum:capacity_mib"],
                "filters": ["cluster=cluster-a", "power_state=poweredOn"],
            },
        )

        self.assertEqual(result["rows"], [{"count": 1, "sum_capacity_mib": 102400}])

    def test_queries_cdrom_and_usb_device_inventory(self):
        self.assertIn("cdrom", QUERY.ENTITY_SCHEMAS)
        self.assertIn("usb", QUERY.ENTITY_SCHEMAS)
        cdrom = QUERY.run_query(
            self.path,
            {"entity": "cdrom", "metrics": ["count"], "filters": ["connected=true"]},
        )
        usb = QUERY.run_query(
            self.path,
            {"entity": "usb", "metrics": ["count"], "filters": ["connected=false"]},
        )

        self.assertEqual(cdrom["rows"], [{"count": 1}])
        self.assertEqual(usb["rows"], [{"count": 1}])

    def test_rejects_non_allowlisted_fields(self):
        self.assertTrue(hasattr(QUERY, "run_query"))
        with self.assertRaisesRegex(ValueError, "not allowed"):
            QUERY.run_query(self.path, {"entity": "vm", "select": ["annotation"]})

    def test_reuses_sqlite_index_with_private_posix_permissions(self):
        self.assertTrue(hasattr(QUERY, "run_query"))
        index_path = Path(self.tempdir.name) / "inventory.sqlite"
        plan = {"entity": "vm", "metrics": ["count"]}

        first = QUERY.run_query(self.path, plan, index_path=index_path)
        second = QUERY.run_query(self.path, plan, index_path=index_path)

        self.assertFalse(first["index_reused"])
        self.assertTrue(second["index_reused"])
        self.assertTrue(index_path.is_file())
        # Windows uses inherited ACLs; st_mode cannot express owner-only access.
        if os.name != "nt":
            self.assertEqual(index_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(second["rows"], [{"count": 3}])

        workbook = load_workbook(self.path)
        workbook["vInfo"].append(
            ["new-vm", "poweredOn", False, 1, 1024, 1024, 512, "cluster-b", "esx-03", "vmx-19", False, "Ubuntu Linux", ""]
        )
        workbook.save(self.path)
        rebuilt = QUERY.run_query(self.path, plan, index_path=index_path)

        self.assertFalse(rebuilt["index_reused"])
        self.assertEqual(rebuilt["rows"], [{"count": 4}])

    def test_returns_only_warnings_relevant_to_the_query_entity(self):
        workbook = Workbook()
        workbook.remove(workbook.active)
        add_sheet(
            workbook,
            "vInfo",
            ["VM", "Powerstate", "Template", "CPUs", "Memory", "Cluster"],
            [["orphan-vm", "poweredOn", False, 2, 4096, "cluster-without-hosts"]],
        )
        add_sheet(workbook, "vHost", ["Host", "Cluster", "# Cores", "# Memory"], [])
        workbook.save(self.path)

        vm_result = QUERY.run_query(self.path, {"entity": "vm", "metrics": ["count"]})
        cluster_result = QUERY.run_query(
            self.path,
            {"entity": "cluster", "select": ["cluster", "cpu_ratio", "memory_ratio"]},
        )

        self.assertEqual(vm_result["warnings"], [])
        self.assertEqual(
            {item["code"] for item in cluster_result["warnings"]},
            {"missing_physical_cpu_capacity", "missing_physical_memory_capacity"},
        )

    def test_scopes_cluster_capacity_warnings_to_an_exact_cluster_filter(self):
        workbook = Workbook()
        workbook.remove(workbook.active)
        add_sheet(
            workbook,
            "vInfo",
            ["VM", "Powerstate", "Template", "CPUs", "Memory", "Cluster"],
            [
                ["valid-vm", "poweredOn", False, 2, 4096, "valid-cluster"],
                ["orphan-vm", "poweredOn", False, 2, 4096, "missing-cluster"],
            ],
        )
        add_sheet(
            workbook,
            "vHost",
            ["Host", "Cluster", "# Cores", "# Memory"],
            [["esx-01", "valid-cluster", 8, 32768]],
        )
        workbook.save(self.path)

        valid = QUERY.run_query(
            self.path,
            {"entity": "cluster", "metrics": ["count"], "filters": ["cluster=valid-cluster"]},
        )
        missing = QUERY.run_query(
            self.path,
            {"entity": "cluster", "metrics": ["count"], "filters": ["cluster=missing-cluster"]},
        )

        self.assertEqual(valid["warnings"], [])
        self.assertEqual(len(missing["warnings"]), 2)
        self.assertTrue(all(item["scope"] == "missing-cluster" for item in missing["warnings"]))

    def test_cli_emits_json_for_a_structured_query(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                str(self.path),
                "--entity",
                "vm",
                "--metric",
                "count",
                "--filter",
                "guest_os_family=linux",
                "--group-by",
                "cluster",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(completed.stdout.strip())
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["rows"], [{"cluster": "cluster-a", "count": 1}])

    def test_cli_rejects_a_non_allowlisted_field(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                str(self.path),
                "--entity",
                "vm",
                "--select",
                "annotation",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("not allowed", completed.stderr)


if __name__ == "__main__":
    unittest.main()
