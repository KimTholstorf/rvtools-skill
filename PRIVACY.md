# Privacy policy

Last updated: November 3, 2026

This policy covers RVTools Analyzer, RVTools Analyzer Desktop, the related Codex and Claude skills, and the project website at [analyzer.rvtools.help](https://analyzer.rvtools.help/). The project is maintained by Kim Tholstorf. Support and privacy questions can be raised through [GitHub Issues](https://github.com/KimTholstorf/rvtools-skill/issues).

RVTools exports are sensitive infrastructure records. Use only data you are authorized to process, in an execution environment and AI account approved by your organization or customer.

## What the software processes

The analyzer reads the RVTools workbook you select and the instructions you give it. An export can contain VM and host names, IP addresses, network configuration, hardware identifiers, operating systems, capacity, licensing information, and free-text fields. Some exports may also contain personal information, such as names or email addresses embedded in inventory fields.

The software uses this information to answer inventory questions and produce health, migration, sizing, licensing, and cost reports. It can create parser output, a SQLite query index, and report files. These derived files can be as sensitive as the original workbook. The conversational index excludes certain sensitive fields, including licence keys and annotations; that does not sanitize the source workbook or every possible output.

There is no developer-operated analysis backend. The analyzer does not send workbooks or analysis results to the maintainer, and the project adds no usage telemetry or advertising trackers to the analysis scripts. The maintainer receives information only if you choose to share it, for example in a support issue.

## Local and cloud processing

**Desktop and local CLI use.** When you provide a local path in a session with local filesystem access, parsing, indexes, and report files are created in that execution environment. The Desktop ChatGPT package instructs the assistant to stop if local execution is unavailable rather than ask for an upload or silently switch to cloud execution.

Local processing does not mean offline AI. Your questions, selected findings, tool results, and report text may be sent to the AI provider operating the session. The assistant's tools, permissions, and your organization's controls also affect what it can read or transmit. Skill instructions are not a replacement for endpoint or network security controls.

**Cloud chats.** Attaching a workbook sends it to the AI platform. The Cloud package processes that uploaded copy and creates indexes and reports in the platform's cloud workspace. The platform and authorized workspace administrators may have access under the applicable account terms and settings. Using a desktop app window does not, by itself, mean execution is local.

The analyzer does not set or override an AI provider's training, access, data-location, or retention policies. Check the terms and settings for the account you use before sharing customer information.

## Network requests and other recipients

Some features use external services:

- Pricing lookups contact Oracle, Microsoft, or Google public pricing APIs using catalog parameters such as product, SKU, region, currency, or pricing model. The pricing adapters do not send workbook rows, VM names, or customer inventory.
- Hardware, operating-system lifecycle, and compatibility research may use the assistant's search or browsing tools. Instructions limit these searches to necessary public product identifiers, such as vendor, model, or OS version, rather than customer names or raw inventory.
- Local CLI installations may download pinned Python packages on first use. The ChatGPT ZIPs bundle verified dependencies for offline setup. Package services can receive normal connection information when downloads occur.

The services handling those requests can receive technical connection information, such as an IP address, and retain it under their own policies. The AI provider also handles any information included in the conversation or passed through its tools.

The website and downloads use GitHub and Cloudflare services. Visiting the site, resolving release links, or downloading packages can expose ordinary connection and request information to those providers. Their privacy policies apply to that processing.

## Retention and deletion

The analyzer has no central store of customer workbooks and no maintainer-controlled retention period for your analysis files.

- **Local files:** workbooks, indexes, and reports remain until you delete them or the environment removes them. Closing a chat or uninstalling the plugin does not necessarily remove separately saved files, backups, or synced copies.
- **Cloud files and conversations:** retention and deletion depend on the AI platform, account settings, and administrator policies. A workspace reset may remove temporary files, but it is not a promise that all platform-held copies have been deleted. Use the platform's deletion controls for uploaded files and chats.
- **Pricing cache and runtime:** local dependencies and catalog caches can remain after a session. The default pricing-cache freshness interval is 24 hours; this is a refresh interval, not an automatic deletion deadline. Cached catalogs do not contain workbook rows.
- **Support:** GitHub issue text, attachments, and account information remain public unless removed using GitHub's controls. Closing an issue does not delete it. Copies in notifications, repository history, or third-party archives may persist.

## Your choices and questions

Prefer a local workbook path when uploads are not allowed. Review generated files and conversation output before sharing them. You can use a masked export where appropriate, but check that it preserves the fields needed for the analysis and that the remaining data is safe to disclose.

Do not submit passwords, API keys, other access secrets, or unrelated sensitive personal data for analysis. Do not attach customer workbooks, private reports, licence keys, or credentials to public support issues. Use synthetic or suitably masked examples instead.

For questions about information you shared with the project, open a [GitHub issue](https://github.com/KimTholstorf/rvtools-skill/issues) describing the request without including confidential details. If the request needs private information, agree on a suitable private channel before sharing it. Requests concerning files or conversations held by an AI platform must be directed to that provider or your workspace administrator; the maintainer cannot access or delete them for you. Any privacy rights available under applicable law remain unaffected.

## Changes

Updates to this policy are published in this repository with a revised date. Git history records earlier versions. Review the current policy when changing execution environments or updating the plugin.
