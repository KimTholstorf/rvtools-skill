# Contributing to RVTools Analyzer

Thanks for helping improve RVTools Analyzer. The project deliberately keeps factual calculations in Python and interpretation in the skill instructions. That split makes findings repeatable while still allowing Claude and Codex to explain what they mean.

## Repository tour

- `SKILL.md` is the main instruction set. It routes questions to the correct analysis lens and defines privacy and reporting rules.
- `skills/rvtools-analyzer/SKILL.md` is the installed plugin entry point shared by Claude and Codex.
- `packaging/chatgpt/desktop/SKILL.md` and `packaging/chatgpt/cloud/SKILL.md` are the local and uploaded-file entry points. They define different execution and privacy rules; the builder copies the main `SKILL.md` into each package as `WORKFLOW.md`, without maintaining separate analysis rules.
- `tools/package_chatgpt_plugin.py` builds the portable ChatGPT ZIPs from an explicit file allowlist, generates variant manifests from the existing metadata, and tests the packaged runtime. Runtime calculations still come from `scripts/`.
- `scripts/parse_rvtools.py` reads a workbook and produces deterministic inventory facts, findings, migration results, and sizing data.
- `scripts/query_rvtools.py` builds the local allowlisted SQLite index used for conversational questions.
- `scripts/rvtools/` contains reusable domain logic. Migration rules live in `migration.py`, provider catalogs in `targets.py`, shared sizing calculations in `sizing.py`, and the normalized cloud bill of materials in `bom.py`.
- `scripts/rvtools/pricing/` contains the OCI, Azure, and Google public price-list adapters. Tests mock those APIs; the test suite must not depend on live prices or credentials.
- `references/` contains the guidance used to interpret parser results. Put vendor-specific policy here rather than hiding it in a prompt or duplicating Python calculations.
- `assets/report-template.html` is the shared HTML report design.
- `.claude-plugin/`, `.codex-plugin/`, `.agents/plugins/`, and `commands/` contain installation and marketplace metadata.
- `tests/` covers parsing, querying, migration, sizing, packaging, and the public repository contract.
- `pdf/` contains synthetic public examples. Real RVTools exports and customer-derived reports must never be committed.

## Local setup

You need Python 3.8 or newer. There is no Node.js build step.

Create a private development environment and install the same pinned packages used by CI:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install \
  openpyxl==3.1.5 \
  et_xmlfile==2.0.0 \
  defusedxml==0.7.1
```

On Windows, activate it with `.venv\Scripts\activate` instead.

End users do not need this setup. `scripts/run_rvtools.py` creates an isolated, hash-verified runtime automatically when the installed skill first needs it. If the package includes a `wheels/` directory, the launcher verifies the exact wheel set and installs with the package index disabled. An incomplete or altered bundle fails instead of falling back to a download.

## Build and test

This repository does not compile into an application. The build is the tested skill bundle, so the full test suite is the main local quality gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests
```

Run it before opening a pull request or creating a release tag. GitHub Actions repeats the suite on Linux, macOS, and Windows with Python 3.9, 3.12, and 3.14.

CI also builds both ChatGPT variants and runs their first-use bootstrap, parsing, OCVS sizing and conversational query against a synthetic workbook. The smoke test starts with an empty Python environment and unusable network proxies, then compares packaged results with the local engine. It needs no customer files, pricing credentials or live price lookups. Package tests check the distinct identities, desktop executor requirement, privacy entry points and byte-for-byte shared resources.

You can also exercise the installed runtime against a local workbook:

```bash
python scripts/run_rvtools.py parse /path/to/export.xlsx --pretty
```

For a quick conversational-query check:

```bash
python scripts/run_rvtools.py query /path/to/export.xlsx \
  --entity vm --metric count --filter power_state=poweredOff
```

If the Claude CLI is installed, validate its package metadata as an extra check:

```bash
claude plugin validate --strict .
```

## Making changes

Start with a failing test when changing deterministic behavior. Keep parsing, calculations, and supportable detection rules in Python. Keep narrative guidance, remediation advice, and report wording in `SKILL.md` or the relevant file under `references/`.

Provider limits and node specifications belong in `scripts/rvtools/targets.py`. Shared capacity arithmetic belongs in `scripts/rvtools/sizing.py`. This keeps OCVS, AVS, GCVE, and custom VCF hardware profiles on the same calculation path.

Keep provider billing fields and SKU matching in the relevant adapter under `scripts/rvtools/pricing/`. Keep cross-provider quantity, subtotal, and VCF-delta behavior in `scripts/rvtools/bom.py`. A missing or ambiguous live rate should produce a partial or unpriced BOM, not a guessed price or a failed sizing report.

Please preserve these project rules:

