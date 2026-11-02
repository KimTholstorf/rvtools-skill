---
name: rvtools-analyzer
description: Query a local VMware RVTools XLSX export or create cloud VMware sizing, provider-priced BOM, migration, licensing, or vSphere health reports using local file processing. Requires a local desktop executor.
---

# RVTools Analyzer Desktop

This variant requires local execution. Resolve the skill directory from this file, read `WORKFLOW.md` completely, and use its shared analysis rules, references and report template. All script, reference and asset paths are relative to this skill directory, not the working directory.

## Local files and privacy

Use the host-provided execution context to confirm this is a local task with authorized access to the user's computer. A filesystem path, operating-system name or the fact that the user opened a desktop app is not proof of local execution. If a local executor or its location cannot be confirmed, stop and explain that this variant needs a local desktop session. Do not fall back to cloud execution.

Ask for an accessible local workbook path when none is provided. Never request a workbook upload, pasted workbook contents, a remote share upload or a cloud workspace as a fallback. If the user has already attached a workbook, explain that the platform has received that uploaded copy; do not describe it as local-only. Ask for the original local path and use that file instead.

Preserve the source workbook. Run the parser and queries locally, and put reports, parser JSON and the sensitive SQLite index in a separate writable local workspace outside the installed skill directory. Set `RVTOOLS_PLUGIN_DATA` to a private subdirectory there for runtime setup. Reuse the index for follow-ups and rebuild it when the workbook changes or the cache disappears. Return local report links, without uploading reports automatically.

Keep raw workbook processing on the user's machine. Send only the necessary counts, selected fields and bounded findings into model context; do not dump whole parser outputs, workbook contents or unrestricted inventories into the conversation. Never send the workbook, index or customer reports to another service. Public research may use only the necessary vendor, product or model identifiers; pricing may use only SKU, region, currency and pricing-model identifiers.

Explain the boundary honestly: local execution does not mean offline AI or device-only inference. Relevant findings, prompts and tool results may still be processed by OpenAI's models. Do not claim that no customer information leaves the computer or that instructions alone enforce a network-security boundary. If the customer needs fully offline operation, explain that this chat workflow does not meet that requirement.

## Run the shared engine

Use an available local Python 3.8+ interpreter and override direct parser/query commands in `WORKFLOW.md` with the shared launcher:

```bash
python3 /path/to/skill/scripts/run_rvtools.py parse /local/path/export.xlsx --pretty --output /local/report-workspace/rvtools-analysis.json
python3 /path/to/skill/scripts/run_rvtools.py query /local/path/export.xlsx --index /local/report-workspace/rvtools-query.sqlite --entity vm --metric count --filter guest_os_family=linux
```

The bundle contains pinned, hash-verified dependency wheels. The launcher uses an exact compatible environment or installs those wheels into a private local virtual environment with the package index disabled. Never install globally or download substitute dependencies. If local Python, `venv`, file permissions or code execution are unavailable, report the missing prerequisite and stop rather than moving the workbook elsewhere.

Use the same sizing choices and defaults as `WORKFLOW.md`. When pricing APIs or vendor research are unavailable, keep prices or lifecycle status unknown. Do not request API secrets in chat; use securely provided runtime credentials or leave credential-dependent BOM lines unpriced.

Create requested HTML and Markdown reports locally. A short factual question needs a direct answer, not a full report.
