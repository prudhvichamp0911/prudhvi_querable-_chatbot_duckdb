import json
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from backend.schema_discovery import get_schema
from langchain_tools import query_mongodb

load_dotenv()

llm = ChatOpenRouter(
    model="google/gemini-2.5-flash",
    temperature=0
)

question = "How many companies are in the United States?"

# Get the live MongoDB schema
schema_data = get_schema()
schema = json.dumps(schema_data, indent=2, default=str)

# Ask the LLM to generate the application query
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

print()
print("========== 1. GENERATED QUERY ==========")
print(query_response)
print("=========================================")

# Convert generated response to JSON
try:
    query_data = json.loads(query_response)
except json.JSONDecodeError:
    print()
    print("QUERY JSON ERROR")
    raise

# Send the exact query through the existing validation/database tool
result = query_mongodb.invoke(json.dumps(query_data))

print()
print("========== 2. DATABASE TOOL RESULT ==========")
print(result)
print("==============================================")

# Ask the LLM to turn the database result into the final answer
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

print()
print("========== 3. FINAL LLM ANSWER ==========")
print(answer)
print("==========================================")