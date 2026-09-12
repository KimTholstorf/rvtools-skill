import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class BomBootstrapTests(unittest.TestCase):
    def test_bom_domain_imports(self):
        module = importlib.import_module("rvtools.bom")
        self.assertEqual(module.DEFAULT_CURRENCY, "USD")

    def test_current_estate_vcf_cores_use_full_silicon_and_socket_minimum(self):
        licensing = importlib.import_module("rvtools.licensing")
        summary = licensing.summarize_vcf_hosts(
            [
                {"cpu": 2, "corespercpu": 8, "cores": 16},
                {"cpu": 2, "corespercpu": 48, "cores": 96},
            ]
        )

        self.assertTrue(summary["calculation_complete"])
        self.assertEqual(summary["physical_silicon_cores"], 112)
        self.assertEqual(summary["vcf_licensable_cores"], 128)
        self.assertFalse(summary["entitlement_verified"])


def sizing_result(target, recommendations, *, storage_required_tib=10.0):
    clusters = []
    for index, (node_type, shape_series, hosts, cores, memory) in enumerate(recommendations):
        clusters.append(
            {
                "target_cluster": f"cluster-{index + 1}",
                "recommendation": {
                    "node_type": node_type,
                    "shape_series": shape_series,
                    "total_hosts": hosts,
                    "configured_physical_cores_per_host": cores,
                    "memory_gib_per_host": memory,
                    "vcf_licensable_cores_per_host": cores,
                    "vcf_licensable_cores": hosts * cores,
                    "raw_storage_tb_total": 20 * hosts,
                },
            }
        )
    return {
        "status": "complete",
        "target": {"id": target, "name": target.upper()},
        "clusters": clusters,
        "totals": {
            "total_hosts": sum(item[2] for item in recommendations),
            "vcf_licensable_cores": sum(item[2] * item[3] for item in recommendations),
            "storage_required_tib": storage_required_tib,
        },
    }


class FakeAdapter:
    provider = "fake"
    monthly_hours = 730
    columns = ("Category", "Component", "SKU", "Quantity", "Rate", "Monthly")

    def component_specs(self, sizing, storage_plan=None):
        return [
            {
                "category": "Compute",
                "component": "example host",
                "sku": "sku-1",
                "quantity": 2,
                "billing_quantity": 2,
                "billing_unit": "host hour",
            }
        ]

    def quote(self, spec, *, region, currency, pricing_model):
        return {
            "status": "priced",
            "currency": currency,
            "unit_price": 5.0,
            "unit": "1 Hour",
            "effective_at": "2026-09-01",
            "source_url": "https://example.test/prices",
            "provider_fields": {"SKU": spec["sku"]},
        }


