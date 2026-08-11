# Azure VMware Solution migration lens

Use this reference with [hcx_common.md](hcx_common.md) for the `hcx_avs` lens and parser target `avs`.

## Target facts to verify

The parser carries a dated planning catalog for AV36, AV36P, AV48, AV52, and AV64 host types. AV64 reports separate OSA and ESA capacity-tier values because the architecture changes the raw capacity. Treat the catalog as a convenient comparison table, not a live Azure capacity promise. Before recommending a SKU, verify its specifications, generation, regional availability, quota, and deployment constraints in Microsoft's [AVS host specification table](https://learn.microsoft.com/en-us/azure/azure-vmware/introduction), [Gen 2 guidance](https://learn.microsoft.com/en-us/azure/azure-vmware/native-introduction), and [AVS limits](https://learn.microsoft.com/en-us/azure/azure-vmware/azure-vmware-solution-limits).

AVS hosts use Intel processors. An AMD source host therefore blocks live CPU-state methods in the deterministic screen; Bulk or Cold remains a conditional powered-off route. Confirm exact EVC compatibility rather than treating all Intel generations as interchangeable.

## AVS-specific interpretation

- Verify source ESXi and vCenter support against the current HCX interoperability result. The parser deliberately does not hard-code a minimum version because support depends on the current HCX release and migration method.
- AVS is not an end-to-end IPv6 target. Any populated VM IPv6 evidence is a network redesign flag; confirm the current limitation and dual-stack requirements in [AVS networking guidance](https://learn.microsoft.com/en-us/azure/azure-vmware/tutorial-network-checklist).
- Verify HCX service-mesh sizing, appliances, ExpressRoute/Global Reach routing, MON, DNS/NTP, and firewall ports using [Configure VMware HCX in AVS](https://learn.microsoft.com/en-us/azure/azure-vmware/configure-vmware-hcx).
- Network Extension depends on supported source switching and a deliberate gateway cutover plan. Check route scale and the chosen AVS generation before building large stretched-network waves.
- Size storage from actual used capacity, growth, slack, and the selected vSAN failure-tolerance/RAID policy. If Azure NetApp Files or Elastic SAN is part of the design, model it separately instead of treating host raw capacity as universally usable.
- If portable VCF licensing is proposed, confirm entitlement quantity, term, portability rules, and coverage for every target host using [Portable VCF on AVS](https://learn.microsoft.com/en-us/azure/azure-vmware/vmware-cloud-foundations-license-portability). Do not infer contractual entitlement from RVTools.

## Assessment framing

Use Microsoft's [Azure Migrate AVS assessment calculations](https://learn.microsoft.com/en-us/azure/migrate/concepts-azure-vmware-solution-assessment-calculation) as a cross-check for sizing assumptions. Explain any difference between its utilization-based model and an RVTools configuration-only estimate.

Do not call a VM or wave AVS-ready until the target subscription/region, quota, SKU, connectivity, storage policy, and HCX Validate result are confirmed.
