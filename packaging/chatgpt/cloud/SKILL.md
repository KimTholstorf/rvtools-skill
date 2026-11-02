---
name: rvtools-analyzer
description: Query an uploaded VMware RVTools XLSX export or create cloud VMware sizing, provider-priced BOM, migration, licensing, or vSphere health reports, including host hardware and guest OS lifecycle.
---

# RVTools Analyzer

This is the Cloud variant's ChatGPT runtime entrypoint, designed for uploaded workbooks. Resolve the skill directory from this file, read `WORKFLOW.md` completely, and use its shared analysis rules, references and report template. All script, reference and asset paths are relative to this skill directory, not the working directory.

## Files and privacy

Use the workbook path made available by the chat's file tools. A path on the user's computer is not a cloud-accessible file; if the workbook is unavailable, ask for an upload approved under the customer's data policy. Explain, before requesting an upload, that the workbook will be processed in the AI platform's cloud environment rather than remaining on the user's machine. Offer the local Codex or Claude Code installation when local file processing is required.

Never upload the workbook or derived inventory to another service. Public documentation research must use only the necessary product, vendor or model identifiers. Pricing requests may use only SKU, region, currency and pricing-model identifiers. Do not request API secrets in chat; without securely supplied runtime credentials, leave credential-dependent BOM lines unpriced.

Choose a writable session workspace outside the installed skill directory. Set `RVTOOLS_PLUGIN_DATA` to a private subdirectory there for runtime setup. Preserve the input workbook and put parser JSON, reports and the sensitive SQLite index in that workspace. Reuse the index while it remains available; rebuild from the workbook if the session workspace is reset. Do not promise cross-chat persistence or local-only processing.

## Run the shared engine

Use the available Python 3.8+ interpreter and override direct parser/query commands in `WORKFLOW.md` with the shared launcher:

```bash
python3 /path/to/skill/scripts/run_rvtools.py parse /path/to/upload.xlsx --pretty --output /writable/session/rvtools-analysis.json
python3 /path/to/skill/scripts/run_rvtools.py query /path/to/upload.xlsx --index /writable/session/rvtools-query.sqlite --entity vm --metric count --filter guest_os_family=linux
```

The bundle contains pinned, hash-verified dependency wheels. The launcher uses an exact compatible environment or installs those wheels into a private temporary virtual environment with the package index disabled. Never install globally or download substitute dependencies. If Python, `venv` or code execution is unavailable, explain the runtime limitation instead of attempting model-based workbook calculations.

Use the same sizing choices and defaults as `WORKFLOW.md`; cloud execution must not change them. When pricing APIs or vendor research are unavailable, report the coverage gap and keep unverified prices or lifecycle status unknown.

Create requested HTML and Markdown reports in the writable session workspace and return download links supported by the chat. A short factual question needs a direct answer, not a full report.
