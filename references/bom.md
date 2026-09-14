# Cloud VMware Bill of Materials and Pricing

Use this reference when a user asks for a priced cloud sizing report or a bill of materials (BOM) for OCVS, AVS, or GCVE. Build the BOM from the completed Python sizing result. Do not infer host quantities again in prose.

## Inputs and defaults

The default currency is USD. Use another ISO currency code when the user asks for it. Azure and Google pricing require the exact target region; do not substitute a nearby or generic US region. OCI public list prices are currency-specific but not region-specific.

The default pricing model is on demand. One-year and three-year options are valid only where the provider API returns a unique matching commitment or reservation rate. If the requested model is unavailable, keep the quantity and mark the line `unpriced`.

Run the parser with `--include-bom` after the sizing topology has been resolved. Useful options are:

```bash
--currency EUR
--pricing-model on_demand
--target-region westeurope
--vcf-entitlement-cores 4096
--storage-headroom-percent 25
```

For AVS with Azure Elastic SAN, also use `--storage-strategy elastic_san` and provide `--elastic-san-base-tib`. The base portion carries performance; the remaining required capacity is priced as capacity-only units. Do not invent that split. For OCVS, `--storage-vpu-per-gb` defaults to 10 and must be changed when the selected Block Volume performance level differs.

## Quantity rules

- Use host and node quantities directly from `sizing.clusters[].recommendation`.
- Use configured OCPUs or memory only for provider billing fields that charge those units.
- Calculate portable VCF licensing from full physical silicon, including reduced-core cloud configurations and storage-only nodes. Never use configured cores or logical threads as a substitute.
- Show the current-estate VCF requirement, target requirement, and either additional cores required or surplus cores. The current estate is a hardware-derived planning proxy unless the customer confirms its actual subscription entitlement. Use `--vcf-entitlement-cores` only for a customer-confirmed entitlement.
- Keep VMware subscription rows unpriced. Broadcom or reseller pricing is not part of a cloud provider's public pricing API.

## Storage

OCVS uses separate OCI Block Volume capacity and performance-unit rows. AVS and GCVE host-local vSAN is included with the selected hosts, but usable capacity still needs validation against storage policy, failure tolerance, rebuild reserve, free-space requirements, and data reduction. Only add Azure Elastic SAN or GCVE storage-only nodes when the design explicitly selects and sizes them.

## Provider tables

Use the provider's own vocabulary rather than forcing every report into OCI columns.

OCVS columns:

```text
Category | Target shape/component | OCI part number | Oracle API product name | Billable quantity | <currency> list rate | Estimated monthly
```

AVS columns:

```text
Category | Azure component | Azure product | SKU name | Meter name | Azure SKU ID | Region | Billable quantity | Billing unit | Currency | Retail price | Estimated monthly
```

GCVE columns:

```text
Category | GCVE component | Google SKU ID | Google SKU description | Service region | Billable quantity | Usage unit | Pricing model | Currency | List rate | Estimated monthly
```

Place VMware licensing rows below the provider components. Do not include unpriced licensing rows in the cloud subtotal.

Use the selected storage basis for the provider rows and first subtotal. When `bom.storage_growth_comparison.status` is `complete`, add exactly one row immediately below that subtotal. Label it **Comparison: subtotal with 25% storage allowance** and show both the additional monthly storage cost and `subtotal_with_growth`. This is a comparison only; it must not change the selected BOM. If storage is bundled with hosts or the storage lines are not all priced, explain why the comparison is unavailable instead of estimating it in prose.

## Price lookup behavior

The adapters query the [Oracle pricing API](https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/), [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices), and [Google Cloud Billing Catalog API](https://cloud.google.com/billing/docs/reference/rest/v1/services.skus/list). Oracle and Azure allow anonymous price-list reads. Google requires `GOOGLE_CLOUD_API_KEY` or `GOOGLE_API_KEY` in the local environment.

Only provider, SKU, region, currency, and pricing-model identifiers are sent to a pricing endpoint. No workbook rows, VM names, host names, customer names, or report content are included. Responses may be cached for 24 hours in the plugin's private data directory or an operating-system temporary directory.

Use three pricing states:

- `complete`: every cloud-provider component has one price;
- `partial`: at least one component is priced and at least one is not;
- `unpriced`: quantities are complete but no component has a usable price.

Never report a grand total for a partial BOM. Report the priced subtotal and name every unpriced line. Do not show the 25% comparison subtotal unless all selected provider and separately billed storage lines needed for it are priced. API errors, missing credentials, ambiguous SKU matches, unsupported currencies, and missing regional rates must not fail the sizing report.

Track quantity completeness separately. AVS or GCVE host-local vSAN remains `validation_required` until the selected node mix has been checked against a defined storage policy and usable-capacity model. In that state, a fully priced host list is still only a priced subtotal, not a complete design total.

Hourly OCVS estimates use 744 hours per month. Azure and Google use 730 hours. Reservation or commitment charges returned as term totals are divided by the number of months in the term. Label every result as an estimate based on public list rates, before discounts, taxes, support, data transfer, backup, migration services, and other unlisted components.
