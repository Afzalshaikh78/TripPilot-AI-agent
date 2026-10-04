import os
from pathlib import Path
import certifi
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import requests
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

tavily_client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": (
                f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"
            ),
        }
    }
)

async def get_all_tools():
    tools = await tavily_client.get_tools()
    print("avalaible tools")
    for tool in tools:
        print(tool.name)


tavily_search_tool = None

async def intialize_mcp():
    await initialize_tavily()


async def initialize_tavily():
    global tavily_search_tool
    if tavily_search_tool is None:
        tools = await tavily_client.get_tools()
        tavily_search_tool = next(tool for tool in tools if tool.name == "tavily_search")


async def tavily_mcp_search(query:str):
    await initialize_tavily()
    results = await tavily_search_tool.ainvoke({"query": query})
    return results

def get_weather(city: str) -> dict:
    """Fetch current weather and forecast directly, avoiding MCP subprocess startup."""
    params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"}

    def fetch(url: str):
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        current_future = executor.submit(fetch, "https://api.openweathermap.org/data/2.5/weather")
        forecast_future = executor.submit(fetch, "https://api.openweathermap.org/data/2.5/forecast")
        current = current_future.result()
        forecast = forecast_future.result()

    return {
        "current": {
            "temperature_c": current["main"]["temp"],
            "feels_like_c": current["main"]["feels_like"],
            "condition": current["weather"][0]["description"],
        },
        "forecast": [
            {"datetime": item["dt_txt"], "temperature_c": item["main"]["temp"], "condition": item["weather"][0]["description"]}
            for item in forecast["list"][:5]
        ],
    }
