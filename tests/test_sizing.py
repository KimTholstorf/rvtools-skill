import importlib
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def workload_rows(cluster, vm_count, vcpus, memory_gib, *, power_state="poweredOn"):
    rows = []
    remaining_cpu = vcpus
    remaining_memory_mib = memory_gib * 1024
    for index in range(vm_count):
        remaining_vms = vm_count - index
        cpus = math.ceil(remaining_cpu / remaining_vms)
        memory_mib = math.ceil(remaining_memory_mib / remaining_vms)
        rows.append(
            {
                "VM": f"{cluster}-vm-{index + 1}",
                "Cluster": cluster,
                "Powerstate": power_state,
                "Template": False,
                "CPUs": cpus,
                "Memory": memory_mib,
                "Provisioned MiB": 1024,
                "In Use MiB": 512,
            }
        )
        remaining_cpu -= cpus
        remaining_memory_mib -= memory_mib
    return rows


class SizingBootstrapTests(unittest.TestCase):
    def test_sizing_domain_imports(self):
        module = importlib.import_module("rvtools.sizing")
        self.assertEqual(module.DEFAULT_POLICY_ID, "recommended")
        self.assertEqual(set(module.POLICIES), {"recommended", "active_only"})


class SizingEngineTests(unittest.TestCase):
    def setUp(self):
        self.sizing = importlib.import_module("rvtools.sizing")

    def test_recommended_policy_reproduces_reference_six_cluster_design(self):
        cluster_inputs = {
            "Production": (1069, 2930, 11775),
            "Edge": (18, 67, 228),
            "MS SQL": (82, 212, 1271),
            "MS SQL 2": (84, 270, 1456),
            "Oracle BizTalk": (11, 36, 198),
            "SAP HANA": (38, 184, 5402),
        }
        vms = []
        hosts = []
        for cluster, (vm_count, vcpus, memory_gib) in cluster_inputs.items():
            vms.extend(workload_rows(cluster, vm_count, vcpus, memory_gib))
            hosts.append({"Host": f"{cluster}-host", "Cluster": cluster})

        result = self.sizing.size_environment(
            {"vInfo": vms, "vHost": hosts},
            "ocvs",
            policy_id="recommended",
            topology="source_aligned",
        )

        by_cluster = {row["target_cluster"]: row for row in result["clusters"]}
        self.assertEqual(
            {
                name: (row["recommendation"]["node_type"], row["recommendation"]["total_hosts"])
                for name, row in by_cluster.items()
            },
            {
                "Production": ("BM.Standard.E4.128-128", 8),
                "Edge": ("BM.Optimized3.36-26", 2),
                "MS SQL": ("BM.Standard2.52-52", 3),
                "MS SQL 2": ("BM.Standard2.52-52", 3),
                "Oracle BizTalk": ("BM.Optimized3.36-26", 2),
                "SAP HANA": ("BM.Standard.E4.128-128", 4),
            },
        )
        self.assertEqual(result["totals"]["total_hosts"], 22)
        self.assertEqual(result["totals"]["vcf_licensable_cores"], 1992)
        self.assertEqual(by_cluster["Production"]["role"], "unified_management")
        self.assertTrue(
            all(row["recommendation"]["one_host_loss_validated"] for row in result["clusters"])
        )

    def test_recommended_policy_defaults_to_provisioned_storage_without_growth(self):
        rows = {
            "vInfo": workload_rows("cluster-a", 2, 8, 16),
            "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
        }

        result = self.sizing.size_environment(rows, "ocvs", topology="consolidated")

        self.assertEqual(result["policy"]["storage_headroom_percent"], 0)
        self.assertEqual(result["policy"]["storage_basis"], "provisioned")
        self.assertEqual(
            result["totals"]["storage_required_tib"],
            result["totals"]["provisioned_storage_tib"],
        )

    def test_explicit_storage_growth_override_is_recorded_and_applied(self):
        rows = {
            "vInfo": workload_rows("cluster-a", 4, 8, 16),
            "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
        }

        result = self.sizing.size_environment(
            rows,
            "ocvs",
            topology="consolidated",
            storage_headroom_percent=25,
        )

        self.assertEqual(result["policy"]["storage_headroom_percent"], 25)
        self.assertEqual(result["policy"]["storage_basis"], "provisioned_plus_growth")
        self.assertEqual(result["policy"]["storage_headroom_source"], "user_selected")
        self.assertEqual(
            result["totals"]["storage_required_tib"],
            round(result["totals"]["provisioned_storage_tib"] * 1.25, 4),
        )

    def test_storage_headroom_finding_uses_addressable_capacity(self):
        rows = {
            "vInfo": [
                {
                    **workload_rows("cluster-a", 1, 4, 8)[0],
                    "Provisioned MiB": 1600 * 1024 * 1024,
                }
            ],
            "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
            "vDatastore": [
                {
                    "Name": "shared-ds",
                    "VI SDK Server": "vc-a",
                    "Cluster name": "cluster-a",
                    "Capacity MiB": 1800 * 1024 * 1024,
                },
                {
                    "Name": "shared-ds",
                    "VI SDK Server": "vc-a",
                    "Cluster name": "cluster-a",
                    "Capacity MiB": 1800 * 1024 * 1024,
                },
            ],
        }

        result = self.sizing.size_environment(rows, "ocvs", topology="consolidated")

        self.assertEqual(result["storage_capacity"]["status"], "complete")
        self.assertEqual(result["storage_capacity"]["datastores_counted"], 1)
        self.assertEqual(result["storage_capacity"]["addressable_storage_tib"], 1800)
        self.assertEqual(result["storage_capacity"]["provisioning_headroom_tib"], 200)
        self.assertEqual(result["storage_capacity"]["provisioning_headroom_percent"], 12.5)
        self.assertEqual(result["design_findings"][0]["id"], "limited_storage_headroom")
        self.assertEqual(result["design_findings"][0]["severity"], "information")

    def test_storage_headroom_severity_increases_when_margin_is_tighter(self):
        base_vm = workload_rows("cluster-a", 1, 4, 8)[0]
        base_vm["Provisioned MiB"] = 100 * 1024 * 1024
        for capacity_tib, expected in ((108, "low"), (100, "medium"), (90, "medium")):
            with self.subTest(capacity_tib=capacity_tib):
                rows = {
                    "vInfo": [base_vm],
                    "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
                    "vDatastore": [
                        {
                            "Name": "ds-a",
                            "Cluster name": "cluster-a",
                            "Capacity MiB": capacity_tib * 1024 * 1024,
                        }
                    ],
                }
                result = self.sizing.size_environment(
                    rows, "ocvs", topology="consolidated"
                )
                self.assertEqual(result["design_findings"][0]["severity"], expected)

    def test_recommendation_includes_management_facing_host_count_fields(self):
        rows = {
            "vInfo": workload_rows("cluster-a", 1, 4, 8),
            "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
        }

        result = self.sizing.size_environment(
            rows, "ocvs", topology="source_aligned"
        )
        presentation = result["clusters"][0]["recommendation"]["presentation"]

        self.assertEqual(presentation["workload_capacity_hosts"], 1)
        self.assertEqual(presentation["one_host_resilience_hosts"], 2)
        self.assertEqual(presentation["cloud_service_minimum_hosts"], 3)
        self.assertEqual(presentation["recommended_hosts"], 3)
        self.assertEqual(
            presentation["what_determined_the_result"], "Cloud service minimum"
        )
        self.assertEqual(
            result["topology"]["display_name"], "Retain the existing cluster structure"
        )

    def test_provider_minimum_is_not_blindly_incremented_for_failure_reserve(self):
        rows = {
            "vInfo": workload_rows("Primary", 1, 4, 8)
            + workload_rows("Small workload", 1, 4, 8),
            "vHost": [
                {"Host": "primary-host", "Cluster": "Primary"},
                {"Host": "small-host", "Cluster": "Small workload"},
            ],
        }

        result = self.sizing.size_environment(
            rows,
            "ocvs",
            policy_id="recommended",
            topology="source_aligned",
            primary_source_cluster="Primary",
        )
        by_cluster = {row["target_cluster"]: row for row in result["clusters"]}

        self.assertEqual(by_cluster["Primary"]["recommendation"]["provider_minimum_hosts"], 3)
        self.assertEqual(by_cluster["Primary"]["recommendation"]["total_hosts"], 3)
        self.assertEqual(
            by_cluster["Small workload"]["recommendation"]["provider_minimum_hosts"], 2
        )
        self.assertEqual(by_cluster["Small workload"]["recommendation"]["total_hosts"], 2)
        self.assertEqual(
            by_cluster["Small workload"]["recommendation"]["failure_cpu_floor"], 2
        )
        self.assertEqual(
            by_cluster["Small workload"]["recommendation"]["presentation"][
                "what_determined_the_result"
            ],
            "One-host resilience and cloud service minimum",
        )

    def test_failure_capacity_can_raise_count_above_provider_minimum(self):
        rows = {
            "vInfo": workload_rows("Only cluster", 5, 400, 100),
            "vHost": [{"Host": "host-1", "Cluster": "Only cluster"}],
        }
        result = self.sizing.size_environment(
            rows,
            "avs",
            policy_id="recommended",
            topology="consolidated",
            target_node="AV36",
        )
        recommendation = result["clusters"][0]["recommendation"]

        self.assertGreater(recommendation["total_hosts"], 3)
        self.assertEqual(
            recommendation["total_hosts"],
            max(
                recommendation["normal_cpu_floor"],
                recommendation["normal_memory_floor"],
                recommendation["failure_cpu_floor"],
                recommendation["failure_memory_floor"],
                recommendation["provider_minimum_hosts"],
            ),
        )

    def test_active_only_is_an_explicit_less_conservative_option(self):
        rows = {
            "vInfo": workload_rows("cluster-a", 1, 4, 8)
            + workload_rows("cluster-a", 1, 500, 400, power_state="poweredOff"),
            "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
        }
        recommended = self.sizing.size_environment(
            rows, "avs", policy_id="recommended", topology="consolidated", target_node="AV36"
        )
        active = self.sizing.size_environment(
            rows, "avs", policy_id="active_only", topology="consolidated", target_node="AV36"
        )

        self.assertEqual(recommended["policy"]["compute_scope"], "all_non_template_vms")
        self.assertEqual(active["policy"]["compute_scope"], "powered_on_non_template_vms")
        self.assertEqual(recommended["totals"]["compute_vms"], 2)
        self.assertEqual(active["totals"]["compute_vms"], 1)
        self.assertGreater(recommended["totals"]["total_hosts"], active["totals"]["total_hosts"])
        self.assertTrue(recommended["policy"]["memory_is_binding"])
        self.assertFalse(active["policy"]["memory_is_binding"])

    def test_default_policy_labels_are_provider_appropriate(self):
        rows = {
            "vInfo": workload_rows("cluster-a", 1, 4, 8),
            "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
        }

        ocvs = self.sizing.size_environment(rows, "ocvs", topology="consolidated")
        avs = self.sizing.size_environment(rows, "avs", topology="consolidated")
        gcve = self.sizing.size_environment(rows, "gcve", topology="consolidated")

        self.assertEqual(
            ocvs["policy"]["display_name"], "Recommended OCVS planning assumptions"
        )
        self.assertEqual(
            avs["policy"]["display_name"], "Recommended cloud sizing assumptions"
        )
        self.assertEqual(
            gcve["policy"]["display_name"], "Recommended cloud sizing assumptions"
        )
        self.assertNotIn("Oracle", str(avs))
        self.assertNotIn("Oracle", str(gcve))

    def test_custom_vcf_hardware_profile_uses_the_same_neutral_engine(self):
        rows = {
            "vInfo": workload_rows("cluster-a", 4, 96, 384),
            "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
        }
        profile = {
            "id": "vcf",
            "name": "VMware Cloud Foundation",
            "catalog_reviewed": "2026-09-11",
            "nodes": [
                {
                    "id": "customer-bom-node",
                    "shape_series": "customer-bom-node",
                    "configured_physical_cores": 32,
                    "silicon_cores": 32,
                    "vcf_licensable_cores": 32,
                    "memory_gib": 512,
                    "storage_only": False,
                    "raw_storage_tb": None,
                }
            ],
            "sizing_constraints": {
                "primary_role": "management_domain",
                "workload_role": "workload_domain",
                "primary_minimum_hosts": 4,
                "workload_minimum_hosts": 3,
                "maximum_hosts_per_cluster": 64,
            },
        }

        result = self.sizing.size_environment(
            rows,
            "vcf",
            topology="consolidated",
            target_profile_override=profile,
        )

        self.assertEqual(result["target"]["id"], "vcf")
        self.assertEqual(result["policy"]["display_name"], "Recommended sizing assumptions")
        self.assertEqual(result["clusters"][0]["role"], "management_domain")
        self.assertEqual(result["clusters"][0]["recommendation"]["node_type"], "customer-bom-node")
        self.assertNotIn("Oracle", str(result))

    def test_each_catalog_node_is_evaluated_once(self):
        rows = {
            "vInfo": workload_rows("cluster-a", 1, 8, 16),
            "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
        }
        profile = {
            "id": "vcf",
            "name": "VMware Cloud Foundation",
            "catalog_reviewed": "2026-09-11",
            "nodes": [
                {
                    "id": "node-a",
                    "configured_physical_cores": 32,
                    "silicon_cores": 32,
                    "vcf_licensable_cores": 32,
                    "memory_gib": 512,
                },
                {
                    "id": "node-b",
                    "configured_physical_cores": 64,
                    "silicon_cores": 64,
                    "vcf_licensable_cores": 64,
                    "memory_gib": 1024,
                },
            ],
            "sizing_constraints": {
                "primary_role": "management_domain",
                "workload_role": "workload_domain",
                "primary_minimum_hosts": 4,
                "workload_minimum_hosts": 3,
                "maximum_hosts_per_cluster": 64,
            },
        }

        with patch.object(
            self.sizing,
            "_candidate_result",
            wraps=self.sizing._candidate_result,
        ) as candidate_result:
            self.sizing.size_environment(
                rows,
                "vcf",
                topology="consolidated",
                target_profile_override=profile,
            )

        self.assertEqual(candidate_result.call_count, 2)

    def test_source_aligned_skips_declared_clusters_without_hosts(self):
        rows = {
            "vInfo": workload_rows("active-cluster", 1, 4, 8),
            "vHost": [{"Host": "host-a", "Cluster": "active-cluster"}],
            "vCluster": [
                {"Name": "active-cluster", "NumHosts": 1},
                {"Name": "empty-cluster", "NumHosts": 0},
            ],
        }

        result = self.sizing.size_environment(
            rows, "ocvs", topology="source_aligned"
        )

        self.assertEqual(result["topology"]["source_clusters"], ["active-cluster"])
        self.assertEqual(result["topology"]["excluded_zero_host_clusters"], ["empty-cluster"])

    def test_prepared_input_reuses_normalization_without_changing_results(self):
        rows = {
            "vInfo": workload_rows("cluster-a", 2, 12, 32),
            "vHost": [{"Host": "host-a", "Cluster": "cluster-a"}],
        }
        prepared = self.sizing.prepare_sizing_input(rows)

        direct = self.sizing.size_environment(rows, "ocvs", topology="consolidated")
        reused = self.sizing.size_environment(
            rows, "ocvs", topology="consolidated", prepared=prepared
        )

        self.assertEqual(reused, direct)

    def test_unknown_target_policy_and_topology_are_rejected(self):
        rows = {"vInfo": [], "vHost": []}
        with self.assertRaisesRegex(ValueError, "unknown sizing policy"):
            self.sizing.size_environment(rows, "ocvs", policy_id="not-a-policy")
        with self.assertRaisesRegex(ValueError, "unknown sizing topology"):
            self.sizing.size_environment(rows, "ocvs", topology="not-a-topology")

    def test_source_aligned_rejects_same_named_clusters_from_multiple_vcenters(self):
        rows = {
            "vInfo": workload_rows("Production", 1, 4, 8),
            "vHost": [
                {"Host": "host-a", "Cluster": "Production", "VI SDK Server": "vc-a"},
                {"Host": "host-b", "Cluster": "Production", "VI SDK Server": "vc-b"},
            ],
        }

        with self.assertRaisesRegex(ValueError, "same-named source clusters"):
            self.sizing.size_environment(rows, "ocvs", topology="source_aligned")


if __name__ == "__main__":
    unittest.main()
