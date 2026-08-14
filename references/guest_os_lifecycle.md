# Guest Operating-System Lifecycle

Use this reference for conversational guest-OS lifecycle questions and for every health-check or OCVS, AVS, or GCVE migration report that includes `vInfo` data. This check covers OS-vendor lifecycle only. Do not use it to decide VMware, target ESXi, application, or HCX compatibility.

## Source data and scope

Use the normalized VM `guest_os` value, which prefers the operating system reported by VMware Tools and falls back to the configured guest OS. Keep `guest_os_source` with the result. Exclude templates unless the user asks to include them, and apply the report's cluster, datacenter, vCenter, or other scope before counting statuses.

Query distinct `guest_os` values first, research each distinct value once, and then map the result back to the in-scope VMs. If the value does not identify a sufficiently exact product and release, classify it as `unknown`. Do not infer a specific version from broad values such as “Windows Server 2016 or later,” “Other Linux,” or a guest-family identifier.

## Current vendor verification

Lifecycle dates change and vendors use different phase names. During each assessment, verify the product and release against current primary vendor lifecycle documentation. Use third-party lifecycle sites only to discover the vendor source, never as the final authority. Search only the generic OS product and version; do not include VM names, customer names, host names, or other inventory data.

Record the vendor, normalized product and release, matched RVTools value, lifecycle status, applicable support phase, relevant end date, source URL, source publication or update date when available, assessment date, and match confidence. Preserve conflicting vendor evidence as a coverage gap.

Use exactly these statuses:

- `vendor_supported`: the release is within the vendor's ordinary supported phase, including the vendor's standard security-maintenance phase.
- `vendor_extended_support`: ordinary support has ended and the release is currently within an official extended, maintenance, sustaining-with-fixes, ESM, ESU, ELS, or LTSS phase. State the vendor's own phase name. Availability of that phase does not prove that the customer purchased or activated it; extended-support entitlement is not proven by RVTools.
- `vendor_out_of_support`: the vendor states that the release is end-of-life, or both ordinary support and any applicable time-bounded extended support have ended.
- `unknown`: the release is missing or ambiguous, no exact primary-vendor match is found, lifecycle evidence conflicts, or the product is an appliance or custom OS whose lifecycle cannot be established from RVTools.

Do not treat indefinite access to documentation, self-support, or sustaining support without new fixes as equivalent to an actively supported security-maintenance phase. Explain the vendor's terms when their lifecycle model does not fit neatly into the shared labels.

## Conversational answers

For questions such as “Which VMs run an unsupported OS?” or “Are any operating systems in extended support?”, query the VM entity using `guest_os`, `guest_os_source`, VM, power state, and the requested scope. Return counts by lifecycle status, the matched OS releases, applicable dates, primary sources, and bounded VM examples. State how many VMs remain `unknown` and why.

## Health-check reporting

Add a **Guest operating-system lifecycle** section to the health-check report:

- Report `vendor_out_of_support` as a high-priority health warning because routine vendor fixes and security updates are no longer available.
- Report `vendor_extended_support` as a medium-priority warning and require confirmation of the customer's entitlement, update channel, and upgrade plan.
- Report `unknown` as a coverage gap, not as supported or unsupported.
- Keep findings grouped by exact matched OS release with counts and bounded VM examples.

## Cloud migration reporting

Add a separate **Guest operating-system lifecycle awareness** section to every OCVS, AVS, or GCVE cloud migration report. Show the same status counts, dates, sources, and unknown coverage, but treat them as customer-owned lifecycle context only.

Guest-OS lifecycle findings must not change HCX migration-method statuses, eligibility counts, blockers, or method recommendations. Do not add them to HCX warnings or claim that an out-of-support OS cannot be moved. Make clear that the customer remains responsible for upgrading or obtaining the required vendor support.

## Quality checks

- Confirm every distinct, sufficiently specific in-scope OS release has a current primary-vendor source or an explicit `unknown` result.
- Confirm ordinary support, extended-support availability, and customer entitlement are not conflated.
- Confirm report totals map back to the same VM scope used elsewhere in the assessment.
- Confirm no guest-OS lifecycle result altered a deterministic HCX method outcome.
