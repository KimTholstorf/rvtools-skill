![RVTools Analyzer. Ask questions about VMware inventory and turn RVTools exports into migration, readiness, and health-check reports.](images/readme-hero.svg)

## What it can do

- Answer questions about VMs, operating systems, power states, hosts, clusters, and hardware.
- Calculate CPU and memory overcommit ratios.
- Review VMware Cloud Foundation readiness.
- Compare HCX vMotion, Replication Assisted vMotion (RAV), Bulk Migration, and Cold Migration per VM.
- Estimate required VCF cores and included, additional, or surplus vSAN capacity.
- Run vSphere health checks, including hardware lifecycle and support status.
- Assess each workload for migration to OCVS, AVS, or GCVE using HCX vMotion, Replication Assisted vMotion (RAV), Bulk Migration, or Cold Migration.
- Size the target cluster from powered-on workloads, including N+1 capacity and VCF licensing based on each node’s full physical silicon (as per updated Broadcom silicon guidance of June 17, 2026. [Broadcom KB 313548](https://knowledge.broadcom.com/external/article/313548/counting-cores-for-vmware-cloud-foundati.html)).
- Explore OCVS shapes, AVS hosts, and GCVE nodes through normal questions.
- Create self-contained HTML and Markdown reports.

## Sample reports

- [Download the synthetic health-check sample (PDF)](pdf/health-check-report-sample.pdf)
- [Download the synthetic OCVS migration sample (PDF)](pdf/ocvs-migration-analysis-sample.pdf)
- [Download the synthetic OCVS sizing sample (PDF)](pdf/ocvs-sizing-report-sample.pdf)

All three reports use fully synthetic data and contain no customer-derived inventory.

## Conversational inventory questions

You do not need to run a full assessment to explore an RVTools export. Ask normal questions such as how many Linux VMs are powered on, which hosts have inactive Hyper-Threading, or what the CPU overcommit ratio is for a particular cluster. Follow-up questions can filter, group, count, or compare VMs, hosts, clusters, datastores, disks, networks, snapshots, licence inventory, migration results, and cloud node types. Answers state the filters and defaults used, and report unknown or missing data instead of filling in the gaps.

The first question creates a private local index that can be reused for the same workbook, making later questions faster. The index contains only approved inventory fields and leaves out annotations, snapshot descriptions, credentials, licence keys, serial numbers, and other sensitive free text. Straightforward questions get a direct answer; when you ask what the data means or what to do next, the skill applies the relevant health, migration, licensing, or sizing guidance.

## vSphere health checks

The health check reviews hosts, VMs, datastores, networks, snapshots, VMware Tools, and virtual hardware for operational debt or configuration risks. It also reports CPU and memory overcommit for powered-on workloads by cluster and across the exported estate. Powered-off demand is shown separately, and missing RVTools sheets or fields are called out so gaps are not mistaken for a clean result.

Where host data is available, the report covers server and CPU models, BIOS and ESXi versions, and whether Hyper-Threading is available and active. Each distinct server model is checked against current vendor lifecycle sources. If an exact model match cannot be verified, the report records a coverage gap instead of guessing. Health thresholds are screening rules, not a substitute for performance history or a detailed platform review.

## Cloud VMware migration assessments

For OCVS, AVS, and GCVE assessments, the skill checks every non-template VM against each HCX migration method. A workload is reported as `eligible`, `conditional`, `blocked`, or `unknown`, with the reasons kept alongside the result. Missing compatibility data is reported as unknown instead of quietly passing the VM.

The assessment also covers provider-specific planning details such as target CPU compatibility, AVS host types, GCVE node families, storage architecture, regional availability, networking, and licensing checks. These catalogs are dated snapshots of vendor documentation. The skill checks current primary sources before using them in a customer design.

## Cloud VMware sizing

Sizing for OCVS, AVS, and GCVE starts with powered-on, non-template VMs and reports powered-off workloads as excluded demand. The default model uses a 4:1 vCPU-to-physical-core ratio, no generic growth allowance, accepts aggregate memory overcommit, and adds one host for N+1 failure and patching capacity. The result shows the workload host count, N+1 host, memory ratio, largest-VM fit, and the assumptions behind the recommendation.

Workload capacity is calculated from the cores made available by the selected node, while portable VCF licensing counts every physical silicon core in each purchased host. A reduced-core cloud configuration therefore does not reduce the VCF core count. This follows Broadcom's [core-counting guidance](https://knowledge.broadcom.com/external/article/313548/counting-cores-for-vmware-cloud-foundati.html). Storage is kept separate because policy overhead, rebuild reserve, free space, and migration staging still need a design review.

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
codex plugin marketplace add KimTholstorf/rvtools-skill --ref main
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
- “What VMware licences are recorded in this export? Don’t show the licence keys.”
- “How many VCF cores does this estate need, and will it need extra vSAN capacity?”
- “Run a vSphere health check and create an HTML report.”
- “Assess this environment for an OCVS migration using HCX.”
- “Which VMs would block RAV when moving to Azure VMware Solution (AVS)?”
- “How many VMs are eligible for Bulk Migration to AVS, grouped by cluster?”
- “Assess this estate for Google Cloud VMware Engine (GCVE), and compare the suitable node types.”
- “Show the CPU, memory, and raw storage for GCVE ve2-standard-128.”

Short factual questions get a direct answer in chat. A full assessment creates an HTML report in an interactive session or a Markdown report in a file-oriented session, unless you ask for a different supported format.

## Data handling and privacy

An RVTools export can describe nearly every corner of a VMware environment, so treat it like sensitive infrastructure documentation. The skill tells the agent to:

- Keep the workbook, parser output, and SQLite query index local.
- Preserve the source workbook and write reports separately.
- Exclude annotations, snapshot descriptions, credentials, license keys, and serial numbers from the conversational index.
- Return bounded examples rather than full infrastructure inventories.
- Use only vendor and model identifiers—not the raw workbook—when researching hardware lifecycle status.

The parser and query scripts do not contain code that uploads the workbook. If you attach the file to Claude or ChatGPT, the platform's own file-handling and retention terms still apply. On first use, the launcher may contact the configured Python package index to download its pinned dependencies. Hardware lifecycle and compatibility checks may also consult public vendor documentation, but they use vendor and model identifiers rather than the workbook itself.

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
