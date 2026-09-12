# Deterministic Cloud VMware Sizing

Use this reference for OCVS, AVS, and GCVE sizing. The Python sizing engine is the calculation record. Do not recalculate host counts in prose or replace an engine result with mental arithmetic.

The arithmetic also supports on-premises VCF through an injected target hardware profile. Require a verified bill of materials with per-host configured cores, physical silicon cores, memory, cluster roles, and supported minimums. Do not infer a target VCF node from the source hosts. Without that profile, report workload demand and request the missing design input instead of inventing a host count.

## Choose the design inputs first

Before sizing more than one source cluster, ask whether the target should be:

- `consolidated`: compatible source clusters share the fewest practical target clusters;
- `source_aligned`: each populated source cluster keeps a separate target cluster.

Do not assume consolidation. If the user chooses source alignment, exclude source clusters with no hosts and list them in the scope. The engine selects the largest target workload as the primary or management cluster unless `--primary-source-cluster` supplies a deliberate choice. State that mapping in the report.

## Capacity policies

The default `recommended` policy uses:

- all non-template workloads, regardless of power state, for compute demand;
- a 4:1 configured-vCPU-to-configured-physical-core ratio;
- 20% normal-operation CPU headroom;
- 20% normal-operation memory headroom, with configured memory as a binding constraint;
- one-host-loss CPU and memory validation;
- provisioned storage for all selected VMs and templates, plus 25% storage headroom.

For OCVS, call this the **Oracle default sizing policy**. For AVS and GCVE, call it the **recommended sizing policy** and do not associate it with Oracle.

Use `active_only` only when the user deliberately selects it. It uses powered-on non-template workloads, a 4:1 CPU ratio, no generic CPU or memory headroom, and aggregate memory overcommit. It still validates one-host-loss CPU capacity and largest-VM memory fit. It includes all selected VMs and templates in provisioned storage but applies no generic storage headroom.

Neither policy is a substitute for performance history. Always request sustained CPU, memory, storage latency/IOPS, and network demand before a purchase commitment.

## Host-count constraints

For each candidate node, the engine calculates independent floors:

```text
normal CPU floor = ceil(vCPU / (configured cores × CPU ratio × (1 - CPU headroom)))
normal memory floor = ceil(configured RAM / (host RAM × (1 - memory headroom)))
one-host-loss CPU floor = ceil(vCPU / (configured cores × CPU ratio)) + 1
one-host-loss memory floor = ceil(configured RAM / host RAM) + 1
total hosts = max(normal floors, one-host-loss floors, provider minimum)
```

The memory floors are zero when the selected policy accepts aggregate memory overcommit. A provider minimum is itself purchased capacity. Never add another host blindly to that minimum. For example, an OCVS standard workload whose demand fits on one surviving host requires two hosts, not three.

Current production cluster constraints in the target catalog are:

- OCVS standard unified-management cluster: minimum 3, maximum 32;
- OCVS standard workload cluster: minimum 2, maximum 32;
- AVS cluster: minimum 3, maximum 16;
- GCVE standard cluster: minimum 3, maximum 32.

Recheck these limits against current provider documentation when they affect a customer design.

## Node selection

If the user names a node or host type, size that node and report an invalid selection rather than silently switching SKUs.

Without a selected node, the engine evaluates every compute node in the dated target catalog. It removes dominated choices and selects the knee of the Pareto frontier between:

- total purchased hosts;
- total full-silicon VCF cores.

This is a reproducible planning recommendation, not a price optimization. Show the retained alternatives and validate current price, region, quota, availability, workload performance, and commercial terms before purchase.

Use configured physical cores for workload fit. Use full physical silicon for portable VCF licensing even when the provider enables fewer cores. Never use logical threads as physical cores.

## Storage

The engine reports source in-use storage, provisioned storage, policy headroom, and required target capacity separately. Do not treat raw HCI capacity as usable capacity.

- For OCVS standard shapes, size OCI Block Volume independently from compute and retain the automatically created management datastore in the design.
- For AVS and GCVE, apply the selected vSAN policy, failure-to-tolerate setting, rebuild reserve, required slack, and data-reduction assumption before concluding that local raw storage is sufficient.
- Model AVS external storage, GCVE storage-only nodes, or external NFS as separate choices when applicable.

## Scope and coverage

The engine prefers a VM's direct cluster field and can recover its cluster from related VM sheets when RVTools omits that field from `vInfo`. Duplicate workbook headers are preserved, and the last populated occurrence is used. Ambiguous or unattributed workloads are excluded from cluster sizing and reported as a bounded coverage gap.

Do not silently place unattributed workloads in the primary cluster. Ask for a mapping or explain how excluding them affects confidence.

## Report from the engine result

For every target cluster, show:

- role and source-to-target mapping;
- VM count, vCPU, configured RAM, and storage demand;
- selected policy and node-selection strategy;
- each normal-operation, one-host-loss, and provider-minimum floor;
- total hosts and binding constraints;
- normal and post-failure CPU and memory percentages;
- largest-VM memory fit;
- full-silicon VCF cores;
- alternatives and validation warnings.

Use `sizing_summary` for conversational estate totals and `sizing_cluster` for per-cluster workings. The index precomputes both policies and both topologies so follow-up questions use the same deterministic figures as the report.

When the report needs commercial quantities or public list prices, pass the completed sizing result to the provider-neutral BOM engine and follow [bom.md](bom.md). Do not let pricing availability change the selected host count.

## Primary sources

- [Oracle OCVS cluster addition and workload-cluster limits](https://docs.oracle.com/en-us/iaas/Content/VMware/Tasks/cluster-add.htm)
- [Oracle OCVS overview and supported shapes](https://docs.oracle.com/en-us/iaas/Content/VMware/Concepts/ocvsoverview.htm)
- [Microsoft AVS architecture and cluster limits](https://learn.microsoft.com/en-us/azure/azure-vmware/architecture-private-clouds)
- [Microsoft AVS deployment planning](https://learn.microsoft.com/en-us/azure/azure-vmware/plan-private-cloud-deployment)
- [Google Cloud VMware Engine components and cluster limits](https://cloud.google.com/vmware-engine/docs/concepts-vmware-components)
- [Broadcom VCF physical-core counting](https://knowledge.broadcom.com/external/article/313548/counting-cores-for-vmware-cloud-foundati.html)
