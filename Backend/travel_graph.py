import os 
import certifi
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import Any, Literal, TypedDict, Annotated
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
from mcp_client import tavily_mcp_search, aviation_mcp_call, extract_destination, forecast_mcp_search, weather_mcp_search


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


Gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not Gemini_api_key or not Gemini_api_key.startswith("AIza"):
    raise ValueError(
        "A valid Gemini API key is required. Set GEMINI_API_KEY in .env to an "
        "API key from Google AI Studio (it starts with 'AIza')."
    )

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key=Gemini_api_key,
)

# if not Mistral_api_key:
#     raise ValueError("MISTRAL_API_KEY not defined")

# llm = ChatMistralAI(
#     model="mistral-small-latest",
#     api_key=Mistral_api_key,
# )

class TravelState(TypedDict):
    messages : Annotated[list[AnyMessage],add_messages]
    user_query : str
    flight_results : str
    hotel_results : str
    itinerary: str
    weather_results : str
    final_response : str
    llm_calls: int
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
        "llm_calls": state.get("llm_calls", 0) + (0 if state.get("clarification_answers") else 1),
    }


def human_review(state: TravelState):
    answers = interrupt({
        "status": "needs_clarification",
        "intent": state["intent"],
        "missing_slots": state["missing_slots"],
    })
    return {"clarification_answers": answers}


def route_after_intent(state: TravelState):
    return "human_review" if state["intent_status"] == "needs_clarification" else "flight_agent"



FLIGHT_AGENT_PROMPT = """
You are a travel flight expert.

User Query:
{query}

Airport Information:
{airport_data}

Airline Information:
{airline_data}

Generate:

1. Likely departure airport
2. Likely arrival airport
3. Airlines serving this route
4. Typical flight duration
5. Estimated airfare range
6. Peak season pricing warning
7. Booking advice

Return concise travel guidance.
"""




# Flight Agent
def flight_agent(state: TravelState):
    print("\nINSIDE FLIGHT AGENT\n")

    intent = state["intent"]
    query = f"Flights from {intent.get('origin') or 'the default origin'} to {intent['destination']}"

    try:
        airports = asyncio.run(
            aviation_mcp_call(
                "list_airports"
            )
        )

        airlines = asyncio.run(
            aviation_mcp_call(
                "list_airlines"
            )
        )


        print("\nAIRPORTS:", airports)
        print("\nAIRLINES:", airlines)

        prompt = FLIGHT_AGENT_PROMPT.format(
            query=query,
            airport_data=str(airports)[:3000],
            airline_data=str(airlines)[:3000]
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
        "llm_calls": state.get("llm_calls", 0) + 1
    }


def hotel_agent(state:TravelState):
    intent = state["intent"]
    query = f"Best {intent.get('budget') or ''} hotels in {intent['destination']} for {intent['duration_days']} days"
    hotel_results = asyncio.run(tavily_mcp_search(query))

    return {
        "hotel_results": hotel_results,
        "messages" : [AIMessage(content="Hotel information fetched")],
        "llm_calls" : state.get("llm_calls",0)+1
    }

def weather_agent(state: TravelState):
    city = state["intent"]["destination"]

    weather_data = asyncio.run(
        weather_mcp_search(city)
    )

    forecast_data = asyncio.run(
        forecast_mcp_search(city)
    )

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



def itinerary_agent(state: TravelState):
    prompt = f"""
Create a complete travel itinerary.

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

Make the itinerary practical, budget-aware, and easy to follow.
"""

    response = llm.invoke([
        SystemMessage(content="You are an expert travel planner."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


def final_agent(state: TravelState):
    final_prompt = f"""
Generate the final travel response for the user.

User Request:
{state['user_query']}

Structured Trip Intent:
{state['intent']}

Flights:
{state['flight_results']}

Hotels:
{state['hotel_results']}

Weather:
{state['weather_results']}

Itinerary:
{state['itinerary']}

Format the final answer beautifully using these sections:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Weather 
5. Day-by-Day Itinerary
6. Estimated Budget
7. Final Recommendations

Important:
- Be clear and practical.
- Mention that live flight API may not provide ticket prices if pricing is unavailable.
- Keep the response useful for real travel planning.
"""

    response = llm.invoke([
        SystemMessage(content="You are a professional AI travel booking assistant."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "final_response" : response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }




graph = StateGraph(TravelState)

graph.add_node("parse_intent", parse_intent)
graph.add_node("human_review", human_review)
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("weather_agent",weather_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)


graph.add_edge(START, "parse_intent")
graph.add_conditional_edges("parse_intent", route_after_intent)
graph.add_edge("human_review", "parse_intent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "weather_agent")
graph.add_edge("weather_agent","itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)



DATABASE_URL = get_database_url()

_conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)

checkpointer = PostgresSaver(_conn)
checkpointer.setup()


travel_graph = graph.compile(checkpointer=checkpointer)



def run_travel_agent(
    user_input: str | None = None,
    thread_id: str | None = None,
    answers: dict[str, Any] | None = None,
):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

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
            "llm_calls": result.get("llm_calls", 0),
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
        "llm_calls": result.get("llm_calls", 0),
    }