- Never upload or commit a real customer workbook, parser output, SQLite index, or customer-derived report.
- Do not expose licence keys, credentials, annotations, serial numbers, or unrestricted infrastructure inventories.
- Treat missing data as unknown. Do not turn an absent field into a clean bill of health.
- Use primary vendor documentation for facts that can change, and record when the catalog was reviewed.
- Update both plugin manifests together when changing the release version. Both ChatGPT manifests are generated from them, so they need no separate version edits.
- Add user-visible changes to `CHANGELOG.md` and update `README.md` when installation or behavior changes.

## Release build

Maintainers publish a release by committing the finished change, creating a matching semantic-version tag, and pushing the branch and tag together. The version in both plugin manifests must match the tag.

```bash
git tag -a v0.6.3 -m "RVTools Analyzer 0.6.3"
git push --atomic origin main v0.6.3
```

Replace `0.6.3` with the release being published. After CI passes for that exact commit, two independent workflows attach their packages to the same GitHub release:

- `release-claude-skill.yml` builds and validates `rvtools-skill-<version>.zip` for Claude Desktop Chat.
- `release-chatgpt-plugin.yml` uses a Desktop/Cloud matrix to build and smoke-test `rvtools-chatgpt-desktop-<version>.zip` and `rvtools-chatgpt-cloud-<version>.zip` for OpenAI's plugin upload.

Both require an exact release tag matching the plugin manifests. Neither runs on a pull-request result or waits for the other packaging workflow. New release workflows must be present on the default branch for GitHub's `workflow_run` trigger to discover them.

### Build the ChatGPT ZIPs locally

```bash
python tools/package_chatgpt_plugin.py download-wheels --output dist/chatgpt-wheels
for variant in desktop cloud; do
  python tools/package_chatgpt_plugin.py build \
    --variant "$variant" \
    --wheel-dir dist/chatgpt-wheels \
    --output "dist/rvtools-chatgpt-${variant}-0.6.3.zip"
  python tools/package_chatgpt_plugin.py smoke-test "dist/rvtools-chatgpt-${variant}-0.6.3.zip"
done
```

Only the download step needs access to PyPI. It fetches the same pinned, SHA-256-verified, platform-independent wheels used by the runtime. Build inputs are explicitly allowed files, not a recursive repository copy; customer samples, outputs, indexes, credentials and development files are excluded. Wheel archives retain their dependency licence files. No wheels or generated ZIPs belong in Git.

The loop above uses Bash. On other shells, run the build and smoke-test commands once for each variant. `--variant` is required; there is no implicit default.

Each ZIP has a portable `plugin.json` at its root and a self-contained skill under `skills/rvtools-analyzer/`. Neither has an MCP server, lifecycle hooks or hosted customer-data service. The Python code, references, wheels and HTML template are identical across variants; only the manifest and runtime entry point differ. Each package is reproducible for identical inputs. Both use `web/favicon.png` as their bundled `assets/icon.png`, referenced by `logo` and `composerIcon`, and link to `https://analyzer.rvtools.help/`. The PNG is a 512×512 rendering of the editable source in `web/favicon.svg`; keep the two files in sync when changing the mark.

The Desktop plugin is named `rvtools-analyzer-desktop` with display name **RVTools Analyzer Desktop**. Its OpenAI extension sets `requires_local_executor: true`. Its instructions stop when a local executor cannot be confirmed, never request a workbook upload as a fallback, and distinguish local file processing from cloud model inference. The cloud package is named `rvtools-analyzer` with display name **RVTools Analyzer**; only its ZIP filename includes `cloud`. The bundled skill keeps the name `rvtools-analyzer` and the display name **RVTools Analyzer**. It is intended for uploaded workbooks and does not set the desktop-only requirement; this is not a platform-enforced cloud-only flag. Existing Codex and Claude plugin identifiers stay unchanged.

### Publish or update the ChatGPT listings

The GitHub workflow builds submission packages; it does not publish to OpenAI. Submit Desktop and Cloud as separate plugin identities/listings. Download each release asset, upload it in the OpenAI Plugins portal, resolve required findings, complete applicable review, then publish the approved version. For an update, upload the matching new ZIP to that variant's existing listing. Follow the [current OpenAI submission guide](https://developers.openai.com/plugins/deploy/submission) and [desktop-only requirements](https://developers.openai.com/plugins/deploy/desktop-only); account access and approval of each listing are controlled by OpenAI.

Before first submission, test both variants in their intended ChatGPT surfaces using synthetic data:

- Desktop: provide a local path, ask a count question, generate a sizing report and open the local reports. Confirm that an unavailable local executor or unreadable path does not lead to an upload request. Confirm that an already attached workbook is not described as local-only.
- Cloud: upload a workbook, ask a count question, generate a sizing report and open its downloads. Confirm that cloud privacy, workspace resets and unavailable pricing are explained correctly.

The automated smoke test verifies the packaged Python runtime, not ChatGPT account eligibility, skill activation, platform executor enforcement or approval. Never use a real customer workbook for public review materials.

## Pull-request checklist

- The full test suite passes.
- New deterministic behavior has focused tests.
- Documentation matches the implementation.
- No private data or generated local indexes are staged.
- Version files and the changelog are updated when the change belongs in a release.
