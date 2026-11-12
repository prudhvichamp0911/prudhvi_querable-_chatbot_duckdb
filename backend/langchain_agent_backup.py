import json
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from langchain_tools import query_mongodb
from backend.schema_discovery import get_schema

load_dotenv()


llm = ChatOpenRouter(
    model="google/gemini-2.5-flash",
    temperature=0
)


def clean_response(response):
    """
    Convert the model response into plain text.
    """

    if isinstance(response, list):
        response = "".join(
            item.get("text", "")
            for item in response
            if isinstance(item, dict)
        )

    return str(response).strip()


def is_database_question(question):
    """
    Decide whether the question requires MongoDB data.
    """

    router_prompt = f"""
Decide whether the user's question requires information
from the MongoDB database.

The database contains a company dataset with fields such as:

company_id
company_name
industry
country
employee_count
hr_technology
technology_category
deployment_type
annual_hr_tech_spend_usd

User question:
{question}

Return ONLY:

DATABASE

or

GENERAL

DATABASE means the answer should come from the MongoDB dataset.

Treat questions about the following as DATABASE questions:

- companies
- company names
- countries
- industries
- employee counts
- HR technologies
- technology categories
- deployment types
- HR technology spending
- counts
- averages
- totals
- unique values
- categories
- filters
- comparisons
- lists of companies

Examples:

How many companies are in India? -> DATABASE

How many companies use Workday? -> DATABASE

Which companies use Workday in the United States? -> DATABASE

What are the technology categories? -> DATABASE

What are the deployment type categories? -> DATABASE

What is the average employee count? -> DATABASE

GENERAL means the user is asking for general knowledge,
conversation, definitions, explanations, greetings,
coding help, or another question that does not require
the database.

Examples:

What is HR technology? -> GENERAL

What is MongoDB? -> GENERAL

Explain Python. -> GENERAL

Hello -> GENERAL
"""

    response = llm.invoke(router_prompt).content

    response = clean_response(response)

    return response.upper().startswith("DATABASE")


def generate_database_query(question):
    """
    Generate a MongoDB query using the live database schema.
    """

    schema = get_schema()

    schema_text = json.dumps(
        schema,
        indent=2,
        default=str
    )

    query_prompt = f"""
You are a MongoDB query generator.

The MongoDB database is:

queryable_chatbot

This is the ACTUAL schema discovered from MongoDB:

{schema_text}

User question:

{question}

Create ONE valid MongoDB query.

Return ONLY valid JSON.
Do not use markdown.
Do not use ```json.
Do not add explanations.

The JSON must contain:

collection
operation
filters
fields
pipeline

Allowed operations:

find
count
distinct
aggregate

--------------------------------------------------
COUNT
--------------------------------------------------

Use count when the user asks:

- how many
- number of companies
- count

Example:

{{
    "collection": "span_companies",
    "operation": "count",
    "filters": {{
        "country": "United States"
    }},
    "fields": [],
    "pipeline": []
}}

--------------------------------------------------
FIND
--------------------------------------------------

Use find when the user asks for actual records,
company names, or company details.

Example:

{{
    "collection": "span_companies",
    "operation": "find",
    "filters": {{
        "country": "United States",
        "hr_technology": "Workday"
    }},
    "fields": [
        "company_name"
    ],
    "pipeline": []
}}

--------------------------------------------------
DISTINCT
--------------------------------------------------

Use distinct when the user asks:

- what are the categories
- what types are available
- what values are available
- list the different categories
- unique values
- what technologies are present
- what deployment types are present

For:

What are the deployment type categories?

use:

{{
    "collection": "span_companies",
    "operation": "distinct",
    "field": "deployment_type",
    "filters": {{}},
    "fields": [],
    "pipeline": []
}}

For:

What are the technology categories?

use:

{{
    "collection": "span_companies",
    "operation": "distinct",
    "field": "technology_category",
    "filters": {{}},
    "fields": [],
    "pipeline": []
}}

IMPORTANT:

"technology_category" and "deployment_type" are DIFFERENT fields.

Do not confuse them.

--------------------------------------------------
AGGREGATE
--------------------------------------------------

Use aggregate for:

- average
- sum
- minimum
- maximum
- grouping
- totals by category
- comparisons requiring calculations

Example:

{{
    "collection": "span_companies",
    "operation": "aggregate",
    "filters": {{}},
    "fields": [],
    "pipeline": [
        {{
            "$group": {{
                "_id": null,
                "average_employee_count": {{
                    "$avg": "$employee_count"
                }}
            }}
        }}
    ]
}}

--------------------------------------------------
IMPORTANT RULES
--------------------------------------------------

1. Use ONLY collections from the actual schema.

2. Use ONLY fields from the actual schema.

3. Never invent fields.

4. Never confuse technology_category with deployment_type.

5. If the question asks for categories or unique values,
   use distinct.

6. Do not answer the question yourself.

7. Do not use general knowledge.

8. Return ONLY the JSON query.

9. Always include:
   collection
   operation
   filters
   fields
   pipeline

10. For distinct, also include:
    field

Return ONLY JSON.
"""

    response = llm.invoke(query_prompt).content

    response = clean_response(response)

    if response.startswith("```"):
        response = response.replace(
            "```json",
            ""
        )
        response = response.replace(
            "```",
            ""
        )
        response = response.strip()

    try:
        return json.loads(response)

    except json.JSONDecodeError:
        return None


