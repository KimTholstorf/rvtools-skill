# RVTools Analyzer

RVTools Analyzer lets Claude Code and Codex query VMware RVTools XLSX exports conversationally and produce evidence-based OCVS/HCX migration, VCF readiness, and vSphere health-check assessments.

It combines a deterministic local Python analysis engine with agent-guided interpretation. Inventory values, overcommit ratios, query results, and built-in detections come from code; the agent applies the requested lens, researches time-sensitive vendor lifecycle facts, and writes the report.

## Capabilities

- Answer inventory questions such as VM counts, guest operating systems, power state, host hardware, and cluster membership.
- Calculate CPU and memory overcommit ratios for powered-on workloads.
- Assess OCVS and VMware HCX migration risks.
- Assess on-premises VMware Cloud Foundation readiness.
- Run a vSphere health check covering snapshots, tools, devices, networking, storage, capacity, hardware lifecycle, and Hyper-Threading.
- Produce self-contained HTML and Markdown reports.

## Requirements

- Claude Code or Codex/ChatGPT desktop with plugin support.
- Python 3.8 or newer with the standard-library `venv` module.
- Network access on first use if the pinned Python dependencies are not already available.

The launcher never uses `sudo` or installs packages globally. When needed, it creates a private environment in the plugin's writable data directory and installs pinned, hash-verified wheels for `openpyxl`, `et_xmlfile`, and `defusedxml`.

## Install with Claude

### Claude Code CLI

```bash
claude plugin marketplace add KimTholstorf/rvtools-skill
claude plugin install rvtools@rvtools-analyzer
```

If Claude asks you to reload plugins, run `/reload-plugins` or start a new session.

Use normal conversation or invoke the short command explicitly:

```text
/rvtools:analyze How many powered-off VMs are in this workbook?
```

### Claude Desktop

1. Open the [latest GitHub release](https://github.com/KimTholstorf/rvtools-skill/releases/latest).
2. Under **Assets**, download `rvtools-skill-<version>.zip`. Do not use GitHub's automatically generated source-code ZIP.
3. In Claude Desktop, open **Settings → Customize → Skills → Add → Upload a skill**.
4. Select the downloaded ZIP and enable **RVTools Analyzer**.

The release ZIP is built only after the tagged commit passes CI and contains the standalone skill bundle expected by Claude Desktop. Use normal conversation after enabling it; the `/rvtools:analyze` command belongs to the Claude Code plugin installation.

## Install in Codex

```bash
codex plugin marketplace add KimTholstorf/rvtools-skill --ref main
codex plugin add rvtools-analyzer@rvtools-analyzer
```

You can also install RVTools Analyzer from the added marketplace in the ChatGPT desktop Plugins Directory. Start a new task after installation.

Use normal conversation or invoke the skill explicitly:

```text
$rvtools-analyzer Run an OCVS migration analysis on this RVTools export.
```

## Examples

Attach or provide the local path to an RVTools `.xlsx` export, then ask:

- “How many virtual machines are powered off?”
- “How many Linux VMs run in each cluster?”
- “What are the CPU and memory overcommit ratios for cluster Production?”
- “List the host vendors, models, CPU models, and Hyper-Threading state.”
- “Run a vSphere health check and create an HTML report.”
- “Assess this environment for an OCVS migration using HCX.”

Simple factual questions return directly in chat. Assessments create an HTML report in interactive sessions and Markdown in file-oriented sessions unless you request another supported format.

## Data handling and privacy

RVTools exports contain sensitive infrastructure data. The skill instructs the agent to:

- Keep the workbook, parser output, and SQLite query index local.
- Preserve the source workbook and write reports separately.
- Exclude annotations, snapshot descriptions, credentials, license keys, and serial numbers from the conversational index.
- Return bounded examples rather than full infrastructure inventories.
- Use only vendor and model identifiers—not the raw workbook—when researching hardware lifecycle status.

The first-use Python dependency download contacts the configured Python package index. Hardware lifecycle and current compatibility research may access primary vendor documentation. The workbook itself is not intentionally uploaded by the skill or its scripts.

## Scope and limitations

RVTools is an inventory snapshot. It cannot by itself prove end-to-end migration or platform readiness. Final decisions still require relevant VMware HCX validation, target design review, hardware compatibility or BOM checks, performance history, licensing confirmation, and vendor documentation.

Project thresholds are labeled as heuristics. Time-sensitive product support, compatibility, licensing, and lifecycle claims must be verified against current primary sources.

## Development

Run the automated tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

Validate Claude packaging:

```bash
claude plugin validate --strict .
```

The repository also contains Codex plugin and skill manifests under `.codex-plugin/`, `.agents/plugins/`, and `skills/`.

## Versioning

RVTools Analyzer follows semantic versioning. Before 1.0, interfaces and finding thresholds may change based on user feedback. Plugin manifest versions are kept aligned across Claude and Codex.

## License

Released under the [MIT License](LICENSE).
