# Queryable Chatbot

A natural-language chatbot that allows users to query structured business data stored in MongoDB. The project combines LangChain, Jev, Gemini through OpenRouter, FastAPI, and OpenUI, with Graphiti and Neo4j providing a contextual knowledge layer where integrated.

## 1. Project Overview

The chatbot enables users to ask business questions in natural language and receive answers based on structured data. It supports company searches, counts, aggregations, spending comparisons, category analysis, and general questions.

**Objectives**
- Simplify access to business data.
- Convert natural-language questions into database queries.
- Validate queries before execution.
- Provide conversational responses.
- Evaluate answer correctness, security, and performance.

## 2. Architecture

### Main request flow

```text
User
  ↓
OpenUI Frontend
  ↓
FastAPI Backend
  ↓
Jev Routing
  ↓
LangChain Agent
  ↓
Query Generation and Validation
  ↓
MongoDB
  ↓
Result Formatting
  ↓
Response to OpenUI
```

### Knowledge graph flow

```text
Project / Contextual Information
              ↓
           Graphiti
              ↓
            Neo4j
              ↓
      Entities and Relationships
              ↓
        Context Retrieval
```

MongoDB is the source of truth for structured business data. Graphiti and Neo4j provide contextual knowledge and relationships. Their participation in individual requests depends on the actual integration.

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend and evaluation scripts |
| FastAPI | Backend API |
| LangChain | Queryable agent and tool integration |
| Jev | Request routing and verification |
| MongoDB / PyMongo | Structured data storage and retrieval |
| Gemini | Configured language model |
| OpenRouter | LLM API gateway |
| Graphiti | Contextual knowledge management |
| Neo4j | Graph database |
| OpenUI | User interface |
| TypeScript | Frontend development where applicable |

The current `backend/langchain_agent.py` configuration uses `google/gemini-2.5-flash` through OpenRouter.

## 4. Component Responsibilities

- **FastAPI:** Accepts questions through the `/ask` endpoint and returns answers.
- **LangChain:** Routes questions, generates database queries, and formats results.
- **Jev:** Provides a routing and verification layer.
- **MongoDB:** Stores structured company data and executes database queries.
- **Gemini + OpenRouter:** Supports language understanding and response generation.
- **Graphiti + Neo4j:** Provides contextual knowledge and graph relationships where integrated.
- **OpenUI:** Presents questions and chatbot responses.

## 5. Project Structure

```text
Queryable_chatbot/
├── backend/
│   ├── main.py
│   ├── langchain_agent.py
│   ├── langchain_tools.py
│   ├── jev_router.py
│   ├── database_tool.py
│   ├── mongodb.py
│   ├── schema_discovery.py
│   ├── validator.py
│   ├── query_executor.py
│   └── graphiti_service.py
├── openui_test/
│   ├── src/
│   ├── public/
│   └── package.json
├── evaluate_golden_set.py
├── evaluation_results.json
├── requirements.txt
├── README.md
└── .gitignore
```

This is a representative structure; the project also contains additional modules and tests.

## 6. Dataset and Database

**Database:** `queryable_chatbot`

**Main collection:** `span_companies`

The dataset contains 500 company records.

| Field | Description |
|---|---|
| `company_id` | Company identifier |
| `company_name` | Company name |
| `industry` | Industry classification |
| `country` | Country |
| `employee_count` | Number of employees |
| `hr_technology` | HR technology used |
| `technology_category` | Technology category |
| `deployment_type` | Deployment model |
| `annual_hr_tech_spend_usd` | Annual HR technology spending in USD |

The application also has other collections, including `orders`, `employees`, `customers`, `order_items`, `products`, and `sales_cleaned`.

MongoDB connection, collection discovery, sample-record retrieval, and representative database queries have been tested.

## 7. Environment Setup

### Prerequisites

- Python 3.10 or a compatible version
- MongoDB
- Node.js and npm for the frontend
- OpenRouter API key
- Neo4j and Graphiti configuration if required

### Install the backend

Clone the repository if you do not already have it:

```powershell
git clone https://github.com/veereshshetkar123/Queryable_chatbot.git
cd Queryable_chatbot
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a local `.env` file with the required configuration:

```dotenv
OPENROUTER_API_KEY=your_key_here
```

Add any other environment variables required by your configuration. Never commit actual credentials.

### Quick start (Windows)

One command starts MongoDB (if needed), the backend and the frontend, then opens the browser:

```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```

If sign-in says **MongoDB is not reachable**, run `scripts\start-mongodb.ps1` once (it asks for
administrator rights). It starts the MongoDB service, caps MongoDB's memory cache at 0.5 GB so it
cannot crash with "out of memory" on an 8 GB machine, and makes Windows restart it automatically.

### Settings: plans and API keys

The gear icon in the sidebar opens **Settings** (General, Account, Plan & billing, API keys, Usage).
Billing is simulated: switching plan changes limits only (Free 50 questions/day, Pro 500, Team
unlimited). Personal API keys (`qc-...`) work on every `/api/*` endpoint and on `/ask`:

```powershell
curl http://127.0.0.1:8000/ask -H "Authorization: Bearer qc-..." -H "Content-Type: application/json" -d '{"question": "How many companies are in India?"}'
```

### Start the backend

From the project root:

```powershell
uvicorn backend.main:app --reload
```

Backend address: `http://127.0.0.1:8000`

### Start the frontend

In a separate terminal:

```powershell
cd openui_test
npm install
npm run dev
```

Frontend address is normally `http://localhost:3000`; use the address printed by the development server if different.

### API endpoint

`POST /ask`

Example request:

```json
{
  "question": "How many companies are in India?"
}
```

The endpoint returns an answer in JSON format.

## 8. Database Tools and Capabilities

The database tool in `backend/database_tool.py` supports:

| Operation | Purpose |
|---|---|
| `find` | Retrieve matching documents |
| `count` | Count matching documents |
| `distinct` | Retrieve unique field values |
| `aggregate` | Perform grouped calculations and aggregations |

The application supports natural-language questions, company searches, filtering, counts, category queries, spending comparisons, aggregations, and general conversation, subject to the capabilities of the current implementation.

## 9. Security and Guardrails

The code reviewed includes these basic controls:

- JSON parsing before database execution.
- Collection validation against the discovered schema.
- Field and filter validation.
- An operation allowlist.
- Rejection of queries that fail validation.
- Rejection of unsupported operations such as `delete`.

### Security limitations

The current checks do not establish complete protection against prompt injection, unsafe aggregation stages, malformed query structures, excessive database reads, or sensitive information exposure.

**Recommended improvements**
- Validate allowed aggregation stages and operators.
- Restrict database permissions.
- Apply query timeouts and result-size limits.
- Keep credentials in environment variables.
- Redact sensitive information from logs.
- Test prompt injection and malformed inputs.

These additional protections should be marked complete only after implementation and testing.

## 10. Golden Set and Evaluation Runner

The project includes an initial evaluation script:

`evaluate_golden_set.py`

It calls the existing `run_langchain_agent(question)` function to test the chatbot and records answers, statuses, and response times.

### Run the evaluation

From the project root:

```powershell
python .\evaluate_golden_set.py
```

The output report is saved to:

`evaluation_results.json`

The initial Golden Set covers company counts, country comparisons, deployment types, HR technology usage, and technology spending.

### Initial evaluation results

| Metric | Result |
|---|---:|
| Questions attempted | 10 |
| Passed checks | 8 |
| Errors | 2 |
| Initially reported pass rate | 80% |

The two errors occurred because the evaluator attempted to process missing expected answers (`None`). They were evaluation-script errors, not confirmed chatbot failures.

The **80% result is preliminary**, not a validated measure of overall chatbot accuracy. Expected answers need to be independently verified against MongoDB, and the scoring logic needs improvement for complex answers.

### Manually verified examples

The following results were checked during development:

| Question | Verified result |
|---|---|
| Companies in India | 38 |
| Companies in the United States | 176 |
| Total companies | 500 |
| Highest average spending by deployment type | Hybrid, approximately $287,128.43 |
| Most common HR technology | iCIMS, 42 companies |
| Highest total spending by country | United States, approximately $44,912,522.60 |
| Lowest average spending by deployment type | SaaS, approximately $211,753.90 |
| Highest average spending by technology category | Global Employment, approximately $324,193.31 |

These verified examples do not establish that every Golden Set answer or every chatbot response is correct.

## 11. Testing and Quality Assurance

### Tests performed

- MongoDB connection and collection discovery.
- Sample SPAN record retrieval.
- Country filtering and selected-field retrieval.
- Basic validator acceptance and rejection checks.
- Rejection of invalid collections, fields, and filters.
- Rejection of unsupported `delete` operations.
- Initial Golden Set evaluation.

### Remaining test work

Some older test files use the `employees` collection instead of the current SPAN dataset. Some test imports also require package-qualified paths to run from the project root.

The complete test suite has not yet been demonstrated to pass in a single automated run.

Future work includes aligning tests with the current schema, verifying expected answers against MongoDB, and running regression tests after changes.

## 12. Performance and Observability

The initial evaluation records response time per question. In the reported 10-question run, response times ranged from approximately 5.24 to 16.39 seconds.

This is an initial observation, not a formal performance benchmark.

| Metric | Status |
|---|---|
| Per-question latency | Recorded in initial evaluation |
| Initial pass rate | Calculated, but preliminary |
| Token usage | Not confirmed as implemented |
| p50 and p95 latency | Not established |
| Database-specific latency | Not established |
| Langfuse tracing | Not confirmed as implemented |

Potential improvements include reducing unnecessary model calls, measuring database and model latency separately, tracking token usage, and comparing changes against a consistent baseline.

## 13. October Plan: Status and Remaining Work

| Requirement | Status |
|---|---|
| Architecture and setup documentation | Documented |
| MongoDB integration | Connection and representative queries tested |
| LLM configuration | Documented |
| Query tools and validation | Basic controls implemented and tested |
| Golden Set | Initial 10-question set |
| Evaluation runner | Created and executed |
| Evaluation accuracy | Requires stronger scoring and verified expected answers |
| Pass@1 and pass^3 | Not fully implemented or verified |
| Security testing | Basic checks tested; comprehensive coverage remains |
| Token monitoring and Langfuse | Not confirmed as implemented |
| CI/CD and regression gate | Not confirmed as implemented |
| Known issues and future improvements | Documented |

### Metric definitions

- **Pass@1:** The proportion of questions answered correctly on the first attempt.
- **Pass^3:** A reliability measure across three attempts, which requires a clearly defined scoring rule and repeated runs.
- **p50 latency:** Median response time.
- **p95 latency:** Response time at the 95th percentile.

These metrics should be reported only after the corresponding measurements have been implemented and run.

## 14. Known Issues and Future Improvements

### Known issues

1. Two questions in the initial evaluation encountered errors because missing expected answers were not handled.
2. Basic keyword and number checks may incorrectly pass incomplete answers.
3. All expected Golden Set results need independent verification.
4. Some legacy tests use older collections and may not represent the current dataset.
5. Comprehensive aggregation-pipeline and prompt-injection protections remain unverified.
6. Token monitoring, formal latency percentiles, CI/CD, and full regression testing are not confirmed as complete.
7. Graphiti and Neo4j participation in the live request flow needs verification.

### Future improvements

- Expand and independently verify the Golden Set.
- Improve scoring for counts, rankings, lists, averages, and totals.
- Implement pass@1 and pass^3 with documented rules.
- Strengthen query validation and security tests.
- Add token tracking and structured latency measurements.
- Add automated regression testing and CI/CD.
- Verify and document the graph integration.
- Compare model and prompt changes against a consistent baseline.

## 15. GitHub and Credential Safety

Do not commit API keys, passwords, database credentials, private tokens, or `.env` files.

Ensure `.gitignore` includes entries such as:

```gitignore
.env
.venv/
__pycache__/
*.pyc
```

Review tracked files before pushing to GitHub to ensure no credentials have been exposed.

## 16. Project Summary

The Queryable Chatbot provides a natural-language interface for structured business data using FastAPI, LangChain, MongoDB, Jev, Gemini through OpenRouter, and OpenUI. Graphiti and Neo4j provide a contextual knowledge layer where integrated.

The project has a working foundation, a 500-record SPAN dataset, basic query-validation controls, and an initial Golden Set evaluation runner.

The first 10-question run reported eight passed checks and two evaluator errors. The result remains preliminary until the scoring logic and expected answers are fully verified.

The main priorities are to improve evaluation reliability, strengthen security testing, measure performance and token usage, and establish automated regression testing and CI/CD.
