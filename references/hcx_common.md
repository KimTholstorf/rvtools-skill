# Shared VMware HCX migration rules

Read this reference for every OCVS, AVS, or GCVE migration assessment, then read the selected provider reference. The deterministic assessment is a planning screen from RVTools data. It is not a substitute for the current [Broadcom Product Interoperability Matrix](https://interopmatrix.broadcom.com/Interoperability), HCX Validate, or a migration test.

## Method model

Assess every non-template VM separately for `hcx_vmotion`, `rav`, `bulk`, and `cold`. Report one of:

- `eligible`: no incompatible condition was found in the available RVTools fields;
- `conditional`: a known remediation, design choice, or powered-off treatment is required;
- `blocked`: the available evidence conflicts with the method;
- `unknown`: a field needed for a safe conclusion is missing or ambiguous.

`eligible` means eligible in this screening only. Always retain the associated manual gates.

Use HCX vMotion for small numbers of compatible VMs that need live state transfer. Use Replication Assisted vMotion (RAV) when a larger wave needs low downtime and the source, target, network, storage, and VM configuration pass validation. Use Bulk Migration where planned reboots are acceptable. Use Cold Migration for workloads that cannot retain running CPU state or need offline device/storage work.

## Evidence-backed compatibility rules

- A suspended VM is not a live-migration candidate. Resume and validate it, or plan a controlled cold move.
- RAV requires virtual hardware version 9 or later. Treat a missing hardware version as unknown for RAV. For every method, also confirm that the target ESXi release supports the VM's hardware version. See Broadcom's [RAV configuration requirements](https://knowledge.broadcom.com/external/article/440117/configuring-vmware-hcx-replication-assis.html) and [virtual hardware compatibility guidance](https://knowledge.broadcom.com/external/article/418811/hcx-validation-fails-with-hardware-versi.html).
- Fault Tolerance, DirectPath I/O, unsupported IOMMU configurations, shared SCSI buses, and multi-writer disks require a different availability or migration design. RVTools does not expose every variant reliably.
- A physical-mode RDM cannot be replicated as an ordinary cloud VMDK. A virtual-mode RDM normally needs conversion and method validation. If the compatibility mode is absent, report `unknown` rather than guessing. See Broadcom's [HCX Bulk Migration with RDM disks](https://knowledge.broadcom.com/external/article/417249/hcx-bulk-migration-stuck-at-initial-sync.html).
- Independent disks and clustered/shared disks block replication-based methods until reconfigured. Cold migration remains conditional because storage presentation or application-level migration still needs design. See [HCX migration failures due to SCSI bus sharing](https://knowledge.broadcom.com/external/article/442091/hcx-migration-failures-due-to-scsi-bus-s.html).
- VMware Tools must be installed and running for Bulk Migration. For other methods, a bad Tools state is a remediation warning. See [HCX Bulk Migration and VMware Tools](https://knowledge.broadcom.com/external/article/395399/hcx-bulk-migration-check-failed-with-mes.html).
- Connected USB and virtual media must be removed or explicitly handled before validation. Snapshot and consolidation debt should be cleared before replication.
- Live CPU state cannot cross Intel and AMD boundaries. Block HCX vMotion and RAV when the target CPU vendor is known to differ; keep powered-off methods conditional. Confirm EVC and the exact generations in the [Broadcom EVC and CPU compatibility FAQ](https://knowledge.broadcom.com/external/article/313545/vmware-evc-and-cpu-compatibility-faq.html).
- A VM on a standard vSwitch can still be mapped to a target network, but HCX Network Extension requires a supported distributed-switch or NSX design. Report it as a network design finding, not an automatic VM-method blocker.

## Mandatory manual gates

RVTools cannot establish these facts. Every report must list them as open evidence until verified:

- current vCenter, ESXi, NSX, and HCX interoperability;
- measured bandwidth, latency, packet loss, and data-change rate;
- DNS, NTP, routing, firewall ports, certificates, and service-account permissions;
- overlapping source, target, management, and workload CIDRs;
- sustained CPU, memory, storage latency/IOPS/throughput, network history, HA reserve, management overhead, and growth;
- backup, monitoring, security, application dependency, cutover, rollback, and business-owner validation;
- successful HCX Validate for each migration group immediately before execution.

Broadcom notes that migration scale depends on storage, hosts, bandwidth, latency, packet loss, disk count, and churn. Do not turn an RVTools inventory total into a safe concurrency number.

## Reporting

Lead with exact per-method counts and named blockers, then show conditional treatments. Keep provider capacity facts separate from workload sizing. Include the target catalog review date and link to current vendor documentation because node types, regional availability, quotas, licensing, and limits change.
