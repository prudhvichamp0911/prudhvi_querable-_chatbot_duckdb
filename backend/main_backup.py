from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.langchain_agent import run_langchain_agent
from backend.jev_router import route_question


app = FastAPI()


app.mount(
    "/static",
    StaticFiles(directory="backend/static"),
    name="static"
)


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def home():
    return FileResponse("backend/static/index.html")


@app.post("/ask")
def ask_question(request: QuestionRequest):

    print()
    print("=" * 70)
    print("FASTAPI /ASK DEBUG")
    print("=" * 70)
    print("QUESTION RECEIVED:", request.question)

    # Send the same user question to Jev
    # Jev works as a backend router/verifier layer
    try:
        jev_result = route_question(request.question)

        print()
        print("JEV RESULT:")
        print(jev_result)

    except Exception as e:
        print()
        print("[JEV ERROR]", str(e))
        jev_result = None

    print()
    print("CALLING LANGCHAIN AGENT...")
    
    # Original Queryable Chatbot remains responsible for the answer
    answer = run_langchain_agent(request.question)

    print()
    print("LANGCHAIN ANSWER:")
    print(answer)

    print("=" * 70)

    return {
        "answer": answer
    }