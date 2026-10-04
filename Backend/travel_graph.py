import os 
import certifi
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import Any, Literal, TypedDict, Annotated
from functools import wraps
import logging
import operator
import time
import uuid
import asyncio
import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import interrupt, Command
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
# from tools.tavily_tool import tavily_search
# from mcp_client_test import tavily_mcp_search
from mcp_client import get_weather, tavily_mcp_search


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. "
            "Please add your Render PostgreSQL External Database URL to .env"
        )

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    return database_url


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("A valid GOOGLE_API_KEY is required.")

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    api_key=GOOGLE_API_KEY,
    thinking_budget=0,
    temperature=0.2,
    max_tokens=1600,
    request_timeout=20,
    retries=2,
)

logger = logging.getLogger(__name__)


def timed_node(name: str):
    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            started_at = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                logger.warning("node_timing node=%s duration_ms=%d", name, (time.perf_counter() - started_at) * 1000)
        return wrapped
    return decorator

class TravelState(TypedDict):
    messages : Annotated[list[AnyMessage],add_messages]
    user_query : str
    flight_results : str
    hotel_results : str
    itinerary: str
    weather_results : str
    final_response : str
    llm_calls: Annotated[int, operator.add]
    intent: dict[str, Any]
    missing_slots: list[dict[str, Any]]
    intent_status: Literal["needs_clarification", "ready"]
    clarification_answers: dict[str, Any]


class ParsedIntent(BaseModel):
    destination: str | None = None
    origin: str | None = None
    duration_days: int | None = None
    travel_dates: str | None = None
    budget: str | None = None
    travel_style: list[str] = Field(default_factory=list)


SLOT_CONFIG = {
    "destination": {"label": "Where are you going?", "options": None},
    "duration_days": {"label": "How many days?", "options": None},
    "travel_dates": {"label": "When are you travelling?", "options": None},
    "budget": {"label": "What is your budget preference?", "options": ["Budget", "Mid-range", "Luxury"]},
    "travel_style": {"label": "What kind of trip do you want?", "options": ["Relaxed", "Adventure", "Culture", "Food", "Nightlife"], "multiple": True},
}


def missing_slots(intent: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": key, **config}
        for key, config in SLOT_CONFIG.items()
        if not intent.get(key)
    ]


def parse_query_intent(query: str) -> dict[str, Any]:
    parser = llm.with_structured_output(ParsedIntent)
    result = parser.invoke([
        SystemMessage(content=(
            "Extract only explicit travel details. Do not guess missing values. "
            "duration_days must be a number; travel_dates can be a date or date range."
        )),
        HumanMessage(content=query),
    ])
    return result.model_dump()


@timed_node("parse_intent")
def parse_intent(state: TravelState):
    # On resume, validate the structured form data only; do not re-send raw chat text.
    if state.get("clarification_answers"):
        intent = ParsedIntent.model_validate({
            **state.get("intent", {}),
            **state["clarification_answers"],
        }).model_dump()
    else:
        intent = parse_query_intent(state["user_query"])

    slots = missing_slots(intent)
    return {
        "intent": intent,
        "missing_slots": slots,
        "intent_status": "needs_clarification" if slots else "ready",
        "clarification_answers": {},
        "llm_calls": 0 if state.get("clarification_answers") else 1,
    }


def human_review(state: TravelState):
    answers = interrupt({
        "status": "needs_clarification",
        "intent": state["intent"],
        "missing_slots": state["missing_slots"],
    })
    return {"clarification_answers": answers}


def route_after_intent(state: TravelState):
    return "human_review" if state["intent_status"] == "needs_clarification" else ["flight_agent", "hotel_agent", "weather_agent"]



FLIGHT_AGENT_PROMPT = """
You are a travel flight expert.

Trip intent:
{intent}

Generate:

1. Likely departure airport
2. Likely arrival airport
3. Typical flight duration, only when confidently known
4. Peak season pricing warning
5. Booking advice

Do not invent live schedules, available seats, fares, or airline inventory.
Return concise travel guidance in no more than 150 words.
"""




# Flight Agent
@timed_node("flight_agent")
def flight_agent(state: TravelState):
    print("\nINSIDE FLIGHT AGENT\n")

    intent = state["intent"]
    try:
        prompt = FLIGHT_AGENT_PROMPT.format(
            intent=intent,
        )

        response = llm.invoke([
            SystemMessage(
                content="You are an expert travel flight planner."
            ),
            HumanMessage(content=prompt)
        ])

        flight_data = response.content

    except Exception as e:

        flight_data = f"Flight information unavailable: {str(e)}"

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(
                content="Flight recommendations generated"
            )
        ],
        "llm_calls": 1,
    }


