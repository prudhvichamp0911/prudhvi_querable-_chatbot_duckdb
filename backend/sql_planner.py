"""SQL prompt and response parsing for the DuckDB query engine.

Pure functions: ``langchain_agent`` makes the LLM call and passes the text in,
so this module is easy to test and never talks to the model or the database.
"""

import json
import re

import sqlglot
from sqlglot import exp

OPERATIONS = {"select", "count"}


def build_sql_prompt(question, schema_text, hints="", feedback=""):
    # geo.query_hints is shared with the MongoDB planner and says "$in".
    hints = (hints or "").replace(
        "Filter the country field with $in over these",
        "Filter with country IN (...) using these",
    )
    return f"""
You are a careful DuckDB SQL planner for a read-only analytics chatbot.
Write one DuckDB SQL query that answers the user's question.

Available tables (column types, and a few example values for text columns):

{schema_text}

User question:
{question}

{hints}

{feedback}

Return ONLY one valid JSON object with this structure:

{{
    "operation": "select",
    "sql": "SELECT ..."
}}

"operation" is "count" when the answer is a single record count, otherwise
"select".

QUERY RULES:

1. Write exactly one SELECT statement (WITH ... SELECT is fine).
   Never write INSERT, UPDATE, DELETE, CREATE, DROP, COPY, ATTACH, PRAGMA,
   SET or INSTALL, and never read files (read_csv, read_parquet, glob).

2. Use only the tables and columns listed above, spelled exactly as listed.
   Quote a column with double quotes only if its name needs it.

3. Pick the table that actually holds the requested records.
   Do not always use the same table.

4. For a single record count, return one column aliased exactly "count",
   e.g. SELECT count(*) AS count FROM ... and set "operation": "count".

5. For totals, averages, minimums, maximums and per-group figures, use
   aggregate functions with GROUP BY on the exact dimension requested.
   Give every computed column a short snake_case alias such as
   company_count, total_revenue or avg_spend. Put the label column first.

6. For top or bottom N, compute the metric for every group, then
   ORDER BY it in the right direction and LIMIT N.

7. Match text with the spellings shown in the example values. Use
   ILIKE for case-insensitive or partial matches.

8. JOIN tables only on real key columns that exist in both tables
   (for example orders.customer_id = customers.customer_id).

9. For percentages, use the correct numerator and denominator.
   Multiply by 100.0 and ROUND to 2 decimals.

10. Return raw numbers. Do not build sentences or mix text and numbers
    inside the query.

11. Include every metric and condition the user asked for. Do not
    substitute a different grouping or metric.

12. If part of the question cannot be answered from these tables, query
    the part that can be answered. The final answer will explain the gap.

13. Keep result sets small: add LIMIT 50 to queries that list records
    unless the user asked for a specific number.

14. Return valid JSON only, without Markdown or explanations.
"""


def _strip_fences(text):
    text = str(text or "").strip()
    match = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _tables(sql):
    try:
        tree = sqlglot.parse_one(sql, read="duckdb")
    except sqlglot.errors.ParseError:
        return []
    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    names = []
    for table in tree.find_all(exp.Table):
        if table.name and table.name not in ctes and table.name not in names:
            names.append(table.name)
    return names


def parse_sql_response(text):
    """The model's JSON as a query dict, or None when it is unusable.

    The dict keeps the shape the rest of the app expects: ``operation`` for
    the direct count/empty shortcuts and ``collection`` for the query card.
    """

    try:
        data = json.loads(_strip_fences(text))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    sql = str(data.get("sql") or "").strip()
    if not sql:
        return None

    operation = str(data.get("operation") or "select").lower()
    if operation not in OPERATIONS:
        operation = "select"

    return {
        "engine": "duckdb",
        "operation": operation,
        "sql": sql,
        "collection": ", ".join(_tables(sql)),
    }
