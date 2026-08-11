# HCX Migration Readiness for Oracle Cloud VMware Solution

Use this reference with [hcx_common.md](hcx_common.md) for the `hcx_ocvs` lens and parser target `ocvs`. Treat the parser output as a screening assessment, not as a substitute for HCX Validate, the Broadcom interoperability matrix, or an application migration test.

Last source review: 2026-08-07.

## Assessment stance

- Prefer HCX vMotion for compatible, latency-sensitive individual workloads when live migration is required.
- Prefer Replication Assisted vMotion (RAV) for larger migration waves that need low downtime and satisfy RAV constraints.
- Treat Bulk Migration as a valid fallback with planned interruption, not as a failure. Oracle documents that its service interruption is equivalent to a reboot.
- Use Cold Migration when a workload cannot satisfy live or replication-assisted constraints and a controlled outage is acceptable.
- Never infer the final migration profile from RVTools alone. Recommend HCX Validate for every migration group.

Oracle describes HCX vMotion, Bulk Migration, their network mapping, and validation workflow in [Learn About Migrating Applications Using HCX](https://docs.oracle.com/en/solutions/migrate-vmware-workloads-oraclecloud/learn-migrating-applications-using-hcx.html). Broadcom documents current RAV prerequisites and restrictions in [Configuring VMware HCX Replication Assisted vMotion](https://knowledge.broadcom.com/external/article/440117/configuring-vmware-hcx-replication-assis.html).

## Interpret deterministic detections

### Blockers or likely profile changers

- `raw_device_mapping`: Physical-mode RDM is unsupported for HCX Bulk Migration. Virtual-mode RDM can be converted to VMDK at the destination. Require exact mode confirmation and a disk conversion or reattachment plan. See [HCX Bulk Migration with RDM disks](https://knowledge.broadcom.com/external/article/417249/hcx-bulk-migration-stuck-at-initial-sync.html).
- `independent_disk`: RAV prohibits independent persistent and non-persistent disks. Select another method or remediate the disk mode.
- `shared_disk`: RAV prohibits shared SCSI buses and multi-writer disks; vSphere Replication-based Bulk Migration does not support clustered disks. Plan application-cluster downtime and Cold Migration or an application-native move. See [HCX migration failures due to SCSI bus sharing](https://knowledge.broadcom.com/external/article/442091/hcx-migration-failures-due-to-scsi-bus-s.html).
- `fault_tolerance_enabled`: RAV prohibits Fault Tolerance. Disable FT only under an approved availability plan, or choose a supported alternative.
- `connected_usb` and `connected_cdrom`: RAV prohibits attached virtual media, and local devices can block vMotion. Disconnect nonessential devices and validate again.
- `cdrom_starts_connected`: Review disconnected media configured to reconnect at the next power-on so it does not reappear before a migration wave.
- `vm_suspended`: Resume and validate guest health before migration; otherwise use a deliberate cold workflow.

Broadcom's RAV guidance also prohibits DirectPath I/O, IOMMU for vMotion/Cold/RAV in relevant releases, and vVol-backed workloads. RVTools may not expose all of these reliably, so list them as manual validation gaps. See [IOMMU migration limitation](https://knowledge.broadcom.com/external/article/382187/hcx-vmotioncoldrav-migration-unsupporte.html).

### Material warnings

- `stale_snapshot` and `consolidation_needed`: Clear snapshot and consolidation debt before creating migration waves. Snapshots can retain stale network configuration and can interfere with HCX validation or backup/migration locks. See [snapshot-related HCX validation failure](https://knowledge.broadcom.com/external/article/401607/hcx-bulk-migration-validation-fails-wit.html) and [HCX interoperability with snapshot-based backups](https://knowledge.broadcom.com/external/article/328980/hcx-interoperability-with-backup-solutio.html).
- `tools_not_running`: VMware Tools must be installed for Bulk Migration. Outdated tools can produce a warning and should normally be remediated before the wave. See [HCX Bulk Migration and VMware Tools](https://knowledge.broadcom.com/external/article/395399/hcx-bulk-migration-check-failed-with-mes.html).
- `standard_vswitch_attachment`: VSS networks are supported at the HCX source, but every source network still needs an explicit target mapping or extension design. Do not describe VSS use alone as an HCX blocker.
- `vmkernel_network_attachment`: Treat a workload NIC on a VMkernel port group as a high-priority isolation and mapping defect.
- `dvport_vlan_zero`, `dvport_promiscuous_mode`, `dvport_mac_changes`, `dvport_forged_transmits`, and `dvport_ephemeral_binding`: Require intentional target-side policy mapping. Do not assume source security exceptions should be reproduced.
- `legacy_vm_hardware`: RAV requires hardware version 9 or newer. Versions below the target operational baseline still warrant compatibility review even if they satisfy that minimum.
- `possible_cleartext_secret`: Remove credentials from annotations or snapshot descriptions before sharing reports or exporting inventories.

## CPU and target-cluster planning

OCVS currently offers both Intel and AMD host shapes, but shapes in a cluster must use the same processor vendor. Live vMotion does not make Intel and AMD compatible; EVC works only within a CPU vendor. Therefore:

- Interpret `non_intel_host` as a target-vendor and migration-profile decision, not as an inherent OCVS incompatibility.
- Match target processor vendor for live migration, or plan a powered-off method when changing vendor.
- Review source EVC mode, CPU generation, BIOS/microcode consistency, and application CPU-feature dependencies outside RVTools.

Sources: [OCVS supported shapes and cluster rules](https://docs.oracle.com/en-us/iaas/Content/VMware/Concepts/ocvsoverview.htm), [Broadcom EVC and CPU compatibility FAQ](https://knowledge.broadcom.com/external/article/313545/vmware-evc-and-cpu-compatibility-faq.html).

## Connectivity and service-mesh readiness

RVTools cannot prove underlay readiness. Require a separate checklist for:

- supported source vCenter/ESXi and HCX interoperability;
- DNS and NTP consistency;
- management, vMotion, and replication network profiles;
- firewall ports and routing;
- target compute, datastore, and network reachability;
- measured bandwidth, latency, packet loss, and change rate;
- network extension scope and rollback;
- migration-wave storage headroom and backup blackout windows.

Oracle's OCVS HCX component guide identifies the required source network profiles, DNS/NTP, permissions, and site connectivity, and recommends FastConnect for best performance: [Configure OCVS HCX Components](https://docs.oracle.com/en/solutions/migrate-vmware-workloads-oraclecloud/configure-oracle-cloud-vmware-solution-hcx-components.html). Broadcom notes that RAV underlay throughput must be at least 150 Mbps and that actual scale depends on storage, hosts, bandwidth, latency, packet loss, disk count, and data churn: [RAV configuration](https://knowledge.broadcom.com/external/article/440117/configuring-vmware-hcx-replication-assis.html) and [Bulk/RAV scalability](https://knowledge.broadcom.com/external/article/321604/hcx-bulk-migration-replication-assiste.html).

## Sizing guardrails

- Do not compare a VM's vCPU or memory directly with host OCPU or RAM and declare it incompatible. vSphere scheduling, reservations, HA policy, management overhead, storage design, and oversubscription all matter.
- Treat `vm_cpu_large`, `vm_memory_large`, and `vm_provisioned_storage_large` as design-review flags only. The parser's provisioned-storage threshold is 10 TiB and is a migration-duration triage rule, not an OCVS maximum.
- Use sustained performance history, not one RVTools sample, for target sizing.
- Re-check the live OCVS shape table when the user requests current sizing; Oracle changes available shapes and software bundles over time.
- Include N+1/HA reserve, management workload overhead, growth, storage policy overhead, and migration concurrency in the target model.

Current OCVS shape and cluster characteristics are maintained in [Overview of Oracle Cloud VMware Solution](https://docs.oracle.com/en-us/iaas/Content/VMware/Concepts/ocvsoverview.htm).

## Report conclusion levels

- **Blocked for preferred profile**: a documented constraint prevents vMotion/RAV until remediated.
- **Migration warning**: supported in principle, but validation, mapping, cleanup, or a controlled outage is required.
- **Planning input**: capacity, vendor, licensing, or topology information that changes design but is not a compatibility result.
- **Coverage gap**: required evidence is absent from RVTools and must be validated elsewhere.
