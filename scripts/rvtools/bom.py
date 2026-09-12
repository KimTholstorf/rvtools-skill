"""Provider-neutral bill-of-materials calculations for cloud VMware sizing."""

from __future__ import annotations

from datetime import datetime, timezone

from .pricing import adapter_for


DEFAULT_CURRENCY = "USD"
DEFAULT_PRICING_MODEL = "on_demand"


def storage_plan_for_sizing(
    sizing,
    *,
    strategy=None,
    redundancy="LRS",
    elastic_san_base_tib=None,
    storage_vpu_per_gb=10,
):
    """Resolve the storage components that belong in a provider BOM."""
    target = sizing.get("target", {}).get("id")
    required_tib = float(sizing.get("totals", {}).get("storage_required_tib") or 0)
    if target == "ocvs":
        if strategy not in (None, "provider_default", "block_volume"):
            raise ValueError("OCVS BOM storage strategy must be block_volume")
        vpu_per_gb = float(storage_vpu_per_gb)
        if vpu_per_gb < 0:
            raise ValueError("OCI Block Volume performance units cannot be negative")
        return {
            "strategy": "block_volume",
            "capacity_tib": required_tib,
            "vpu_per_gb": vpu_per_gb,
            "capacity_validated": True,
            "note": "External OCI Block Volume capacity; validate performance units and resilience design.",
        }
    if target == "avs":
        if strategy in (None, "provider_default", "integrated_vsan"):
            return {
                "strategy": "integrated_vsan",
                "capacity_tib": required_tib,
                "capacity_validated": False,
                "note": "Included host-local vSAN; usable capacity depends on host type and storage policy.",
            }
        if strategy != "elastic_san":
            raise ValueError("AVS BOM storage strategy must be integrated_vsan or elastic_san")
        redundancy = str(redundancy or "LRS").upper()
        if redundancy not in {"LRS", "ZRS"}:
            raise ValueError("Elastic SAN redundancy must be LRS or ZRS")
        if elastic_san_base_tib is None:
            raise ValueError("Elastic SAN pricing requires an explicit base capacity in TiB")
        base_tib = float(elastic_san_base_tib)
        if base_tib < 0 or base_tib > required_tib:
            raise ValueError("Elastic SAN base capacity must be between zero and required storage")
        return {
            "strategy": "elastic_san",
            "redundancy": redundancy,
            "base_tib": base_tib,
            "capacity_tib": required_tib - base_tib,
            "total_tib": required_tib,
            "capacity_validated": True,
            "note": "External Azure Elastic SAN; validate throughput and IOPS before purchase.",
        }
    if target == "gcve":
        if strategy not in (None, "provider_default", "integrated_vsan"):
            raise ValueError(
                "GCVE storage-only BOM quantities must be supplied by a validated storage design"
            )
        return {
            "strategy": "integrated_vsan",
            "capacity_tib": required_tib,
            "capacity_validated": False,
            "note": "Included HCI-node vSAN; usable capacity depends on node family and storage policy.",
        }
    raise ValueError(f"unknown BOM target: {target}")


def _round(value):
    return round(float(value), 6)


def _licensing(sizing, current_vcf_cores, current_entitlement_verified):
    target = sizing.get("totals", {}).get("vcf_licensable_cores")
    current = None if current_vcf_cores is None else float(current_vcf_cores)
    if target is None:
        additional = surplus = None
    elif current is None:
        additional = surplus = None
    else:
        additional = max(float(target) - current, 0)
        surplus = max(current - float(target), 0)
    return {
        "status": (
            "complete" if target is not None and current is not None else "target_only"
        ),
        "current_vcf_cores": current,
        "target_vcf_cores": target,
        "additional_vcf_cores": additional,
        "surplus_vcf_cores": surplus,
        "current_entitlement_verified": bool(current_entitlement_verified),
        "current_vcf_basis": (
            "verified_entitlement"
            if current_entitlement_verified
            else "hardware_requirement_proxy"
        ),
        "price_source": "Broadcom or reseller quote required",
    }


def _license_lines(licensing):
    current_label = (
        "Current VCF cores (confirmed entitlement)"
        if licensing["current_entitlement_verified"]
        else "Current-estate VCF core requirement"
    )
    current_note = (
        "Customer-confirmed entitlement supplied as a BOM input."
        if licensing["current_entitlement_verified"]
        else "Hardware-derived planning proxy; verify the customer's actual entitlement."
    )
    rows = [
        {
            "category": "VMware licensing",
            "component": current_label,
            "quantity": licensing["current_vcf_cores"],
            "note": current_note,
        },
        {
            "category": "VMware licensing",
            "component": "Target VCF core requirement",
            "quantity": licensing["target_vcf_cores"],
            "note": "Uses full physical silicon cores for every selected target host.",
        },
    ]
    if licensing["additional_vcf_cores"] is not None:
        label = (
            "Additional VCF cores required"
            if licensing["additional_vcf_cores"] > 0
            else "Surplus VCF cores"
        )
        quantity = max(
            licensing["additional_vcf_cores"], licensing["surplus_vcf_cores"]
        )
        rows.append(
            {
                "category": "VMware licensing",
                "component": label,
                "quantity": quantity,
                "note": "Broadcom or reseller quote required; no public cloud price is applied.",
            }
        )
    return rows


