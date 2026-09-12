---
name: rvtools-analyzer
description: Analyze and conversationally query VMware RVTools multi-sheet .xlsx exports, and produce evidence-based assessments, cloud sizing, and provider-priced BOMs for Oracle Cloud VMware Solution (OCVS), Azure VMware Solution (AVS), or Google Cloud VMware Engine (GCVE) migrations with VMware HCX, on-premises VMware Cloud Foundation (VCF) re-platforming, or general vSphere health, hardware lifecycle, guest operating-system lifecycle, security, licensing, and capacity. Use when an agent receives an RVTools export or is asked factual inventory questions, VM/host/cluster counts, server vendor/model, CPU or Hyper-Threading questions, guest OS or OS support questions, filtered or grouped inventory queries, migration blockers, HCX readiness, VCF readiness, cloud price or BOM estimates, snapshot or disk risk, network configuration, overcommit, VM sprawl, end-of-sale/support status, or infrastructure health from RVTools data.
---

# RVTools Analyzer

Turn an RVTools export into deterministic facts or query results first, then apply a lens only when interpretation is requested.

## Route the request

Classify each request before selecting a lens:

- For a factual inventory question, use query mode and read [references/querying.md](references/querying.md). Do not require a lens.
- For an assessment or recommendation, parse the workbook and select one lens below.
- For a mixed request, query the facts first, then interpret those results through the requested or clearly implied lens.

Reuse the same workbook and local query index for conversational follow-ups. Reset the index when the user changes the workbook.

For current VMware licence inventory or VCF/vSAN subscription-capacity questions, use the `license`, `vcf_license`, and `vcf_license_summary` query entities described in [references/querying.md](references/querying.md), then apply [references/vcf_onprem.md](references/vcf_onprem.md). Never reproduce a licence key.

For conversational questions about unsupported, end-of-life, or extended-support guest operating systems, query the distinct VM `guest_os` values and follow [references/guest_os_lifecycle.md](references/guest_os_lifecycle.md). Do not answer from a static lifecycle table.

## Select the lens

Map the user's intent to exactly one lens unless they explicitly request a comparison or combined assessment:

- OCVS or Oracle Cloud VMware Solution: use `hcx_ocvs`; read [references/hcx_common.md](references/hcx_common.md), then [references/hcx_ocvs.md](references/hcx_ocvs.md).
- AVS or Azure VMware Solution: use `hcx_avs`; read [references/hcx_common.md](references/hcx_common.md), then [references/hcx_avs.md](references/hcx_avs.md).
- GCVE or Google Cloud VMware Engine: use `hcx_gcve`; read [references/hcx_common.md](references/hcx_common.md), then [references/hcx_gcve.md](references/hcx_gcve.md).
- HCX, RAV, vMotion, Bulk Migration, or cloud migration without a named target: ask which of OCVS, AVS, or GCVE is intended.
- VMware Cloud Foundation, VCF, workload domain, management domain, convergence, import, or on-premises re-platforming: use `vcf_onprem` and read [references/vcf_onprem.md](references/vcf_onprem.md). For target-hardware sizing, also read [references/sizing.md](references/sizing.md) and require a verified VCF hardware profile.
- Health check, hygiene, capacity, sprawl, snapshot debt, hardware lifecycle, security posture, licensing exposure, or general environment review: use `hygiene` and read [references/hygiene.md](references/hygiene.md). For every hygiene assessment with `vHost` data, also read and follow [references/hardware_lifecycle.md](references/hardware_lifecycle.md).

Ask which lens to use when the intent is ambiguous. Do not run every lens or cloud target by default. For an explicitly combined request, keep each lens's conclusions separate and deduplicate shared findings.

For every hygiene assessment or OCVS, AVS, or GCVE migration report with `vInfo` data, also read and follow [references/guest_os_lifecycle.md](references/guest_os_lifecycle.md). Keep guest-OS lifecycle separate from deterministic HCX method screening.

For an OCVS, AVS, or GCVE sizing report with more than one source cluster in scope, inspect the scope first and ask the user to choose consolidated or source-aligned target clusters unless their request already makes that choice. Do not generate the sizing report while this material design input is unresolved. Follow the topology definitions and calculation rules in [references/hcx_common.md](references/hcx_common.md). A single source cluster does not require this question.

For every cloud sizing request, also read [references/sizing.md](references/sizing.md). Use the deterministic Python result as the calculation record. The `recommended` policy is the baseline unless the user deliberately asks for `active_only` or supplies different assumptions.

