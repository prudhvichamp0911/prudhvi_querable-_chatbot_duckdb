"""DuckDB analytics store for the chat query engine (QUERY_ENGINE=duckdb).

The business CSVs in ``data/`` are loaded into one DuckDB file, one table per
CSV, named like the MongoDB collections so both engines answer the same
questions. The app only ever opens that file read-only with file and network
access switched off; ``build`` is the one place that writes it.
"""

import json
import os
import threading
from pathlib import Path

import duckdb

from backend.config import settings
from backend.guardrails import EMAIL_VALUE, PHONE_VALUE, PII_FIELD_PATTERN, _mask

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = Path(settings.duckdb_path) if settings.duckdb_path else DATA / "analytics.duckdb"

SOURCES = {
    "span_companies": DATA / "span_companies.csv",
    "customers": DATA / "kaggle_ecommerce" / "customers.csv",
    "orders": DATA / "kaggle_ecommerce" / "orders.csv",
    "order_items": DATA / "kaggle_ecommerce" / "order_items.csv",
    "products": DATA / "kaggle_ecommerce" / "products.csv",
    "sales_cleaned": DATA / "kaggle_ecommerce" / "sales_cleaned.csv",
}

SAMPLE_VALUES = 3

# Bump when the build changes what is stored (e.g. masking rules), so files
# built by an older version are rebuilt instead of served.
BUILD_FORMAT = 2

# Caps for the app's connection, so one bad query cannot exhaust the machine
# before the time limit stops it. lock_configuration stops SET from undoing them.
MEMORY_LIMIT = "512MiB"
THREADS = 2

_lock = threading.Lock()
_conn = {"path": None, "conn": None}
_schema_text_cache = {}


def _sql_literal(text):
    return "'" + str(text).replace("'", "''") + "'"


def _ident(name):
    return '"' + str(name).replace('"', '""') + '"'


def _redact_enabled():
    return bool(settings.redact_pii)


def marker_path(path):
    """Sidecar recording how the file was built (format and masking)."""

    path = Path(path)
    return path.with_name(path.name + ".build.json")


def _expected_marker():
    return {"format": BUILD_FORMAT, "redact_pii": _redact_enabled()}