def build_bom(
    sizing,
    *,
    adapter=None,
    region=None,
    currency=DEFAULT_CURRENCY,
    pricing_model=DEFAULT_PRICING_MODEL,
    current_vcf_cores=None,
    current_entitlement_verified=False,
    storage_plan=None,
):
    """Build a deterministic BOM and enrich it with optional live list prices."""
    recommendations_complete = bool(sizing.get("clusters")) and all(
        cluster.get("status", "complete") == "complete"
        and cluster.get("recommendation") is not None
        for cluster in sizing.get("clusters", [])
    )
    totals = sizing.get("totals", {})
    if (
        sizing.get("status") != "complete"
        or not recommendations_complete
        or totals.get("total_hosts") is None
        or totals.get("vcf_licensable_cores") is None
    ):
        raise ValueError("a completed sizing result is required before building a BOM")
    target = sizing.get("target", {}).get("id")
    adapter = adapter or adapter_for(target)
    currency = str(currency or DEFAULT_CURRENCY).strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency must be a three-letter ISO code")
    if current_vcf_cores is not None and float(current_vcf_cores) < 0:
        raise ValueError("current VCF cores cannot be negative")
    region = str(region or "").strip() or None
    warnings = []
    quantity_status = "complete"
    if storage_plan and storage_plan.get("capacity_validated") is False:
        quantity_status = "validation_required"
        warnings.append(
            {
                "code": "storage_capacity_validation_required",
                "message": storage_plan.get("note")
                or "Usable storage capacity must be validated before treating this as a complete design BOM.",
            }
        )
    can_price = True
    if getattr(adapter, "region_required", True) and not region:
        can_price = False
        warnings.append(
            {
                "code": "pricing_region_required",
                "message": "A target region is required for live provider pricing; quantities remain available.",
            }
        )

    lines = []
    table_rows = []
    for spec in adapter.component_specs(sizing, storage_plan=storage_plan):
        quote = (
            adapter.quote(spec, region=region, currency=currency, pricing_model=pricing_model)
            if can_price and not spec.get("unpriced_reason")
            else {"status": "unpriced", "reason": spec.get("unpriced_reason") or "pricing_region_required"}
        )
        unit_price = quote.get("unit_price") if quote.get("status") == "priced" else None
        monthly = None
        if unit_price is not None:
            factor = float(quote.get("monthly_factor", adapter.monthly_hours))
            monthly = _round(float(spec["billing_quantity"]) * float(unit_price) * factor)
        line = {
            "category": spec["category"],
            "component": spec["component"],
            "provider_sku": spec.get("sku"),
            "quantity": spec["quantity"],
            "billing_quantity": spec["billing_quantity"],
            "billing_unit": quote.get("unit") or spec.get("billing_unit"),
            "currency": currency,
            "region": region,
            "pricing_model": pricing_model,
            "unit_price": unit_price,
            "estimated_monthly": monthly,
            "pricing_status": quote.get("status", "unpriced"),
            "unpriced_reason": quote.get("reason"),
            "price_effective_at": quote.get("effective_at"),
            "price_source_url": quote.get("source_url"),
            "provider_fields": quote.get("provider_fields", {}),
        }
        lines.append(line)
        if hasattr(adapter, "table_row"):
            table_rows.append(adapter.table_row(spec, line))
        else:
            table_rows.append(dict(line))
        if quote.get("status") != "priced":
            warnings.append(
                {
                    "code": quote.get("reason") or "price_unavailable",
                    "component": spec["component"],
                    "message": "The component quantity is included, but a unique live list price was not available.",
                }
            )

    priced = [line for line in lines if line["estimated_monthly"] is not None]
    all_priced = bool(lines) and len(priced) == len(lines)
    subtotal = _round(sum(line["estimated_monthly"] for line in priced)) if priced else None
    pricing_status = "complete" if all_priced else "partial" if priced else "unpriced"
    status = (
        "complete"
        if pricing_status == "complete" and quantity_status == "complete"
        else "unpriced"
        if pricing_status == "unpriced"
        else "partial"
    )
    licensing = _licensing(
        sizing, current_vcf_cores, current_entitlement_verified
    )
    if licensing["status"] != "complete":
        warnings.append(
            {
                "code": "current_vcf_core_requirement_unavailable",
                "message": "Target VCF cores are shown, but current-estate CPU topology is incomplete, so the delta is unavailable.",
            }
        )
    license_lines = _license_lines(licensing)
    if hasattr(adapter, "license_table_row"):
        license_table_rows = [
            adapter.license_table_row(row, currency=currency) for row in license_lines
        ]
    else:
        license_table_rows = list(license_lines)
    table_columns = (
        adapter.columns_for(currency)
        if hasattr(adapter, "columns_for")
        else list(adapter.columns)
    )
    return {
        "schema_version": "1.0",
        "status": status,
        "pricing_status": pricing_status,
        "quantity_status": quantity_status,
        "provider": target,
        "region": region,
        "currency": currency,
        "pricing_model": pricing_model,
        "monthly_hours": adapter.monthly_hours,
        "storage_plan": storage_plan,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lines": lines,
        "licensing": licensing,
        "license_lines": license_lines,
        "priced_monthly_subtotal": subtotal,
        "priced_monthly_total": (
            subtotal if all_priced and quantity_status == "complete" else None
        ),
        "table": {
            "columns": list(table_columns),
            "rows": table_rows,
            "license_rows": license_table_rows,
        },
        "warnings": warnings,
        "exclusions": [
            "Taxes, negotiated discounts, support plans, network egress, backup, and migration services are excluded unless represented by an explicit line item.",
            "Portable VMware Cloud Foundation subscription pricing requires a Broadcom or reseller quote.",
        ],
    }
