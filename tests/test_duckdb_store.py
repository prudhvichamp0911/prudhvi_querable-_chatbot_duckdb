"""DuckDB store: builds a read-only analytics file from the CSVs."""

import duckdb
import pytest

from backend import duckdb_store


@pytest.fixture()
def csv_sources(tmp_path):
    companies = tmp_path / "span_companies.csv"
    companies.write_text(
        "company_id,company_name,country,annual_hr_tech_spend_usd,signup_date\n"
        "S1,Alpha,India,1000.5,2024-01-02\n"
        "S2,Beta,India,3000,2024-02-03\n"
        "S3,Gamma,United States,5000,2024-03-04\n",
        encoding="utf-8",
    )
    orders = tmp_path / "orders.csv"
    orders.write_text("order_id,company_id\n1,S1\n2,S3\n", encoding="utf-8")
    return {"span_companies": companies, "orders": orders}


@pytest.fixture()
def store(tmp_path, csv_sources):
    path = tmp_path / "analytics.duckdb"
    duckdb_store.build(path, csv_sources)
    duckdb_store.reset_connection()
    yield path
    duckdb_store.reset_connection()


def test_build_creates_one_table_per_csv(store):
    with duckdb.connect(str(store), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        count = conn.execute("SELECT count(*) FROM span_companies").fetchone()[0]
    assert tables == {"span_companies", "orders"}
    assert count == 3


def test_build_skips_when_csvs_are_older(store, csv_sources):
    assert duckdb_store.build(store, csv_sources) is False


def test_build_reloads_when_forced(store, csv_sources):
    assert duckdb_store.build(store, csv_sources, force=True) is True


def test_schema_lists_tables_and_columns(store):
    schema = duckdb_store.schema(store)
    assert schema["orders"] == ["order_id", "company_id"]
    assert "annual_hr_tech_spend_usd" in schema["span_companies"]


def test_schema_text_has_types_and_text_samples(store):
    text = duckdb_store.schema_text(store)
    assert "span_companies" in text and "orders" in text
    assert "country" in text and "India" in text
    assert "DOUBLE" in text or "DECIMAL" in text


def test_connection_is_read_only(store):
    conn = duckdb_store.connect(store)
    with pytest.raises(duckdb.Error):
        conn.cursor().execute("DELETE FROM orders")


def test_connection_blocks_file_access(store, csv_sources):
    conn = duckdb_store.connect(store)
    path = str(csv_sources["orders"]).replace("\\", "/")
    with pytest.raises(duckdb.Error):
        conn.cursor().execute(f"SELECT * FROM read_csv('{path}')").fetchall()


def test_schema_text_never_samples_personal_data(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("name,contact_email,phone\nAda,ada@x.example,+44 20 7946 0000\n", encoding="utf-8")
    path = tmp_path / "p.duckdb"
    duckdb_store.build(path, {"people": csv})
    duckdb_store.reset_connection()
    try:
        text = duckdb_store.schema_text(path)
    finally:
        duckdb_store.reset_connection()
    assert "contact_email" in text and "phone" in text
    assert "ada@x.example" not in text
    assert "7946" not in text
    assert "'Ada'" in text


# --- a file built under other rules is rebuilt, never reused -------------

def test_build_writes_a_marker(store):
    import json

    marker = json.loads(duckdb_store.marker_path(store).read_text(encoding="utf-8"))
    assert marker == {"format": duckdb_store.BUILD_FORMAT, "redact_pii": True}


def test_file_without_marker_is_rebuilt(store, csv_sources):
    duckdb_store.marker_path(store).unlink()
    assert duckdb_store.build(store, csv_sources) is True


def test_file_from_older_format_is_rebuilt(store, csv_sources, monkeypatch):
    monkeypatch.setattr(duckdb_store, "BUILD_FORMAT", duckdb_store.BUILD_FORMAT + 1)
    assert duckdb_store.build(store, csv_sources) is True


def test_file_built_without_masking_is_rebuilt_when_masking_is_on(tmp_path, monkeypatch):
    csv = tmp_path / "people.csv"
    csv.write_text("name,contact_email\nAda,ada@x.example\n", encoding="utf-8")
    path = tmp_path / "p.duckdb"
    monkeypatch.setattr(duckdb_store, "_redact_enabled", lambda: False)
    duckdb_store.build(path, {"people": csv})
    monkeypatch.setattr(duckdb_store, "_redact_enabled", lambda: True)
    assert duckdb_store.build(path, {"people": csv}) is True
    duckdb_store.reset_connection()
    with duckdb.connect(str(path), read_only=True) as conn:
        assert conn.execute("SELECT contact_email FROM people").fetchone()[0] == "a***@x.example"


def test_connect_rebuilds_a_stale_default_file(tmp_path, monkeypatch):
    csv = tmp_path / "people.csv"
    csv.write_text("name,contact_email\nAda,ada@x.example\n", encoding="utf-8")
    path = tmp_path / "p.duckdb"
    monkeypatch.setattr(duckdb_store, "_redact_enabled", lambda: False)
    duckdb_store.build(path, {"people": csv})
    monkeypatch.setattr(duckdb_store, "_redact_enabled", lambda: True)
    monkeypatch.setattr(duckdb_store, "DB_PATH", path)
    monkeypatch.setattr(duckdb_store, "SOURCES", {"people": csv})
    try:
        cur = duckdb_store.connect().cursor()
        assert cur.execute("SELECT contact_email FROM people").fetchone()[0] == "a***@x.example"
    finally:
        duckdb_store.reset_connection()
