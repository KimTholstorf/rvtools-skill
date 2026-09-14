"""Versioned migration target profiles and planning catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


CATALOG_REVIEWED = "2026-09-11"


@dataclass(frozen=True)
class TargetProfile:
    """Provider-specific facts layered over shared HCX compatibility rules."""

    id: str
    name: str
    cpu_vendor: Optional[str]
    nodes: Tuple[Dict[str, Any], ...]
    sizing_constraints: Dict[str, Any]
    manual_gates: Tuple[Dict[str, str], ...]
    sources: Tuple[Dict[str, str], ...]


def _node(
    node_id,
    physical_cores,
    logical_threads,
    memory_gib,
    storage_tb,
    architecture,
    *,
    storage_only=False,
    availability="selected_regions",
    storage_by_architecture=None,
    cpu_model=None,
    cpu_vendor=None,
    shape_series=None,
    silicon_cores=None,
):
    silicon_cores = physical_cores if silicon_cores is None else silicon_cores
    return {
        "id": node_id,
        "shape_series": shape_series or node_id,
        "physical_cores": physical_cores,
        "configured_physical_cores": physical_cores,
        "silicon_cores": silicon_cores,
        "vcf_licensable_cores": silicon_cores,
        "vcf_license_core_basis": "full_physical_silicon",
        "logical_threads": logical_threads,
        "cpu_vendor": cpu_vendor,
        "cpu_model": cpu_model,
        "memory_gib": memory_gib,
        "raw_storage_tb": storage_tb,
        "vsan_architecture": architecture,
        "storage_only": storage_only,
        "availability": availability,
        "catalog_reviewed": CATALOG_REVIEWED,
        "raw_storage_tb_osa": (storage_by_architecture or {}).get("OSA"),
        "raw_storage_tb_esa": (storage_by_architecture or {}).get("ESA"),
    }


AVS_NODES = (
    _node("AV36", 36, 72, 576, 15.2, "OSA", cpu_model="Intel Xeon Gold 6140", cpu_vendor="Intel"),
    _node("AV36P", 36, 72, 768, 19.2, "OSA", cpu_model="Intel Xeon Gold 6240", cpu_vendor="Intel"),
    _node("AV48", 48, 96, 1024, 25.6, "ESA", cpu_model="Intel Xeon Gold 6442Y", cpu_vendor="Intel"),
    _node("AV52", 52, 104, 1536, 38.4, "OSA", cpu_model="Intel Xeon Platinum 8270", cpu_vendor="Intel"),
    _node(
        "AV64",
        64,
        128,
        1024,
        None,
        "OSA_or_ESA",
        storage_by_architecture={"OSA": 15.36, "ESA": 19.25},
        cpu_model="Intel Xeon Platinum 8370C",
        cpu_vendor="Intel",
    ),
)


def _ocvs_nodes():
    nodes = []
    shapes = (
        ("BM.Standard2.52", "Intel", 52, (12, 26, 38, 52), 768),
        ("BM.Standard3.64", "Intel", 64, (16, 32, 48, 64), 1024),
        ("BM.Standard.E4.128", "AMD", 128, (32, 64, 96, 128), 2048),
        ("BM.Standard.E5.192", "AMD", 192, (48, 96, 144, 192), 2304),
        ("BM.Optimized3.36", "Intel", 36, (18, 26), 512),
    )
    for shape, vendor, silicon_cores, configurations, memory_gib in shapes:
        for configured_cores in configurations:
            nodes.append(
                _node(
                    f"{shape}-{configured_cores}",
                    configured_cores,
                    configured_cores * 2,
                    memory_gib,
                    None,
                    "external_block",
                    cpu_vendor=vendor,
                    shape_series=shape,
                    silicon_cores=silicon_cores,
                )
            )
    return tuple(nodes)


def _gcve_nodes():
    nodes = [_node("ve1-standard-72", 36, 72, 768, 19.2, "OSA", cpu_vendor="Intel")]
    for family, storage in (
        ("mega", 51.2),
        ("large", 38.4),
        ("standard", 25.5),
        ("small", 12.8),
    ):
        for logical_threads in (64, 80, 96, 112, 128):
            nodes.append(
                _node(
                    f"ve2-{family}-{logical_threads}",
                    logical_threads // 2,
                    logical_threads,
                    2048,
                    storage,
                    "vSAN",
                    cpu_vendor="Intel",
                    silicon_cores=64,
                )
            )
    nodes.append(
        _node(
            "ve1-standard-so",
            0,
            0,
            0,
            19.2,
            "OSA",
            storage_only=True,
            cpu_vendor="Intel",
            silicon_cores=36,
        )
    )
    for family, storage in (
        ("mega", 51.2),
        ("large", 38.4),
        ("standard", 25.5),
        ("small", 12.8),
    ):
        nodes.append(
            _node(
                f"ve2-{family}-so",
                0,
                0,
                0,
                storage,
                "vSAN",
                storage_only=True,
                cpu_vendor="Intel",
                silicon_cores=64,
            )
        )
    return tuple(nodes)


COMMON_GATES = (
    {
        "id": "hcx_interoperability",
        "evidence": "Source vCenter, ESXi and HCX versions plus the current Broadcom interoperability result.",
    },
    {
        "id": "bandwidth_latency_churn",
        "evidence": "Measured bandwidth, latency, packet loss and workload data-change rate for each wave.",
    },
    {
        "id": "dns_ntp_firewall",
        "evidence": "Bidirectional DNS, synchronized time, routing and required HCX firewall ports.",
    },
    {
        "id": "cidr_overlap",
        "evidence": "Source, target, management, workload and connected-network CIDRs checked for overlap.",
    },
    {
        "id": "hcx_validate",
        "evidence": "Successful HCX Validate for every migration group immediately before execution.",
    },
    {
        "id": "performance_sizing",
        "evidence": "Validate the selected planning assumptions, operating headroom, continued operation with one host unavailable, largest-VM fit, and storage design against sustained CPU, memory, storage, and network history.",
    },
)


PROFILES = {
    "ocvs": TargetProfile(
        id="ocvs",
        name="Oracle Cloud VMware Solution",
        cpu_vendor=None,
        nodes=_ocvs_nodes(),
        sizing_constraints={
            "primary_role": "unified_management",
            "workload_role": "workload",
            "primary_minimum_hosts": 3,
            "workload_minimum_hosts": 2,
            "maximum_hosts_per_cluster": 32,
        },
        manual_gates=COMMON_GATES
        + (
            {
                "id": "target_cpu_vendor",
                "evidence": "Selected OCVS Intel or AMD target shape and source EVC compatibility.",
            },
            {
                "id": "ocvs_shape_region",
                "evidence": "Current OCVS shape availability and capacity in the selected OCI region.",
            },
        ),
        sources=(
            {
                "title": "Oracle Cloud VMware Solution overview",
                "url": "https://docs.oracle.com/en-us/iaas/Content/VMware/Concepts/ocvsoverview.htm",
            },
            {
                "title": "Configure OCVS HCX components",
                "url": "https://docs.oracle.com/en/solutions/migrate-vmware-workloads-oraclecloud/configure-oracle-cloud-vmware-solution-hcx-components.html",
            },
        ),
    ),
    "avs": TargetProfile(
        id="avs",
        name="Azure VMware Solution",
        cpu_vendor="Intel",
        nodes=AVS_NODES,
        sizing_constraints={
            "primary_role": "primary",
            "workload_role": "workload",
            "primary_minimum_hosts": 3,
            "workload_minimum_hosts": 3,
            "maximum_hosts_per_cluster": 16,
        },
        manual_gates=COMMON_GATES
        + (
            {
                "id": "avs_generation_region_quota",
                "evidence": "AVS Gen 1 or Gen 2, target region, host SKU availability and allocated quota.",
            },
            {
                "id": "avs_evc_generation",
                "evidence": "Exact source CPU generation, EVC mode, AVS host type, and any heterogeneous-cluster constraint.",
            },
            {
                "id": "avs_network_extension",
                "evidence": "vDS-backed extension scope, MON routing, gateway cutover and Gen 2 route-scale design.",
            },
            {
                "id": "avs_storage_policy",
                "evidence": "Selected vSAN FTT/RAID or external ANF/Elastic SAN design and operational slack.",
            },
            {
                "id": "portable_vcf",
                "evidence": "Portable VCF cores and expiry cover every target AVS host that requires BYOL.",
            },
        ),
        sources=(
            {
                "title": "Plan Azure VMware Solution deployment",
                "url": "https://learn.microsoft.com/en-us/azure/azure-vmware/introduction",
            },
            {
                "title": "Configure VMware HCX in Azure VMware Solution",
                "url": "https://learn.microsoft.com/en-us/azure/azure-vmware/configure-vmware-hcx",
            },
            {
                "title": "Azure VMware Solution assessment calculations",
                "url": "https://learn.microsoft.com/en-us/azure/migrate/concepts-azure-vmware-solution-assessment-calculation",
            },
            {
                "title": "Portable VCF on Azure VMware Solution",
                "url": "https://learn.microsoft.com/en-us/azure/azure-vmware/vmware-cloud-foundations-license-portability",
            },
        ),
    ),
    "gcve": TargetProfile(
        id="gcve",
        name="Google Cloud VMware Engine",
        cpu_vendor="Intel",
        nodes=_gcve_nodes(),
        sizing_constraints={
            "primary_role": "primary",
            "workload_role": "workload",
            "primary_minimum_hosts": 3,
            "workload_minimum_hosts": 3,
            "maximum_hosts_per_cluster": 32,
        },
        manual_gates=COMMON_GATES
        + (
            {
                "id": "gcve_region_capacity",
                "evidence": "Target region, zone, node-family availability, project quota and capacity allocation.",
            },
            {
                "id": "gcve_cluster_node_family",
                "evidence": "Each cluster uses one compute node type, with storage-only nodes from the same family where selected.",
            },
            {
                "id": "gcve_ip_plan",
                "evidence": "Management CIDR/IP Plan supports the required remote sites and Network Extension appliance scale.",
            },
            {
                "id": "gcve_storage_strategy",
                "evidence": "Selected HCI, storage-only and external NFS datastore mix with storage-policy overhead.",
            },
            {
                "id": "gcve_license_model",
                "evidence": "Current license-included or portable-VCF commercial model is confirmed for the target commitment.",
            },
        ),
        sources=(
            {
                "title": "Use VMware HCX to migrate to VMware Engine",
                "url": "https://docs.cloud.google.com/vmware-engine/docs/workloads/howto-migrate-vms-using-hcx",
            },
            {
                "title": "VMware Engine node types",
                "url": "https://docs.cloud.google.com/vmware-engine/docs/concepts-node-types",
            },
            {
                "title": "VMware Engine networking requirements",
                "url": "https://docs.cloud.google.com/vmware-engine/docs/quickstart-networking-requirements",
            },
        ),
    ),
}


def target_profile(target_id, *, target_node=None, target_cpu_vendor=None):
    """Return one validated target profile as a serializable dictionary."""
    key = str(target_id).strip().casefold()
    if key not in PROFILES:
        raise ValueError(f"unknown migration target: {target_id}")
    profile = PROFILES[key]
    nodes = list(profile.nodes)
    if target_node:
        selected = [node for node in nodes if node["id"].casefold() == str(target_node).casefold()]
        if not selected:
            raise ValueError(f"unknown {key} target node: {target_node}")
    else:
        selected = []
    selected_cpu_vendor = selected[0].get("cpu_vendor") if selected else None
    fixed_cpu_vendor = selected_cpu_vendor or profile.cpu_vendor
    if target_cpu_vendor and fixed_cpu_vendor:
        requested = "AMD" if str(target_cpu_vendor).strip().casefold() == "amd" else str(target_cpu_vendor).strip().title()
        if requested != fixed_cpu_vendor:
            raise ValueError(f"{profile.name} uses {fixed_cpu_vendor} hosts; target CPU vendor cannot be overridden")
    cpu_vendor = target_cpu_vendor or fixed_cpu_vendor
    if cpu_vendor:
        normalized = str(cpu_vendor).strip().title()
        if normalized not in {"Intel", "Amd"}:
            raise ValueError("target CPU vendor must be Intel or AMD")
        cpu_vendor = "AMD" if normalized == "Amd" else normalized
    return {
        "id": profile.id,
        "name": profile.name,
        "cpu_vendor": cpu_vendor,
        "selected_node": selected[0] if selected else None,
        "nodes": nodes,
        "sizing_constraints": dict(profile.sizing_constraints),
        "catalog_reviewed": CATALOG_REVIEWED,
        "manual_gates": list(profile.manual_gates),
        "sources": list(profile.sources),
    }
