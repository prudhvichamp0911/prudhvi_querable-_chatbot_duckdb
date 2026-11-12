"""Validated, read-only SQL execution against the DuckDB analytics store.

Checks run before anything touches the database:
  1. exactly one statement, and it is a SELECT (WITH / UNION allowed);
  2. every table is one of the analytics tables (or a CTE defined in the query);
  3. no file, network or environment functions (read_csv, glob, getenv, ...).

The connection itself is read-only with external access disabled, rows are
capped at MAX_RESULT_ROWS, queries are interrupted after the time limit, and
results pass through the same PII redaction as MongoDB results. Personal
data is also masked in the DuckDB file itself (see duckdb_store.build), so
renaming a column in SQL cannot reveal the raw values.
"""

import datetime
import decimal
import threading
import uuid

import duckdb
import sqlglot
from sqlglot import exp

from backend import duckdb_store
from backend.config import settings
from backend.guardrails import redact_pii

MAX_ROWS = settings.max_result_rows
TIMEOUT_SECONDS = settings.mongo_max_time_ms / 1000

BLOCKED_FUNCTIONS = {
    "glob", "getenv", "query", "query_table", "sniff_csv", "parquet_scan",
    "parquet_metadata", "parquet_schema", "parquet_file_metadata",
    "parquet_kv_metadata", "iceberg_scan", "delta_scan", "load", "install",
    "duckdb_secrets", "duckdb_settings", "current_setting", "ducklake",
    # Functions that can build huge values from a tiny query.
    "range", "generate_series", "repeat", "list_resize", "array_resize",
    "lpad", "rpad", "list_repeat", "array_repeat", "string_split_regex",
}
BLOCKED_PREFIXES = ("read_", "write_", "duckdb_", "pg_", "sqlite_", "mysql_", "postgres_")
QUERY_TYPES = (exp.Select, exp.Union, exp.Intersect, exp.Except)


class SQLValidationError(ValueError):
    """The SQL was rejected before it reached the database."""


class SQLTimeoutError(RuntimeError):
    """The query ran longer than the time limit and was stopped."""


def _function_name(node):
    if isinstance(node, exp.Anonymous):
        return str(node.this or "").lower()
    return (node.sql_name() or "").lower()


def validate_sql(sql, allowed_tables):
    """Raise SQLValidationError unless ``sql`` is one safe SELECT."""

    sql = (sql or "").strip()
    if not sql:
        raise SQLValidationError("The SQL query is empty.")

    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as error:
        raise SQLValidationError(f"The SQL could not be parsed: {error}") from error

    if len(statements) != 1:
        raise SQLValidationError("Send exactly one statement; only one SELECT is allowed.")

    tree = statements[0]
    if not isinstance(tree, QUERY_TYPES):
        raise SQLValidationError(
            f"Only SELECT queries are allowed (got {tree.key.upper()})."
        )

    for node in tree.walk():
        if isinstance(node, exp.Command) or isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create)):
            raise SQLValidationError("Only SELECT queries are allowed.")
        if isinstance(node, exp.Func):
            name = _function_name(node)
            if name in BLOCKED_FUNCTIONS or name.startswith(BLOCKED_PREFIXES):
                raise SQLValidationError(f"The function {name} is not allowed.")

    allowed = {name.lower() for name in allowed_tables}
    ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            name = table.this.sql(dialect="duckdb") if table.this else "?"
            raise SQLValidationError(f"Only plain table names are allowed, not {name}.")
        name = table.name.lower()
        if table.args.get("db") or table.args.get("catalog"):
            raise SQLValidationError(f"Use the table name only, not {table.sql(dialect='duckdb')}.")
        if name not in allowed and name not in ctes:
            raise SQLValidationError(
                f"Unknown table {table.name}. Available tables: {', '.join(sorted(allowed))}."
            )

    return tree.sql(dialect="duckdb")


def _plain(value):
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def run_sql(sql):
    """Validate and run one SELECT; returns a list of plain dict rows."""

    conn = duckdb_store.connect()
    safe_sql = validate_sql(sql, duckdb_store.table_names())

    cur = conn.cursor()
    timed_out = threading.Event()

    def stop():
        timed_out.set()
        cur.interrupt()

    timer = threading.Timer(TIMEOUT_SECONDS, stop)
    timer.start()
    try:
        cur.execute(safe_sql)
        columns = [col[0] for col in cur.description]
        rows = cur.fetchmany(MAX_ROWS)
    except duckdb.Error as error:
        if timed_out.is_set():
            raise SQLTimeoutError(
                f"The query took longer than {TIMEOUT_SECONDS:g} s and was stopped."
            ) from error
        raise
    finally:
        timer.cancel()
        cur.close()

    records = [{col: _plain(value) for col, value in zip(columns, row)} for row in rows]
    return redact_pii(records)
