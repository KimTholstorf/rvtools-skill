"""Versioned migration target profiles and planning catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


CATALOG_REVIEWED = "2026-08-11"


@dataclass(frozen=True)
class TargetProfile:
    """Provider-specific facts layered over shared HCX compatibility rules."""

    id: str
    name: str
    cpu_vendor: Optional[str]
    nodes: Tuple[Dict[str, Any], ...]
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
):
    return {
        "id": node_id,
        "physical_cores": physical_cores,
        "logical_threads": logical_threads,
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
    _node("AV36", 36, 72, 576, 15.2, "OSA", cpu_model="Intel Xeon Gold 6140"),
    _node("AV36P", 36, 72, 768, 19.2, "OSA", cpu_model="Intel Xeon Gold 6240"),
    _node("AV48", 48, 96, 1024, 25.6, "ESA", cpu_model="Intel Xeon Gold 6442Y"),
    _node("AV52", 52, 104, 1536, 38.4, "OSA", cpu_model="Intel Xeon Platinum 8270"),
    _node(
        "AV64",
        64,
        128,
        1024,
        None,
        "OSA_or_ESA",
        storage_by_architecture={"OSA": 15.36, "ESA": 19.25},
        cpu_model="Intel Xeon Platinum 8370C",
    ),
)


def _gcve_nodes():
    nodes = [_node("ve1-standard-72", 36, 72, 768, 19.2, "OSA")]
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
                )
            )
    nodes.append(_node("ve1-standard-so", 0, 0, 0, 19.2, "OSA", storage_only=True))
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
        "evidence": "Sustained CPU, memory, storage IOPS/throughput and network history with HA and growth assumptions.",
    },
)


PROFILES = {
    "ocvs": TargetProfile(
        id="ocvs",
        name="Oracle Cloud VMware Solution",
        cpu_vendor=None,
        nodes=(),
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
    if target_cpu_vendor and profile.cpu_vendor:
        requested = "AMD" if str(target_cpu_vendor).strip().casefold() == "amd" else str(target_cpu_vendor).strip().title()
        if requested != profile.cpu_vendor:
            raise ValueError(f"{profile.name} uses {profile.cpu_vendor} hosts; target CPU vendor cannot be overridden")
    cpu_vendor = target_cpu_vendor or profile.cpu_vendor
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
        "catalog_reviewed": CATALOG_REVIEWED,
        "manual_gates": list(profile.manual_gates),
        "sources": list(profile.sources),
    }
