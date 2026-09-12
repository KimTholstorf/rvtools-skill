"""Google Cloud Billing Catalog adapter for GCVE BOM components."""

from __future__ import annotations

import os
from collections import defaultdict
from urllib.parse import urlencode

from .base import CachedJsonFetcher, money_value, normalized_text


SERVICE_ID = "C079-64FE-9109"
API_URL = f"https://cloudbilling.googleapis.com/v1/services/{SERVICE_ID}/skus"


class GooglePricingAdapter:
    provider = "gcve"
    monthly_hours = 730
    region_required = True
    columns = (
        "Category",
        "GCVE component",
        "Google SKU ID",
        "Google SKU description",
        "Service region",
        "Billable quantity",
        "Usage unit",
        "Pricing model",
        "Currency",
        "List rate",
        "Estimated monthly",
    )

    def __init__(self, *, environ=None, fetch_json=None):
        self.environ = os.environ if environ is None else environ
        self.api_key = self.environ.get("GOOGLE_CLOUD_API_KEY") or self.environ.get("GOOGLE_API_KEY")
        self.fetch_json = fetch_json or CachedJsonFetcher()
        self._catalog_cache = {}
        self._api_failure = None

    def component_specs(self, sizing, storage_plan=None):
        grouped = defaultdict(int)
        for cluster in sizing.get("clusters", []):
            recommendation = cluster.get("recommendation") or {}
            if recommendation.get("node_type"):
                grouped[recommendation["node_type"]] += int(recommendation.get("total_hosts") or 0)
        specs = [
            {
                "category": "GCVE HCI nodes",
                "component": f"{hosts} × {node}",
                "sku": node,
                "quantity": hosts,
                "billing_quantity": hosts,
                "billing_unit": "node hour",
                "node_type": node,
            }
            for node, hosts in sorted(grouped.items())
        ]
        storage_only = (storage_plan or {}).get("storage_only_nodes", {})
        for node, count in sorted(storage_only.items()):
            if int(count) > 0:
                specs.append(
                    {
                        "category": "GCVE storage-only nodes",
                        "component": f"{int(count)} × {node}",
                        "sku": node,
                        "quantity": int(count),
                        "billing_quantity": int(count),
                        "billing_unit": "node hour",
                        "node_type": node,
                    }
                )
        return specs

    def _catalog(self, currency):
        currency = currency.upper()
        if currency in self._catalog_cache:
            return self._catalog_cache[currency]
        headers = {"Accept": "application/json", "X-Goog-Api-Key": self.api_key}
        url = API_URL + "?" + urlencode({"currencyCode": currency})
        skus = []
        while url:
            payload = self.fetch_json(url, headers=headers)
            skus.extend(payload.get("skus", []))
            token = payload.get("nextPageToken")
            url = API_URL + "?" + urlencode(
                {"currencyCode": currency, "pageToken": token}
            ) if token else None
        self._catalog_cache[currency] = skus
        return skus

    @staticmethod
    def _node_matches(description, node_type):
        text = normalized_text(description)
        node = normalized_text(node_type)
        if node.startswith("ve2 "):
            _, family, size = node.split()
            if size == "so":
                return "gen 2" in text and family in text and "storage only" in text
            return "gen 2" in text and family in text and size in text and "node" in text and "storage only" not in text
        if node == "ve1 standard 72":
            return "72" in text and "node" in text and "storage only" not in text and "gen 2" not in text
        if node == "ve1 standard so":
            return "storage only" in text and "gen 2" not in text
        return False

    def quote(self, spec, *, region, currency, pricing_model):
        if not self.api_key:
            return {"status": "unpriced", "reason": "google_api_key_required"}
        if not region:
            return {"status": "unpriced", "reason": "pricing_region_required"}
        if self._api_failure is not None:
            return {
                "status": "unpriced",
                "reason": "pricing_api_unavailable",
                "detail": self._api_failure,
            }
        usage_types = {
            "on_demand": {"ondemand", "on demand"},
            "one_year": {"commit1yr", "commit 1 yr", "1 year"},
            "three_year": {"commit3yr", "commit 3 yr", "3 year"},
        }.get(pricing_model)
        if usage_types is None:
            return {"status": "unpriced", "reason": "google_pricing_model_unsupported"}
        try:
            skus = self._catalog(currency)
        except Exception as exc:
            self._api_failure = str(exc)
            return {"status": "unpriced", "reason": "pricing_api_unavailable", "detail": self._api_failure}
        candidates = []
        for sku in skus:
            regions = sku.get("serviceRegions", [])
            usage_type = normalized_text(sku.get("category", {}).get("usageType"))
            if region not in regions or usage_type not in usage_types:
                continue
            if self._node_matches(sku.get("description"), spec["node_type"]):
                candidates.append(sku)
        if not candidates:
            return {"status": "unpriced", "reason": "google_rate_unavailable"}
        if len(candidates) > 1:
            return {"status": "unpriced", "reason": "google_rate_ambiguous"}
        sku = candidates[0]
        pricing = sku.get("pricingInfo", [])[-1] if sku.get("pricingInfo") else {}
        expression = pricing.get("pricingExpression", {})
        rates = expression.get("tieredRates", [])
        zero_tier = [row for row in rates if float(row.get("startUsageAmount") or 0) == 0]
        if len(zero_tier) != 1:
            return {"status": "unpriced", "reason": "google_tiered_rate_requires_input"}
        unit_price = money_value(zero_tier[0].get("unitPrice"))
        if unit_price is None:
            return {"status": "unpriced", "reason": "google_rate_unavailable"}
        return {
            "status": "priced",
            "currency": currency.upper(),
            "unit_price": unit_price,
            "unit": expression.get("usageUnit") or spec["billing_unit"],
            "monthly_factor": self.monthly_hours,
            "effective_at": pricing.get("effectiveTime"),
            "source_url": API_URL,
            "provider_fields": {
                "Google SKU ID": sku.get("skuId"),
                "Google SKU description": sku.get("description"),
                "Service region": region,
                "Pricing model": sku.get("category", {}).get("usageType"),
            },
        }

    def table_row(self, spec, line):
        fields = line.get("provider_fields", {})
        return {
            "Category": line["category"],
            "GCVE component": line["component"],
            "Google SKU ID": fields.get("Google SKU ID"),
            "Google SKU description": fields.get("Google SKU description"),
            "Service region": fields.get("Service region") or line.get("region"),
            "Billable quantity": line["billing_quantity"],
            "Usage unit": line["billing_unit"],
            "Pricing model": fields.get("Pricing model") or line.get("pricing_model"),
            "Currency": line["currency"],
            "List rate": line["unit_price"],
            "Estimated monthly": line["estimated_monthly"],
        }

    def license_table_row(self, row, *, currency):
        return {
            "Category": row["category"],
            "GCVE component": row["component"],
            "Google SKU ID": None,
            "Google SKU description": row["note"],
            "Service region": None,
            "Billable quantity": row["quantity"],
            "Usage unit": "VCF core",
            "Pricing model": None,
            "Currency": currency,
            "List rate": None,
            "Estimated monthly": None,
        }
