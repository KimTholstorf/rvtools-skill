---
name: rvtools-analyzer
description: Analyze and query VMware RVTools XLSX exports for OCVS, AVS, or GCVE migration with HCX, VCF readiness, vSphere health, hardware lifecycle, overcommit, licensing, capacity, and inventory questions.
---

# RVTools Analyzer

Invoke this skill explicitly as `$rvtools-analyzer` in Codex. In Claude Code, use the shorter `/rvtools:analyze` command. It may also activate automatically when the user's request matches its description.

Resolve the plugin root as the directory two levels above this file. Read the plugin root's `SKILL.md` completely and follow its routing, lenses, privacy rules, interpretation guidance, report formats, and quality checks.

Override the root skill's direct Python commands with the private runtime launcher. Select an available Python 3.8+ command for the platform (`python3` on most Unix systems, `python` or `py -3` where appropriate); the examples below use `python3`:

```bash
python3 /absolute/path/to/plugin/scripts/run_rvtools.py parse /absolute/path/to/export.xlsx --pretty --max-examples 25 --output /safe/local/path/rvtools-analysis.json
```

```bash
python3 /absolute/path/to/plugin/scripts/run_rvtools.py query /absolute/path/to/export.xlsx \
  --index /safe/session/path/rvtools-query.sqlite \
  --entity vm --metric count --filter guest_os_family=linux
```

Resolve every script, reference, and asset path from the plugin root rather than the user's working directory.

The launcher requires Python 3.8 or newer. Use the current environment only when its dependency versions match exactly. Otherwise let the launcher create a private virtual environment under `RVTOOLS_PLUGIN_DATA`, `PLUGIN_DATA`, `CLAUDE_PLUGIN_DATA`, or its OS-temporary fallback and download the pinned, hash-verified wheels on first use. Never install dependencies globally, use `sudo`, or alter the user's system or Homebrew Python.
