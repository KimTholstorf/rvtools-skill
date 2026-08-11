# Changelog

All notable changes to RVTools Analyzer are documented here.

## [0.3.0] - 2026-08-11

### Added

- Added per-VM screening for HCX vMotion, RAV, Bulk Migration, and Cold Migration across OCVS, AVS, and GCVE.
- Added separate provider profiles, manual validation gates, and primary vendor references for all three cloud targets.
- Added dated AVS host and GCVE node catalogs, including AV64 OSA and ESA storage variants.
- Added conversational `migration_method`, `migration_finding`, and `target_node` query entities.

### Changed

- Replaced detection-to-lens coupling with provider-neutral source tags and target-specific migration results.
- Bumped the parser output schema to 2.0 and the local query-index schema to 6 for the new migration records.
- Moved ESXi compatibility to the current HCX interoperability check instead of relying on a static minimum version.
- Kept duplicate VM names distinct by vCenter or host where RVTools provides enough identity data.

### Fixed

- Missing virtual hardware or CPU-vendor evidence now produces an `unknown` result instead of a false eligible result.
- Added an explicit manual gate when duplicate VM names cannot be tied safely to related workbook rows.

## [0.2.0] - 2026-08-11

### Added

- Added sanitized conversational queries for current VMware licence inventory without exposing licence keys, labels, or feature strings.
- Added per-host, per-cluster, and estate-wide VCF core licensing calculations with the 16-core minimum per physical CPU.
- Added included vSAN entitlement, add-on TiB, and surplus TiB calculations with a verified raw-capacity override and explicit datastore-proxy warnings.
- Added synthetic health-check and OCVS migration screenshots and downloadable PDF report samples.

### Changed

- Reworked the README with a more conversational voice and a report-inspired branded header.

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

[0.3.0]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/KimTholstorf/rvtools-skill/releases/tag/v0.1.0
