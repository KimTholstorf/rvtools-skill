# Host Hardware Lifecycle and Hyper-Threading

Use this reference with the `hygiene` lens whenever `vHost` is present. Lifecycle data is time-sensitive: research it during each assessment instead of relying on a static model-age table.

## Inventory first

1. Query every distinct vendor/model combination with a host count, CPU model, `HT Available`, and `HT Active`.
2. Keep raw `Vendor`, `Model`, and `CPU Model` strings for matching. Use the derived CPU vendor only for grouping.
3. Report blank vendor/model, HT, or BIOS values as a coverage gap. Never treat a blank boolean as false.
4. Keep host names and other inventory details out of web searches. Search only the minimum vendor, model, and product-family strings needed to locate public lifecycle material.

## Research every model

Search for the exact model on a primary vendor support, product-lifecycle, End-of-Life, or End-of-Sale page. Use search results and third-party lifecycle databases only to discover the primary vendor document. Prefer the latest amended vendor notice over an older copy.

Confirm that the exact model, part number, or an explicitly covering product family appears in the affected-products table. A replacement-product reference does not prove that the replacement has the same lifecycle dates. If the match remains ambiguous, label it unverified rather than transferring dates from a similar name.

For each distinct vendor/model record:

- vendor, model, and affected host count;
- matched vendor product name or family and match confidence;
- lifecycle status with an as-of date;
- End-of-Life announcement date;
- End-of-Sale date and last ship date, when published;
- end of software maintenance or vulnerability/security support, when published;
- end of service-contract renewal, when published;
- Last Date of Support, EOSL, or the vendor's equivalent;
- direct primary vendor source URL and document update date;
- operational action and target date.

End-of-Sale does not mean the product is already unsupported. Preserve the vendor's milestone names and dates rather than collapsing everything into “EOL.” Contract entitlement is not present in RVTools and must be checked separately.

If no authoritative notice is found, say “no matching vendor lifecycle notice located”; do not call the model current or supported. Make this a coverage gap and recommend confirmation through the vendor support portal or account team.

## Hygiene prioritization

Use these report priorities, based on the assessment date:

- **High:** Last Date of Support has passed; vulnerability/security maintenance has ended; or support ends within 12 months.
- **Medium:** End-of-Sale has passed while support remains available, or Last Date of Support is within 24 months.
- **Low/planning:** An End-of-Life announcement exists but End-of-Sale is still in the future.
- **Coverage gap:** vendor/model is absent, the product match is uncertain, no primary vendor source is available, or a required milestone is unpublished.

These are project prioritization rules, not vendor severity labels. Surface the exact dates so the user can adjust urgency for spares, support contracts, regulatory patch obligations, and refresh lead time.

## Hyper-Threading and firmware

Flag a host when `HT Available` is true and `HT Active` is false, and call out mixed active states within a cluster. Treat the result as a configuration review, not an automatic recommendation to enable Hyper-Threading: validate security policy, CPU-vulnerability mitigations, licensing, workload behavior, BIOS support, and cluster consistency first.

Use BIOS vendor/version/date as evidence for firmware review. Do not declare firmware stale from its date alone; compare the exact server model and installed version with a current primary vendor advisory or firmware catalog.

CPU model and generation are supporting evidence for compatibility, security, and refresh planning, but server lifecycle status must be tied primarily to the server vendor/model match.

## Cisco HyperFlex matching example

For an RVTools model such as `HXAF240C-M5SX`, search Cisco's current HyperFlex M5 lifecycle notices and verify that the affected-product scope includes the exact SKU or its explicitly named HX C240 M5 family. Cisco notices can be amended, so open the [current Cisco Hyperconverged M5 notice](https://www.cisco.com/c/en/us/products/collateral/hyperconverged-infrastructure/hyperflex-hx-series/hyperconverged-m5-eol.html) and use its table rather than copying dates from another Cisco product or an old search snippet.
