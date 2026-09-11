![RVTools Analyzer. Ask questions about VMware inventory and turn RVTools exports into migration, readiness, and health-check reports.](images/readme-hero.svg)

## What it can do

- Answer questions about VMs, operating systems, power states, hosts, clusters, and hardware.
- Calculate CPU and memory overcommit ratios.
- Review VMware Cloud Foundation readiness.
- Compare HCX vMotion, Replication Assisted vMotion (RAV), Bulk Migration, and Cold Migration per VM.
- Estimate required VCF cores and included, additional, or surplus vSAN capacity.
- Run vSphere health checks, including host hardware and guest operating-system lifecycle and support status.
- Assess each workload for migration to OCVS, AVS, or GCVE using HCX vMotion, Replication Assisted vMotion (RAV), Bulk Migration, or Cold Migration.
- Size cloud VMware clusters with repeatable CPU, memory, failure-capacity, storage, and full-silicon VCF calculations (as per updated core-counting guidance of June 17, 2026. [Broadcom KB 313548](https://knowledge.broadcom.com/external/article/313548/counting-cores-for-vmware-cloud-foundati.html)).
- Explore OCVS shapes, AVS hosts, and GCVE nodes through normal questions.
- Create self-contained HTML and Markdown reports.

## Sample reports

- [Download the synthetic health-check sample (PDF)](pdf/health-check-report-sample.pdf)
- [Download the synthetic OCVS migration sample (PDF)](pdf/ocvs-migration-analysis-sample.pdf)
- [Download the synthetic OCVS sizing sample (PDF)](pdf/ocvs-sizing-report-sample.pdf)

All three reports use fully synthetic data and contain no customer-derived inventory.

## Conversational inventory questions

You do not need to run a full assessment to explore an RVTools export. Ask normal questions such as how many Linux VMs are powered on, which hosts have inactive Hyper-Threading, or what the CPU overcommit ratio is for a particular cluster. Follow-up questions can filter, group, count, or compare VMs, hosts, clusters, datastores, disks, networks, snapshots, licence inventory, migration results, cloud node types, and sizing results. Answers state the filters and defaults used, and report unknown or missing data instead of filling in the gaps.

The first question creates a private local index that can be reused for the same workbook, making later questions faster. The index contains only approved inventory fields and leaves out annotations, snapshot descriptions, credentials, licence keys, serial numbers, and other sensitive free text. Straightforward questions get a direct answer; when you ask what the data means or what to do next, the skill applies the relevant health, migration, licensing, or sizing guidance.

[See conversational examples here](https://github.com/KimTholstorf/rvtools-skill#examples)

## vSphere health checks

The health check reviews hosts, VMs, datastores, networks, snapshots, VMware Tools, and virtual hardware for operational debt or configuration risks. It also reports CPU and memory overcommit for powered-on workloads by cluster and across the exported estate. Powered-off demand is shown separately, and missing RVTools sheets or fields are called out so gaps are not mistaken for a clean result.

Where host data is available, the report covers server and CPU models, BIOS and ESXi versions, and whether Hyper-Threading is available and active. Each distinct server model is checked against current vendor lifecycle sources. If an exact model match cannot be verified, the report records a coverage gap instead of guessing. Health thresholds are screening rules, not a substitute for performance history or a detailed platform review.

```bash
Run a vSphere health check on this RVTools export and create an HTML report.
```

## Cloud VMware migration assessments

For OCVS, AVS, and GCVE assessments, the skill checks every non-template VM against each HCX migration method. A workload is reported as `eligible`, `conditional`, `blocked`, or `unknown`, with the reasons kept alongside the result. Missing compatibility data is reported as unknown instead of quietly passing the VM.

The assessment also covers provider-specific planning details such as target CPU compatibility, AVS host types, GCVE node families, storage architecture, regional availability, networking, and licensing checks. These catalogs are dated snapshots of vendor documentation. The skill checks current primary sources before using them in a customer design.

```bash
Assess this RVTools export for an OCVS migration using HCX and create an HTML report.
```

## Cloud VMware sizing

Sizing for OCVS, AVS, and GCVE now comes from a shared Python engine, so the same workbook and assumptions produce the same result in Claude and Codex. It calculates each cluster’s CPU, memory, one-host-loss capacity, provider minimum, storage demand, and full-silicon VCF requirement. The report shows which constraint set the final host count instead of simply adding an N+1 host to every cluster.

The recommended policy includes all non-template workloads, regardless of power state. It uses a 4:1 vCPU-to-physical-core ratio, 20% CPU and memory headroom, configured memory as a sizing constraint, one-host-loss validation, and 25% headroom on provisioned storage. OCVS reports call this the Oracle default sizing policy. AVS and GCVE reports call it the recommended sizing policy.

If you want a leaner estimate, ask for the active-only policy. That option sizes compute from powered-on, non-template VMs, applies no generic CPU or memory headroom, and allows aggregate memory overcommit. It still checks one-host-loss CPU capacity and whether the largest VM fits on a host. The selected policy is always named in the result.

If the scope contains several source clusters, the skill asks whether to consolidate them into fewer target clusters or keep one target cluster for each source cluster. It sizes the chosen layout in detail and adds a short comparison of the other option, including the difference in cluster count, purchased hosts, N+1 capacity, and VCF cores. It does not assume consolidation on the user's behalf.

When no node type is supplied, the engine compares valid choices and selects a practical trade-off between host count and full-silicon VCF cores. That is a planning recommendation, not a price quote. Region, availability, quota, workload performance, and commercial terms still need checking before purchase.

Workload capacity is calculated from the cores made available by the selected node, while portable VCF licensing counts every physical silicon core in each purchased host. A reduced-core cloud configuration therefore does not reduce the VCF core count. This follows Broadcom's [core-counting guidance](https://knowledge.broadcom.com/external/article/313548/counting-cores-for-vmware-cloud-foundati.html). Storage remains a separate design decision because vSAN policy overhead, rebuild reserve, required free space, and migration staging affect usable capacity.

The same calculation engine can size new on-premises VCF hardware once you provide a verified bill of materials. It will not assume that the current hosts are the right target design.

```bash
Size an OCVS target cluster for this RVTools export and create an HTML report with the assumptions and VCF licensing estimate.
```

## Requirements

You will need:

- Claude Code, Claude Desktop, or Codex/ChatGPT desktop with the relevant skill or plugin support.
- Python 3.8 or newer with the standard-library `venv` module.
- Network access on first use if the pinned Python dependencies are not already available.

The launcher does not use `sudo` or install packages globally. If the required packages are missing, it creates a private Python environment in the plugin's writable data directory and installs pinned, hash-verified versions of `openpyxl`, `et_xmlfile`, and `defusedxml` there.

## Install and update

### Claude Code

```bash
claude plugin marketplace add KimTholstorf/rvtools-skill
claude plugin install rvtools@rvtools-analyzer
```

If Claude asks for a plugin reload, run `/reload-plugins` or start a fresh session.

This installation works in the Claude Code CLI and in local sessions opened from the [Code tab in Claude Desktop](https://code.claude.com/docs/en/desktop). Both use the Claude Code plugin system, so you do not need the release ZIP for the Code tab.

You can chat normally or call the command directly:

```text
/rvtools:analyze How many powered-off VMs are in this workbook?
```

### Claude Desktop Chat

Use the ZIP only if you want RVTools Analyzer available in regular Claude conversations through the Chat tab. Installing the plugin with the Claude Code CLI does not add it to Claude Chat's separate custom-skills list.

1. Open the [latest GitHub release](https://github.com/KimTholstorf/rvtools-skill/releases/latest).
2. Under **Assets**, download `rvtools-skill-<version>.zip`. Do not use GitHub's automatically generated source-code ZIP.
3. In Claude Desktop, open **Settings → Customize → Skills → Add → Upload a skill**.
4. Select the downloaded ZIP and enable **RVTools Analyzer**.

The release ZIP is built only after the tagged commit passes CI. It contains the standalone bundle required by Claude's [custom-skill upload](https://support.claude.com/en/articles/12512180-use-skills-in-claude). Once enabled, start a chat and attach an RVTools export. The `/rvtools:analyze` command belongs to the Claude Code plugin and is not used in ordinary Chat conversations.

### Codex

```bash
codex plugin marketplace add KimTholstorf/rvtools-skill
codex plugin add rvtools-analyzer@rvtools-analyzer
```

You can also find RVTools Analyzer in the ChatGPT desktop Plugins Directory after adding the marketplace. Start a new task once installation finishes.

Then chat normally or invoke the skill explicitly:

```text
$rvtools-analyzer Run an OCVS migration analysis on this RVTools export.
```

### Updating

For Claude Code:

```bash
claude plugin update rvtools@rvtools-analyzer
```

Restart Claude Code when the update finishes, or run `/reload-plugins` if prompted.

For Codex:

```bash
codex plugin marketplace upgrade rvtools-analyzer
```

This refreshes the installed marketplace snapshot. Start a new Codex task afterward so it loads the updated plugin.

## Examples

Attach an RVTools `.xlsx` export, or provide its local path, and ask something like:

- “How many virtual machines are powered off?”
- “How many Linux VMs run in each cluster?”
- “What are the CPU and memory overcommit ratios for cluster Production?”
- “List the host vendors, models, CPU models, and Hyper-Threading state.”
- “Which VMs run guest operating systems that are out of support or in extended support?”
- “What VMware licences are recorded in this export? Don’t show the licence keys.”
- “How many VCF cores does this estate need, and will it need extra vSAN capacity?”
- “Run a vSphere health check and create an HTML report.”
- “Assess this environment for an OCVS migration using HCX.”
- “Which VMs would block RAV when moving to Azure VMware Solution (AVS)?”
- “How many VMs are eligible for Bulk Migration to AVS, grouped by cluster?”
- “Assess this estate for Google Cloud VMware Engine (GCVE), and compare the suitable node types.”
- “Show the CPU, memory, and raw storage for GCVE ve2-standard-128.”
- “Size this estate for OCVS with the recommended policy and preserve the populated source clusters.”
- “Show how the OCVS result changes with active-only sizing.”

Short factual questions get a direct answer in chat. A full assessment creates an HTML report in an interactive session or a Markdown report in a file-oriented session, unless you ask for a different supported format.

## Data handling and privacy

An RVTools export can describe nearly every corner of a VMware environment, so treat it like sensitive infrastructure documentation. When Codex, Claude Code, or another local agent can access the filesystem, provide the workbook's local path instead of attaching it. This avoids creating a separate uploaded copy and lets the skill work with the file where it already resides.

Using a local path does not make the session fully offline. The AI platform may still process the question, selected findings, bounded query results, and report text. If the chat cannot access local files and the workbook must be attached, the platform's file-handling and retention terms apply. Use an account and data-control policy approved for the information in the export.

The skill limits exposure by:

- Reading the source in place, preserving it, and writing reports separately.
- Keeping parser output and the private SQLite query index on the local filesystem.
- Leaving annotations, snapshot descriptions, credentials, licence keys, serial numbers, and other sensitive free text out of the conversational index.
- Returning counts and bounded examples instead of dumping full infrastructure inventories into the conversation.
- Using only the minimum vendor and model identifiers needed for public hardware lifecycle research, never the raw workbook.

The parser and query scripts contain no workbook-upload code. Network access may still be used on first run to download pinned Python dependencies from the configured package index. Lifecycle, compatibility, and current product checks may consult public vendor documentation using only the identifiers needed for the lookup.

## Scope and limitations

An RVTools export is a snapshot, not a readiness certificate. An `eligible` result means that the available workbook data did not reveal a blocker for that method. It does not prove that a migration will work from end to end. Final decisions still need the relevant VMware HCX validation, a target design review, hardware compatibility or BOM checks, performance history, licensing confirmation, and current vendor documentation.

The reports label project thresholds as heuristics rather than vendor limits. Product support, compatibility, licensing, and lifecycle details change over time, so the agent must check current primary sources before relying on them.

## Development

Run the automated tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

Validate Claude packaging:

```bash
claude plugin validate --strict .
```

Codex plugin and skill manifests live under `.codex-plugin/`, `.agents/plugins/`, and `skills/`.

## Versioning

RVTools Analyzer follows semantic versioning. Until 1.0, interfaces and finding thresholds may change as people use the skill and report what works. Claude and Codex plugin manifests always carry the same version.

## License

Released under the [MIT License](LICENSE).