class BomEngineTests(unittest.TestCase):
    def setUp(self):
        self.bom = importlib.import_module("rvtools.bom")

    def test_builds_normalized_bom_and_vcf_delta(self):
        sizing = sizing_result("avs", [("AV64", "AV64", 3, 64, 1024)])
        result = self.bom.build_bom(
            sizing,
            adapter=FakeAdapter(),
            region="eastus",
            current_vcf_cores=128,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["monthly_hours"], 730)
        self.assertEqual(result["priced_monthly_total"], 7300.0)
        self.assertEqual(result["licensing"]["target_vcf_cores"], 192)
        self.assertEqual(result["licensing"]["additional_vcf_cores"], 64)
        self.assertEqual(result["licensing"]["surplus_vcf_cores"], 0)
        self.assertEqual(result["table"]["columns"], list(FakeAdapter.columns))
        self.assertEqual(
            result["license_lines"][-1]["component"], "Additional VCF cores required"
        )

    def test_missing_region_keeps_quantities_but_does_not_guess_a_price(self):
        sizing = sizing_result("gcve", [("ve1-standard-72", "ve1-standard-72", 3, 36, 768)])
        result = self.bom.build_bom(sizing, adapter=FakeAdapter())

        self.assertEqual(result["status"], "unpriced")
        self.assertEqual(result["lines"][0]["quantity"], 2)
        self.assertIsNone(result["lines"][0]["unit_price"])
        self.assertIn("pricing_region_required", {row["code"] for row in result["warnings"]})

    def test_partial_pricing_never_reports_a_misleading_grand_total(self):
        class PartialAdapter(FakeAdapter):
            def component_specs(self, sizing, storage_plan=None):
                first = super().component_specs(sizing)[0]
                return [first, {**first, "component": "missing", "sku": "sku-2"}]

            def quote(self, spec, **kwargs):
                if spec["sku"] == "sku-2":
                    return {"status": "unpriced", "reason": "not found"}
                return super().quote(spec, **kwargs)

        result = self.bom.build_bom(
            sizing_result("avs", [("AV64", "AV64", 3, 64, 1024)]),
            adapter=PartialAdapter(),
            region="eastus",
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["priced_monthly_subtotal"], 7300.0)
        self.assertIsNone(result["priced_monthly_total"])

    def test_provider_storage_defaults_and_elastic_san_split_are_deterministic(self):
        ocvs = self.bom.storage_plan_for_sizing(
            sizing_result("ocvs", [("BM.Standard3.64-64", "BM.Standard3.64", 3, 64, 1024)], storage_required_tib=12.5)
        )
        avs = self.bom.storage_plan_for_sizing(
            sizing_result("avs", [("AV64", "AV64", 3, 64, 1024)], storage_required_tib=100),
            strategy="elastic_san",
            elastic_san_base_tib=28,
        )
        gcve = self.bom.storage_plan_for_sizing(
            sizing_result("gcve", [("ve2-mega-96", "ve2-mega-96", 3, 64, 2048)])
        )

        self.assertEqual(ocvs["strategy"], "block_volume")
        self.assertEqual(ocvs["capacity_tib"], 12.5)
        self.assertEqual((avs["base_tib"], avs["capacity_tib"]), (28, 72))
        self.assertEqual(gcve["strategy"], "integrated_vsan")
        self.assertFalse(gcve["capacity_validated"])

    def test_elastic_san_requires_an_explicit_performance_bearing_base(self):
        with self.assertRaisesRegex(ValueError, "explicit base capacity"):
            self.bom.storage_plan_for_sizing(
                sizing_result("avs", [("AV64", "AV64", 3, 64, 1024)]),
                strategy="elastic_san",
            )

    def test_unvalidated_integrated_storage_withholds_a_design_total(self):
        sizing = sizing_result("avs", [("AV64", "AV64", 3, 64, 1024)])
        storage = self.bom.storage_plan_for_sizing(sizing)

        result = self.bom.build_bom(
            sizing,
            adapter=FakeAdapter(),
            region="eastus",
            storage_plan=storage,
        )

        self.assertEqual(result["pricing_status"], "complete")
        self.assertEqual(result["quantity_status"], "validation_required")
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["priced_monthly_total"])
        self.assertEqual(result["priced_monthly_subtotal"], 7300)

    def test_incomplete_sizing_cannot_produce_a_partial_design_bom(self):
        sizing = sizing_result("ocvs", [("BM.Standard3.64-64", "BM.Standard3.64", 3, 64, 1024)])
        sizing["status"] = "attention_required"
        sizing["clusters"][0]["status"] = "no_valid_target_node"
        sizing["clusters"][0]["recommendation"] = None
        sizing["totals"]["total_hosts"] = None

        with self.assertRaisesRegex(ValueError, "completed sizing result"):
            self.bom.build_bom(sizing, adapter=FakeAdapter(), region="eastus")

    def test_confirmed_entitlement_is_distinct_from_the_hardware_proxy(self):
        result = self.bom.build_bom(
            sizing_result("avs", [("AV64", "AV64", 3, 64, 1024)]),
            adapter=FakeAdapter(),
            region="eastus",
            current_vcf_cores=256,
            current_entitlement_verified=True,
        )

        self.assertEqual(result["licensing"]["current_vcf_basis"], "verified_entitlement")
        self.assertEqual(result["licensing"]["surplus_vcf_cores"], 64)
        self.assertEqual(
            result["license_lines"][0]["component"],
            "Current VCF cores (confirmed entitlement)",
        )
        self.assertIn("Customer-confirmed", result["license_lines"][0]["note"])


