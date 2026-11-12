
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 60000;

export async function POST(request: NextRequest) {
  const requestStart = performance.now();

  try {
    const body = await request.json();
    const question = body?.question;

    if (!question || typeof question !== "string" || !question.trim()) {
      return NextResponse.json(
        { error: "Question is required." },
        { status: 400 }
      );
    }

    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      REQUEST_TIMEOUT_MS
    );

    let response: Response;

    try {
      response = await fetch(`${BACKEND_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: question.trim(),
        }),
        cache: "no-store",
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }

    const backendDuration = performance.now() - requestStart;

    console.info(
      `[PERF] FastAPI request completed in ${backendDuration.toFixed(0)} ms`
    );

    if (!response.ok) {
      const errorText = await response.text();

      console.error(
        `[BACKEND ERROR] Status ${response.status}: ${errorText}`
      );

      return NextResponse.json(
        {
          error: "Queryable Agent backend returned an error.",
          details: errorText,
        },
        { status: response.status }
      );
    }

    const data = await response.json();

    if (typeof data?.answer !== "string") {
      console.error(
        "[BACKEND ERROR] Response did not contain a string answer."
      );

      return NextResponse.json(
        { error: "The backend returned an invalid answer format." },
        { status: 502 }
      );
    }

    console.info(
      `[PERF] Total chat route time: ${(performance.now() - requestStart).toFixed(0)} ms`
    );

    // Keep the existing response format for frontend compatibility.
    return NextResponse.json({
      answer: data.answer,
    });
  } catch (error) {
    const duration = performance.now() - requestStart;

    if (error instanceof Error && error.name === "AbortError") {
      console.error(
        `[QUERYABLE TIMEOUT] Backend request exceeded ${REQUEST_TIMEOUT_MS} ms.`
      );

      return NextResponse.json(
        {
          error: "The backend took too long to respond. Please try again.",
        },
        { status: 504 }
      );
    }

    console.error(
      `[QUERYABLE BRIDGE ERROR] After ${duration.toFixed(0)} ms:`,
      error
    );

    return NextResponse.json(
      {
        error:
          "Could not connect to the Queryable Agent backend. Make sure FastAPI is running.",
      },
      { status: 500 }
    );
  }
}
