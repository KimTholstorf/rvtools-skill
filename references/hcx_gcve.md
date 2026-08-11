# Google Cloud VMware Engine migration lens

Use this reference with [hcx_common.md](hcx_common.md) for the `hcx_gcve` lens and parser target `gcve`.

## Target facts to verify

The parser carries a dated planning catalog for ve1, configurable ve2 node types, and storage-only nodes. Google describes ve2 CPU choices as logical processors, with two logical processors per physical core. Keep logical-thread and physical-core values distinct. Verify current CPU, memory, storage, regional availability, and minimum-node rules in [VMware Engine node types](https://cloud.google.com/vmware-engine/docs/concepts-node-types) before sizing.

GCVE nodes use Intel processors. An AMD source host blocks live CPU-state methods in the deterministic screen; powered-off Bulk or Cold remains conditional. Exact EVC compatibility still needs validation.

## GCVE-specific interpretation

- Check every source version against the Broadcom interoperability result for the selected method. Google explicitly directs customers to that matrix in [Migrate VMs using HCX](https://cloud.google.com/vmware-engine/docs/workloads/howto-migrate-vms-using-hcx). The parser deliberately does not hard-code a minimum ESXi version.
- Validate private-cloud CIDR planning early. The management IP plan, connected VPCs, Cloud Router design, DNS, and reachability determine whether HCX appliances and Network Extension can be deployed cleanly. Use Google's [VMware Engine networking requirements](https://cloud.google.com/vmware-engine/docs/quickstart-networking-requirements).
- Plan HCX appliances, service mesh, firewall rules, and migration groups from [Migrate VMs using HCX](https://cloud.google.com/vmware-engine/docs/workloads/howto-migrate-vms-using-hcx). Confirm the HCX license edition and enabled services in the actual private cloud.
- Treat HCI-node raw storage, storage-only nodes, and external NFS datastores as separate design options. Apply the chosen vSAN policy, operational slack, HA reserve, and growth before comparing capacity.
- Confirm target region/zone capacity, project quotas, node family, commitment, and the current VMware licensing model. These are commercial and service facts that RVTools cannot supply.

## Assessment framing

Report ve2 CPU values with both the vendor's logical-processor label and the derived physical-core value. Do not compare source physical cores directly with GCVE logical processors without showing the conversion.

Do not call a VM or wave GCVE-ready until the target project, region/zone, node type, IP plan, connectivity, storage design, license model, and HCX Validate result are confirmed.
