# Contributing to RVTools Analyzer

Thanks for helping improve RVTools Analyzer. The project deliberately keeps factual calculations in Python and interpretation in the skill instructions. That split makes findings repeatable while still allowing Claude and Codex to explain what they mean.

## Repository tour

- `SKILL.md` is the main instruction set. It routes questions to the correct analysis lens and defines privacy and reporting rules.
- `skills/rvtools-analyzer/SKILL.md` is the installed plugin entry point shared by Claude and Codex.
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

End users do not need this setup. `scripts/run_rvtools.py` creates an isolated, hash-verified runtime automatically when the installed skill first needs it.

## Build and test

This repository does not compile into an application. The build is the tested skill bundle, so the full test suite is the main local quality gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests
```

Run it before opening a pull request or creating a release tag. GitHub Actions repeats the suite on Linux, macOS, and Windows with Python 3.9, 3.12, and 3.14.

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
- Update both plugin manifests together when changing the release version.
- Add user-visible changes to `CHANGELOG.md` and update `README.md` when installation or behavior changes.

## Release build

Maintainers publish a release by committing the finished change, creating a matching semantic-version tag, and pushing the branch and tag together. The version in both plugin manifests must match the tag.

```bash
git tag -a v0.6.0 -m "RVTools Analyzer 0.6.0"
git push --atomic origin main v0.6.0
```

Replace `0.6.0` with the release being published. After CI passes for that exact commit, the separate release workflow builds the Claude Desktop ZIP from `SKILL.md`, `assets/`, `references/`, and `scripts/`, validates its contents, and attaches it to the GitHub release.

## Pull-request checklist

- The full test suite passes.
- New deterministic behavior has focused tests.
- Documentation matches the implementation.
- No private data or generated local indexes are staged.
- Version files and the changelog are updated when the change belongs in a release.
