import json
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from backend.schema_discovery import get_schema

load_dotenv()

llm = ChatOpenRouter(
    model="google/gemini-2.5-flash",
    temperature=0
)

question = "How many companies are in the United States?"

schema_data = get_schema()
schema = json.dumps(schema_data, indent=2, default=str)

query_prompt = f"""
You are a database query agent.

The MongoDB database is:

queryable_chatbot

Here is the current database schema discovered directly
from MongoDB:

{schema}

The user asked:

{question}

Create ONE valid MongoDB query for the user's question.

Return ONLY valid JSON.
Do not use markdown.
Do not use ```json.
Do not add explanations.

Rules:

1. Use only collections that exist in the provided schema.
2. Use only fields that exist in the selected collection.
3. Choose the collection that best matches the user's question.
4. For questions about HR technology companies, use
   the span_companies collection when appropriate.
5. Do not invent collections.
6. Do not invent fields.
7. Return exactly ONE query as valid JSON.
"""

response = llm.invoke(query_prompt).content

if isinstance(response, list):
    response = "".join(
        item.get("text", "")
        for item in response
        if isinstance(item, dict)
    )

response = response.strip()

print()
print("========== GENERATED QUERY ==========")
print(response)
print("=====================================")