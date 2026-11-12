import json
from langchain_tools import query_mongodb

query = {
    "collection": "span_companies",
    "aggregate": [
        {
            "$match": {
                "country": "United States"
            }
        },
        {
            "$count": "company_count"
        }
    ]
}

print()
print("========== QUERY SENT TO VALIDATOR ==========")
print(json.dumps(query, indent=2))

result = query_mongodb.invoke(json.dumps(query))

print()
print("========== VALIDATOR / TOOL RESULT ==========")
print(result)
print("==============================================")