import os
import shutil
import sys
from pathlib import Path
from typing import Any
import certifi
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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
# Mistral_api_key = os.getenv("MISTRAL_API_KEY")
# if not Mistral_api_key:
#     raise ValueError("MISTRAL_API_KEY not defined")

# llm = ChatMistralAI(
#     model="mistral-small-latest",
#     api_key=Mistral_api_key,
# )

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
AVIATION_STACK_API_KEY = (
    os.getenv("AVIATION_STACK_API_KEY")
    or os.getenv("AVIATIONSTACK_API_KEY")
)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
print("AVIATION_STACK_API_KEY set:", bool(AVIATION_STACK_API_KEY))

UVX_COMMAND = shutil.which("uvx") or "uvx"

client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": (
                f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"
            ),
        },

        "aviationstack": {
            "transport": "stdio",
            "command": UVX_COMMAND,
            "args": [
                "--python",
                "3.13",
                "--with",
                "mcp<2.0.0",
                "aviationstack-mcp",
            ],
            "env": {
                "AVIATION_STACK_API_KEY": AVIATION_STACK_API_KEY,
            },
        },

        "weather": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [
                str(Path(__file__).parent / "custom_weather_mcp.py")
            ],
            "env": {
                "OPENWEATHER_API_KEY": OPENWEATHER_API_KEY,
            },
        },
    }
)


async def get_all_tools():
    tools = await client.get_tools()
    print("avalaible tools")
    for tool in tools:
        print(tool.name)


tavily_search_tool = None
avaition_tools = {}

async def intialize_mcp():
    global tavily_search_tool
    global avaition_tools

    if tavily_search_tool is not None and avaition_tools:
        return 


    tools = await client.get_tools()
    print("avaliable tools")

    for tool in tools:
        print(tool.name)

    tavily_search_tool = next(
        tool
        for tool in tools
        if tool.name == "tavily_search"
    )

    avaition_tools = {
        tool.name : tool
        for tool in tools
        if tool.name!= "tavily_search"
    }

 

async def tavily_mcp_search(query:str):
    await intialize_mcp()
    results = await tavily_search_tool.ainvoke({"query": query})
    return results


async def aviation_mcp_call(
        tool_name:str,
        tool_args: dict = None
):
    tools = await client.get_tools()
    tool = next(
        t for t in tools
        if t.name == tool_name
    )

    result = await tool.ainvoke(
        tool_args or {}
    )
    return result



weather_tool = None
forecast_tool = None

async def intialize_weather():
    global weather_tool,forecast_tool

    if weather_tool is not None:
        return 

    tools = await client.get_tools()
    print("avaliable tools")
    
    for tool in tools:
        print(tool.name)

    weather_tool = next(
        t for t in tools
        if t.name == "get_current_weather"
    )
    forecast_tool = next(
        t for t in tools
        if t.name == "get_forecast"
    )



async def weather_mcp_search(city:str):
    await intialize_weather()
    return await weather_tool.ainvoke(
        {
            "city":city
        }
    )
    
async def forecast_mcp_search(city:str):
    await intialize_weather()
    return await forecast_tool.ainvoke({
        "city" : city
    })



def extract_destination(query:str):
    prompt = f"""
    extract only the destination city or country

    Query:{
        query
    }

Return only destionation name.

"""
    response = llm.invoke(prompt)
    return response.content.strip()
