"""The agent's DuckDB path (QUERY_ENGINE=duckdb), with the LLM faked."""

import json
from types import SimpleNamespace

import pytest

from backend import chat_service, duckdb_store, jev_router, langchain_agent
from backend.insights import result_insights


@pytest.fixture()
def duck(tmp_path, monkeypatch):
    csv = tmp_path / "span_companies.csv"
    csv.write_text(
        "company_id,company_name,country,deployment_type,annual_hr_tech_spend_usd\n"
        "S1,Alpha,India,SaaS,1000\n"
        "S2,Beta,India,Hybrid,3000\n"
        "S3,Gamma,United States,Hybrid,5000\n",
        encoding="utf-8",
    )
    path = tmp_path / "analytics.duckdb"
    duckdb_store.build(path, {"span_companies": csv})
    duckdb_store.reset_connection()
    monkeypatch.setattr(duckdb_store, "DB_PATH", path)
    monkeypatch.setenv("QUERY_ENGINE", "duckdb")
    from backend.schema_discovery import clear_schema_cache

    clear_schema_cache()
    yield path
    clear_schema_cache()
    duckdb_store.reset_connection()


def fake_llm(monkeypatch, *outputs):
    prompts = []
    calls = iter(outputs)

    def invoke(prompt, stage):
        prompts.append(prompt)
        return SimpleNamespace(content=next(calls))

    monkeypatch.setattr(langchain_agent, "monitored_llm_invoke", invoke)
    return prompts


def test_schema_context_comes_from_duckdb(duck):
    schema, text = langchain_agent.get_schema_context()
    assert list(schema) == ["span_companies"]
    assert "TABLE span_companies (3 rows)" in text
    assert "'India'" in text


def test_get_schema_follows_engine(duck):
    from backend.schema_discovery import get_schema

    assert "deployment_type" in get_schema()["span_companies"]


def test_generate_sql_query_uses_sql_prompt(duck, monkeypatch):
    sql = "SELECT country, count(*) AS company_count FROM span_companies GROUP BY country"
    prompts = fake_llm(monkeypatch, json.dumps({"operation": "select", "sql": sql}))

    query = langchain_agent.generate_database_query("Companies per country?")

    assert query == {
        "engine": "duckdb",
        "operation": "select",
        "sql": sql,
        "collection": "span_companies",
    }
    assert "DuckDB SQL" in prompts[0]
    assert "TABLE span_companies" in prompts[0]
    assert "$match" not in prompts[0]


def test_generate_sql_query_strips_fences_and_defaults_operation(duck, monkeypatch):
    fake_llm(monkeypatch, '```json\n{"sql": "SELECT count(*) AS count FROM span_companies"}\n```')
    query = langchain_agent.generate_database_query("How many companies?")
    assert query["operation"] == "select"
    assert query["sql"].startswith("SELECT count(*)")


@pytest.mark.parametrize("output", ["not json", "[]", '{"operation": "select"}', '{"sql": ""}'])
def test_generate_sql_query_rejects_bad_output(duck, monkeypatch, output):
    fake_llm(monkeypatch, output)
    assert langchain_agent.generate_database_query("anything") is None


def test_repair_feedback_reaches_the_prompt(duck, monkeypatch):
    prompts = fake_llm(monkeypatch, '{"sql": "SELECT 1 AS x FROM span_companies"}')
    langchain_agent.generate_database_query("q", 'Binder Error: column "contry" not found')
    assert 'column "contry" not found' in prompts[0]


def test_execute_runs_sql_on_duckdb(duck):
    rows = langchain_agent.execute_mongodb_query(
        {
            "engine": "duckdb",
            "operation": "select",
            "sql": "SELECT deployment_type, avg(annual_hr_tech_spend_usd) AS avg_spend "
            "FROM span_companies GROUP BY deployment_type ORDER BY avg_spend DESC",
        }
    )
    assert rows == [
        {"deployment_type": "Hybrid", "avg_spend": 4000.0},
        {"deployment_type": "SaaS", "avg_spend": 1000.0},
    ]


@pytest.mark.parametrize(
    "sql, message",
    [
        ("DROP TABLE span_companies", "SELECT"),
        ("SELECT contry FROM span_companies", "contry"),
    ],
)
def test_execute_raises_with_the_real_error(duck, sql, message):
    with pytest.raises(RuntimeError) as error:
        langchain_agent.execute_mongodb_query({"engine": "duckdb", "operation": "select", "sql": sql})
    assert message in str(error.value)


def test_count_result_is_formatted_directly(duck):
    text = langchain_agent.format_database_result(
        {"engine": "duckdb", "operation": "count"}, [{"count": 38}]
    )
    assert text == "The query returned 38 matching records."


def test_full_agent_answers_from_duckdb(duck, monkeypatch):
    monkeypatch.setattr(langchain_agent, "is_database_question", lambda q: True)
    fake_llm(monkeypatch, '{"operation": "count", "sql": "SELECT count(*) AS count FROM span_companies WHERE country = \'India\'"}')
    assert langchain_agent.run_langchain_agent("How many companies are in India?") == (
        "The query returned 2 matching records."
    )


def test_query_cache_key_includes_engine(monkeypatch):
    monkeypatch.setenv("QUERY_ENGINE", "duckdb")
    duck_key = chat_service._cache_key("How many  companies?")
    monkeypatch.setenv("QUERY_ENGINE", "mongo")
    mongo_key = chat_service._cache_key("how many companies?")
    assert duck_key != mongo_key
    assert duck_key.endswith("how many companies?")


def test_router_names_tables_for_duckdb(monkeypatch):
    monkeypatch.setenv("QUERY_ENGINE", "duckdb")
    text = jev_router._schema_summary({"span_companies": ["country"]})
    assert "MongoDB" not in text
    assert "tables" in text


def test_insights_read_sql_style_rows():
    rows = [
        {"country": "United States", "company_count": 176},
        {"country": "India", "company_count": 38},
        {"country": "Germany", "company_count": 20},
    ]
    insights = result_insights(rows)
    assert insights
    assert "United States" in json.dumps(insights)


def test_geography_hints_use_sql_wording():
    from backend.geo import query_hints
    from backend.sql_planner import build_sql_prompt

    prompt = build_sql_prompt("Companies in Europe?", "TABLE t", query_hints("Companies in Europe?"))
    assert "Germany" in prompt
    assert "$in" not in prompt
    assert "country IN (" in prompt


def test_health_reports_query_engine(duck, app_client):
    body = app_client.get("/api/health").json()
    assert body["query_engine"] == "duckdb"
    assert body["duckdb"] == "ok"