def format_database_result(
    question,
    query_data,
    result
):
    """
    Format simple database results directly without
    another LLM call.

    This improves speed and prevents the LLM from
    replacing database answers with general knowledge.
    """

    operation = query_data.get(
        "operation"
    )

    # --------------------------------------------------
    # COUNT
    # --------------------------------------------------

    if operation == "count":

        if (
            isinstance(result, list)
            and len(result) > 0
            and "count" in result[0]
        ):

            count = result[0]["count"]

            return f"There are {count} companies matching your criteria."

    # --------------------------------------------------
    # DISTINCT
    # --------------------------------------------------

    if operation == "distinct":

        if isinstance(result, list):

            values = []

            for item in result:

                if (
                    isinstance(item, dict)
                    and "value" in item
                ):
                    values.append(
                        str(item["value"])
                    )

            if values:

                return (
                    "The categories in the dataset are: "
                    + ", ".join(values)
                    + "."
                )

    # --------------------------------------------------
    # FIND
    # --------------------------------------------------

    if operation == "find":

        if isinstance(result, list):

            if len(result) == 0:
                return "No matching records were found in the dataset."

            if all(
                isinstance(item, dict)
                and "company_name" in item
                for item in result
            ):

                names = [
                    item["company_name"]
                    for item in result
                ]

                return (
                    "The matching companies are: "
                    + ", ".join(names)
                    + "."
                )

    # --------------------------------------------------
    # AGGREGATE
    # --------------------------------------------------

    if operation == "aggregate":

        # Simple average result
        if (
            isinstance(result, list)
            and len(result) > 0
            and isinstance(result[0], dict)
        ):

            first = result[0]

            if "average_employee_count" in first:

                value = first[
                    "average_employee_count"
                ]

                return (
                    f"The average employee count is {value:.2f}."
                )

    return None


def run_langchain_agent(question):

    # --------------------------------------------------
    # STEP 1: ROUTING
    # --------------------------------------------------

    if not is_database_question(question):

        general_prompt = f"""
You are a helpful general-purpose AI assistant.

Answer the user's question clearly and naturally.

User question:
{question}

Give a simple and useful answer.
Do not invent facts.
"""

        answer = llm.invoke(
            general_prompt
        ).content

        return clean_response(answer)

    # --------------------------------------------------
    # STEP 2: GENERATE QUERY
    # --------------------------------------------------

    query_data = generate_database_query(
        question
    )

    if not query_data:
        return (
            "I could not create a valid database query "
            "for this question."
        )

    # --------------------------------------------------
    # STEP 3: EXECUTE QUERY
    # --------------------------------------------------

    try:

        result = query_mongodb.invoke(
            {
                "query": json.dumps(
                    query_data
                )
            }
        )

    except Exception as e:

        return (
            f"Database query failed: {str(e)}"
        )

    # --------------------------------------------------
    # STEP 4: DIRECT ANSWER
    # --------------------------------------------------

    direct_answer = format_database_result(
        question,
        query_data,
        result
    )

    if direct_answer:
        return direct_answer

    # --------------------------------------------------
    # STEP 5: FALLBACK FOR COMPLEX AGGREGATIONS
    # --------------------------------------------------

    answer_prompt = f"""
You are answering a database question.

User question:
{question}

MongoDB result:
{result}

IMPORTANT RULES:

1. Use ONLY the MongoDB result.
2. Do not use outside knowledge.
3. Do not invent information.
4. Do not change database values.
5. If the result is empty, say that no matching data
   was found.
6. Give a concise answer.

Return only the answer.
"""

    answer = llm.invoke(
        answer_prompt
    ).content

    return clean_response(answer)