For a cloud sizing report or BOM request, also read [references/bom.md](references/bom.md). Resolve the sizing topology first, then append the provider-specific BOM from the same sizing result. Default to USD unless the user asks for another currency. Require an exact region for priced AVS and GCVE output; keep the BOM unpriced rather than guessing when pricing inputs or API access are unavailable.

Treat a future lens as another file under `references/`. Let that reference declare which parser detection IDs or categories it interprets; do not duplicate parsing logic or require a separate workbook pass.

## Protect the export

Treat RVTools exports, parser JSON, and reports as sensitive infrastructure data.

- Keep the workbook and derived data local unless the user explicitly authorizes another destination.
- Never upload raw data to a web service for analysis or source research.
- Do not echo annotation text, snapshot descriptions, license keys, serial numbers, credentials, or full network inventories unnecessarily.
- Preserve the source workbook; write outputs to a separate path.
- Treat the SQLite query index as sensitive derived data, create it with owner-only permissions, and keep it local.
- Bound affected-object examples. Prefer counts plus the few objects needed for remediation.

## Parse deterministically

Locate this skill directory, then run:

```bash
python3 scripts/parse_rvtools.py /absolute/path/to/export.xlsx --pretty --max-examples 25 --output /safe/local/path/rvtools-analysis.json
```

For a cloud migration assessment, add exactly one target:

```bash
python3 scripts/parse_rvtools.py /absolute/path/to/export.xlsx --target ocvs --pretty --output /safe/local/path/ocvs-analysis.json
python3 scripts/parse_rvtools.py /absolute/path/to/export.xlsx --target avs --pretty --output /safe/local/path/avs-analysis.json
python3 scripts/parse_rvtools.py /absolute/path/to/export.xlsx --target gcve --pretty --output /safe/local/path/gcve-analysis.json
```

For a sizing result, add the chosen topology. The recommended policy is applied by default:

```bash
python3 scripts/parse_rvtools.py /absolute/path/to/export.xlsx --target ocvs \
  --sizing-topology source_aligned --include-bom --currency USD \
  --pretty --output /safe/local/path/ocvs-sizing.json
```

Use `--sizing-policy active_only` only when the user deliberately selects the less conservative active-workload model. Use `--primary-source-cluster` when the primary or unified-management mapping is known.

Use `--vcf-entitlement-cores` only when the user supplies or confirms the actual portable VCF entitlement. Otherwise the BOM compares the target with the in-scope hosts' calculated requirement and labels that figure as a hardware proxy.

Use `--target-node` and `--target-region` only when the user has selected them. For OCVS, use `--target-cpu-vendor Intel|AMD` when known; otherwise retain the target CPU vendor manual gate.

The script requires Python 3 and `openpyxl`. If `openpyxl` is unavailable, use an environment-provided Python runtime that already includes it or report the dependency clearly. Do not upload the workbook or substitute model-based spreadsheet reading for the deterministic pass.

The parser emits:

- `source`: file identity, RVTools version, export time, and available sheets;
- `inventory`: workload, template, host, cluster, datastore, disk, NIC, and snapshot counts;
- `capacity_mib`: VM and datastore storage totals;
- `overcommit`: per-cluster and overall CPU and memory allocation ratios for powered-on workloads, plus powered-off inventory and coverage warnings;
- `facts`: power state, ESXi version, host vendor/model, CPU vendor/model, Hyper-Threading, and VM hardware distributions;
- `detections`: provider-neutral source-health rule ID, severity, category, tags, count, and bounded safe examples;
- `migration`: when `--target` is supplied, the target profile, exact per-VM/per-method screening, findings, manual gates, and dated vendor source catalog;
- `sizing`: when `--target` is supplied, either the deterministic sizing result or a topology-selection prompt for a multi-cluster scope;
- `bom`: when `--include-bom` is supplied, provider-specific quantities, public list-price evidence, monthly estimates, and current-estate versus target VCF cores;
- `warnings`: missing sheets and resulting coverage gaps.

Stop and report an invalid-input error if `vInfo` is absent. Continue with explicit coverage limitations when optional sheets are missing.

## Query conversationally

For factual or follow-up questions, use the allowlisted query tool rather than inventing spreadsheet code:

```bash
python3 scripts/query_rvtools.py /absolute/path/to/export.xlsx \
  --index /safe/session/path/rvtools-query.sqlite \
  --entity vm --metric count --filter guest_os_family=linux
```

Translate the user's wording into the CLI's structured fields and filters according to [references/querying.md](references/querying.md). Return exact aggregates and state the applied scope. Use bounded row listings only when the user asks which objects are affected. Never query or reproduce non-allowlisted sensitive text.

For an estate-wide VCF licensing estimate, query `vcf_license_summary`. If the user supplies verified raw vSAN capacity, pass it with `--vsan-raw-tib`; otherwise preserve the result's vSAN evidence label and caveat. Use `vcf_license` for per-host or per-cluster workings and `license` for sanitized current assignments.

For migration questions, query `migration_method` for exact VM/method outcomes, `migration_finding` for affected workloads and reasons, and `target_node` for the dated OCVS, AVS, or GCVE node catalog. Filter by `target=ocvs|avs|gcve`. Use `configured_physical_cores` for usable compute capacity, but always use `silicon_cores` and `vcf_licensable_cores` for portable-VCF licensing. Never reduce the VCF count because a provider exposes or enables only part of the processor. Always retain the screening-not-validation warning.

For sizing questions, query `sizing_summary` for estate or topology totals and `sizing_cluster` for the per-cluster node, constraint floors, utilization, one-host-loss result, and VCF cores. Filter by target, policy, and topology. These records are precomputed by the same engine used by parser reports; do not recalculate them in prose.

## Interpret the selected lens

1. For a migration lens, use the selected target's `migration` result as the method decision record. Use provider-neutral `detections` only as supporting health, capacity, security, or remediation evidence.
2. Apply the shared HCX reference and the selected provider reference. For VCF or health checks, use the relevant detection categories and the lens reference. Do not convert a heuristic into a vendor limit.
3. Distinguish:
   - documented blocker or requirement;
   - warning that needs remediation or validation;
   - planning input;
   - coverage gap outside RVTools.
4. Keep source facts separate from inference. State assumptions about target release, target shape, migration profile, storage architecture, or VCF workflow.
5. Do not claim that RVTools alone proves migration or VCF readiness. Require HCX Validate, HCL/BOM checks, target design validation, and performance history where applicable.
6. Re-verify time-sensitive product versions, node or host types, compatibility, licensing, regional availability, and limits against current Oracle, Microsoft, Google, or Broadcom primary documentation when those details affect the conclusion.
7. For the hygiene lens, research every distinct nonblank host vendor/model against current primary vendor lifecycle sources. Record the exact matched scope and as-of date; never equate End-of-Sale with end of support. Report missing vendor/model data or an unverified model match as a coverage gap.
8. For guest-OS lifecycle, research exact in-scope releases against current primary-vendor sources. Treat extended-support availability as distinct from customer entitlement, keep ambiguous versions unknown, and never change an HCX method result because of OS lifecycle.
9. For OCVS, AVS, or GCVE sizing, use the deterministic `sizing` result. Calculate workload fit from configured capacity and VCF licensing from full physical silicon. Include the VCF-core obligation when comparing node types, including reduced-core and storage-only variants. Withhold the licensing recommendation if the full silicon count cannot be verified from current provider and Broadcom documentation.
10. For multi-cluster sizing, make the user's topology choice the primary sizing recommendation and include a brief reverse-topology comparison. Never present consolidated sizing as the assumed default.
11. For a cloud BOM, use the provider adapter's rows without renaming API-native identifiers. Calculate the current-estate VCF requirement from in-scope hosts and the target requirement from full physical silicon. Preserve `partial` or `unpriced` status and never fill a missing rate with an estimate from another region, currency, or SKU.

## Produce the report

Honor the requested format. If none is stated:

- For a factual query or conversational follow-up, answer directly in chat; do not create a full report unless requested.
- For an assessment in interactive chat, create a visual self-contained HTML report using [assets/report-template.html](assets/report-template.html) and also give a short chat summary.
- For scripted, terminal, or file-oriented use, create a Markdown report.

Use this information order:

1. Executive assessment and confidence.
2. Assessment scope and coverage.
3. Inventory and capacity snapshot.
4. Findings by severity with affected counts, safe examples, impact, and next action.
5. Lens-specific readiness or migration-profile implications.
6. For cloud sizing, the primary topology design and a concise reverse-topology comparison.
7. Prioritized remediation plan: before design, before pilot, before wave, after move.
8. Coverage gaps and additional evidence required.
9. Method, thresholds, assumptions, source workbook hash, and authoritative source links.
10. Acronym glossary.
11. For cloud sizing, Bill of materials and public list-price estimate.