class ProviderAdapterTests(unittest.TestCase):
    def test_ocvs_expands_shape_components_and_preserves_existing_columns(self):
        oci = importlib.import_module("rvtools.pricing.oci")
        sizing = sizing_result(
            "ocvs",
            [
                ("BM.Standard.E4.128-128", "BM.Standard.E4.128", 2, 128, 2048),
                ("BM.Standard2.52-52", "BM.Standard2.52", 3, 52, 768),
            ],
            storage_required_tib=20,
        )
        specs = oci.OciPricingAdapter().component_specs(sizing)

        self.assertEqual(oci.OciPricingAdapter.monthly_hours, 744)
        self.assertIn("OCI part number", oci.OciPricingAdapter.columns)
        self.assertEqual(
            [(row["sku"], row["billing_quantity"]) for row in specs],
            [
                ("B93113", 256),
                ("B93114", 4096),
                ("B88514", 156),
                ("B91961", 20480),
                ("B91962", 204800),
            ],
        )

        unpriced = oci.OciPricingAdapter(fetch_json=lambda *args, **kwargs: {}).table_row(
            specs[0],
            {
                "category": specs[0]["category"],
                "component": specs[0]["component"],
                "provider_fields": {},
                "billing_quantity": specs[0]["billing_quantity"],
                "unit_price": None,
                "estimated_monthly": None,
            },
        )
        self.assertEqual(unpriced["OCI part number"], "B93113")
        self.assertEqual(
            unpriced["Oracle API product name"], "Compute - Standard - E4 - OCPU"
        )

    def test_azure_uses_api_native_columns_and_elastic_san_rows(self):
        azure = importlib.import_module("rvtools.pricing.azure")
        sizing = sizing_result("avs", [("AV64", "AV64", 3, 64, 1024)], storage_required_tib=100)
        adapter = azure.AzurePricingAdapter(fetch_json=lambda *args, **kwargs: {})
        specs = adapter.component_specs(
            sizing,
            storage_plan={
                "strategy": "elastic_san",
                "redundancy": "LRS",
                "base_tib": 20,
                "capacity_tib": 80,
            },
        )

        self.assertEqual(adapter.monthly_hours, 730)
        self.assertIn("Azure SKU ID", adapter.columns)
        self.assertEqual(specs[0]["api_sku_name"], "AV64 VCF BYOL")
        self.assertEqual(
            [row["api_meter_name"] for row in specs[1:]],
            [
                "Premium LRS Provisioned Base Unit",
                "Premium LRS Provisioned Capacity Unit",
            ],
        )

    def test_google_requires_a_key_for_live_prices_but_not_for_bom_quantities(self):
        google = importlib.import_module("rvtools.pricing.google")
        adapter = google.GooglePricingAdapter(environ={}, fetch_json=lambda *args, **kwargs: {})
        specs = adapter.component_specs(
            sizing_result("gcve", [("ve2-mega-96", "ve2-mega-96", 3, 64, 2048)])
        )
        quote = adapter.quote(
            specs[0], region="us-central1", currency="USD", pricing_model="on_demand"
        )

        self.assertEqual(adapter.monthly_hours, 730)
        self.assertIn("Google SKU ID", adapter.columns)
        self.assertEqual(quote["status"], "unpriced")
        self.assertEqual(quote["reason"], "google_api_key_required")

    def test_azure_filters_trial_and_wrong_region_records(self):
        azure = importlib.import_module("rvtools.pricing.azure")
        payload = {
            "Items": [
                {
                    "currencyCode": "USD",
                    "retailPrice": 0,
                    "armRegionName": "eastus",
                    "productName": "Specialized Compute Azure VMware Solution",
                    "skuName": "AV64 Trial Node",
                    "meterName": "AV64 Trial Node",
                    "skuId": "trial",
                    "unitOfMeasure": "1 Hour",
                    "type": "Consumption",
                    "effectiveStartDate": "2026-01-01T00:00:00Z",
                },
                {
                    "currencyCode": "USD",
                    "retailPrice": 10,
                    "armRegionName": "eastus",
                    "productName": "Specialized Compute Azure VMware Solution",
                    "skuName": "AV64 VCF BYOL",
                    "meterName": "AV64 VCF BYOL Node",
                    "skuId": "real",
                    "unitOfMeasure": "1 Hour",
                    "type": "Consumption",
                    "effectiveStartDate": "2026-01-01T00:00:00Z",
                },
            ],
            "NextPageLink": None,
        }
        adapter = azure.AzurePricingAdapter(fetch_json=lambda *args, **kwargs: payload)
        spec = adapter.component_specs(
            sizing_result("avs", [("AV64", "AV64", 3, 64, 1024)])
        )[0]
        quote = adapter.quote(spec, region="eastus", currency="USD", pricing_model="on_demand")

        self.assertEqual(quote["status"], "priced")
        self.assertEqual(quote["unit_price"], 10)
        self.assertEqual(quote["provider_fields"]["Azure SKU ID"], "real")

    def test_oci_selects_the_requested_currency_and_payg_rate(self):
        oci = importlib.import_module("rvtools.pricing.oci")
        payload = {
            "lastUpdated": "2026-09-01",
            "items": [
                {
                    "partNumber": "B93113",
                    "displayName": "Compute - Standard - E4 - OCPU",
                    "metricName": "OCPU per hour",
                    "currencyCodeLocalizations": [
                        {
                            "currencyCode": "EUR",
                            "prices": [
                                {"model": "PAY_AS_YOU_GO", "value": "0.031"}
                            ],
                        }
                    ],
                }
            ],
        }
        adapter = oci.OciPricingAdapter(fetch_json=lambda *args, **kwargs: payload)
        quote = adapter.quote(
            {
                "sku": "B93113",
                "billing_unit": "OCPU hour",
            },
            region=None,
            currency="EUR",
            pricing_model="on_demand",
        )

        self.assertEqual(quote["status"], "priced")
        self.assertEqual(quote["unit_price"], 0.031)
        self.assertEqual(quote["provider_fields"]["OCI part number"], "B93113")

    def test_google_selects_region_node_and_usage_type_without_putting_key_in_url(self):
        google = importlib.import_module("rvtools.pricing.google")
        calls = []

        def fetch(url, **kwargs):
            calls.append((url, kwargs))
            return {
                "skus": [
                    {
                        "skuId": "GCVE-96",
                        "description": "VMware Engine Gen 2 mega 96 node",
                        "serviceRegions": ["us-central1"],
                        "category": {"usageType": "OnDemand"},
                        "pricingInfo": [
                            {
                                "effectiveTime": "2026-09-01T00:00:00Z",
                                "pricingExpression": {
                                    "usageUnit": "h",
                                    "tieredRates": [
                                        {
                                            "startUsageAmount": 0,
                                            "unitPrice": {"units": "11", "nanos": 500000000},
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ]
            }

        adapter = google.GooglePricingAdapter(
            environ={"GOOGLE_CLOUD_API_KEY": "private-test-key"}, fetch_json=fetch
        )
        spec = adapter.component_specs(
            sizing_result("gcve", [("ve2-mega-96", "ve2-mega-96", 3, 64, 2048)])
        )[0]
        quote = adapter.quote(
            spec,
            region="us-central1",
            currency="USD",
            pricing_model="on_demand",
        )

        self.assertEqual(quote["status"], "priced")
        self.assertEqual(quote["unit_price"], 11.5)
        self.assertEqual(quote["provider_fields"]["Google SKU ID"], "GCVE-96")
        self.assertNotIn("private-test-key", calls[0][0])
        self.assertEqual(calls[0][1]["headers"]["X-Goog-Api-Key"], "private-test-key")

    def test_pricing_adapter_stops_retrying_after_an_endpoint_failure(self):
        oci = importlib.import_module("rvtools.pricing.oci")
        calls = []

        def fail(url, **kwargs):
            calls.append(url)
            raise OSError("offline")

        adapter = oci.OciPricingAdapter(fetch_json=fail)
        first = adapter.quote(
            {"sku": "B93113", "billing_unit": "OCPU hour"},
            region=None,
            currency="USD",
            pricing_model="on_demand",
        )
        second = adapter.quote(
            {"sku": "B93114", "billing_unit": "GiB hour"},
            region=None,
            currency="USD",
            pricing_model="on_demand",
        )

        self.assertEqual(first["reason"], "pricing_api_unavailable")
        self.assertEqual(second["reason"], "pricing_api_unavailable")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