@timed_node("hotel_agent")
def hotel_agent(state:TravelState):
    intent = state["intent"]
    query = f"Best {intent.get('budget') or ''} hotels in {intent['destination']} for {intent['duration_days']} days"
    try:
        hotel_results = asyncio.run(tavily_mcp_search(query))
    except Exception as error:
        hotel_results = f"Hotel information unavailable: {error}"

    return {
        "hotel_results": hotel_results,
        "messages" : [AIMessage(content="Hotel information fetched")],
        "llm_calls": 0,
    }

@timed_node("weather_agent")
def weather_agent(state: TravelState):
    city = state["intent"]["destination"]
    try:
        weather = get_weather(city)
        weather_data = weather["current"]
        forecast_data = weather["forecast"]
    except Exception as error:
        weather_data = f"Weather unavailable: {error}"
        forecast_data = "Forecast unavailable"

    return {
        "weather_results": f"""
        Current Weather:
        {weather_data}

        Forecast:
        {forecast_data}
        """,
        "messages": [
            AIMessage(
                content="Weather information fetched"
            )
        ]
    }



@timed_node("itinerary_agent")
def itinerary_agent(state: TravelState):
    prompt = f"""
Create the final, concise travel plan for the user.

User Query:
{state['user_query']}

Structured Trip Intent:
{state['intent']}

Flight Results:
{state['flight_results']}

Hotel Results:
{state['hotel_results']}

Weather Results:
{state['weather_results']}

Format with: Trip Summary, Flight Information, Hotel Suggestions, Weather,
Day-by-Day Itinerary, Estimated Budget, and Final Recommendations. Make it practical and budget-aware.
"""

    response = llm.invoke([
        SystemMessage(content="You are an expert travel planner."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "final_response": response.content,
        "messages": [response],
        "llm_calls": 1,
    }




graph = StateGraph(TravelState)

graph.add_node("parse_intent", parse_intent)
graph.add_node("human_review", human_review)
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("weather_agent",weather_agent)
graph.add_node("itinerary_agent", itinerary_agent)


graph.add_edge(START, "parse_intent")
graph.add_conditional_edges("parse_intent", route_after_intent)
graph.add_edge("human_review", "parse_intent")
graph.add_edge(["flight_agent", "hotel_agent", "weather_agent"], "itinerary_agent")
graph.add_edge("itinerary_agent", END)



DATABASE_URL = get_database_url()



def run_travel_agent(
    user_input: str | None = None,
    thread_id: str | None = None,
    answers: dict[str, Any] | None = None,
):
    # Only clarification submissions resume a checkpoint. Every new prompt is a new trip.
    if answers is None:
        thread_id = f"user_{uuid.uuid4().hex}"
    elif not thread_id:
        raise ValueError("thread_id is required when resuming a clarification.")

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # Neon can close idle serverless connections. Create a connection for each
    # invocation while checkpoints remain persisted under the same thread ID.
    with psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row) as connection:
        checkpointer = PostgresSaver(connection)
        checkpointer.setup()
        travel_graph = graph.compile(checkpointer=checkpointer)
        previous_state = travel_graph.get_state(config)
        previous_llm_calls = previous_state.values.get("llm_calls", 0) if answers is not None else 0

        if answers is not None:
            result = travel_graph.invoke(Command(resume=answers), config=config)
        else:
            result = travel_graph.invoke(
                {
                    "messages": [HumanMessage(content=user_input or "")],
                    "user_query": user_input or "",
                    "flight_results": "",
                    "hotel_results": "",
                    "weather_results": "",
                    "itinerary": "",
                    "final_response": "",
                    "llm_calls": 0,
                    "intent": {},
                    "missing_slots": [],
                    "intent_status": "needs_clarification",
                    "clarification_answers": {},
                },
                config=config,
            )

    request_llm_calls = max(0, result.get("llm_calls", 0) - previous_llm_calls)

    interruptions = result.get("__interrupt__", ())
    if interruptions:
        payload = interruptions[0].value
        return {
            "thread_id": thread_id,
            "status": "needs_clarification",
            "intent": payload["intent"],
            "missing_slots": payload["missing_slots"],
            "answer": "",
            "flight_results": "",
            "hotel_results": "",
            "weather_results": "",
            "itinerary": "",
            "llm_calls": request_llm_calls,
        }

    return {
        "thread_id": thread_id,
        "status": "ready",
        "intent": result.get("intent", {}),
        "missing_slots": [],
        "answer": result.get("final_response", ""),
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "weather_results": result.get("weather_results",""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": request_llm_calls,
    }
