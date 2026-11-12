from backend.jev_router import route_question
from backend.langchain_agent import run_langchain_agent


question = "How many companies are in the United States?"


print()
print("=" * 60)
print("STEP 1 - JEV")
print("=" * 60)

try:
    jev_result = route_question(question)
    print("Jev result:")
    print(jev_result)
except Exception as e:
    print("Jev error:")
    print(e)
    jev_result = None


print()
print("=" * 60)
print("STEP 2 - LANGCHAIN AGENT AFTER JEV")
print("=" * 60)

answer = run_langchain_agent(question)

print("LangChain answer:")
print(answer)

print()
print("=" * 60)