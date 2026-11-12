import sys
import time
import json

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter

from validator import validate_query
from database_tool import run_database_query

load_dotenv()


models = [
    ("Gemini", "~google/gemini-flash-latest"),
    ("OpenAI", "~openai/gpt-luna-latest"),
    ("Claude", "~anthropic/claude-sonnet-latest"),
]


questions = [
    "How many customers are there?",
    "Which product generated the highest revenue?"
]


schema = """
MongoDB database: queryable_chatbot

customers:
customer_id, country, signup_date

products:
product_id, product_name, category

orders:
order_id, customer_id, order_date, status

order_items:
order_id, product_id, quantity, price

sales_cleaned:
order_id, product_id, quantity, price, Revenue, customer_id, order_date, year, month
"""


def clean_json(text):
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return text


for name, model in models:

    print("\n" + "=" * 60)
    print("MODEL:", name)
    print("ID:", model)

    llm = ChatOpenRouter(
        model=model,
        temperature=0
    )

    for question in questions:

        print("\nQuestion:", question)

        prompt = f"""
You are a MongoDB query generator.

Database schema:
{schema}

User question:
{question}

Create ONE valid MongoDB query.

Return ONLY JSON.

Allowed operations:
- count
- find
- aggregate

For count use:
{{
  "collection": "customers",
  "operation": "count",
  "filters": {{}}
}}

For aggregate use:
{{
  "collection": "sales_cleaned",
  "operation": "aggregate",
  "pipeline": []
}}

Do not add explanations.
"""

        start = time.time()

        try:
            response = llm.invoke(prompt)

            elapsed = time.time() - start

            response_text = clean_json(response.content)

            print("Time:", round(elapsed, 2), "seconds")
            print("Generated query:", response_text)

            try:
                query_data = json.loads(response_text)

                if not validate_query(query_data):
                    print("Query validation: FAILED")
                    continue

                print("Query validation: PASSED")

                result = run_database_query(query_data)

                print("MongoDB result:", result)

                metadata = response.response_metadata

                print("Cost:", metadata.get("cost"))
                print("Token details:", metadata.get("cost_details"))

            except Exception as error:
                print("Query error:", error)

        except Exception as error:
            print("LLM error:", error)