In **Assessment scope and coverage**, state whether the report covers the full exported estate or a filtered selection. Show selected versus exported counts for vCenters, datacenters, clusters, hosts, workload VMs, powered-on VMs, and templates when those fields are available. Name every selected vCenter and datacenter, and list cluster names when ten or fewer are selected; otherwise give the count and a bounded appendix. Datacenter names must not replace cluster names when the user selected individual clusters.

Establish the filter before calculating any result. Apply the same scope filter to inventory, sizing, migration methods, findings, remediation counts, and licensing. Explicitly list excluded clusters or the exclusion rule. If an entity cannot be attributed to the selection because its RVTools relationship field is missing, omit the scoped total and report a coverage gap. When no filter was requested, say “full exported estate”; do not imply that one workbook necessarily represents the customer's entire VMware environment.

For HTML, keep it self-contained with no remote scripts, fonts, analytics, or data calls. Replace the template placeholders, remove unused sections, escape source-derived strings, and avoid embedding the full parser JSON.

For Markdown, use compact tables only where they improve comparison. Write exact affected counts and label truncated example lists.

End assessment reports with a concise acronym glossary. Define only abbreviations used in the report, including product names and migration methods such as HCX and RAV. Describe HCX as the VMware workload-mobility and network-extension platform; do not force an obsolete product-name expansion. Spell out an acronym on first use where that improves readability, even when it also appears in the glossary.

## Quality checks

Before finishing:

- Confirm the reported inventory totals match parser JSON.
- Confirm factual answers match query JSON and state whether templates, power states, filters, grouping, or row limits affected the result.
- Confirm hygiene reports state the overcommit formulas, powered-on scope, and powered-off exclusions exactly as emitted by the parser.
- Confirm every finding belongs to the selected lens or is clearly labeled shared context.
- Confirm migration reports use the selected target only, show per-method statuses, preserve manual gates, and state the target catalog review date.
- Confirm no matched secret value is present in the report.
- Confirm warning and coverage-gap sections reflect missing sheets.
- Confirm thresholds are labeled vendor-backed or project heuristic according to the lens reference.
- Confirm a hygiene assessment with `vHost` data covers every distinct vendor/model with an authoritative lifecycle status or an explicit coverage gap, and reports Hyper-Threading availability versus active state without treating unknown as false.
- Confirm health and cloud migration reports classify every sufficiently specific in-scope guest OS using the shared lifecycle statuses, cite current primary-vendor sources, and keep ambiguous releases unknown. Confirm guest-OS lifecycle did not alter any HCX method status.
- Confirm recommendations do not imply changes were executed.
- Confirm a VCF licensing result uses physical cores with the per-CPU minimum, states the included host scope, and withholds the estate total when CPU topology is incomplete.
- Confirm every cloud-node recommendation distinguishes configured compute from full physical silicon and uses `vcf_licensable_cores`, not configured or disabled cores, for VCF licensing.
- Confirm every sizing report uses the deterministic engine result, names the selected policy, shows all binding host-count constraints, and does not add a failure host blindly to the provider minimum.
- Confirm OCVS reports call the recommended profile the Oracle default sizing policy. Confirm AVS and GCVE reports call it the recommended sizing policy and do not attribute it to Oracle.
- Confirm every multi-cluster cloud sizing report records the user's topology choice, shows the primary source-to-target cluster mapping, and includes the reverse-topology comparison using the same scope and assumptions.
- Confirm every priced cloud sizing report uses `bom.table`, names the currency, region and pricing model, distinguishes complete, partial and unpriced results, and does not present a partial subtotal as a grand total.
- Confirm current-estate VCF is labeled as a hardware-derived requirement unless actual entitlement was verified, and target VCF uses full physical silicon.
- Confirm a vSAN result distinguishes verified raw TiB from an RVTools datastore-capacity proxy and reports either add-on TiB or surplus TiB, never both as positive.
- Confirm scope coverage shows selected versus exported infrastructure and that every reported total uses the same scope filter.
- Confirm the acronym glossary defines every non-obvious abbreviation used in the report and contains no unused entries.
- Open or render the HTML artifact and fix clipped, unreadable, or empty sections.
