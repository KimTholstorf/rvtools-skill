"""Oracle public price-list adapter for OCVS BOM components."""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlencode

from .base import CachedJsonFetcher


API_URL = "https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/"
PAYMENT_MODELS = {
    "on_demand": "PAY_AS_YOU_GO",
    "pay_as_you_go": "PAY_AS_YOU_GO",
}
SHAPE_COMPONENTS = {
    "BM.Standard2.52": (("Compute", "B88514", "Compute - Virtual Machine Standard - X7", "cores"),),
    "BM.Standard3.64": (
        ("Compute", "B94176", "Compute - Standard - X9 - OCPU", "cores"),
        ("Memory", "B94177", "Compute - Standard - X9 - Memory", "memory"),
    ),
    "BM.Standard.E4.128": (
        ("Compute", "B93113", "Compute - Standard - E4 - OCPU", "cores"),
        ("Memory", "B93114", "Compute - Standard - E4 - Memory", "memory"),
    ),
    "BM.Standard.E5.192": (
        ("Compute", "B97384", "Compute - Standard - E5 - OCPU", "cores"),
        ("Memory", "B97385", "Compute - Standard - E5 - Memory", "memory"),
    ),
    "BM.Optimized3.36": (
        ("Compute", "B93311", "Compute - Optimized - X9 - OCPU", "cores"),
        ("Memory", "B93312", "Compute - Optimized - X9 - Memory", "memory"),
    ),
}


