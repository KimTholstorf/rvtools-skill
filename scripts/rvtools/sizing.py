"""Deterministic, provider-neutral capacity sizing for cloud VMware targets."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .targets import PROFILES, target_profile


DEFAULT_POLICY_ID = "recommended"
MIB_PER_GIB = 1024.0
MIB_PER_TIB = 1024.0 * 1024.0


@dataclass(frozen=True)
class CapacityPolicy:
    """User-selectable assumptions, independent of a cloud provider."""

    id: str
    compute_scope: str
    vcpu_per_physical_core: float
    cpu_headroom_percent: float
    memory_headroom_percent: float
    memory_is_binding: bool
    storage_scope: str
    storage_headroom_percent: float
    failure_reserve_hosts: int


POLICIES = {
    "recommended": CapacityPolicy(
        id="recommended",
        compute_scope="all_non_template_vms",
        vcpu_per_physical_core=4.0,
        cpu_headroom_percent=20.0,
        memory_headroom_percent=20.0,
        memory_is_binding=True,
        storage_scope="all_selected_vms_and_templates",
        storage_headroom_percent=25.0,
        failure_reserve_hosts=1,
    ),
    "active_only": CapacityPolicy(
        id="active_only",
        compute_scope="powered_on_non_template_vms",
        vcpu_per_physical_core=4.0,
        cpu_headroom_percent=0.0,
        memory_headroom_percent=0.0,
        memory_is_binding=False,
        storage_scope="all_selected_vms_and_templates",
        storage_headroom_percent=0.0,
        failure_reserve_hosts=1,
    ),
}


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _value(row: Mapping[str, Any], *headers: str, default: Any = None) -> Any:
    """Return the last populated occurrence, including preserved duplicate headers."""
    for header in headers:
        wanted = _key(header)
        matches = []
        for position, (key, value) in enumerate(row.items()):
            normalized = _key(key)
            if normalized == wanted or re.fullmatch(rf"{re.escape(wanted)}\d+", normalized):
                if value not in (None, ""):
                    matches.append((position, value))
        if matches:
            return matches[-1][1]
    return default


def _number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().casefold() in {
        "true",
        "yes",
        "y",
        "1",
        "enabled",
        "connected",
    }


def _is_powered_on(value: Any) -> bool:
    return _key(value) in {"poweredon", "on"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ceil_ratio(numerator: float, denominator: float) -> int:
    if numerator <= 0:
        return 0
    if denominator <= 0:
        raise ValueError("sizing capacity must be greater than zero")
    return int(math.ceil((numerator / denominator) - 1e-12))


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _policy_payload(policy: CapacityPolicy, target_id: str) -> Dict[str, Any]:
    payload = asdict(policy)
    payload["display_name"] = (
        "Oracle default sizing policy"
        if target_id == "ocvs" and policy.id == DEFAULT_POLICY_ID
        else "Recommended sizing policy"
        if policy.id == DEFAULT_POLICY_ID
        else "Active-only sizing policy"
    )
    return payload


def _cluster_evidence(
    rows: Mapping[str, Sequence[Mapping[str, Any]]]
) -> Tuple[Dict[Tuple[str, str], set], Dict[str, set]]:
    evidence_by_identity: Dict[Tuple[str, str], set] = {}
    evidence_by_name: Dict[str, set] = {}
    for sheet in ("vDisk", "vNetwork", "vSnapshot", "vTools", "vCD", "vUSB"):
        for row in rows.get(sheet, []):
            vm = _text(_value(row, "VM"))
            vcenter = _text(_value(row, "VI SDK Server", "vCenter"))
            cluster = _text(_value(row, "Cluster", "Cluster name"))
            if vm and cluster and _key(cluster) not in {"cluster", "unassigned"}:
                evidence_by_name.setdefault(vm, set()).add(cluster)
                if vcenter:
                    evidence_by_identity.setdefault((vm, vcenter), set()).add(cluster)
    return evidence_by_identity, evidence_by_name


def normalize_inventory(
    rows: Mapping[str, Sequence[Mapping[str, Any]]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Normalize VM sizing fields and resolve cluster evidence consistently."""
    related_by_identity, related_by_name = _cluster_evidence(rows)
    records = []
    attribution_issues = []
    for row in rows.get("vInfo", []):
        vm = _text(_value(row, "VM")) or "(unnamed VM)"
        vcenter = _text(_value(row, "VI SDK Server", "vCenter"))
        direct_cluster = _text(_value(row, "Cluster", "Cluster name"))
        candidates = (
            related_by_identity.get((vm, vcenter), set())
            if vcenter and (vm, vcenter) in related_by_identity
            else related_by_name.get(vm, set())
        )
        if direct_cluster and _key(direct_cluster) not in {"cluster", "unassigned"}:
            cluster = direct_cluster
            cluster_evidence = "vInfo"
        elif len(candidates) == 1:
            cluster = next(iter(candidates))
            cluster_evidence = "related_vm_sheet"
        else:
            cluster = "(unassigned)"
            cluster_evidence = "unavailable" if not candidates else "ambiguous"
            attribution_issues.append(
                (
                    "vm_cluster_attribution_unavailable"
                    if not candidates
                    else "vm_cluster_attribution_ambiguous",
                    vm,
                )
            )
        records.append(
            {
                "vm": vm,
                "cluster": cluster,
                "cluster_evidence": cluster_evidence,
                "power_state": _text(_value(row, "Powerstate")),
                "template": _truthy(_value(row, "Template")),
                "vcpus": _number(_value(row, "CPUs", "vCPU")),
                "memory_mib": _number(_value(row, "Memory", "Size MiB")),
                "provisioned_mib": _number(_value(row, "Provisioned MiB")),
                "in_use_mib": _number(_value(row, "In Use MiB")),
            }
        )
    warnings = []
    for code in sorted({issue[0] for issue in attribution_issues}):
        affected = [vm for issue_code, vm in attribution_issues if issue_code == code]
        warnings.append(
            {
                "code": code,
                "count": len(affected),
                "examples": affected[:25],
                "examples_truncated": len(affected) > 25,
                "message": "The affected VMs could not be assigned to exactly one source cluster for sizing.",
            }
        )
    return records, warnings


