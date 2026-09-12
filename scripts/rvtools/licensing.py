"""Deterministic VMware Cloud Foundation core calculations."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping, Optional, Sequence


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _value(row: Mapping[str, Any], *headers: str) -> Any:
    for header in headers:
        wanted = _key(header)
        matches = [
            value
            for key, value in row.items()
            if (key == wanted or re.fullmatch(rf"{re.escape(wanted)}\d+", str(key)))
            and value not in (None, "")
        ]
        if matches:
            return matches[-1]
    return None


def _number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def host_core_requirement(
    row: Mapping[str, Any],
    *,
    value_getter: Optional[Callable[..., Any]] = None,
) -> dict:
    """Return full-silicon VCF cores with the 16-core-per-socket minimum."""
    get = value_getter or _value
    sockets = _number(get(row, "# CPU"))
    cores_per_cpu = _number(get(row, "Cores per CPU"))
    physical_cores = _number(get(row, "# Cores", "Cores"))
    if sockets <= 0:
        licensable = None
    elif physical_cores > 0:
        licensable = max(physical_cores, sockets * 16)
    elif cores_per_cpu > 0:
        physical_cores = sockets * cores_per_cpu
        licensable = sockets * max(cores_per_cpu, 16)
    else:
        licensable = None
    return {
        "cpu_sockets": sockets,
        "cores_per_cpu": cores_per_cpu,
        "physical_silicon_cores": physical_cores,
        "vcf_licensable_cores": licensable,
        "minimum_core_adjustment": (
            None if licensable is None else licensable - physical_cores
        ),
        "basis": "full_physical_silicon_with_16_core_per_cpu_minimum",
    }


def summarize_vcf_hosts(
    rows: Sequence[Mapping[str, Any]],
    *,
    value_getter: Optional[Callable[..., Any]] = None,
) -> dict:
    """Summarize the current estate's hardware-based VCF requirement."""
    hosts = [host_core_requirement(row, value_getter=value_getter) for row in rows]
    complete = bool(hosts) and all(
        host["vcf_licensable_cores"] is not None for host in hosts
    )
    return {
        "host_count": len(hosts),
        "calculation_complete": complete,
        "physical_silicon_cores": sum(
            host["physical_silicon_cores"] for host in hosts
        ),
        "vcf_licensable_cores": (
            sum(host["vcf_licensable_cores"] for host in hosts)
            if complete
            else None
        ),
        "basis": "full_physical_silicon_with_16_core_per_cpu_minimum",
        "entitlement_verified": False,
        "hosts": hosts,
    }
