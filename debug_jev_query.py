import json
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from backend.schema_discovery import get_schema
from backend.jev_router import route_question
from langchain_tools import query_mongodb

load_dotenv()

llm = ChatOpenRouter(
    model="google/gemini-2.5-flash",
    temperature=0
)

question = "How many companies are in the United States?"

print()
print("=" * 60)
print("STEP 1 - JEV ROUTING")
print("=" * 60)

try:
    jev_result = route_question(question)
    print(jev_result)
except Exception as e:
    print("Jev error:", e)
    jev_result = None


print()
print("=" * 60)
print("STEP 2 - GET MONGODB SCHEMA")
print("=" * 60)

schema_data = get_schema()
schema = json.dumps(schema_data, indent=2, default=str)

print("span_companies exists:", "span_companies" in schema_data)


print()
print("=" * 60)
print("STEP 3 - GENERATE QUERY AFTER JEV")
print("=" * 60)

query_prompt = f"""
You are a database query agent.

MongoDB database:
queryable_chatbot

Current MongoDB schema:
{schema}

User question:
{question}

Return ONE query using EXACTLY this format.

For count:

{{
    "collection": "collection_name",
    "operation": "count",
    "filters": {{}}
}}

For aggregate:

{{
    "collection": "collection_name",
    "operation": "aggregate",
    "pipeline": []
}}

Rules:

1. Return ONLY valid JSON.
2. Do not use markdown.
3. The top-level keys must include "collection" and "operation".
4. "operation" must be "find", "count", or "aggregate".
5. Never use "aggregate" as a top-level key.
6. Use only existing collections and fields.
7. For HR technology company questions, use span_companies.
8. For this question, use the simplest correct query.
"""

query_response = llm.invoke(query_prompt).content

if isinstance(query_response, list):
    query_response = "".join(
        item.get("text", "")
        for item in query_response
        if isinstance(item, dict)
    )

query_response = query_response.strip()

if query_response.startswith("```"):
    query_response = query_response.replace("```json", "")
    query_response = query_response.replace("```", "")
    query_response = query_response.strip()

print(query_response)


print()
print("=" * 60)
print("STEP 4 - DATABASE RESULT")
print("=" * 60)

try:
    query_data = json.loads(query_response)
    result = query_mongodb.invoke(json.dumps(query_data))
    print(result)
except Exception as e:
    print("Query/database error:", e)
    result = None


print()
print("=" * 60)
print("STEP 5 - FINAL ANSWER")
print("=" * 60)

answer_prompt = f"""
You are a database assistant.

User question:
{question}

MongoDB result:
{result}

Answer using ONLY the MongoDB result.

Do not invent information.

If the result contains a count, report that count exactly.
"""

answer = llm.invoke(answer_prompt).content

if isinstance(answer, list):
    answer = "".join(
        item.get("text", "")
        for item in answer
        if isinstance(item, dict)
    )

print(answer)

print()
print("=" * 60)