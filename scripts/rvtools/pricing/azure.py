"""Microsoft Azure Retail Prices adapter for AVS BOM components."""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlencode

from .base import CachedJsonFetcher


API_URL = "https://prices.azure.com/api/retail/prices"


class AzurePricingAdapter:
    provider = "avs"
    monthly_hours = 730
    region_required = True
    columns = (
        "Category",
        "Azure component",
        "Azure product",
        "SKU name",
        "Meter name",
        "Azure SKU ID",
        "Region",
        "Billable quantity",
        "Billing unit",
        "Currency",
        "Retail price",
        "Estimated monthly",
    )

    def __init__(self, *, fetch_json=None):
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
                "category": "AVS hosts",
                "component": f"{hosts} × {node}",
                "sku": node,
                "api_product_name": "Specialized Compute Azure VMware Solution",
                "api_sku_name": f"{node} VCF BYOL",
                "api_meter_name": f"{node} VCF BYOL Node",
                "quantity": hosts,
                "billing_quantity": hosts,
                "billing_unit": "host hour",
            }
            for node, hosts in sorted(grouped.items())
        ]
        storage_plan = storage_plan or {}
        if storage_plan.get("strategy") == "elastic_san":
            redundancy = str(storage_plan.get("redundancy", "LRS")).upper()
            for label, amount in (
                ("Base", float(storage_plan.get("base_tib") or 0)),
                ("Capacity", float(storage_plan.get("capacity_tib") or 0)),
            ):
                if amount <= 0:
                    continue
                specs.append(
                    {
                        "category": "External storage",
                        "component": f"Azure Elastic SAN Premium {redundancy} {label.lower()} capacity",
                        "sku": f"Premium {redundancy}",
                        "api_product_name": "Azure Elastic SAN",
                        "api_sku_name": f"Premium {redundancy}",
                        "api_meter_name": f"Premium {redundancy} Provisioned {label} Unit",
                        "quantity": amount,
                        "billing_quantity": amount * 1024,
                        "billing_unit": "GiB month",
                    }
                )
        return specs

    def _catalog(self, product, region, currency):
        cache_key = (product, region, currency.upper())
        if cache_key in self._catalog_cache:
            return self._catalog_cache[cache_key]
        expression = f"productName eq '{product}' and armRegionName eq '{region}'"
        url = API_URL + "?" + urlencode(
            {
                "api-version": "2023-01-01-preview",
                "currencyCode": f"'{currency.upper()}'",
                "$filter": expression,
            }
        )
        items = []
        while url:
            payload = self.fetch_json(url)
            items.extend(payload.get("Items", []))
            url = payload.get("NextPageLink")
        self._catalog_cache[cache_key] = items
        return items

    def quote(self, spec, *, region, currency, pricing_model):
        if not region:
            return {"status": "unpriced", "reason": "pricing_region_required"}
        if self._api_failure is not None:
            return {
                "status": "unpriced",
                "reason": "pricing_api_unavailable",
                "detail": self._api_failure,
            }
        try:
            items = self._catalog(spec["api_product_name"], region, currency)
        except Exception as exc:
            self._api_failure = str(exc)
            return {"status": "unpriced", "reason": "pricing_api_unavailable", "detail": self._api_failure}
        candidates = [
            item for item in items
            if item.get("armRegionName") == region
            and str(item.get("currencyCode", "")).upper() == currency.upper()
            and item.get("productName") == spec["api_product_name"]
            and item.get("skuName") == spec["api_sku_name"]
            and item.get("meterName") == spec["api_meter_name"]
        ]
        if pricing_model == "on_demand":
            candidates = [item for item in candidates if item.get("type") == "Consumption"]
            monthly_factor = self.monthly_hours if "hour" in spec["billing_unit"] else 1
        elif pricing_model in {"one_year", "three_year"}:
            term = "1 Year" if pricing_model == "one_year" else "3 Years"
            candidates = [
                item for item in candidates
                if item.get("type") == "Reservation" and item.get("reservationTerm") == term
            ]
            monthly_factor = 1 / (12 if pricing_model == "one_year" else 36)
        else:
            return {"status": "unpriced", "reason": "azure_pricing_model_unsupported"}
        if not candidates:
            return {"status": "unpriced", "reason": "azure_rate_unavailable"}
        if len(candidates) > 1:
            return {"status": "unpriced", "reason": "azure_rate_ambiguous"}
        item = candidates[0]
        return {
            "status": "priced",
            "currency": currency.upper(),
            "unit_price": float(item["retailPrice"]),
            "unit": item.get("unitOfMeasure") or spec["billing_unit"],
            "monthly_factor": monthly_factor,
            "effective_at": item.get("effectiveStartDate"),
            "source_url": API_URL,
            "provider_fields": {
                "Azure product": item.get("productName"),
                "SKU name": item.get("skuName"),
                "Meter name": item.get("meterName"),
                "Azure SKU ID": item.get("skuId"),
                "Region": item.get("armRegionName"),
            },
        }

    def table_row(self, spec, line):
        fields = line.get("provider_fields", {})
        return {
            "Category": line["category"],
            "Azure component": line["component"],
            "Azure product": fields.get("Azure product") or spec.get("api_product_name"),
            "SKU name": fields.get("SKU name") or spec.get("api_sku_name"),
            "Meter name": fields.get("Meter name") or spec.get("api_meter_name"),
            "Azure SKU ID": fields.get("Azure SKU ID"),
            "Region": fields.get("Region") or line.get("region"),
            "Billable quantity": line["billing_quantity"],
            "Billing unit": line["billing_unit"],
            "Currency": line["currency"],
            "Retail price": line["unit_price"],
            "Estimated monthly": line["estimated_monthly"],
        }

    def license_table_row(self, row, *, currency):
        return {
            "Category": row["category"],
            "Azure component": row["component"],
            "Azure product": row["note"],
            "SKU name": None,
            "Meter name": None,
            "Azure SKU ID": None,
            "Region": None,
            "Billable quantity": row["quantity"],
            "Billing unit": "VCF core",
            "Currency": currency,
            "Retail price": None,
            "Estimated monthly": None,
        }
