"""SQL safety checks and execution for the DuckDB query engine."""

import datetime
import decimal

import duckdb
import pytest

from backend import duckdb_store, sql_tool
from backend.sql_tool import SQLValidationError, validate_sql

TABLES = {"span_companies", "orders"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT country, count(*) AS n FROM span_companies GROUP BY country",
        "WITH t AS (SELECT * FROM span_companies) SELECT count(*) FROM t",
        "SELECT o.order_id FROM orders o JOIN span_companies s ON o.company_id = s.company_id",
        "SELECT country FROM span_companies UNION SELECT company_id FROM orders",
        "SELECT count(*) AS count FROM span_companies;",
    ],
)
def test_valid_selects_pass(sql):
    validate_sql(sql, TABLES)


@pytest.mark.parametrize(
    "sql, reason",
    [
        ("DROP TABLE orders", "SELECT"),
        ("DELETE FROM orders", "SELECT"),
        ("INSERT INTO orders VALUES (1, 'x')", "SELECT"),
        ("SELECT 1; DROP TABLE orders", "one statement"),
        ("ATTACH 'x.db'", "SELECT"),
        ("COPY orders TO 'out.csv'", "SELECT"),
        ("PRAGMA show_tables", "SELECT"),
        ("SELECT * FROM secret_table", "secret_table"),
        ("SELECT * FROM read_csv('C:/Windows/win.ini')", "read_csv"),
        ("SELECT * FROM read_parquet('x.parquet')", "read_parquet"),
        ("SELECT getenv('OPENROUTER_API_KEY')", "getenv"),
        ("SELECT * FROM glob('*')", "glob"),
        ("", "empty"),
        ("SELEC country FROM", "parse"),
    ],
)
def test_unsafe_or_bad_sql_is_rejected(sql, reason):
    with pytest.raises(SQLValidationError) as error:
        validate_sql(sql, TABLES)
    assert reason.lower() in str(error.value).lower()


@pytest.fixture()
def store(tmp_path, monkeypatch):
    csv = tmp_path / "span_companies.csv"
    rows = ["company_id,country,spend,signup_date,contact_email"]
    rows += [f"S{i},Country{i % 3},{i}.5,2024-01-0{1 + i % 9},p{i}@corp.example" for i in range(300)]
    csv.write_text("\n".join(rows) + "\n", encoding="utf-8")
    path = tmp_path / "analytics.duckdb"
    duckdb_store.build(path, {"span_companies": csv})
    duckdb_store.reset_connection()
    monkeypatch.setattr(duckdb_store, "DB_PATH", path)
    yield path
    duckdb_store.reset_connection()


def test_run_sql_returns_rows_as_dicts(store):
    rows = sql_tool.run_sql(
        "SELECT country, count(*) AS company_count FROM span_companies "
        "GROUP BY country ORDER BY country"
    )
    assert rows == [
        {"country": "Country0", "company_count": 100},
        {"country": "Country1", "company_count": 100},
        {"country": "Country2", "company_count": 100},
    ]


def test_run_sql_caps_rows(store, monkeypatch):
    monkeypatch.setattr(sql_tool, "MAX_ROWS", 50)
    assert len(sql_tool.run_sql("SELECT * FROM span_companies")) == 50


def test_run_sql_makes_values_json_friendly(store):
    row = sql_tool.run_sql(
        "SELECT CAST(spend AS DECIMAL(10,2)) AS d, signup_date FROM span_companies LIMIT 1"
    )[0]
    assert isinstance(row["d"], float)
    assert isinstance(row["signup_date"], str)
    assert not isinstance(row["d"], decimal.Decimal)
    assert not isinstance(row["signup_date"], datetime.date)


def test_run_sql_redacts_pii(store):
    rows = sql_tool.run_sql("SELECT contact_email FROM span_companies WHERE company_id = 'S7'")
    assert rows == [{"contact_email": "p***@corp.example"}]


def test_run_sql_rejects_unsafe_sql(store):
    with pytest.raises(SQLValidationError):
        sql_tool.run_sql("DROP TABLE span_companies")


def test_run_sql_stops_at_time_limit(store, monkeypatch):
    monkeypatch.setattr(sql_tool, "TIMEOUT_SECONDS", 0.2)
    with pytest.raises(sql_tool.SQLTimeoutError):
        sql_tool.run_sql(
            "SELECT count(*) FROM span_companies a, span_companies b, "
            "span_companies c, span_companies d"
        )


# --- personal data is masked in the file itself ------------------------
# Redaction by output column name can be dodged by renaming (aliases,
# subqueries, row references), so the DuckDB file stores masked values and
# no query can return the raw ones.

RAW = ["ada.lovelace@corp.example", "+44 20 7946 0001", "12 Analytical Engine Rd"]


@pytest.fixture()
def pii_store(tmp_path, monkeypatch):
    csv = tmp_path / "people.csv"
    csv.write_text(
        "name,contact_email,phone,home_address,notes\n"
        "Ada,ada.lovelace@corp.example,+44 20 7946 0001,12 Analytical Engine Rd,"
        "reach me at ada.lovelace@corp.example\n",
        encoding="utf-8",
    )
    path = tmp_path / "pii.duckdb"
    duckdb_store.build(path, {"people": csv})
    duckdb_store.reset_connection()
    monkeypatch.setattr(duckdb_store, "DB_PATH", path)
    yield path
    duckdb_store.reset_connection()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM people",
        "SELECT contact_email AS x, phone AS y, home_address AS z, notes AS n FROM people",
        "SELECT x FROM (SELECT contact_email AS x FROM people) AS t",
        "SELECT a, b, c FROM people AS t(nm, a, b, c)",
        "SELECT CAST(people AS VARCHAR) AS row_text FROM people",
        "SELECT replace(contact_email, '@', ' at ') AS e FROM people",
        "SELECT name FROM people UNION ALL SELECT contact_email FROM people",
        "WITH t AS (SELECT phone AS p FROM people) SELECT p FROM t",
    ],
)
def test_raw_personal_data_never_leaves_duckdb(pii_store, sql):
    text = str(sql_tool.run_sql(sql))
    for raw in RAW:
        assert raw not in text
    assert "lovelace" not in text and "7946 0001" not in text


def test_masked_values_keep_the_existing_format(pii_store):
    row = sql_tool.run_sql("SELECT name, contact_email, notes FROM people")[0]
    assert row["name"] == "Ada"
    assert row["contact_email"] == "a***@corp.example"
    assert row["notes"] == "reach me at a***@corp.example"


def test_counting_personal_data_still_works(pii_store):
    rows = sql_tool.run_sql("SELECT count(DISTINCT contact_email) AS n FROM people")
    assert rows == [{"n": 1}]


# --- resource limits ------------------------------------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT repeat('x', 1000000000) AS s FROM orders",
        "SELECT range(100000000) AS r FROM orders",
        "SELECT generate_series(1, 100000000) AS r FROM orders",
        "SELECT list_resize([1], 100000000) AS r FROM orders",
        "SELECT * FROM range(1000000000000)",
    ],
)
def test_value_building_functions_are_blocked(sql):
    with pytest.raises(SQLValidationError):
        validate_sql(sql, TABLES)


def test_connection_has_memory_and_thread_caps(store):
    cur = duckdb_store.connect().cursor()
    threads = cur.execute("SELECT current_setting('threads')").fetchone()[0]
    memory = cur.execute("SELECT current_setting('memory_limit')").fetchone()[0]
    assert int(threads) <= duckdb_store.THREADS
    assert memory.startswith("512")
    with pytest.raises(duckdb.Error):
        cur.execute("SET memory_limit = '64GB'")
