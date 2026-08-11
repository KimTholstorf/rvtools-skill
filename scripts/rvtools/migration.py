"""Provider-neutral, per-VM and per-method migration assessment."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from .targets import PROFILES, target_profile


TARGET_IDS = tuple(PROFILES)
METHODS = ("hcx_vmotion", "rav", "bulk", "cold")
STATUS_RANK = {"eligible": 0, "unknown": 1, "conditional": 2, "blocked": 3}


REASONS = {
    "suspended_vm": {
        "category": "power_state",
        "summary": "The VM is suspended and must be resumed or deliberately powered off before migration.",
    },
    "legacy_hardware_below_9": {
        "category": "compatibility",
        "summary": "RAV requires virtual hardware version 9 or later.",
    },
    "hardware_version_unknown": {
        "category": "compatibility",
        "summary": "The virtual hardware version is missing, so HCX method compatibility cannot be concluded.",
    },
    "fault_tolerance": {
        "category": "availability",
        "summary": "Fault Tolerance must be removed under an approved availability plan before HCX migration.",
    },
    "physical_rdm": {
        "category": "storage",
        "summary": "Physical-mode RDM cannot be replicated to the cloud target and needs conversion or manual reattachment.",
    },
    "virtual_rdm": {
        "category": "storage",
        "summary": "Virtual-mode RDM needs method validation and normally converts to VMDK at the destination.",
    },
    "rdm_mode_unknown": {
        "category": "storage",
        "summary": "RDM compatibility mode is missing, so the migration method cannot be concluded safely.",
    },
    "independent_disk": {
        "category": "storage",
        "summary": "Independent disks are incompatible with replication-based migration until reconfigured.",
    },
    "shared_disk": {
        "category": "storage",
        "summary": "Shared or multi-writer storage prevents live and replication-based migration; plan coordinated downtime.",
    },
    "connected_usb": {
        "category": "device",
        "summary": "A connected USB device must be disconnected or replaced before migration.",
    },
    "connected_cdrom": {
        "category": "device",
        "summary": "Connected virtual media can fail live migration and should be disconnected before validation.",
    },
    "tools_not_running": {
        "category": "guest",
        "summary": "VMware Tools is not running or installed; Bulk Migration requires remediation.",
    },
    "consolidation_needed": {
        "category": "storage",
        "summary": "Disk consolidation debt should be cleared before replication begins.",
    },
    "snapshot_present": {
        "category": "storage",
        "summary": "Existing snapshots require review before a replication-based migration wave.",
    },
    "cross_vendor_cpu": {
        "category": "cpu",
        "summary": "Source and target CPU vendors differ, preventing preservation of live CPU state.",
    },
    "source_cpu_vendor_unknown": {
        "category": "cpu",
        "summary": "The source CPU vendor is unavailable, so live CPU-state compatibility cannot be concluded.",
    },
    "avs_ipv6": {
        "category": "network",
        "summary": "AVS does not currently provide end-to-end IPv6 support; the workload needs an IPv4/remediation design.",
    },
    "standard_vswitch_network": {
        "category": "network",
        "summary": "The VM uses a standard vSwitch; migration mapping remains possible, but HCX Network Extension requires vDS or NSX.",
    },
}


def _value(row, *headers, default=None):
    for header in headers:
        normalized = re.sub(r"[^a-z0-9]+", "", str(header).casefold())
        for candidate in (header, normalized):
            if candidate in row and row[candidate] not in (None, ""):
                return row[candidate]
    return default


def _truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().casefold() in {"true", "yes", "y", "1", "on", "enabled"}


def _vm(row):
    return str(_value(row, "VM", default="(unnamed VM)"))


def _hardware_version(value):
    match = re.search(r"(\d+)", str(value or ""))
    return int(match.group(1)) if match else None


def _cpu_vendor(value):
    text = str(value or "").casefold()
    if "intel" in text:
        return "Intel"
    if "amd" in text or "epyc" in text:
        return "AMD"
    return "Unknown"


def _merge_status(current, incoming):
    return incoming if STATUS_RANK[incoming] > STATUS_RANK[current] else current


def assess_migration(
    rows,
    target_id,
    *,
    target_node=None,
    target_region=None,
    target_cpu_vendor=None,
):
    """Assess RVTools rows against one target without claiming HCX validation."""
    target = target_profile(
        target_id,
        target_node=target_node,
        target_cpu_vendor=target_cpu_vendor,
    )
    target["region"] = target_region
    workloads = [row for row in rows.get("vInfo", []) if not _truthy(_value(row, "Template"))]
    templates_excluded = sum(_truthy(_value(row, "Template")) for row in rows.get("vInfo", []))
    host_rows = {str(_value(row, "Host", default="")): row for row in rows.get("vHost", [])}
    vm_context = []
    context_by_row = {}
    contexts_by_vm = defaultdict(list)
    ambiguous_related_rows = set()
    for row in workloads:
        context = {
            "vm": _vm(row),
            "cluster": str(_value(row, "Cluster", default="(unassigned)")),
            "host": str(_value(row, "Host", default="")),
            "vcenter": str(_value(row, "VI SDK Server", default="")),
            "methods": {
                method: {"status": "eligible", "reason_ids": []}
                for method in METHODS
            },
        }
        vm_context.append(context)
        context_by_row[id(row)] = context
        contexts_by_vm[context["vm"]].append(context)
    findings = []

    def apply_context(context, reason_id, method_statuses, *, finding_status=None):
        affected_methods = []
        for method, incoming in method_statuses.items():
            method_result = context["methods"][method]
            method_result["status"] = _merge_status(method_result["status"], incoming)
            if reason_id not in method_result["reason_ids"]:
                method_result["reason_ids"].append(reason_id)
            affected_methods.append(method)
        findings.append(
            {
                "target": target["id"],
                "finding_id": reason_id,
                "category": REASONS[reason_id]["category"],
                "vm": context["vm"],
                "cluster": context["cluster"],
                "host": context["host"],
                "vcenter": context["vcenter"],
                "status": finding_status
                or max(method_statuses.values(), key=lambda item: STATUS_RANK[item]),
                "methods": affected_methods,
                "summary": REASONS[reason_id]["summary"],
            }
        )

    def contexts_for_row(row):
        candidates = contexts_by_vm.get(_vm(row), [])
        if len(candidates) <= 1:
            return candidates
        vcenter = str(_value(row, "VI SDK Server", default=""))
        if vcenter:
            matches = [item for item in candidates if item["vcenter"] == vcenter]
            if matches:
                return matches
        host = str(_value(row, "Host", default=""))
        if host:
            matches = [item for item in candidates if item["host"] == host]
            if matches:
                return matches
        ambiguous_related_rows.add(id(row))
        return candidates

    def apply_row(row, reason_id, method_statuses, *, finding_status=None):
        for context in contexts_for_row(row):
            apply_context(
                context,
                reason_id,
                method_statuses,
                finding_status=finding_status,
            )

    for row in workloads:
        context = context_by_row[id(row)]
        power = str(_value(row, "Powerstate", default="")).casefold()
        if "suspend" in power:
            apply_context(
                context,
                "suspended_vm",
                {"hcx_vmotion": "blocked", "rav": "blocked", "bulk": "blocked", "cold": "conditional"},
            )
        hardware = _hardware_version(_value(row, "HW version"))
        if hardware is not None and hardware < 9:
            apply_context(
                context,
                "legacy_hardware_below_9",
                {"rav": "blocked"},
            )
        elif hardware is None:
            apply_context(context, "hardware_version_unknown", {"rav": "unknown"})
        ft_state = str(_value(row, "FT State", default="")).strip().casefold()
        if ft_state not in {"", "notconfigured", "not configured", "disabled", "off"}:
            apply_context(
                context,
                "fault_tolerance",
                {"hcx_vmotion": "blocked", "rav": "blocked", "bulk": "blocked", "cold": "conditional"},
            )
        if _truthy(_value(row, "Consolidation Needed")):
            apply_context(context, "consolidation_needed", {"rav": "conditional", "bulk": "conditional"})

        host_row = host_rows.get(context["host"], {})
        source_cpu_vendor = _cpu_vendor(_value(host_row, "CPU Model"))
        if target["cpu_vendor"]:
            if source_cpu_vendor == "Unknown":
                apply_context(
                    context,
                    "source_cpu_vendor_unknown",
                    {"hcx_vmotion": "unknown", "rav": "unknown"},
                )
            elif source_cpu_vendor != target["cpu_vendor"]:
                apply_context(
                    context,
                    "cross_vendor_cpu",
                    {"hcx_vmotion": "blocked", "rav": "blocked", "bulk": "conditional", "cold": "conditional"},
                )
    for row in rows.get("vDisk", []):
        if _truthy(_value(row, "Template")):
            continue
        raw_mode = str(_value(row, "Raw Comp. Mode", "Raw Com. Mode", default="")).casefold()
        if _truthy(_value(row, "Raw")) or raw_mode:
            if "physical" in raw_mode:
                apply_row(
                    row,
                    "physical_rdm",
                    {"hcx_vmotion": "blocked", "rav": "blocked", "bulk": "blocked", "cold": "conditional"},
                )
            elif "virtual" in raw_mode:
                apply_row(row, "virtual_rdm", {method: "conditional" for method in METHODS})
            else:
                apply_row(row, "rdm_mode_unknown", {method: "unknown" for method in METHODS})
        if "independent" in str(_value(row, "Disk Mode", default="")).casefold():
            apply_row(
                row,
                "independent_disk",
                {"hcx_vmotion": "blocked", "rav": "blocked", "bulk": "blocked", "cold": "conditional"},
            )
        sharing = " ".join(
            str(_value(row, header, default=""))
            for header in ("Sharing mode", "Shared Bus")
        ).strip().casefold()
        if sharing and not all(token in {"", "none", "nosharing", "sharingnone", "false"} for token in sharing.split()):
            apply_row(
                row,
                "shared_disk",
                {"hcx_vmotion": "blocked", "rav": "blocked", "bulk": "blocked", "cold": "conditional"},
            )

    for sheet, reason_id in (("vUSB", "connected_usb"), ("vCD", "connected_cdrom")):
        for row in rows.get(sheet, []):
            if not _truthy(_value(row, "Template")) and _truthy(_value(row, "Connected")):
                apply_row(
                    row,
                    reason_id,
                    {"hcx_vmotion": "blocked", "rav": "blocked", "bulk": "conditional", "cold": "conditional"},
                )

    for row in rows.get("vTools", []):
        status = str(_value(row, "Tools", default="")).casefold()
        if (
            not _truthy(_value(row, "Template"))
            and str(_value(row, "Powerstate", default="")).casefold() == "poweredon"
            and any(token in status for token in ("notrunning", "not running", "notinstalled", "not installed"))
        ):
            apply_row(row, "tools_not_running", {"hcx_vmotion": "conditional", "rav": "conditional", "bulk": "blocked"})

    snapshot_contexts = {}
    for row in rows.get("vSnapshot", []):
        if not _truthy(_value(row, "Template")):
            for context in contexts_for_row(row):
                snapshot_contexts[id(context)] = context
    for context in snapshot_contexts.values():
        apply_context(context, "snapshot_present", {"rav": "conditional", "bulk": "conditional"})

    for row in rows.get("vNetwork", []):
        if _truthy(_value(row, "Template")):
            continue
        if str(_value(row, "Switch", default="")).casefold().startswith("vswitch"):
            apply_row(row, "standard_vswitch_network", {}, finding_status="conditional")
        if target["id"] == "avs" and str(_value(row, "IPv6 Address", default="")).strip():
            apply_row(row, "avs_ipv6", {method: "conditional" for method in METHODS})

    vm_methods = sorted(
        vm_context,
        key=lambda item: (item["vm"].casefold(), item["vcenter"].casefold(), item["host"].casefold()),
    )
    summary = {
        method: dict(Counter(row["methods"][method]["status"] for row in vm_methods))
        for method in METHODS
    }
    finding_summary = [
        {"finding_id": finding_id, "count": count}
        for finding_id, count in sorted(Counter(item["finding_id"] for item in findings).items())
    ]
    manual_gates = list(target["manual_gates"])
    if ambiguous_related_rows:
        manual_gates.append(
            {
                "id": "vm_identity_disambiguation",
                "evidence": "Resolve duplicate VM names for related-sheet rows that lack a matching vCenter or host identifier.",
            }
        )
    return {
        "assessment_schema_version": "1.0",
        "target": {key: value for key, value in target.items() if key not in {"manual_gates", "sources"}},
        "scope": {
            "workload_vms": len(workloads),
            "templates_excluded": templates_excluded,
            "duplicate_vm_names": sum(count > 1 for count in Counter(_vm(row) for row in workloads).values()),
            "ambiguous_related_rows": len(ambiguous_related_rows),
            "identity_basis": "vm_name_plus_vcenter_or_host_when_available",
            "status_basis": "rvtools_screening_not_hcx_validation",
        },
        "method_summary": summary,
        "finding_summary": finding_summary,
        "vm_methods": vm_methods,
        "findings": findings,
        "manual_gates": manual_gates,
        "sources": target["sources"],
    }
