---
name: rvtools-analyzer
description: Analyze and conversationally query VMware RVTools multi-sheet .xlsx exports, and produce evidence-based assessments for Oracle Cloud VMware Solution (OCVS) migrations with VMware HCX, on-premises VMware Cloud Foundation (VCF) re-platforming, or general vSphere hygiene, hardware lifecycle, health, security, licensing, and capacity. Use when an agent receives an RVTools export or is asked factual inventory questions, VM/host/cluster counts, server vendor/model, CPU or Hyper-Threading questions, guest OS questions, filtered or grouped inventory queries, migration blockers, HCX readiness, VCF readiness, snapshot or disk risk, network configuration, overcommit, VM sprawl, end-of-sale/support status, or infrastructure health from RVTools data.
---

# RVTools Analyzer

Turn an RVTools export into deterministic facts or query results first, then apply a lens only when interpretation is requested.

## Route the request

Classify each request before selecting a lens:

- For a factual inventory question, use query mode and read [references/querying.md](references/querying.md). Do not require a lens.
- For an assessment or recommendation, parse the workbook and select one lens below.
- For a mixed request, query the facts first, then interpret those results through the requested or clearly implied lens.

Reuse the same workbook and local query index for conversational follow-ups. Reset the index when the user changes the workbook.

## Select the lens

Map the user's intent to exactly one lens unless they explicitly request a comparison or combined assessment:

- OCVS, Oracle Cloud VMware Solution, HCX, cloud migration, RAV, vMotion, or Bulk Migration: use `hcx_ocvs` and read [references/hcx_ocvs.md](references/hcx_ocvs.md).
- VMware Cloud Foundation, VCF, workload domain, management domain, convergence, import, or on-premises re-platforming: use `vcf_onprem` and read [references/vcf_onprem.md](references/vcf_onprem.md).
- Health check, hygiene, capacity, sprawl, snapshot debt, hardware lifecycle, security posture, licensing exposure, or general environment review: use `hygiene` and read [references/hygiene.md](references/hygiene.md). For every hygiene assessment with `vHost` data, also read and follow [references/hardware_lifecycle.md](references/hardware_lifecycle.md).

Ask which lens to use when the intent is ambiguous. Do not run all three by default. For an explicitly combined request, keep each lens's conclusions separate and deduplicate shared findings.

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

The script requires Python 3 and `openpyxl`. If `openpyxl` is unavailable, use an environment-provided Python runtime that already includes it or report the dependency clearly. Do not upload the workbook or substitute model-based spreadsheet reading for the deterministic pass.

The parser emits:

- `source`: file identity, RVTools version, export time, and available sheets;
- `inventory`: workload, template, host, cluster, datastore, disk, NIC, and snapshot counts;
- `capacity_mib`: VM and datastore storage totals;
- `overcommit`: per-cluster and overall CPU and memory allocation ratios for powered-on workloads, plus powered-off inventory and coverage warnings;
- `facts`: power state, ESXi version, host vendor/model, CPU vendor/model, Hyper-Threading, and VM hardware distributions;
- `detections`: rule ID, severity, category, supported built-in lenses, count, and bounded safe examples;
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

## Interpret the selected lens

1. Filter detections to the selected built-in lens using each detection's `lenses` list. For an added lens reference, use the detection IDs or categories named by that reference.
2. Apply the selected reference's interpretation. Do not convert a heuristic into a vendor limit.
3. Distinguish:
   - documented blocker or requirement;
   - warning that needs remediation or validation;
   - planning input;
   - coverage gap outside RVTools.
4. Keep source facts separate from inference. State assumptions about target release, target shape, migration profile, storage architecture, or VCF workflow.
5. Do not claim that RVTools alone proves migration or VCF readiness. Require HCX Validate, HCL/BOM checks, target design validation, and performance history where applicable.
6. Re-verify time-sensitive product versions, shapes, compatibility, licensing, and limits against current Oracle or Broadcom primary documentation when those details affect the conclusion.
7. For the hygiene lens, research every distinct nonblank host vendor/model against current primary vendor lifecycle sources. Record the exact matched scope and as-of date; never equate End-of-Sale with end of support. Report missing vendor/model data or an unverified model match as a coverage gap.

## Produce the report

Honor the requested format. If none is stated:

- For a factual query or conversational follow-up, answer directly in chat; do not create a full report unless requested.
- For an assessment in interactive chat, create a visual self-contained HTML report using [assets/report-template.html](assets/report-template.html) and also give a short chat summary.
- For scripted, terminal, or file-oriented use, create a Markdown report.

Use this information order:

1. Executive assessment and confidence.
2. Inventory and capacity snapshot.
3. Findings by severity with affected counts, safe examples, impact, and next action.
4. Lens-specific readiness or migration-profile implications.
5. Prioritized remediation plan: before design, before pilot, before wave, after move.
6. Coverage gaps and additional evidence required.
7. Method, thresholds, assumptions, source workbook hash, and authoritative source links.

For HTML, keep it self-contained with no remote scripts, fonts, analytics, or data calls. Replace the template placeholders, remove unused sections, escape source-derived strings, and avoid embedding the full parser JSON.

For Markdown, use compact tables only where they improve comparison. Write exact affected counts and label truncated example lists.

## Quality checks

Before finishing:

- Confirm the reported inventory totals match parser JSON.
- Confirm factual answers match query JSON and state whether templates, power states, filters, grouping, or row limits affected the result.
- Confirm hygiene reports state the overcommit formulas, powered-on scope, and powered-off exclusions exactly as emitted by the parser.
- Confirm every finding belongs to the selected lens or is clearly labeled shared context.
- Confirm no matched secret value is present in the report.
- Confirm warning and coverage-gap sections reflect missing sheets.
- Confirm thresholds are labeled vendor-backed or project heuristic according to the lens reference.
- Confirm a hygiene assessment with `vHost` data covers every distinct vendor/model with an authoritative lifecycle status or an explicit coverage gap, and reports Hyper-Threading availability versus active state without treating unknown as false.
- Confirm recommendations do not imply changes were executed.
- Open or render the HTML artifact and fix clipped, unreadable, or empty sections.