class OciPricingAdapter:
    provider = "ocvs"
    monthly_hours = 744
    region_required = False
    columns = (
        "Category",
        "Target shape/component",
        "OCI part number",
        "Oracle API product name",
        "Billable quantity",
        "USD list rate",
        "Estimated monthly",
    )

    @classmethod
    def columns_for(cls, currency):
        return (*cls.columns[:-2], f"{currency.upper()} list rate", cls.columns[-1])

    def __init__(self, *, fetch_json=None):
        self.fetch_json = fetch_json or CachedJsonFetcher()
        self._api_failure = None

    def component_specs(self, sizing, storage_plan=None):
        grouped = defaultdict(lambda: {"hosts": 0, "cores": 0, "memory": 0})
        for cluster in sizing.get("clusters", []):
            recommendation = cluster.get("recommendation") or {}
            shape = recommendation.get("shape_series")
            hosts = int(recommendation.get("total_hosts") or 0)
            if not shape or not hosts:
                continue
            grouped[shape]["hosts"] += hosts
            grouped[shape]["cores"] += hosts * float(
                recommendation.get("configured_physical_cores_per_host") or 0
            )
            grouped[shape]["memory"] += hosts * float(
                recommendation.get("memory_gib_per_host") or 0
            )

        specs = []
        for shape in sorted(grouped):
            values = grouped[shape]
            if shape not in SHAPE_COMPONENTS:
                specs.append(
                    {
                        "category": "Compute",
                        "component": f"{values['hosts']} × {shape}",
                        "sku": None,
                        "quantity": values["hosts"],
                        "billing_quantity": values["hosts"],
                        "billing_unit": "host",
                        "unpriced_reason": "oci_shape_mapping_unavailable",
                    }
                )
                continue
            for category, sku, product, basis in SHAPE_COMPONENTS[shape]:
                quantity = values[basis]
                suffix = " — memory" if basis == "memory" else " — CPU"
                if shape == "BM.Standard2.52":
                    suffix = ""
                specs.append(
                    {
                        "category": category,
                        "component": f"{values['hosts']} × {shape}{suffix}",
                        "sku": sku,
                        "api_product_name": product,
                        "quantity": quantity,
                        "billing_quantity": quantity,
                        "billing_unit": "GiB hour" if basis == "memory" else "OCPU hour",
                    }
                )

        storage_plan = storage_plan or {}
        storage_tib = float(storage_plan.get("capacity_tib") or sizing.get("totals", {}).get("storage_required_tib") or 0)
        if storage_tib > 0:
            gib = storage_tib * 1024
            vpu_per_gb = float(storage_plan.get("vpu_per_gb", 10))
            specs.extend(
                [
                    {
                        "category": "Storage",
                        "component": f"{storage_tib:,.2f} TiB Block Volume capacity",
                        "sku": "B91961",
                        "api_product_name": "Storage - Block Volume - Storage",
                        "quantity": gib,
                        "billing_quantity": gib,
                        "billing_unit": "GiB month",
                    },
                    {
                        "category": "Performance",
                        "component": f"Balanced, {vpu_per_gb:g} VPU/GB",
                        "sku": "B91962",
                        "api_product_name": "Storage - Block Volume - Performance Units",
                        "quantity": gib * vpu_per_gb,
                        "billing_quantity": gib * vpu_per_gb,
                        "billing_unit": "performance unit month",
                    },
                ]
            )
        return specs

    def quote(self, spec, *, region, currency, pricing_model):
        if spec.get("unpriced_reason") or not spec.get("sku"):
            return {"status": "unpriced", "reason": spec.get("unpriced_reason") or "sku_missing"}
        model = PAYMENT_MODELS.get(pricing_model)
        if model is None:
            return {"status": "unpriced", "reason": "oci_pricing_model_unsupported"}
        if self._api_failure is not None:
            return {
                "status": "unpriced",
                "reason": "pricing_api_unavailable",
                "detail": self._api_failure,
            }
        url = API_URL + "?" + urlencode(
            {"partNumber": spec["sku"], "currencyCode": currency.upper()}
        )
        try:
            payload = self.fetch_json(url)
        except Exception as exc:  # network/catalog failures are reportable, not fatal
            self._api_failure = str(exc)
            return {"status": "unpriced", "reason": "pricing_api_unavailable", "detail": self._api_failure}
        matches = [item for item in payload.get("items", []) if item.get("partNumber") == spec["sku"]]
        if not matches:
            return {"status": "unpriced", "reason": "oci_sku_unavailable"}
        if len(matches) > 1:
            return {"status": "unpriced", "reason": "oci_sku_ambiguous"}
        item = matches[0]
        localizations = [
            row for row in item.get("currencyCodeLocalizations", [])
            if str(row.get("currencyCode", "")).upper() == currency.upper()
        ]
        prices = [
            price for row in localizations for price in row.get("prices", [])
            if price.get("model") == model
        ]
        if not prices:
            return {"status": "unpriced", "reason": "oci_currency_or_rate_unavailable"}
        if len(prices) > 1:
            return {"status": "unpriced", "reason": "oci_rate_ambiguous"}
        return {
            "status": "priced",
            "currency": currency.upper(),
            "unit_price": float(prices[0]["value"]),
            "unit": item.get("metricName") or spec["billing_unit"],
            "monthly_factor": self.monthly_hours if "hour" in spec["billing_unit"] else 1,
            "effective_at": payload.get("lastUpdated"),
            "source_url": API_URL,
            "provider_fields": {
                "OCI part number": spec["sku"],
                "Oracle API product name": item.get("displayName") or spec.get("api_product_name"),
            },
        }

    def table_row(self, spec, line):
        fields = line.get("provider_fields", {})
        rate_column = f"{line.get('currency', 'USD')} list rate"
        return {
            "Category": line["category"],
            "Target shape/component": line["component"],
            "OCI part number": spec.get("sku"),
            "Oracle API product name": fields.get("Oracle API product name")
            or spec.get("api_product_name"),
            "Billable quantity": line["billing_quantity"],
            rate_column: line["unit_price"],
            "Estimated monthly": line["estimated_monthly"],
        }

    def license_table_row(self, row, *, currency):
        return {
            "Category": row["category"],
            "Target shape/component": row["component"],
            "OCI part number": None,
            "Oracle API product name": row["note"],
            "Billable quantity": row["quantity"],
            f"{currency} list rate": None,
            "Estimated monthly": None,
        }