def _is_stale(path, sources):
    """True when the file must be rebuilt.

    Fails closed: a missing or unreadable marker, an older build format, or a
    different masking setting all count as stale, so a file built before
    masking existed (or with it switched off) is never served.
    """

    path = Path(path)
    if not path.exists():
        return True
    try:
        marker = json.loads(marker_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if marker != _expected_marker():
        return True
    built = path.stat().st_mtime
    return any(Path(src).stat().st_mtime > built for src in sources.values() if Path(src).exists())


def _register_masking(conn):
    """SQL functions wrapping guardrails' masking, used only while building.

    Personal data is masked in the file itself rather than in query results:
    result redaction goes by output column name, and SQL has too many ways to
    rename a column (aliases, subqueries, row references) to police them all.
    """

    def mask(value):
        return None if value in (None, "") else _mask(value)

    def mask_emails(value):
        return None if value is None else EMAIL_VALUE.sub(lambda m: _mask(m.group(0)), value)

    conn.create_function("qc_mask", mask, ["VARCHAR"], "VARCHAR")
    conn.create_function("qc_mask_emails", mask_emails, ["VARCHAR"], "VARCHAR")


def _column_expr(name, data_type):
    col = _ident(name)
    if not _redact_enabled():
        return col
    if PII_FIELD_PATTERN.search(name):
        return f"qc_mask(CAST({col} AS VARCHAR)) AS {col}"
    if data_type == "VARCHAR":
        return f"qc_mask_emails({col}) AS {col}"
    return col


def build(path=None, sources=None, force=False):
    """Load every CSV into ``path``. Returns True when the file was (re)built."""

    path = Path(path or DB_PATH)
    sources = sources or SOURCES
    if not force and not _is_stale(path, sources):
        return False

    # Close the app's read-only handle first: Windows will not replace an
    # open file.
    reset_connection()
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    marker = marker_path(path)
    if marker.exists():
        marker.unlink()  # an interrupted build must not look current

    with duckdb.connect(str(tmp)) as conn:
        if _redact_enabled():
            _register_masking(conn)
        for table, csv_path in sources.items():
            csv_text = str(Path(csv_path)).replace("\\", "/")
            source = f"read_csv_auto({_sql_literal(csv_text)}, header = true)"
            columns = conn.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()
            select = ", ".join(_column_expr(name, data_type) for name, data_type, *_ in columns)
            conn.execute(f"CREATE TABLE {_ident(table)} AS SELECT {select} FROM {source}")
    os.replace(tmp, path)
    marker.write_text(json.dumps(_expected_marker()), encoding="utf-8")
    _schema_text_cache.clear()
    return True


def reset_connection():
    with _lock:
        if _conn["conn"] is not None:
            try:
                _conn["conn"].close()
            except duckdb.Error:
                pass
        _conn["path"], _conn["conn"] = None, None


def connect(path=None):
    """Shared read-only connection; callers use ``.cursor()`` per query."""

    if path is None:
        path = DB_PATH
        if _is_stale(path, SOURCES):
            build(path, SOURCES)
    path = str(Path(path))

    with _lock:
        if _conn["conn"] is None or _conn["path"] != path:
            if _conn["conn"] is not None:
                _conn["conn"].close()
            _conn["conn"] = duckdb.connect(
                path,
                read_only=True,
                config={
                    "enable_external_access": False,
                    "memory_limit": MEMORY_LIMIT,
                    "threads": THREADS,
                    "lock_configuration": True,
                },
            )
            _conn["path"] = path
        return _conn["conn"]


def table_names(path=None):
    cur = connect(path).cursor()
    try:
        rows = cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
    finally:
        cur.close()
    return [row[0] for row in rows]


def _columns(cur):
    rows = cur.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'main' ORDER BY table_name, ordinal_position"
    ).fetchall()
    columns = {}
    for table, column, data_type in rows:
        columns.setdefault(table, []).append((column, data_type))
    return columns


def schema(path=None):
    """``{table: [column, ...]}``, the same shape as MongoDB schema discovery."""

    cur = connect(path).cursor()
    try:
        return {table: [name for name, _ in cols] for table, cols in _columns(cur).items()}
    finally:
        cur.close()


def schema_text(path=None):
    """Tables with row counts, column types and a few text samples, for the LLM."""

    conn = connect(path)
    key = (_conn["path"], os.path.getmtime(_conn["path"]))
    if key in _schema_text_cache:
        return _schema_text_cache[key]

    cur = conn.cursor()
    try:
        lines = []
        for table, cols in _columns(cur).items():
            count = cur.execute(f"SELECT count(*) FROM {_ident(table)}").fetchone()[0]
            lines.append(f"TABLE {table} ({count} rows)")
            for name, data_type in cols:
                line = f"  - {name} {data_type}"
                # Example values go to the LLM, so personal-data columns
                # (and values that look like e-mails or phone numbers) are
                # never sampled.
                if data_type == "VARCHAR" and not PII_FIELD_PATTERN.search(name):
                    samples = cur.execute(
                        f"SELECT DISTINCT {_ident(name)} FROM {_ident(table)} "
                        f"WHERE {_ident(name)} IS NOT NULL LIMIT {SAMPLE_VALUES}"
                    ).fetchall()
                    samples = [
                        row[0] for row in samples
                        if not EMAIL_VALUE.search(str(row[0])) and not PHONE_VALUE.search(str(row[0]))
                    ]
                    if samples:
                        line += "  e.g. " + ", ".join(repr(value) for value in samples)
                lines.append(line)
        text = "\n".join(lines)
    finally:
        cur.close()

    _schema_text_cache.clear()
    _schema_text_cache[key] = text
    return text
