import json
from langchain_tools import query_mongodb

query = {
    "collection": "span_companies",
    "operation": "count",
    "filters": {
        "country": "United States"
    }
}

tool_input = {
    "query": json.dumps(query)
}

result = query_mongodb.invoke(tool_input)

print("TOOL RESULT:")
print(result)