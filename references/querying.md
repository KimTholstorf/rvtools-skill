# Conversational RVTools Queries

Use this reference for factual inventory questions and follow-ups. Query mode is not a lens: retrieve facts first, then apply `hcx_ocvs`, `vcf_onprem`, or `hygiene` only when the user asks for interpretation.

## Session workflow

1. Keep the workbook local.
2. Create one temporary session directory and remember its absolute path.
3. Pass `<session-directory>/rvtools-query.sqlite` with `--index` on every query for the same workbook.
4. Rebuild automatically when the workbook hash changes. Use a new index when the user switches workbooks.
5. Answer from query JSON. State defaults, filters, unknown classifications, and truncation.

The index is owner-readable only and excludes annotations, snapshot descriptions, credentials, license keys, serial numbers, and other free-text secret-bearing fields.

## Command grammar

```bash
python3 scripts/query_rvtools.py WORKBOOK --index INDEX --entity ENTITY \
  [--select FIELD]... [--metric METRIC]... [--filter FILTER]... \
  [--group-by FIELD]... [--order-by FIELD:asc|desc]... [--limit 1..100] \
  [--include-templates] [--vsan-raw-tib TIB] [--pretty]
```

Metrics:

- `count`
- `count_distinct:FIELD`
- `sum:FIELD`, `avg:FIELD`, `min:FIELD`, or `max:FIELD`

Filters use `field=value` or `field__operator=value`. Supported operators are `eq`, `ne`, `contains`, `startswith`, `endswith`, `gt`, `gte`, `lt`, `lte`, and `in`. `in` accepts comma-separated values. Text equality is case-insensitive.

## Entities and allowlisted fields

- `vm`: `vm`, `power_state`, `template`, `cluster`, `host`, `guest_os`, `guest_os_family`, `guest_os_source`, `cpus`, `memory_mib`, `provisioned_mib`, `in_use_mib`, `hardware_version`, `tools_status`, `consolidation_needed`
- `host`: `host`, `cluster`, `vendor`, `model`, `cpu_vendor`, `cpu_model`, `ht_available`, `ht_active`, `cpu_sockets`, `cores_per_cpu`, `cores`, `cpu_speed_mhz`, `memory_mib`, `cpu_usage_percent`, `memory_usage_percent`, `bios_vendor`, `bios_version`, `bios_date`, `esxi_version`
- `cluster`: `cluster`, `host_count`, `powered_on_vms`, `configured_vcpus`, `physical_cores`, `cpu_ratio`, `configured_memory_mib`, `physical_memory_mib`, `memory_ratio`, `powered_off_vms`, `powered_off_vcpus`, `powered_off_memory_mib`
- `datastore`: `datastore`, `type`, `cluster`, `capacity_mib`, `provisioned_mib`, `in_use_mib`, `free_mib`, `free_percent`, `accessible`
- `license`: `name`, `cost_unit`, `total`, `used`, `expiration_date`, `vi_sdk_server`
- `vcf_license`: `host`, `cluster`, `cpu_sockets`, `cores_per_cpu`, `physical_cores`, `vcf_licensable_cores`, `core_minimum_adjustment`
- `vcf_license_summary`: `host_count`, `physical_cores`, `vcf_licensable_cores`, `core_calculation_complete`, `vsan_entitlement_tib`, `vsan_capacity_tib`, `vsan_capacity_evidence`, `vsan_capacity_is_raw`, `vsan_addon_required_tib`, `vsan_entitlement_surplus_tib`
- `disk`: `vm`, `template`, `power_state`, `cluster`, `host`, `disk`, `capacity_mib`, `raw`, `disk_mode`, `sharing_mode`, `raw_compatibility_mode`
- `network`: `vm`, `template`, `power_state`, `network`, `switch`, `connected`, `cluster`, `host`
- `snapshot`: `vm`, `template`, `cluster`, `host`, `created_at`, `size_mib`, `power_state`
- `dvport`: `port_group`, `switch`, `vlan`, `allow_promiscuous`, `mac_changes`, `forged_transmits`, `binding_type`
- `cdrom`: `vm`, `template`, `power_state`, `cluster`, `host`, `connected`, `starts_connected`, `device_type`
- `usb`: `vm`, `template`, `power_state`, `cluster`, `host`, `connected`, `device_type`

## Defaults and answer discipline

- Exclude templates for `vm`, `disk`, `network`, and `snapshot` unless explicitly requested.
- Include all workload power states unless filtered. State this when answering VM counts.
- Prefer the VMware Tools-reported guest OS and fall back to configured OS. Report `unknown` counts when relevant.
- Limit listings to 25 rows by default and never exceed 100. Aggregate counts are not truncated.
- Treat a `null` overcommit ratio as unavailable and surface its coverage warning.
- Treat `null` Hyper-Threading fields as unknown. Do not describe them as disabled or unavailable.
- The `license` entity excludes licence keys, labels, and feature strings. Treat workbook assignments as inventory evidence, not proof of contractual entitlement.
- Use `vcf_license_summary` for the current estate. Use `vcf_license` with cluster filters or grouping to show the per-host workings or model alternative target scopes.
- Treat `rvtools_vsan_datastore_capacity_proxy` as an estimate because datastore capacity is not confirmed raw physical vSAN capacity. Use `--vsan-raw-tib` only with a verified raw capacity supplied by the user or another authoritative source.
- Do not infer facts absent from returned rows. Run a follow-up query instead.

## Examples

Count Linux workloads across all power states:

```bash
python3 scripts/query_rvtools.py WORKBOOK --index INDEX \
  --entity vm --metric count --filter guest_os_family=linux
```

Count powered-on Linux workloads by cluster:

```bash
python3 scripts/query_rvtools.py WORKBOOK --index INDEX \
  --entity vm --metric count --filter guest_os_family=linux \
  --filter power_state=poweredOn --group-by cluster
```

Read one cluster's overcommit values:

```bash
python3 scripts/query_rvtools.py WORKBOOK --index INDEX \
  --entity cluster --filter cluster=CLUSTER_NAME \
  --select cluster --select cpu_ratio --select memory_ratio \
  --select configured_vcpus --select physical_cores
```

Summarize host hardware models and Hyper-Threading state:

```bash
python3 scripts/query_rvtools.py WORKBOOK --index INDEX \
  --entity host --metric count \
  --group-by vendor --group-by model --group-by cpu_model \
  --group-by ht_available --group-by ht_active
```

Summarize sanitized current VMware licence assignments:

```bash
python3 scripts/query_rvtools.py WORKBOOK --index INDEX \
  --entity license --limit 100
```

Calculate estate-wide VCF cores and estimate the vSAN entitlement balance:

```bash
python3 scripts/query_rvtools.py WORKBOOK --index INDEX \
  --entity vcf_license_summary
```

Recalculate the vSAN balance from independently verified raw capacity:

```bash
python3 scripts/query_rvtools.py WORKBOOK --index INDEX \
  --entity vcf_license_summary --vsan-raw-tib 240
```

List large powered-on VMs with bounded output:

```bash
python3 scripts/query_rvtools.py WORKBOOK --index INDEX \
  --entity vm --filter power_state=poweredOn --filter memory_mib__gte=65536 \
  --select vm --select cluster --select memory_mib \
  --order-by memory_mib:desc --limit 25
```
