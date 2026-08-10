# VCF On-Premises Re-platform Readiness

Use this reference only for the `vcf_onprem` lens. Default to assessing migration into a newly designed VCF environment. If the user means brownfield convergence/import, state that assumption explicitly because the supported workflow and prerequisites differ.

Last source review: 2026-08-07.

## What RVTools can and cannot establish

RVTools can screen workload configuration, source host versions/models, network patterns, storage pressure, and hygiene debt. It cannot prove:

- server, NIC, HBA, controller, disk, firmware, or driver support for the chosen VCF release;
- the valid VCF bill of materials or component interoperability path;
- DNS, forward/reverse lookup, NTP reachability, certificates, passwords, VLAN routing, MTU, physical uplinks, or switch configuration;
- target management-domain and workload-domain design;
- vSAN ESA versus OSA eligibility;
- licensing entitlement, depot access, or lifecycle bundle availability.

Always include these as external validation gates rather than silently marking the environment ready.

## Readiness gates

### 1. Release and lifecycle alignment

- Use `esxi_version_spread`, host versions, and VM hardware versions to expose lifecycle heterogeneity.
- Select the target VCF release first, then validate the supported BOM, upgrade/convergence path, and hardware against the live compatibility data.
- Do not infer support from model names alone. Broadcom states that hardware compatibility must be checked for the target release and architecture. Use the [Broadcom Compatibility Guide](https://compatibilityguide.broadcom.com/) and the applicable VCF release documentation.
- Treat out-of-band or asynchronous patching as a separate lifecycle review item.

Broadcom's current upgrade guidance emphasizes hardware compatibility and version alignment across domains: [VCF 5.0.x release information](https://knowledge.broadcom.com/external/article/314658/vmware-cloud-foundation-50x-releases-im.html). A current VCF 9 example shows that vSAN ESA validates disks and controllers against ESA-specific certification: [VCF installation HCL validation](https://knowledge.broadcom.com/external/article/434503/vcf-install-validation-fails-with-no-vsa.html).

### 2. Cluster and host design

- Use cluster counts, host counts, CPU models, resource utilization, and ESXi versions as design inputs.
- Interpret `non_intel_host` only as CPU-vendor inventory. Intel and AMD both require release- and hardware-specific validation.
- Require homogeneous physical networking and uplink mappings inside each target cluster.
- Confirm management-domain host minimums and storage rules from the exact VCF version and deployment model. Do not use a timeless hard-coded minimum.
- For VCF 9 convergence of a VUM-managed cluster, Broadcom documents a three-host minimum and a transition to vLCM image management; other workflows differ. See [VCF 9 convergence cluster-size validation](https://knowledge.broadcom.com/external/article/434513/unable-to-converge-vsphere-environment-u.html).

Broadcom documents that host commissioning requires incoming uplink names and mappings to match the cluster: [VCF host commissioning uplink compatibility](https://knowledge.broadcom.com/external/article/428877/host-commissioning-via-vcf-operations-or.html).

### 3. Networking

- `standard_vswitch_attachment` shows workload VMs still attached through VSS. Treat this as migration work and an operational consistency concern.
- Do not claim that this detection proves VCF management-network noncompliance: RVTools' VM network rows do not fully establish VMkernel-to-switch mapping.
- For a VCF 9 upgrade/import, separately verify every management, vMotion, vSAN, and overlay VMkernel adapter. Broadcom documents vSphere Distributed Switches as required for VCF 9 management networking and states that VSS-backed VMkernel adapters fail pre-checks: [VCF 9 distributed-switch requirement](https://knowledge.broadcom.com/external/article/430625/upgrading-to-vcf-90-requires-distributed.html).
- Review VLAN 0 or empty VLAN IDs, promiscuous mode, MAC address changes, forged transmits, ephemeral binding, MTU, uplink redundancy, and port-group naming as intentional design decisions, not automatic one-for-one migrations.
- Verify DNS, NTP, firewall ports, routing, and forward/reverse records outside RVTools. VCF installer validation requires valid NTP data: [VCF Installer NTP validation](https://knowledge.broadcom.com/external/article/422243/vcf-installer-validation-fails-with-prov.html).

### 4. Workload portability

- `raw_device_mapping`, `shared_disk`, `independent_disk`, `fault_tolerance_enabled`, connected devices, and VMkernel-network attachments require a migration design even when the target remains VMware.
- `legacy_vm_hardware` is a compatibility and security review flag. Upgrade only after confirming guest support and updating VMware Tools; newer is not automatically better for packaged appliances.
- `tools_not_running` reduces guest observability and can complicate upgrades and migration orchestration.
- `oracle_workload` is a licensing-scope indicator only. Require licensing specialists to validate processor, partitioning, cluster, DR, and mobility implications.

Broadcom notes that a VM cannot run on a platform that does not support its virtual hardware version, while lower versions can lose functionality: [Virtual machine hardware versions](https://knowledge.broadcom.com/external/article/315655/virtual-machine-hardware-versions.html).

### 5. Capacity and operational headroom

- Use datastore capacity, provisioned, used, and free values to identify immediate pressure and thin-provisioning exposure.
- Use host CPU and memory percentages as a point-in-time screening signal only.
- Require sustained performance history, failure-domain reserve, maintenance-mode evacuation capacity, management overhead, storage policy overhead, and growth before sizing the target.
- Treat `vm_cpu_large`, `vm_memory_large`, and `vm_provisioned_storage_large` as placement, migration-duration, and admission-control review flags, not target maximum violations.
- Review HA/DRS enablement, admission control, failed or inaccessible objects, multipathing, and RVTools health errors.

## Readiness result

Use four statuses:

- **Not ready**: a target-release requirement is known to be unmet or a workload has no supported migration treatment.
- **Conditionally ready**: the inventory is workable after named remediation and external validations.
- **Ready for detailed design**: no material RVTools blocker remains, but HCL/BOM/network/lifecycle gates are still pending.
- **Insufficient evidence**: required sheets or non-RVTools evidence are missing.

Never return an unconditional "VCF ready" result from RVTools alone.
