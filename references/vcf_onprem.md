# VCF On-Premises Re-platform Readiness

Use this reference only for the `vcf_onprem` lens. Default to assessing migration into a newly designed VCF environment. If the user means brownfield convergence/import, state that assumption explicitly because the supported workflow and prerequisites differ.

Last source review: 2026-08-11.

## What RVTools can and cannot establish

RVTools can screen workload configuration, source host versions/models, network patterns, storage pressure, and hygiene debt. It cannot prove:

- server, NIC, HBA, controller, disk, firmware, or driver support for the chosen VCF release;
- the valid VCF bill of materials or component interoperability path;
- DNS, forward/reverse lookup, NTP reachability, certificates, passwords, VLAN routing, MTU, physical uplinks, or switch configuration;
- target management-domain and workload-domain design;
- vSAN ESA versus OSA eligibility;
- licensing entitlement, depot access, or lifecycle bundle availability.

Always include these as external validation gates rather than silently marking the environment ready.

## VCF and vSAN subscription-capacity estimate

Use the query entities instead of calculating from VM or vCPU counts:

- `license` returns sanitized RVTools `vLicense` inventory. It excludes keys, labels, and feature strings. Treat assigned and used values as point-in-time technical inventory, not proof of contractual entitlement, portability, renewal rights, or price.
- `vcf_license` shows the per-host CPU topology and calculation.
- `vcf_license_summary` returns the estate total and vSAN entitlement balance.

Broadcom currently licenses VCF core capacity from physical CPU cores on every ESXi host in scope, with a minimum of 16 cores per physical CPU. For each host calculate `max(actual physical cores, CPU sockets × 16)`, then sum the hosts. Withhold the estate total when any included host lacks the socket/core evidence needed to apply the minimum. See [Broadcom core and vSAN capacity counting](https://knowledge.broadcom.com/external/article/313548/counting-cores-for-vmware-cloud-foundati.html).

One purchased VCF core currently includes 1 TiB of vSAN capacity entitlement. Compare that entitlement with the total raw physical capacity contributed by all ESXi hosts to the vSAN clusters in scope:

- `vSAN add-on TiB = max(raw vSAN TiB - VCF licensable cores, 0)`
- `surplus vSAN entitlement TiB = max(VCF licensable cores - raw vSAN TiB, 0)`

Report one side as zero; never imply that surplus entitlement is spare physical storage. Do not convert the TiB difference into pricing or a purchase-order quantity without checking the current contract and sales units.

RVTools `vDatastore` capacity for rows identified as vSAN is only a planning proxy. It may differ from raw disk capacity because of metadata, architecture, claims, or reporting semantics. When the result says `rvtools_vsan_datastore_capacity_proxy`, label the add-on/surplus result as an estimate. Prefer independently verified raw capacity and pass it to `vcf_license_summary` with `--vsan-raw-tib`. If neither evidence source exists, report the included VCF vSAN entitlement and request raw TiB rather than inventing an add-on requirement.

State the host scope. A current-estate total excludes future management-domain hosts, replacement hosts, DR capacity, or other target hardware absent from the workbook. For VCF 9 licensing mechanics, also consult [Broadcom's VCF 9 licensing overview](https://knowledge.broadcom.com/external/article/437242/getting-started-with-vmware-cloud-founda.html).

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

- For a new target-hardware sizing request, read [sizing.md](sizing.md) and use its recommended policy unless the user deliberately selects active-only sizing. The shared engine requires a verified VCF hardware profile or bill of materials; it must not assume that the source host configuration is the target.
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
