"""Golden-set evaluation.

    python evaluate_golden_set.py                  # engine from .env (default mongo)
    python evaluate_golden_set.py --engine duckdb
    python evaluate_golden_set.py --engine mongo
"""

import argparse
import os
import statistics
import time
import re
import json
from datetime import datetime

from backend.langchain_agent import run_langchain_agent


# Golden Set: expected facts verified against MongoDB
golden_set = [
    {
        "id": 1,
        "question": "How many companies are in India?",
        "expected": "38",
    },
    {
        "id": 2,
        "question": "How many companies are in the United States?",
        "expected": "176",
    },
    {
        "id": 3,
        "question": "How many companies are in the dataset?",
        "expected": "500",
    },
    {
        "id": 4,
        "question": "Which deployment type has the highest average annual HR technology spend?",
        "expected": "Hybrid",
    },
    {
        "id": 5,
        "question": "Which HR technology has the highest number of companies?",
        "expected": "iCIMS",
    },
    {
        "id": 6,
        "question": "Which deployment type has the lowest average annual HR technology spend?",
        "expected": "SaaS",
    },
    {
        "id": 7,
        "question": "Which country has the highest total annual HR technology spend?",
        "expected": "United States",
    },
    {
        "id": 8,
        "question": "Which technology category has the highest average annual HR technology spend?",
        "expected": "Global Employment",
    },
    {
        "id": 9,
        "question": "What is the average employee count across all companies?",
        "expected": None,
    },
    {
        "id": 10,
        "question": "List the available deployment types.",
        "expected": None,
    },
]

def check_answer(answer, expected):
    # Check expected numeric values as complete numbers,
    # avoiding accidental matches inside larger numbers.
    if expected.isdigit():
        return re.search(
            rf"(?<![\d.]){re.escape(expected)}(?![\d.])",
            answer
        ) is not None

    return expected.lower() in answer.lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", choices=["mongo", "duckdb"], help="query engine to test")
    args = parser.parse_args()
    if args.engine:
        # backend.config.query_engine() reads this on every call.
        os.environ["QUERY_ENGINE"] = args.engine
    from backend.config import query_engine

    engine = query_engine()
    results = []
    passed = 0
    checked = 0

    print("=" * 60)
    print(f"QUERYABLE CHATBOT - GOLDEN SET EVALUATION ({engine})")
    print("=" * 60)

    for test in golden_set:
        print(f"\nTest {test['id']}: {test['question']}")

        start = time.perf_counter()

        try:
            answer = str(run_langchain_agent(test["question"]))
            latency = time.perf_counter() - start

            if test["expected"] is None:
                # No fixed fact to check: read the answer by hand.
                status = "MANUAL"
            else:
                checked += 1
                success = check_answer(answer, test["expected"])
                if success:
                    passed += 1
                status = "PASS" if success else "REVIEW"

            print("Status:", status)
            print("Expected fact:", test["expected"])
            print("Latency:", round(latency, 2), "seconds")
            print("Answer:", answer[:500])

            results.append({
                "id": test["id"],
                "question": test["question"],
                "expected": test["expected"],
                "answer": answer,
                "status": status,
                "latency_seconds": round(latency, 3),
            })

        except Exception as error:
            latency = time.perf_counter() - start

            print("Status: ERROR")
            print("Error:", str(error))

            results.append({
                "id": test["id"],
                "question": test["question"],
                "expected": test["expected"],
                "status": "ERROR",
                "error": str(error),
                "latency_seconds": round(latency, 3),
            })

    total = len(golden_set)
    pass_rate = (passed / checked * 100) if checked else 0
    latencies = [r["latency_seconds"] for r in results]
    median = round(statistics.median(latencies), 2) if latencies else None
    out_file = f"evaluation_results_{engine}.json"

    report = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "engine": engine,
        "total_tests": total,
        "checked": checked,
        "passed": passed,
        "manual": total - checked - sum(r["status"] == "ERROR" for r in results),
        "errors": sum(r["status"] == "ERROR" for r in results),
        "pass_rate_percent": round(pass_rate, 2),
        "median_latency_seconds": median,
        "results": results,
    }

    with open(out_file, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"Engine: {engine}")
    print(f"Tests: {total} ({checked} with a fixed expected fact)")
    print(f"Passed: {passed}/{checked}  ({pass_rate:.2f}%)")
    print(f"Errors: {report['errors']}   Manual review: {report['manual']}")
    print(f"Median latency: {median} s")
    print(f"Report saved to {out_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
