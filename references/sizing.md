# Deterministic Cloud VMware Sizing

Use this reference for OCVS, AVS, and GCVE sizing. The Python sizing engine is the calculation record. Do not recalculate host counts in prose or replace an engine result with mental arithmetic.

The arithmetic also supports on-premises VCF through an injected target hardware profile. Require a verified bill of materials with per-host configured cores, physical silicon cores, memory, cluster roles, and supported minimums. Do not infer a target VCF node from the source hosts. Without that profile, report workload demand and request the missing design input instead of inventing a host count.

## Choose the design inputs first

Before sizing more than one source cluster, ask whether the target should:

- **Consolidate workloads into fewer clusters** (`consolidated`): compatible source clusters share the fewest practical target clusters.
- **Retain the existing cluster structure** (`source_aligned`): each populated source cluster keeps a separate target cluster.

Use the plain-language labels in reports and questions; keep the identifiers in parentheses internal. Do not assume consolidation. If the user retains the existing structure, exclude source clusters with no hosts and list them in the scope. The engine selects the largest target workload as the primary or management cluster unless `--primary-source-cluster` supplies a deliberate choice. State that mapping in the report.

Storage is a second design input. When neither cluster design nor storage basis is supplied, ask for both in the same concise question. Offer provisioned storage as-is or a user-specified growth allowance. When the user supplies the cluster design but says nothing about storage, use provisioned storage with no growth allowance. Do not ask a cluster-design question for a single source cluster because the two layouts are equivalent.

## Capacity policies

The default `recommended` policy uses:

- all non-template workloads, regardless of power state, for compute demand;
- a 4:1 configured-vCPU-to-configured-physical-core ratio;
- 20% normal-operation CPU headroom;
- 20% normal-operation memory headroom, with configured memory as a binding constraint;
- one-host-loss CPU and memory validation;
- provisioned storage with no automatic growth allowance for all selected VMs and templates.

For OCVS, call this **Recommended OCVS planning assumptions**. For AVS and GCVE, call it **Recommended cloud sizing assumptions** and do not associate it with Oracle.

Apply a positive storage allowance only when the user asks for one. Pass the percentage through `--storage-headroom-percent` so the selected basis is part of the deterministic result. Do not add an unstated allowance in prose or in the BOM.

Use `active_only` only when the user deliberately selects it. It uses powered-on non-template workloads, a 4:1 CPU ratio, no generic CPU or memory headroom, and aggregate memory overcommit. It still validates one-host-loss CPU capacity and largest-VM memory fit. It includes all selected VMs and templates in provisioned storage but applies no generic storage headroom.

Neither policy is a substitute for performance history. Always request sustained CPU, memory, storage latency/IOPS, and network demand before a purchase commitment.

## Host-count calculation

For each candidate node, the engine calculates independent floors:

```text
normal CPU floor = ceil(vCPU / (configured cores × CPU ratio × (1 - CPU headroom)))
normal memory floor = ceil(configured RAM / (host RAM × (1 - memory headroom)))
one-host-loss CPU floor = ceil(vCPU / (configured cores × CPU ratio)) + 1
one-host-loss memory floor = ceil(configured RAM / host RAM) + 1
total hosts = max(normal floors, one-host-loss floors, provider minimum)
```

The memory floors are zero when the selected policy accepts aggregate memory overcommit. A provider minimum is itself purchased capacity. Never add another host blindly to that minimum. For example, an OCVS standard workload whose demand fits on one surviving host requires two hosts, not three.

Keep the floor names above inside the calculation record. In a customer report, title the section **How the host recommendation was determined** and use `recommendation.presentation` to show:

```text
Target cluster | Target host type | Workload capacity | One-host resilience | Cloud service minimum | Recommended hosts | What determined the result
```

**Workload capacity** is the larger of the normal-operation CPU and memory requirements. **One-host resilience** is the minimum purchased fleet needed for the workloads to fit when one host is unavailable for failure or maintenance. **Cloud service minimum** is the provider's minimum purchased host count. **Recommended hosts** is the highest of those three values. Explain this below the table and add a short cluster-specific explanation when the result may otherwise look contradictory.

Current production cluster constraints in the target catalog are:

- OCVS standard unified-management cluster: minimum 3, maximum 32;
- OCVS standard workload cluster: minimum 2, maximum 32;
- AVS cluster: minimum 3, maximum 16;
- GCVE standard cluster: minimum 3, maximum 32.

Recheck these limits against current provider documentation when they affect a customer design.

## Node selection

If the user names a node or host type, size that node and report an invalid selection rather than silently switching SKUs.

