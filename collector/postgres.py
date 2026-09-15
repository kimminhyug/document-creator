"""No raw SQL input. Approved relations/columns + structured SELECT only."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}\Z")


def ident(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError("invalid SQL identifier")
    return '"' + value + '"'


def literal(value):
    if value is None:
        return "NULL"
    if type(value) is bool:
        return "TRUE" if value else "FALSE"
    if type(value) is int:
        return str(value)
    if not isinstance(value, str) or len(value) > 2000 or "\x00" in value or "\\" in value or "\n" in value or "\r" in value:
        raise ValueError("filter value must be a short string, integer, boolean or null")
    return "'" + value.replace("'", "''") + "'"


def compile_query(config, query):
    if set(query) - {"id", "relation", "columns", "filters", "order_by"}:
        raise ValueError("raw SQL/unknown query keys are not allowed")
    relation = config["relations"].get(query["relation"])
    if not relation:
        raise ValueError("relation is not approved")
    table = ident(relation["schema"]) + "." + ident(relation["table"])
    columns = query["columns"]
    if not columns or len(columns) != len(set(columns)) or any(c not in relation["columns"] for c in columns):
        raise ValueError("columns must be unique and approved")
    cap = config["max_cell_chars"]
    # Bounded display evidence, not full-fidelity numeric export. Null remains null.
    projection = ", ".join(f"pg_catalog.left({ident(c)}::text, {cap}) AS {ident(c)}" for c in columns)
    filters = []
    ops = {"eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
    for f in query.get("filters", []):
        if f["column"] not in relation["columns"] or f["op"] not in ops:
            raise ValueError("unapproved filter")
        value = f["value"]
        if value is None:
            if f["op"] not in ("eq", "ne"):
                raise ValueError("null supports eq/ne only")
            filters.append(ident(f["column"]) + (" IS NULL" if f["op"] == "eq" else " IS NOT NULL"))
        else:
            filters.append(f"{ident(f['column'])} {ops[f['op']]} {literal(value)}")
    order = []
    for item in query.get("order_by", []):
        if item["column"] not in relation["columns"] or item["direction"] not in ("asc", "desc"):
            raise ValueError("unapproved order")
        order.append(ident(item["column"]) + " " + item["direction"].upper())
    sql = f"SELECT {projection} FROM {table}"
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    if order:
        sql += " ORDER BY " + ", ".join(order)
    sql += f" LIMIT {config['max_rows'] + 1}"
    # Preflight privileges uses the same qualified relation, not caller SQL.
    relation_name = literal(table)
    privilege_checks = " AND ".join(f"NOT pg_catalog.has_table_privilege(current_user, {relation_name}, '{priv}')" for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "TRIGGER"))
    # Check column-level write grants too; table-only checks do not cover them.
    privilege_checks += f" AND NOT pg_catalog.has_any_column_privilege(current_user, {relation_name}, 'INSERT') AND NOT pg_catalog.has_any_column_privilege(current_user, {relation_name}, 'UPDATE')"
    return sql, privilege_checks


def script(config, query):
    sql, privileges = compile_query(config, query)
    return rf"""
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = {int(config['timeout_ms'])};
SET LOCAL lock_timeout = 1000;
SET LOCAL search_path = pg_catalog;
SET LOCAL standard_conforming_strings = on;
-- Division by zero aborts before reading when the account is privileged.
SELECT 1 / CASE WHEN (
 SELECT NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
 AND NOT rolreplication AND NOT rolbypassrls FROM pg_catalog.pg_roles WHERE rolname = current_user
) AND {privileges} THEN 1 ELSE 0 END AS guard \gset
SELECT pg_catalog.coalesce_placeholder;
""".replace("SELECT pg_catalog.coalesce_placeholder;", f"SELECT COALESCE(pg_catalog.json_agg(q), '[]'::json) FROM ({sql}) AS q;\nROLLBACK;\n")


def run_query(config, query, runtime):
    prefix = config["connection_env_prefix"]
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}
    for key in ("HOST", "PORT", "DATABASE", "USER"):
        val = os.environ.get(prefix + "_" + key)
        if not val:
            raise ValueError(f"missing connection environment variable: {prefix}_{key}")
        env["PG" + ("DATABASE" if key == "DATABASE" else key)] = val
    # Password never appears in arguments, settings, output or SQL.
    password = os.environ.get(prefix + "_PASSWORD")
    passfile = os.environ.get(prefix + "_PASSFILE")
    if not password and not passfile:
        raise ValueError("a product-scoped PASSWORD or PASSFILE is required")
    if password:
        env["PGPASSWORD"] = password
    if passfile:
        env["PGPASSFILE"] = passfile
    env["PGSSLMODE"] = config.get("sslmode", "verify-full")
    if env["PGSSLMODE"] not in ("verify-full", "verify-ca", "require"):
        raise ValueError("TLS is required for PostgreSQL connections")
    cert = os.environ.get(prefix + "_SSLROOTCERT")
    if cert:
        env["PGSSLROOTCERT"] = cert
    env.update(PGCONNECT_TIMEOUT="5", PGAPPNAME="document_creator_readonly", PGOPTIONS="-c default_transaction_read_only=on", PGCLIENTENCODING="UTF8")
    psql = runtime.get("psql")
    if not psql or not Path(psql).is_file():
        raise ValueError("configure local psql executable")
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        result = subprocess.run([psql, "-X", "-w", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"], input=script(config, query).encode(), stdout=stdout, stderr=stderr, env=env, timeout=config["timeout_ms"] / 1000 + 15)
        if result.returncode:
            # psql diagnostics can contain DSNs/SQL values; never publish them.
            raise RuntimeError("PostgreSQL query failed; verify read-only role, TLS and approved relation")
        stdout.seek(0)
        raw = stdout.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024:
            raise RuntimeError("query response exceeds 32 MiB")
    rows = json.loads(raw)
    return {"rows": rows[:config["max_rows"]], "row_limit_reached": len(rows) > config["max_rows"], "cell_char_limit": config["max_cell_chars"], "values_are_text": True}
