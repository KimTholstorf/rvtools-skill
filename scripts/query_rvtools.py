#!/usr/bin/env python3
"""Safely query a local RVTools workbook through an allowlisted inventory index."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from openpyxl import load_workbook


PARSER_PATH = Path(__file__).with_name("parse_rvtools.py")
PARSER_SPEC = importlib.util.spec_from_file_location("rvtools_query_parser", PARSER_PATH)
RVTOOLS = importlib.util.module_from_spec(PARSER_SPEC)
assert PARSER_SPEC.loader is not None
PARSER_SPEC.loader.exec_module(RVTOOLS)

INDEX_SCHEMA_VERSION = "4"
INDEXED_SHEETS = (
    "vInfo",
    "vHost",
    "vTools",
    "vDatastore",
    "vDisk",
    "vNetwork",
    "vSnapshot",
    "vCD",
    "vUSB",
    "dvPort",
)

ENTITY_SCHEMAS = {
    "vm": {
        "vm": "TEXT",
        "power_state": "TEXT",
        "template": "INTEGER",
        "cluster": "TEXT",
        "host": "TEXT",
        "guest_os": "TEXT",
        "guest_os_family": "TEXT",
        "guest_os_source": "TEXT",
        "cpus": "REAL",
        "memory_mib": "REAL",
        "provisioned_mib": "REAL",
        "in_use_mib": "REAL",
        "hardware_version": "TEXT",
        "tools_status": "TEXT",
        "consolidation_needed": "INTEGER",
    },
    "host": {
        "host": "TEXT",
        "cluster": "TEXT",
        "vendor": "TEXT",
        "model": "TEXT",
        "cpu_vendor": "TEXT",
        "cpu_model": "TEXT",
        "ht_available": "INTEGER",
        "ht_active": "INTEGER",
        "cpu_sockets": "REAL",
        "cores_per_cpu": "REAL",
        "esxi_version": "TEXT",
        "cores": "REAL",
        "cpu_speed_mhz": "REAL",
        "memory_mib": "REAL",
        "cpu_usage_percent": "REAL",
        "memory_usage_percent": "REAL",
        "bios_vendor": "TEXT",
        "bios_version": "TEXT",
        "bios_date": "TEXT",
    },
    "cluster": {
        "cluster": "TEXT",
        "host_count": "INTEGER",
        "powered_on_vms": "INTEGER",
        "configured_vcpus": "REAL",
        "physical_cores": "REAL",
        "cpu_ratio": "REAL",
        "configured_memory_mib": "REAL",
        "physical_memory_mib": "REAL",
        "memory_ratio": "REAL",
        "powered_off_vms": "INTEGER",
        "powered_off_vcpus": "REAL",
        "powered_off_memory_mib": "REAL",
    },
    "datastore": {
        "datastore": "TEXT",
        "capacity_mib": "REAL",
        "provisioned_mib": "REAL",
        "in_use_mib": "REAL",
        "free_mib": "REAL",
        "free_percent": "REAL",
        "accessible": "INTEGER",
    },
    "disk": {
        "vm": "TEXT",
        "template": "INTEGER",
        "power_state": "TEXT",
        "cluster": "TEXT",
        "host": "TEXT",
        "disk": "TEXT",
        "capacity_mib": "REAL",
        "raw": "INTEGER",
        "disk_mode": "TEXT",
        "sharing_mode": "TEXT",
        "raw_compatibility_mode": "TEXT",
    },
    "network": {
        "vm": "TEXT",
        "template": "INTEGER",
        "power_state": "TEXT",
        "network": "TEXT",
        "switch": "TEXT",
        "connected": "INTEGER",
        "cluster": "TEXT",
        "host": "TEXT",
    },
    "snapshot": {
        "vm": "TEXT",
        "template": "INTEGER",
        "cluster": "TEXT",
        "host": "TEXT",
        "created_at": "TEXT",
        "size_mib": "REAL",
        "power_state": "TEXT",
    },
    "dvport": {
        "port_group": "TEXT",
        "switch": "TEXT",
        "vlan": "TEXT",
        "allow_promiscuous": "INTEGER",
        "mac_changes": "INTEGER",
        "forged_transmits": "INTEGER",
        "binding_type": "TEXT",
    },
    "cdrom": {
        "vm": "TEXT",
        "template": "INTEGER",
        "power_state": "TEXT",
        "cluster": "TEXT",
        "host": "TEXT",
        "connected": "INTEGER",
        "starts_connected": "INTEGER",
        "device_type": "TEXT",
    },
    "usb": {
        "vm": "TEXT",
        "template": "INTEGER",
        "power_state": "TEXT",
        "cluster": "TEXT",
        "host": "TEXT",
        "connected": "INTEGER",
        "device_type": "TEXT",
    },
}

DEFAULT_SELECT = {
    "vm": ("vm", "power_state", "cluster", "host", "guest_os_family", "cpus", "memory_mib"),
    "host": (
        "host",
        "cluster",
        "vendor",
        "model",
        "cpu_vendor",
        "cpu_model",
        "ht_available",
        "ht_active",
        "cores",
        "memory_mib",
        "esxi_version",
    ),
    "cluster": ("cluster", "host_count", "powered_on_vms", "cpu_ratio", "memory_ratio"),
    "datastore": ("datastore", "capacity_mib", "provisioned_mib", "free_mib", "free_percent"),
    "disk": ("vm", "power_state", "cluster", "disk", "capacity_mib", "disk_mode", "raw", "sharing_mode"),
    "network": ("vm", "power_state", "network", "switch", "connected", "cluster"),
    "snapshot": ("vm", "cluster", "created_at", "size_mib", "power_state"),
    "dvport": ("port_group", "switch", "vlan", "binding_type"),
    "cdrom": ("vm", "power_state", "cluster", "connected", "starts_connected", "device_type"),
    "usb": ("vm", "power_state", "cluster", "connected", "device_type"),
}

TEMPLATE_ENTITIES = {"vm", "disk", "network", "snapshot", "cdrom", "usb"}
FILTER_OPERATORS = {"eq", "ne", "contains", "startswith", "endswith", "gt", "gte", "lt", "lte", "in"}
AGGREGATES = {"sum", "avg", "min", "max", "count_distinct"}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(row, *headers):
    return str(RVTOOLS._value(row, *headers, default="")).strip()


def _number(row, *headers):
    return RVTOOLS._whole_or_float(RVTOOLS._value(row, *headers))


def _bool(row, *headers):
    return int(RVTOOLS._truthy(RVTOOLS._value(row, *headers)))


def _optional_bool(row, *headers):
    value = RVTOOLS._value(row, *headers)
    status = RVTOOLS._optional_truthy(value)
    return None if status is None else int(status)


def _create_table(connection, entity):
    columns = ", ".join(f'"{name}" {kind}' for name, kind in ENTITY_SCHEMAS[entity].items())
    connection.execute(f'CREATE TABLE "{entity}" ({columns})')


def _insert_rows(connection, entity, values):
    columns = tuple(ENTITY_SCHEMAS[entity])
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(f'"{column}"' for column in columns)
    connection.executemany(
        f'INSERT INTO "{entity}" ({column_sql}) VALUES ({placeholders})',
        ([row.get(column) for column in columns] for row in values),
    )


def _build_index(connection, workbook_path, digest):
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    if "vInfo" not in workbook.sheetnames:
        raise ValueError("not an RVTools workbook: required vInfo sheet is missing")
    rows = {sheet: RVTOOLS._read_rows(workbook, sheet) for sheet in INDEXED_SHEETS}

    connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.executemany(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        (
            ("schema_version", INDEX_SCHEMA_VERSION),
            ("source_sha256", digest),
            ("source_file", workbook_path.name),
        ),
    )
    connection.execute(
        "CREATE TABLE query_warning (code TEXT, scope TEXT, message TEXT)"
    )
    for entity in ENTITY_SCHEMAS:
        _create_table(connection, entity)

    tool_status = {
        _text(row, "VM"): _text(row, "Tools")
        for row in rows["vTools"]
        if _text(row, "VM")
    }
    vm_values = []
    for row in rows["vInfo"]:
        guest_os, guest_os_source = RVTOOLS._guest_os(row)
        vm_name = _text(row, "VM") or "(unnamed VM)"
        vm_values.append(
            {
                "vm": vm_name,
                "power_state": _text(row, "Powerstate"),
                "template": _bool(row, "Template"),
                "cluster": _text(row, "Cluster") or "(unassigned)",
                "host": _text(row, "Host"),
                "guest_os": guest_os,
                "guest_os_family": RVTOOLS._guest_os_family(guest_os),
                "guest_os_source": guest_os_source,
                "cpus": _number(row, "CPUs"),
                "memory_mib": _number(row, "Memory", "Size MiB"),
                "provisioned_mib": _number(row, "Provisioned MiB"),
                "in_use_mib": _number(row, "In Use MiB"),
                "hardware_version": _text(row, "HW version"),
                "tools_status": tool_status.get(vm_name, ""),
                "consolidation_needed": _bool(row, "Consolidation Needed"),
            }
        )
    _insert_rows(connection, "vm", vm_values)
    vm_context = {row["vm"]: row for row in vm_values}

    _insert_rows(
        connection,
        "host",
        (
            {
                "host": _text(row, "Host") or "(unnamed host)",
                "cluster": _text(row, "Cluster") or "(unassigned)",
                "vendor": _text(row, "Vendor"),
                "model": _text(row, "Model"),
                "cpu_vendor": RVTOOLS._cpu_vendor(_text(row, "CPU Model")),
                "cpu_model": _text(row, "CPU Model"),
                "ht_available": _optional_bool(row, "HT Available"),
                "ht_active": _optional_bool(row, "HT Active"),
                "cpu_sockets": _number(row, "# CPU"),
                "cores_per_cpu": _number(row, "Cores per CPU"),
                "esxi_version": _text(row, "ESX Version"),
                "cores": _number(row, "# Cores", "Cores"),
                "cpu_speed_mhz": _number(row, "Speed"),
                "memory_mib": _number(row, "# Memory", "Memory"),
                "cpu_usage_percent": _number(row, "CPU usage %"),
                "memory_usage_percent": _number(row, "Memory usage %"),
                "bios_vendor": _text(row, "BIOS Vendor"),
                "bios_version": _text(row, "BIOS Version"),
                "bios_date": _text(row, "BIOS Date"),
            }
            for row in rows["vHost"]
        ),
    )

    overcommit = RVTOOLS._overcommit_summary(rows)
    _insert_rows(connection, "cluster", overcommit["clusters"])
    connection.executemany(
        "INSERT INTO query_warning (code, scope, message) VALUES (?, ?, ?)",
        (
            (
                warning["code"],
                str(warning.get("cluster") or warning.get("sheet") or "overcommit"),
                warning["message"],
            )
            for warning in overcommit["warnings"]
        ),
    )

    _insert_rows(
        connection,
        "datastore",
        (
            {
                "datastore": _text(row, "Name") or "(unnamed datastore)",
                "capacity_mib": _number(row, "Capacity MiB"),
                "provisioned_mib": _number(row, "Provisioned MiB"),
                "in_use_mib": _number(row, "In Use MiB"),
                "free_mib": _number(row, "Free MiB"),
                "free_percent": _number(row, "Free %"),
                "accessible": _bool(row, "Accessible"),
            }
            for row in rows["vDatastore"]
        ),
    )
    _insert_rows(
        connection,
        "disk",
        (
            {
                "vm": _text(row, "VM"),
                "template": _bool(row, "Template"),
                "power_state": vm_context.get(_text(row, "VM"), {}).get("power_state", ""),
                "cluster": vm_context.get(_text(row, "VM"), {}).get("cluster", ""),
                "host": vm_context.get(_text(row, "VM"), {}).get("host", ""),
                "disk": _text(row, "Disk"),
                "capacity_mib": _number(row, "Capacity MiB"),
                "raw": _bool(row, "Raw"),
                "disk_mode": _text(row, "Disk Mode"),
                "sharing_mode": _text(row, "Sharing mode"),
                "raw_compatibility_mode": _text(row, "Raw Comp. Mode"),
            }
            for row in rows["vDisk"]
        ),
    )
    _insert_rows(
        connection,
        "network",
        (
            {
                "vm": _text(row, "VM"),
                "template": _bool(row, "Template"),
                "power_state": vm_context.get(_text(row, "VM"), {}).get("power_state", ""),
                "network": _text(row, "Network"),
                "switch": _text(row, "Switch"),
                "connected": _bool(row, "Connected"),
                "cluster": _text(row, "Cluster")
                or vm_context.get(_text(row, "VM"), {}).get("cluster", ""),
                "host": _text(row, "Host")
                or vm_context.get(_text(row, "VM"), {}).get("host", ""),
            }
            for row in rows["vNetwork"]
        ),
    )
    _insert_rows(
        connection,
        "snapshot",
        (
            {
                "vm": _text(row, "VM"),
                "template": _bool(row, "Template"),
                "cluster": vm_context.get(_text(row, "VM"), {}).get("cluster", ""),
                "host": vm_context.get(_text(row, "VM"), {}).get("host", ""),
                "created_at": RVTOOLS._serializable(RVTOOLS._value(row, "Date / time")),
                "size_mib": _number(row, "Size MiB (total)", "Size MiB (vmsn)"),
                "power_state": _text(row, "Powerstate")
                or vm_context.get(_text(row, "VM"), {}).get("power_state", ""),
            }
            for row in rows["vSnapshot"]
        ),
    )
    _insert_rows(
        connection,
        "dvport",
        (
            {
                "port_group": _text(row, "Port"),
                "switch": _text(row, "Switch"),
                "vlan": _text(row, "VLAN"),
                "allow_promiscuous": _bool(row, "Allow Promiscuous"),
                "mac_changes": _bool(row, "Mac Changes"),
                "forged_transmits": _bool(row, "Forged Transmits"),
                "binding_type": _text(row, "Type"),
            }
            for row in rows["dvPort"]
        ),
    )
    _insert_rows(
        connection,
        "cdrom",
        (
            {
                "vm": _text(row, "VM"),
                "template": _bool(row, "Template"),
                "power_state": _text(row, "Powerstate")
                or vm_context.get(_text(row, "VM"), {}).get("power_state", ""),
                "cluster": vm_context.get(_text(row, "VM"), {}).get("cluster", ""),
                "host": vm_context.get(_text(row, "VM"), {}).get("host", ""),
                "connected": _bool(row, "Connected"),
                "starts_connected": _bool(row, "Starts Connected"),
                "device_type": _text(row, "Device Type"),
            }
            for row in rows["vCD"]
        ),
    )
    _insert_rows(
        connection,
        "usb",
        (
            {
                "vm": _text(row, "VM"),
                "template": _bool(row, "Template"),
                "power_state": _text(row, "Powerstate")
                or vm_context.get(_text(row, "VM"), {}).get("power_state", ""),
                "cluster": vm_context.get(_text(row, "VM"), {}).get("cluster", ""),
                "host": vm_context.get(_text(row, "VM"), {}).get("host", ""),
                "connected": _bool(row, "Connected"),
                "device_type": _text(row, "Device Type"),
            }
            for row in rows["vUSB"]
        ),
    )
    connection.commit()


def _cached_connection(workbook_path, index_path):
    digest = _sha256(workbook_path)
    if index_path is None:
        connection = sqlite3.connect(":memory:")
        _build_index(connection, workbook_path, digest)
        return connection, False, digest

    index_path = Path(index_path)
    if index_path.resolve() == workbook_path.resolve():
        raise ValueError("index path must not overwrite the source workbook")
    if index_path.exists():
        try:
            connection = sqlite3.connect(index_path)
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            if (
                metadata.get("schema_version") == INDEX_SCHEMA_VERSION
                and metadata.get("source_sha256") == digest
            ):
                return connection, True, digest
            connection.close()
        except sqlite3.Error:
            try:
                connection.close()
            except UnboundLocalError:
                pass

    index_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{index_path.name}.", suffix=".tmp", dir=index_path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary_path)
        _build_index(connection, workbook_path, digest)
        connection.close()
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, index_path)
        os.chmod(index_path, 0o600)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return sqlite3.connect(index_path), False, digest


def _validate_field(entity, field):
    if field not in ENTITY_SCHEMAS[entity]:
        raise ValueError(f"field '{field}' is not allowed for entity '{entity}'")
    return field


def _coerce_value(entity, field, value):
    kind = ENTITY_SCHEMAS[entity][field]
    if kind == "INTEGER":
        lowered = str(value).strip().casefold()
        if lowered in {"true", "yes", "on"}:
            return 1
        if lowered in {"false", "no", "off"}:
            return 0
        return int(value)
    if kind == "REAL":
        return float(value)
    return str(value)


def _filter_sql(entity, expression):
    if "=" not in expression:
        raise ValueError(f"filter '{expression}' must use field=value syntax")
    left, value = expression.split("=", 1)
    if "__" in left:
        field, operator = left.rsplit("__", 1)
    else:
        field, operator = left, "eq"
    _validate_field(entity, field)
    if operator not in FILTER_OPERATORS:
        raise ValueError(f"filter operator '{operator}' is not allowed")
    column = f'"{field}"'
    kind = ENTITY_SCHEMAS[entity][field]
    if operator == "in":
        values = [_coerce_value(entity, field, item.strip()) for item in value.split(",")]
        if not values:
            raise ValueError("in filter requires at least one value")
        placeholders = ", ".join("?" for _ in values)
        return f"{column} IN ({placeholders})", values
    if operator in {"contains", "startswith", "endswith"}:
        if kind != "TEXT":
            raise ValueError(f"operator '{operator}' requires a text field")
        pattern = value
        if operator in {"contains", "endswith"}:
            pattern = "%" + pattern
        if operator in {"contains", "startswith"}:
            pattern = pattern + "%"
        return f"LOWER({column}) LIKE LOWER(?)", [pattern]
    sql_operator = {
        "eq": "=",
        "ne": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
    }[operator]
    parameter = _coerce_value(entity, field, value)
    if kind == "TEXT" and operator in {"eq", "ne"}:
        return f"{column} {sql_operator} ? COLLATE NOCASE", [parameter]
    return f"{column} {sql_operator} ?", [parameter]


def _metric_sql(entity, metric):
    if metric == "count":
        return "COUNT(*)", "count"
    if ":" not in metric:
        raise ValueError(f"metric '{metric}' is not allowed")
    aggregate, field = metric.split(":", 1)
    if aggregate not in AGGREGATES:
        raise ValueError(f"aggregate '{aggregate}' is not allowed")
    _validate_field(entity, field)
    if aggregate in {"sum", "avg"} and ENTITY_SCHEMAS[entity][field] not in {"INTEGER", "REAL"}:
        raise ValueError(f"aggregate '{aggregate}' requires a numeric field")
    function = "COUNT" if aggregate == "count_distinct" else aggregate.upper()
    distinct = "DISTINCT " if aggregate == "count_distinct" else ""
    alias = f"{aggregate}_{field}"
    return f'{function}({distinct}"{field}")', alias


def _compile_query(plan):
    entity = str(plan.get("entity", "")).strip().casefold()
    if entity not in ENTITY_SCHEMAS:
        raise ValueError(f"entity '{entity}' is not allowed")
    metrics = list(plan.get("metrics") or [])
    group_by = list(plan.get("group_by") or [])
    selected = list(plan.get("select") or [])
    for field in group_by + selected:
        _validate_field(entity, field)
    if metrics and selected and set(selected) - set(group_by):
        raise ValueError("selected fields in an aggregate query must also be group_by fields")
    if metrics:
        output_fields = group_by[:]
        select_parts = [f'"{field}"' for field in group_by]
        for metric in metrics:
            expression, alias = _metric_sql(entity, metric)
            select_parts.append(f'{expression} AS "{alias}"')
            output_fields.append(alias)
    else:
        output_fields = selected or list(DEFAULT_SELECT[entity])
        select_parts = [f'"{field}"' for field in output_fields]

    where_parts = []
    parameters = []
    templates_excluded = entity in TEMPLATE_ENTITIES and not bool(plan.get("include_templates"))
    if templates_excluded:
        where_parts.append('"template" = 0')
    for expression in plan.get("filters") or []:
        sql, values = _filter_sql(entity, str(expression))
        where_parts.append(sql)
        parameters.extend(values)

    sql = f'SELECT {", ".join(select_parts)} FROM "{entity}"'
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if group_by:
        sql += " GROUP BY " + ", ".join(f'"{field}"' for field in group_by)

    allowed_order_fields = set(output_fields)
    order_parts = []
    for item in plan.get("order_by") or []:
        value = str(item)
        field, _, direction = value.partition(":")
        direction = (direction or "asc").casefold()
        if field not in allowed_order_fields or direction not in {"asc", "desc"}:
            raise ValueError(f"order_by '{item}' is not allowed")
        order_parts.append(f'"{field}" {direction.upper()}')
    if not order_parts and group_by:
        order_parts = [f'"{field}" ASC' for field in group_by]
    if order_parts:
        sql += " ORDER BY " + ", ".join(order_parts)

    limit = int(plan.get("limit", 25))
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    sql += " LIMIT ?"
    parameters.append(limit + 1)
    return entity, sql, parameters, output_fields, templates_excluded, limit


def run_query(workbook, plan, *, index_path=None):
    workbook_path = Path(workbook)
    if not workbook_path.exists():
        raise FileNotFoundError(workbook_path)
    if workbook_path.suffix.casefold() != ".xlsx":
        raise ValueError("RVTools query input must be an .xlsx workbook")
    entity, sql, parameters, fields, templates_excluded, limit = _compile_query(plan)
    connection, index_reused, digest = _cached_connection(workbook_path, index_path)
    connection.row_factory = sqlite3.Row
    try:
        fetched = connection.execute(sql, parameters).fetchall()
        cluster_scoped = entity == "cluster" or "cluster" in (plan.get("group_by") or [])
        exact_cluster = None
        for query_filter in plan.get("filters") or []:
            filter_text = str(query_filter)
            if filter_text.casefold().startswith("cluster="):
                exact_cluster = filter_text.split("=", 1)[1]
            elif filter_text.casefold().startswith("cluster__eq="):
                exact_cluster = filter_text.split("=", 1)[1]
        if entity == "cluster":
            if exact_cluster is not None:
                warning_query = (
                    "SELECT code, scope, message FROM query_warning "
                    "WHERE scope = ? COLLATE NOCASE OR code = 'multi_vcenter_sources'"
                )
                warning_parameters = (exact_cluster,)
            else:
                warning_query = "SELECT code, scope, message FROM query_warning"
                warning_parameters = ()
        elif cluster_scoped:
            warning_query = (
                "SELECT code, scope, message FROM query_warning "
                "WHERE code = 'multi_vcenter_sources'"
            )
            warning_parameters = ()
        else:
            warning_query = "SELECT code, scope, message FROM query_warning WHERE 0"
            warning_parameters = ()
        warnings = [
            dict(row)
            for row in connection.execute(warning_query, warning_parameters)
        ]
    finally:
        connection.close()
    truncated = len(fetched) > limit
    rows = [dict(row) for row in fetched[:limit]]
    return {
        "source": {"file": workbook_path.name, "sha256": digest},
        "query": {
            "entity": entity,
            "select": fields,
            "filters": list(plan.get("filters") or []),
            "group_by": list(plan.get("group_by") or []),
            "metrics": list(plan.get("metrics") or []),
        },
        "scope": {
            "templates_excluded": templates_excluded,
            "row_limit": limit,
        },
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "warnings": warnings,
        "index_reused": index_reused,
    }


def main(argv=None):
    argument_parser = argparse.ArgumentParser(
        description="Query an RVTools workbook through a local allowlisted SQLite index."
    )
    argument_parser.add_argument("workbook", type=Path, help="Path to the RVTools .xlsx export")
    argument_parser.add_argument("--entity", required=True, choices=sorted(ENTITY_SCHEMAS))
    argument_parser.add_argument("--select", action="append", default=[], help="Field to return; repeat as needed")
    argument_parser.add_argument("--metric", action="append", default=[], help="count or aggregate:field; repeat as needed")
    argument_parser.add_argument("--filter", action="append", default=[], help="field[__operator]=value; repeat as needed")
    argument_parser.add_argument("--group-by", action="append", default=[], help="Grouping field; repeat as needed")
    argument_parser.add_argument("--order-by", action="append", default=[], help="Output field[:asc|desc]; repeat as needed")
    argument_parser.add_argument("--limit", type=int, default=25, help="Maximum rows returned, from 1 to 100")
    argument_parser.add_argument("--include-templates", action="store_true", help="Include templates for VM-linked entities")
    argument_parser.add_argument("--index", type=Path, help="Optional reusable SQLite index path")
    argument_parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    args = argument_parser.parse_args(argv)
    plan = {
        "entity": args.entity,
        "select": args.select,
        "metrics": args.metric,
        "filters": args.filter,
        "group_by": args.group_by,
        "order_by": args.order_by,
        "limit": args.limit,
        "include_templates": args.include_templates,
    }
    try:
        result = run_query(args.workbook, plan, index_path=args.index)
    except (FileNotFoundError, OSError, ValueError, sqlite3.Error) as exc:
        argument_parser.exit(2, f"error: {exc}\n")
    json.dump(result, sys.stdout, indent=2 if args.pretty else None, sort_keys=args.pretty)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