Without a selected node, the engine evaluates every compute node in the dated target catalog. Internally it removes dominated choices and selects a practical trade-off between:

- total purchased hosts;
- total full-silicon VCF cores.

Do not expose “Pareto frontier” or “knee” in a customer report. Say that eligible host types are compared using purchased-host count and VCF licences measured in physical cores. Show **Alternative cloud host options** and describe each option's trade-off. Validate current price, region, quota, availability, workload performance, and commercial terms before purchase.

Use configured physical cores for workload fit. Use full physical silicon for portable VCF licensing even when the provider enables fewer cores. Never use logical threads as physical cores.

## Storage

The engine reports source in-use storage, provisioned storage, the selected growth allowance, and required target capacity separately. Do not treat raw HCI capacity as usable capacity.

It also compares provisioned VM and template storage with unique addressable datastore capacity from `vDatastore`. Call this **provisioning headroom**:

```text
provisioning headroom = addressable datastore capacity - provisioned storage
provisioning headroom percentage = provisioning headroom / provisioned storage x 100
```

Emit **Limited storage headroom** when the percentage is 25% or less:

- `medium` when provisioned storage equals or exceeds addressable capacity;
- `low` when positive headroom is 10% or less;
- `information` when headroom is above 10% and no more than 25%.

This is a design-planning indicator, not proof of an immediate shortage. Thin provisioning means provisioned storage can exceed current consumption or physical capacity. Deduplicate datastores by vCenter, datacenter, and datastore name. If `vDatastore` is absent or incomplete, disclose the coverage gap instead of inferring a clean result.

- For OCVS standard shapes, size OCI Block Volume independently from compute and retain the automatically created management datastore in the design.
- For AVS and GCVE, apply the selected vSAN policy, failure-to-tolerate setting, rebuild reserve, required slack, and data-reduction assumption before concluding that local raw storage is sufficient.
- Model AVS external storage, GCVE storage-only nodes, or external NFS as separate choices when applicable.

## Scope and coverage

The engine prefers a VM's direct cluster field and can recover its cluster from related VM sheets when RVTools omits that field from `vInfo`. Duplicate workbook headers are preserved, and the last populated occurrence is used. Ambiguous or unattributed workloads are excluded from cluster sizing and reported as a bounded coverage gap.

Do not silently place unattributed workloads in the primary cluster. Ask for a mapping or explain how excluding them affects confidence.

## Report from the engine result

Lead with management-facing language. Keep internal identifiers such as `source_aligned`, floor names, binding constraints, and the selection strategy out of headings and primary tables. For every target cluster, show:

- role and source-to-target mapping;
- VM count, vCPU, configured RAM, and storage demand;
- selected planning assumptions and target host type;
- the management-facing host recommendation fields from `recommendation.presentation`;
- normal and post-failure CPU and memory percentages;
- largest-VM memory fit;
- full-silicon VCF cores;
- alternatives and validation warnings.

Use these section names where applicable:

- **Selected design: retain the existing cluster structure** or **Selected design: consolidate workloads into fewer clusters**;
- **How the host recommendation was determined**;
- **Storage capacity and service limits**;
- **CPU compatibility and migration options**;
- **Alternative cloud host options**;
- **What consolidation would change**;
- **What the estimate includes**.

Use `sizing_summary` for conversational estate totals and `sizing_cluster` for per-cluster workings. The index precomputes both policies and both topologies so follow-up questions use the same deterministic figures as the report.

When the report needs commercial quantities or public list prices, pass the completed sizing result to the provider-neutral BOM engine and follow [bom.md](bom.md). Do not let pricing availability change the selected host count.

## Primary sources

- [Oracle OCVS cluster addition and workload-cluster limits](https://docs.oracle.com/en-us/iaas/Content/VMware/Tasks/cluster-add.htm)
- [Oracle OCVS overview and supported shapes](https://docs.oracle.com/en-us/iaas/Content/VMware/Concepts/ocvsoverview.htm)
- [Microsoft AVS architecture and cluster limits](https://learn.microsoft.com/en-us/azure/azure-vmware/architecture-private-clouds)
- [Microsoft AVS deployment planning](https://learn.microsoft.com/en-us/azure/azure-vmware/plan-private-cloud-deployment)
- [Google Cloud VMware Engine components and cluster limits](https://cloud.google.com/vmware-engine/docs/concepts-vmware-components)
- [Broadcom VCF physical-core counting](https://knowledge.broadcom.com/external/article/313548/counting-cores-for-vmware-cloud-foundati.html)
