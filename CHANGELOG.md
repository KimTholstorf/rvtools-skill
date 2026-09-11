# Changelog

This file tracks each RVTools Analyzer release.

## [0.5.0] - 2026-09-11

### Added

- A provider-neutral Python sizing engine shared by OCVS, AVS, and GCVE reports and conversational queries.
- A recommended capacity policy covering all non-template workloads, 20% CPU and memory headroom, binding configured memory, one-host-loss capacity, and 25% provisioned-storage headroom.
- An explicit active-only policy for leaner scenarios based on powered-on workloads, no generic compute headroom, and aggregate memory overcommit.
- Conversational `sizing_summary` and `sizing_cluster` records for exact totals and per-cluster workings.
- Deterministic node comparison that balances purchased-host count with full-silicon VCF cores and retains alternatives for review.
- A target-profile interface for applying the same policy to a verified on-premises VCF hardware bill of materials.

### Changed

- Host counts now use independent normal-operation, one-host-loss, and provider-minimum constraints. A failure host is no longer added blindly to an already sufficient provider minimum.
- OCVS sizing distinguishes the three-host unified-management minimum from the two-host standard-workload minimum.
- Source-aligned sizing excludes and lists clusters with no hosts, and reports workloads that cannot be attributed safely instead of placing them in a target cluster.
- Cloud migration parser output now includes deterministic sizing or asks for a topology choice when several source clusters are present.
- The parser output schema is now version 3.0, and the local query-index schema is version 8.

### Fixed

- Repeated RVTools column names are preserved instead of overwriting one another, improving cluster attribution for workbook variants with duplicate headers.

## [0.4.3] - 2026-09-09

### Added

- Cloud sizing reports can now model either a consolidated target or one target cluster for each source cluster.
- The selected design gets the full sizing analysis, while the alternative gets a short comparison of cluster count, purchased hosts, N+1 capacity, and VCF cores.

### Changed

- Multi-cluster sizing now asks which target layout the user wants instead of assuming that every source cluster should be consolidated.

## [0.4.2] - 2026-08-14

### Added

- Health checks and cloud migration reports now include guest operating-system lifecycle findings based on current vendor sources.
- Conversational questions can identify VMs that are supported, in extended support, out of support, or too broadly labelled to classify safely.

### Changed

- Guest OS lifecycle findings are kept separate from HCX compatibility, so an old operating system is highlighted without being reported as a migration-method blocker.
- The README now calls out guest OS lifecycle checks and includes a matching example question.

## [0.4.1] - 2026-08-11

### Added

- A downloadable synthetic OCVS sizing report that demonstrates host selection, N+1 capacity, large-VM fit, and full-silicon VCF licensing without customer data.

### Changed

- Expanded the README guidance for cloud migration sizing and full-silicon VCF licensing.
- Reworked the changelog wording to make the release history easier to read.

## [0.4.0] - 2026-08-11

### Added

- An OCVS node catalog with separate values for configured compute capacity, full physical silicon, and VCF-licensable cores.
- A shared OCVS, AVS, and GCVE sizing policy based on powered-on workloads, a 4:1 CPU ratio, accepted aggregate memory overcommit, no generic growth uplift, and one N+1 host.
- Generated reports now show the assessment perimeter and end with an acronym glossary.

### Changed

- Target recommendations use configured physical cores for workload fit and every physical silicon core in each purchased node for portable VCF licensing.
- Conversational `target_node` queries now return the shape series, CPU vendor, configured cores, silicon cores, VCF-licensable cores, and licensing basis.
- The local query-index schema is now version 7 to support the expanded target-node records.

## [0.3.0] - 2026-08-11

### Added

- Per-VM screening for HCX vMotion, RAV, Bulk Migration, and Cold Migration across OCVS, AVS, and GCVE.
- Separate provider profiles, manual validation gates, and primary vendor references for each cloud target.
- Dated AVS host and GCVE node catalogs, including the AV64 OSA and ESA storage variants.
- Conversational queries for `migration_method`, `migration_finding`, and `target_node` records.

### Changed

- Migration detections now use provider-neutral source tags and produce target-specific results.
- The parser output schema moved to version 2.0 and the local query-index schema to version 6 for the new migration records.
- ESXi compatibility now uses the current HCX interoperability check instead of a static minimum version.
- Duplicate VM names remain distinct by vCenter or host when RVTools provides enough identity data.

### Fixed

- Missing virtual hardware or CPU-vendor evidence now returns `unknown` instead of incorrectly marking a VM as eligible.
- Ambiguous duplicate VM names now trigger a manual check when related workbook rows cannot be matched safely.

## [0.2.0] - 2026-08-11

### Added

- Sanitized conversational queries for current VMware licence inventory without exposing keys, labels, or feature strings.
- VCF core calculations by host, cluster, or estate, including the 16-core minimum for each physical CPU.
- vSAN entitlement, add-on, and surplus TiB calculations, with a verified raw-capacity override and clear warnings when datastore capacity is only a proxy.
- Synthetic health-check and OCVS migration screenshots, plus downloadable PDF report samples.

### Changed

- Reworked the README in a more conversational voice and added a report-inspired header.

## [0.1.2] - 2026-08-10

### Added

- A separate release workflow packages the Claude Desktop skill ZIP after CI passes for a version-tagged commit.

### Fixed

- RVTools workbook handles now close after parsing and query indexing, allowing Windows to clean up temporary files.
- The runtime no longer calls the POSIX-only `os.fchmod` API when it is unavailable on Windows.

## [0.1.1] - 2026-08-10

### Changed

- Redesigned the self-contained HTML report with an Oracle-inspired presentation style, clearer hierarchy, responsive layouts, and print-friendly output.

### Fixed

- Privacy-permission tests now work on Windows, where access is represented by ACLs rather than POSIX mode bits.

## [0.1.0] - 2026-08-10

### Added

- Deterministic RVTools workbook parsing with bounded evidence and 32 risk checks.
- Allowlisted conversational inventory queries backed by a reusable local SQLite index.
- OCVS/HCX migration, on-premises VCF, and vSphere health-check lenses.
- CPU and memory overcommit calculations by cluster and across the environment.
- Guidance for assessing host vendor, model, CPU, BIOS, Hyper-Threading, and hardware lifecycle.
- Self-contained HTML and Markdown reports.
- A private, on-demand Python environment with pinned and hash-verified dependencies.
- Plugin marketplace packaging for Claude Code and Codex.
- The short Claude command `/rvtools:analyze` and Codex skill `$rvtools-analyzer`.

[0.5.0]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.4.3...v0.5.0
[0.4.3]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/KimTholstorf/rvtools-skill/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/KimTholstorf/rvtools-skill/releases/tag/v0.1.0