def _source_cluster_scope(
    rows: Mapping[str, Sequence[Mapping[str, Any]]], records: Sequence[Mapping[str, Any]]
) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
    host_clusters = {
        _text(_value(row, "Cluster", "Cluster name"))
        for row in rows.get("vHost", [])
        if _text(_value(row, "Host"))
        and _text(_value(row, "Cluster", "Cluster name"))
        and _key(_value(row, "Cluster", "Cluster name")) not in {"cluster", "unassigned"}
    }
    declared_positive = set()
    declared_zero = set()
    for row in rows.get("vCluster", []):
        cluster = _text(_value(row, "Name", "Cluster", "Cluster name"))
        if not cluster:
            continue
        host_count = _number(_value(row, "NumHosts", "Num Hosts", "Host count"))
        (declared_positive if host_count > 0 else declared_zero).add(cluster)

    warnings = []
    source_clusters = host_clusters or declared_positive
    if not source_clusters:
        source_clusters = {
            str(record["cluster"])
            for record in records
            if record["cluster"] != "(unassigned)"
        }
        warnings.append(
            {
                "code": "host_backed_cluster_scope_unavailable",
                "message": "No populated vHost or vCluster evidence was available; sizing uses VM cluster attribution.",
            }
        )
    excluded_zero = sorted(declared_zero - host_clusters)
    return sorted(source_clusters), excluded_zero, warnings


