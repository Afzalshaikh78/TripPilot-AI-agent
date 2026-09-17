from pathlib import Path
import os
import traceback
import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from typing import Any
from langchain_mistralai import ChatMistralAI
from pydantic import BaseModel

from travel_graph import run_travel_agent
from mcp_client import get_all_tools

# REMOVED: nest_asyncio.apply() — this was breaking anyio's event loop
# detection used internally by StaticFiles.

BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

app = FastAPI(
    title="TripPilot AI",
    description="LangGraph Multi-Agent Travel Planner with FastAPI Frontend",
    version="1.0.0"
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


# @app.on_event("startup")
# async def log_mcp_tools_on_startup():
#     print("\nDiscovering MCP tools on startup...", flush=True)
#     await get_all_tools()

if FRONTEND_ASSETS.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_ASSETS)),
        name="assets"
    )


class TravelRequest(BaseModel):
    message: str | None = None
    thread_id: str | None = None
    answers: dict[str, Any] | None = None


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if FRONTEND_DIST.exists():
        return FileResponse(FRONTEND_DIST / "index.html")

    return HTMLResponse(
        "<h1>TripPilot AI</h1><p>Frontend build not found. Run the React build in /frontend.</p>"
    )


@app.post("/api/travel")
async def travel_planner(request_data: TravelRequest):
    try:
        user_message = (request_data.message or "").strip()

        if request_data.answers is None and not user_message:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Message cannot be empty."}
            )

        # Run the sync/blocking LangGraph call in FastAPI's threadpool
        # instead of nest_asyncio hacks. This keeps the main event loop free.
        result = await run_in_threadpool(
            run_travel_agent,
            user_input=user_message,
            thread_id=request_data.thread_id,
            answers=request_data.answers,
        )

        return JSONResponse(
            content={
                "success": True,
                "status": result["status"],
                "thread_id": result["thread_id"],
                "intent": result["intent"],
                "missing_slots": result["missing_slots"],
                "answer": result["answer"],
                "flight_results": result["flight_results"],
                "hotel_results": result["hotel_results"],
                "weather_results": result['weather_results'],
                "itinerary": result["itinerary"],
                "llm_calls": result["llm_calls"],
            }
        )

    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "AI Travel Planner API is running"}


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENVIRONMENT") != "production",
    )
