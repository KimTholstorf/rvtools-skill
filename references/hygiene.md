# VMware Environment Hygiene, Health, and Capacity

Use this reference only for the `hygiene` lens. Separate vendor guidance from local screening heuristics in the report.

Last source review: 2026-08-08.

## Host hardware lifecycle and configuration

For every hygiene assessment that includes `vHost`, follow [hardware_lifecycle.md](hardware_lifecycle.md). Inventory server vendor/model, CPU vendor/model, socket/core topology, Hyper-Threading availability and state, BIOS information, and ESXi version. Research lifecycle/support for every distinct nonblank server vendor/model; do not omit this check merely because the parser has no static lifecycle detection.

Treat `host_hyperthreading_inactive` as a configuration review. Hyper-Threading can be disabled deliberately for security, licensing, or workload reasons, so verify intent and vendor guidance rather than recommending a blanket enablement.

## Vendor-backed findings

### Snapshots and consolidation

- Treat every snapshot as operational debt that needs an owner and expiry date.
- Treat `stale_snapshot` as high priority. The parser uses 72 hours because Broadcom says not to retain a single snapshot longer than that.
- Treat `consolidation_needed` as a data-protection and capacity concern. Plan consolidation with datastore headroom and backup awareness.
- Do not call snapshots backups.

Source: [Best practices for using VMware snapshots](https://knowledge.broadcom.com/external/article?legacyId=1025279). Broadcom also notes that snapshot delta files can approach the size of the base disk and recommends reserving 20–30% additional free capacity when planning snapshot growth: [Recommendations for creating a snapshot for a large VM](https://knowledge.broadcom.com/external/article/418600/recommendations-for-creating-a-snapshot.html).

### VMware Tools and virtual hardware

- Prioritize `tools_not_running` for powered-on workloads, while recognizing that some appliances or supported open-vm-tools configurations need product-specific interpretation.
- Treat `legacy_vm_hardware` as a review, not an instruction to mass-upgrade. Broadcom advises upgrading only when required features or security posture justify it and warns that newer hardware can reduce portability.
- Update or validate VMware Tools before virtual hardware changes; protect the VM and test guest networking/storage after the change.

Sources: [Virtual machine hardware versions](https://knowledge.broadcom.com/external/article/315655/virtual-machine-hardware-versions.html), [hardware-version security considerations](https://knowledge.broadcom.com/external/article/441013/impact-of-vm-hardware-version-on-cpu-sec.html), and [hardware upgrade prerequisites](https://knowledge.broadcom.com/external/article?articleNumber=315390).

### Devices, disks, and network isolation

- Connected CD/DVD and USB devices create avoidable operational coupling. Confirm whether each device is required, and review disconnected CD/DVD devices configured to reconnect at power-on.
- RDMs, independent disks, shared buses, and multi-writer configurations identify special-purpose workloads that need documented ownership, backup, HA, and recovery procedures.
- A VM attached to a VMkernel port group is normally an isolation defect and should be investigated immediately.
- Promiscuous mode, MAC address changes, and forged transmits expand the network attack surface. Validate business purpose and scope.
- VLAN 0 and ephemeral binding are not universally wrong; require an explicit design rationale.

## Project screening heuristics

These thresholds are intentionally conservative triage rules, not VMware configuration maximums or target-platform limits:

- `datastore_low_free_space`: less than 10% free. Escalate sooner when snapshots, thin provisioning, high churn, or rebuild activity increase growth risk.
- `datastore_overprovisioned`: provisioned capacity exceeds physical capacity. This is acceptable only with monitoring, growth controls, and recovery headroom.
- `host_cpu_pressure`: point-in-time CPU usage above 80%.
- `host_memory_pressure`: point-in-time memory usage above 90%.
- `vm_cpu_large`: more than 128 configured vCPUs.
- `vm_memory_large`: more than 1 TiB configured memory.
- `vm_provisioned_storage_large`: more than 10 TiB provisioned storage.

Interpret the parser's overcommit ratios with these project heuristics:

- CPU: up to 2.5:1 conservative; above 2.5 through 4:1 normal; above 4 through 6:1 aggressive; above 6:1 very high.
- Memory: up to 1.3:1 conservative; above 1.3 through 1.8:1 normal; above 1.8 through 2.5:1 aggressive; above 2.5:1 very high.

Label these ranges as project screening heuristics. Workload demand, reservations, limits, NUMA behavior, HA reserve, failover policy, and performance history can make the same ratio acceptable or unsafe in different clusters.

Never turn these screening rules into sizing conclusions without sustained utilization and demand data.

## Security and licensing indicators

- `possible_cleartext_secret` reports only the object and field; never reproduce the matched annotation or snapshot text. Remove the value at source and rotate any exposed credential.
- `oracle_workload` is a keyword-based licensing flag with possible false positives and false negatives. Do not state that a VM runs licensable Oracle software without validation.
- Review annotations, snapshot descriptions, custom fields, exported license keys, host serial numbers, IPs, and network names as sensitive infrastructure data. Keep raw exports and parser JSON local unless the user explicitly authorizes another handling path.

## Capacity narrative

Report:

- VM, template, host, cluster, datastore, disk, NIC, and snapshot counts;
- provisioned versus in-use VM storage;
- datastore capacity, provisioned, in-use, and free capacity;
- ESXi version and VM hardware-version distributions;
- host vendor/model, CPU model, Hyper-Threading state, and authoritative hardware lifecycle/support status;
- power states and obvious sprawl signals;
- per-cluster CPU overcommit as configured vCPUs on powered-on workloads divided by physical host cores;
- per-cluster memory overcommit as configured memory on powered-on workloads divided by physical host memory;
- overall CPU and memory ratios, followed by powered-off VM count, vCPUs, and configured memory reported separately;
- the highest-severity detections with counts and bounded examples;
- missing-sheet warnings and resulting coverage gaps.

State that templates, powered-off VMs, suspended VMs, and other non-powered-on states are excluded from the ratios. Do not describe powered-off allocations as available capacity; show them as potential demand if those VMs are returned to service. If the parser reports missing physical capacity, show the affected ratio as unavailable. If it reports multiple vCenter sources, warn that same-named clusters may have been aggregated.

Do not confuse CPU or memory overcommit with datastore thin-provisioning overcommit; report them as separate capacity dimensions.

Avoid claiming right-sizing savings from RVTools alone. Request at least several weeks of CPU, memory, storage latency/IOPS, and network history before recommending downsizing.