def prepare_sizing_input(
    rows: Mapping[str, Sequence[Mapping[str, Any]]]
) -> Dict[str, Any]:
    """Prepare reusable inventory and cluster scope for repeated sizing views."""
    inventory, attribution_warnings = normalize_inventory(rows)
    source_clusters, excluded_zero, scope_warnings = _source_cluster_scope(
        rows, inventory
    )
    return {
        "inventory": inventory,
        "source_clusters": source_clusters,
        "excluded_zero_host_clusters": excluded_zero,
        "warnings": scope_warnings + attribution_warnings,
    }


def _aggregate(records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    selected = list(records)
    return {
        "vm_count": len(selected),
        "vcpus": _round(sum(_number(row.get("vcpus")) for row in selected), 2),
        "memory_gib": _round(
            sum(_number(row.get("memory_mib")) for row in selected) / MIB_PER_GIB,
            2,
        ),
        "provisioned_storage_tib": _round(
            sum(_number(row.get("provisioned_mib")) for row in selected) / MIB_PER_TIB,
            4,
        ),
        "in_use_storage_tib": _round(
            sum(_number(row.get("in_use_mib")) for row in selected) / MIB_PER_TIB,
            4,
        ),
        "largest_vm_vcpus": _round(
            max((_number(row.get("vcpus")) for row in selected), default=0), 2
        ),
        "largest_vm_memory_gib": _round(
            max((_number(row.get("memory_mib")) for row in selected), default=0)
            / MIB_PER_GIB,
            2,
        ),
    }


def _candidate_result(
    node: Mapping[str, Any],
    demand: Mapping[str, Any],
    policy: CapacityPolicy,
    provider_minimum_hosts: int,
    maximum_hosts: int,
) -> Dict[str, Any]:
    cores = _number(node.get("configured_physical_cores"))
    memory_gib = _number(node.get("memory_gib"))
    vcf_cores = _number(node.get("vcf_licensable_cores"))
    ratio = policy.vcpu_per_physical_core
    cpu_normal_capacity = cores * ratio * (1 - policy.cpu_headroom_percent / 100)
    memory_normal_capacity = memory_gib * (1 - policy.memory_headroom_percent / 100)

    normal_cpu_floor = _ceil_ratio(_number(demand["vcpus"]), cpu_normal_capacity)
    normal_memory_floor = (
        _ceil_ratio(_number(demand["memory_gib"]), memory_normal_capacity)
        if policy.memory_is_binding
        else 0
    )
    failure_cpu_floor = (
        _ceil_ratio(_number(demand["vcpus"]), cores * ratio)
        + policy.failure_reserve_hosts
        if _number(demand["vcpus"]) > 0
        else 0
    )
    failure_memory_floor = (
        _ceil_ratio(_number(demand["memory_gib"]), memory_gib)
        + policy.failure_reserve_hosts
        if policy.memory_is_binding and _number(demand["memory_gib"]) > 0
        else 0
    )
    floors = {
        "normal_cpu": normal_cpu_floor,
        "normal_memory": normal_memory_floor,
        "one_host_loss_cpu": failure_cpu_floor,
        "one_host_loss_memory": failure_memory_floor,
        "provider_minimum": provider_minimum_hosts,
    }
    total_hosts = max(floors.values())
    binding_constraints = [name for name, value in floors.items() if value == total_hosts]
    surviving_hosts = max(total_hosts - policy.failure_reserve_hosts, 0)

    def utilization(numerator: float, per_host: float, host_count: int) -> Optional[float]:
        if numerator <= 0:
            return 0.0
        if per_host <= 0 or host_count <= 0:
            return None
        return _round(100 * numerator / (per_host * host_count), 2)

    normal_cpu_percent = utilization(
        _number(demand["vcpus"]), cores * ratio, total_hosts
    )
    failure_cpu_percent = utilization(
        _number(demand["vcpus"]), cores * ratio, surviving_hosts
    )
    normal_memory_percent = utilization(
        _number(demand["memory_gib"]), memory_gib, total_hosts
    )
    failure_memory_percent = utilization(
        _number(demand["memory_gib"]), memory_gib, surviving_hosts
    )
    one_host_loss_validated = (
        total_hosts >= provider_minimum_hosts
        and surviving_hosts > 0
        and (failure_cpu_percent is None or failure_cpu_percent <= 100)
        and (
            not policy.memory_is_binding
            or failure_memory_percent is None
            or failure_memory_percent <= 100
        )
    )
    result = {
        "node_type": node["id"],
        "shape_series": node.get("shape_series") or node["id"],
        "configured_physical_cores_per_host": cores,
        "silicon_cores_per_host": _number(node.get("silicon_cores")),
        "vcf_licensable_cores_per_host": vcf_cores,
        "memory_gib_per_host": memory_gib,
        "provider_minimum_hosts": provider_minimum_hosts,
        "normal_cpu_floor": normal_cpu_floor,
        "normal_memory_floor": normal_memory_floor,
        "failure_cpu_floor": failure_cpu_floor,
        "failure_memory_floor": failure_memory_floor,
        "total_hosts": total_hosts,
        "binding_constraints": binding_constraints,
        "normal_cpu_utilization_percent": normal_cpu_percent,
        "normal_memory_utilization_percent": normal_memory_percent,
        "post_failure_cpu_utilization_percent": failure_cpu_percent,
        "post_failure_memory_utilization_percent": failure_memory_percent,
        "one_host_loss_validated": one_host_loss_validated,
        "largest_vm_cpu_fits_planning_capacity": (
            _number(demand["largest_vm_vcpus"]) <= cores * ratio
        ),
        "largest_vm_memory_fits_one_host": (
            _number(demand["largest_vm_memory_gib"]) <= memory_gib
        ),
        "vcf_licensable_cores": int(total_hosts * vcf_cores),
        "raw_storage_tb": node.get("raw_storage_tb"),
        "raw_storage_tb_total": (
            _round(total_hosts * _number(node.get("raw_storage_tb")), 4)
            if node.get("raw_storage_tb") is not None
            else None
        ),
        "maximum_hosts_exceeded": total_hosts > maximum_hosts,
    }
    result["valid"] = (
        not result["maximum_hosts_exceeded"]
        and result["largest_vm_memory_fits_one_host"]
        and result["one_host_loss_validated"]
    )
    return result


def _pareto_frontier(candidates: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    valid = [dict(candidate) for candidate in candidates if candidate["valid"]]
    frontier = []
    for candidate in valid:
        dominated = any(
            other["total_hosts"] <= candidate["total_hosts"]
            and other["vcf_licensable_cores"] <= candidate["vcf_licensable_cores"]
            and (
                other["total_hosts"] < candidate["total_hosts"]
                or other["vcf_licensable_cores"] < candidate["vcf_licensable_cores"]
            )
            for other in valid
        )
        if not dominated:
            frontier.append(candidate)

    best_by_outcome: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for candidate in frontier:
        key = (candidate["total_hosts"], candidate["vcf_licensable_cores"])
        current = best_by_outcome.get(key)
        if current is None or (
            candidate["configured_physical_cores_per_host"],
            candidate["memory_gib_per_host"],
            candidate["node_type"],
        ) > (
            current["configured_physical_cores_per_host"],
            current["memory_gib_per_host"],
            current["node_type"],
        ):
            best_by_outcome[key] = candidate
    return sorted(
        best_by_outcome.values(),
        key=lambda row: (row["total_hosts"], -row["vcf_licensable_cores"], row["node_type"]),
    )


def _select_candidate(candidates: Sequence[Mapping[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    frontier = _pareto_frontier(candidates)
    if not frontier:
        raise ValueError("no target node satisfies the sizing constraints")
    if len(frontier) <= 2:
        selected = frontier[0]
    else:
        min_hosts = min(row["total_hosts"] for row in frontier)
        max_hosts = max(row["total_hosts"] for row in frontier)
        min_cores = min(row["vcf_licensable_cores"] for row in frontier)
        max_cores = max(row["vcf_licensable_cores"] for row in frontier)

        def knee_score(row: Mapping[str, Any]) -> Tuple[float, int, int, str]:
            host_span = max_hosts - min_hosts
            core_span = max_cores - min_cores
            normalized_hosts = (
                (row["total_hosts"] - min_hosts) / host_span if host_span else 0
            )
            normalized_cores = (
                (row["vcf_licensable_cores"] - min_cores) / core_span
                if core_span
                else 0
            )
            distance_below_tradeoff = 1 - normalized_hosts - normalized_cores
            return (
                distance_below_tradeoff,
                -row["total_hosts"],
                -row["vcf_licensable_cores"],
                row["node_type"],
            )

        selected = max(frontier, key=knee_score)
    alternatives = [row for row in frontier if row["node_type"] != selected["node_type"]]
    return dict(selected), alternatives


def _size_group(
    group: Mapping[str, Any],
    nodes: Sequence[Mapping[str, Any]],
    policy: CapacityPolicy,
    constraints: Mapping[str, Any],
    *,
    role: str,
    explicit_target_node: bool,
) -> Dict[str, Any]:
    provider_minimum = (
        constraints["primary_minimum_hosts"]
        if role == constraints["primary_role"]
        else constraints["workload_minimum_hosts"]
    )
    compute_demand = _aggregate(group["compute_records"])
    storage_demand = _aggregate(group["storage_records"])
    compute_demand["provisioned_storage_tib"] = storage_demand[
        "provisioned_storage_tib"
    ]
    compute_demand["in_use_storage_tib"] = storage_demand["in_use_storage_tib"]
    compute_demand["storage_required_tib"] = _round(
        storage_demand["provisioned_storage_tib"]
        * (1 + policy.storage_headroom_percent / 100),
        4,
    )
    candidates = [
        _candidate_result(
            node,
            compute_demand,
            policy,
            provider_minimum,
            constraints["maximum_hosts_per_cluster"],
        )
        for node in nodes
    ]
    if explicit_target_node:
        selected = candidates[0]
        alternatives = []
        strategy = "user_selected_node"
        status = "complete" if selected["valid"] else "selected_node_invalid"
    else:
        try:
            selected, alternatives = _select_candidate(candidates)
            status = "complete"
        except ValueError:
            selected = None
            alternatives = []
            status = "no_valid_target_node"
        strategy = "pareto_knee_hosts_and_full_silicon_cores"
    if selected is not None:
        selected["selection_strategy"] = strategy
    return {
        "status": status,
        "target_cluster": group["target_cluster"],
        "role": role,
        "source_clusters": list(group["source_clusters"]),
        "demand": compute_demand,
        "recommendation": selected,
        "pareto_alternatives": alternatives,
        "candidate_evaluations": candidates if selected is None else [],
    }


def size_environment(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    target_id: str,
    *,
    policy_id: str = DEFAULT_POLICY_ID,
    topology: str = "consolidated",
    target_node: Optional[str] = None,
    target_cpu_vendor: Optional[str] = None,
    primary_source_cluster: Optional[str] = None,
    prepared: Optional[Mapping[str, Any]] = None,
    target_profile_override: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Size one cloud VMware target from normalized RVTools rows."""
    target_id = str(target_id).strip().casefold()
    policy_id = str(policy_id).strip().casefold()
    topology = str(topology).strip().casefold()
    if policy_id not in POLICIES:
        raise ValueError(f"unknown sizing policy: {policy_id}")
    if topology not in {"consolidated", "source_aligned"}:
        raise ValueError(f"unknown sizing topology: {topology}")
    policy = POLICIES[policy_id]
    if target_profile_override is None and target_id not in PROFILES:
        raise ValueError(f"unknown sizing target: {target_id}")
    if topology == "source_aligned":
        cluster_vcenters: Dict[str, set] = {}
        for host in rows.get("vHost", []):
            cluster = _text(_value(host, "Cluster", "Cluster name"))
            vcenter = _text(_value(host, "VI SDK Server", "vCenter"))
            if cluster and vcenter:
                cluster_vcenters.setdefault(cluster, set()).add(vcenter)
        ambiguous_clusters = sorted(
            cluster for cluster, vcenters in cluster_vcenters.items() if len(vcenters) > 1
        )
        if ambiguous_clusters:
            raise ValueError(
                "same-named source clusters span multiple vCenters and require a disambiguated scope: "
                + ", ".join(ambiguous_clusters)
            )
    profile = (
        dict(target_profile_override)
        if target_profile_override is not None
        else target_profile(
            target_id,
            target_node=target_node,
            target_cpu_vendor=target_cpu_vendor,
        )
    )
    if str(profile.get("id", "")).casefold() != target_id:
        raise ValueError("target profile id does not match the requested sizing target")
    for required in ("name", "catalog_reviewed", "nodes", "sizing_constraints"):
        if required not in profile:
            raise ValueError(f"target profile is missing required field: {required}")
    constraints = profile["sizing_constraints"]
    for required in (
        "primary_role",
        "workload_role",
        "primary_minimum_hosts",
        "workload_minimum_hosts",
        "maximum_hosts_per_cluster",
    ):
        if required not in constraints:
            raise ValueError(
                f"target profile sizing constraints are missing required field: {required}"
            )
    for index, node in enumerate(profile["nodes"]):
        for required in (
            "id",
            "configured_physical_cores",
            "silicon_cores",
            "vcf_licensable_cores",
            "memory_gib",
        ):
            if required not in node:
                raise ValueError(
                    f"target profile node {index} is missing required field: {required}"
                )
    nodes = [
        node
        for node in profile["nodes"]
        if not node.get("storage_only")
        and _number(node.get("configured_physical_cores")) > 0
        and _number(node.get("memory_gib")) > 0
        and (not target_cpu_vendor or node.get("cpu_vendor") == target_cpu_vendor)
        and (not target_node or node["id"].casefold() == target_node.casefold())
    ]
    if not nodes:
        raise ValueError("no target nodes match the selected sizing inputs")

    prepared_input = dict(prepared) if prepared is not None else prepare_sizing_input(rows)
    inventory = list(prepared_input["inventory"])
    source_clusters = list(prepared_input["source_clusters"])
    excluded_zero = list(prepared_input["excluded_zero_host_clusters"])
    scoped_inventory = [row for row in inventory if row["cluster"] in source_clusters]
    excluded_inventory = [row for row in inventory if row["cluster"] not in source_clusters]
    workloads = [row for row in scoped_inventory if not row["template"]]
    templates = [row for row in scoped_inventory if row["template"]]
    compute_records = (
        workloads
        if policy.compute_scope == "all_non_template_vms"
        else [row for row in workloads if _is_powered_on(row["power_state"])]
    )
    storage_records = scoped_inventory

    if not source_clusters:
        raise ValueError("no source cluster evidence is available for sizing")
    if primary_source_cluster and primary_source_cluster not in source_clusters:
        raise ValueError(
            f"primary source cluster '{primary_source_cluster}' is not in the sizing scope"
        )

    if topology == "consolidated":
        groups = [
            {
                "target_cluster": "Consolidated",
                "source_clusters": source_clusters,
                "compute_records": compute_records,
                "storage_records": storage_records,
            }
        ]
        primary_target = "Consolidated"
    else:
        groups = []
        for cluster in source_clusters:
            groups.append(
                {
                    "target_cluster": cluster,
                    "source_clusters": [cluster],
                    "compute_records": [
                        row for row in compute_records if row["cluster"] == cluster
                    ],
                    "storage_records": [
                        row for row in storage_records if row["cluster"] == cluster
                    ],
                }
            )
        if primary_source_cluster:
            primary_target = primary_source_cluster
        else:
            primary_target = max(
                groups,
                key=lambda group: (
                    sum(_number(row["memory_mib"]) for row in group["compute_records"]),
                    sum(_number(row["vcpus"]) for row in group["compute_records"]),
                    len(group["compute_records"]),
                    group["target_cluster"],
                ),
            )["target_cluster"]

    cluster_results = []
    for group in groups:
        role = (
            constraints["primary_role"]
            if group["target_cluster"] == primary_target
            else constraints["workload_role"]
        )
        cluster_results.append(
            _size_group(
                group,
                nodes,
                policy,
                constraints,
                role=role,
                explicit_target_node=bool(target_node),
            )
        )

    warnings = list(prepared_input["warnings"])
    if excluded_inventory:
        warnings.append(
            {
                "code": "inventory_outside_host_backed_cluster_scope",
                "count": len(excluded_inventory),
                "message": "Inventory that could not be tied to a populated source cluster was excluded from sizing.",
            }
        )
    if not target_node:
        warnings.append(
            {
                "code": "automatic_node_selection_requires_commercial_validation",
                "message": "Automatic selection balances host count and full-silicon VCF cores; validate regional availability, price, performance, and contractual terms before purchase.",
            }
        )
    for cluster in cluster_results:
        if cluster["status"] == "no_valid_target_node":
            warnings.append(
                {
                    "code": "no_valid_target_node",
                    "message": f"No catalog node satisfies every sizing constraint for target cluster {cluster['target_cluster']}.",
                }
            )
        elif cluster["status"] == "selected_node_invalid":
            warnings.append(
                {
                    "code": "selected_target_node_invalid",
                    "message": f"The selected node does not satisfy every sizing constraint for target cluster {cluster['target_cluster']}.",
                }
            )
    warnings.append(
        {
            "code": "configuration_only_sizing",
            "message": "RVTools configuration is a planning baseline; validate sustained CPU, memory, storage, and network demand before purchase.",
        }
    )

    totals = {
        "source_clusters": len(source_clusters),
        "target_clusters": len(cluster_results),
        "workload_vms": len(workloads),
        "compute_vms": len(compute_records),
        "powered_on_workload_vms": sum(
            _is_powered_on(row["power_state"]) for row in workloads
        ),
        "powered_off_or_other_workload_vms": sum(
            not _is_powered_on(row["power_state"]) for row in workloads
        ),
        "templates": len(templates),
        "configured_vcpus": _round(sum(row["vcpus"] for row in compute_records), 2),
        "configured_memory_gib": _round(
            sum(row["memory_mib"] for row in compute_records) / MIB_PER_GIB, 2
        ),
        "provisioned_storage_tib": _round(
            sum(row["provisioned_mib"] for row in storage_records) / MIB_PER_TIB, 4
        ),
        "in_use_storage_tib": _round(
            sum(row["in_use_mib"] for row in storage_records) / MIB_PER_TIB, 4
        ),
        "storage_required_tib": _round(
            sum(row["demand"]["storage_required_tib"] for row in cluster_results), 4
        ),
        "total_hosts": (
            sum(row["recommendation"]["total_hosts"] for row in cluster_results)
            if all(row["recommendation"] is not None for row in cluster_results)
            else None
        ),
        "vcf_licensable_cores": (
            sum(
                row["recommendation"]["vcf_licensable_cores"]
                for row in cluster_results
            )
            if all(row["recommendation"] is not None for row in cluster_results)
            else None
        ),
    }
    return {
        "status": (
            "complete"
            if all(row["status"] == "complete" for row in cluster_results)
            else "attention_required"
        ),
        "engine_version": "1.0",
        "target": {
            "id": target_id,
            "name": profile["name"],
            "catalog_reviewed": profile["catalog_reviewed"],
        },
        "policy": _policy_payload(policy, target_id),
        "topology": {
            "id": topology,
            "source_clusters": source_clusters,
            "target_clusters": [row["target_cluster"] for row in cluster_results],
            "primary_target_cluster": primary_target,
            "excluded_zero_host_clusters": excluded_zero,
        },
        "clusters": cluster_results,
        "totals": totals,
        "warnings": warnings,
    }
