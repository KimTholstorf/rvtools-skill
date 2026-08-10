# Changelog

All notable changes to RVTools Analyzer are documented here.

## [0.1.2] - 2026-08-10

### Added

- Added a separate release workflow that packages a Claude Desktop-compatible skill ZIP only after CI succeeds for a version-tagged commit.

### Fixed

- Closed RVTools workbook handles after parsing and query indexing so Windows can clean up temporary files.
- Avoided calling the POSIX-only `os.fchmod` API when it is unavailable on Windows.

## [0.1.1] - 2026-08-10

### Changed

- Redesigned the self-contained HTML report with a flat Oracle-inspired presentation style, clearer assessment hierarchy, responsive behavior, and print/PDF optimization.

### Fixed

- Made privacy-permission tests portable to Windows, where access is represented by ACLs rather than POSIX mode bits.

## [0.1.0] - 2026-08-10

### Added

- Deterministic RVTools workbook parsing with bounded evidence and 32 risk detections.
- Conversational, allowlisted inventory queries backed by a reusable local SQLite index.
- OCVS/HCX migration, on-premises VCF, and vSphere health-check lenses.
- CPU and memory overcommit calculations by cluster and across the environment.
- Host vendor, model, CPU, BIOS, Hyper-Threading, and lifecycle assessment guidance.
- Self-contained HTML and Markdown assessment output.
- Private on-demand Python environment with pinned, hash-verified dependencies.
- First-class Claude Code and Codex plugin marketplace packaging.
- Short Claude command `/rvtools:analyze` and Codex skill `$rvtools-analyzer`.

[0.1.2]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/KimTholstorf/rvtools-skill/releases/tag/v0.1.0
