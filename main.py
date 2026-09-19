import os
import operator
import re
import time
import uuid
from langchain_core.prompts import prompt
import psycopg
import json
from pathlib import Path
import asyncio
from typing import TypedDict, Annotated,List
from groq import RateLimitError
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import(
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage
)
from langchain_groq import ChatGroq

from mcp_client import tavily_mcp_search, aviation_flight_search,current_weather_mcp_search,forecast_weather_mcp_search

from config import settings
from airport_helper import get_airport_code
from travel_schema import TravelDetails
from travel_parser import extract_travel_details

llm = ChatGoogleGenerativeAI(
    model="google/gemini-3-pro-preview",
    api_key=settings.GEMINI_API_KEY,
    # max_tokens=700,
    # max_retries=0,
)


def invoke_llm(messages):
    """Call Groq and wait out OTPM 429s instead of crashing."""
    last_error = None
    for _ in range(6):
        try:
            return llm.invoke(messages)
        except RateLimitError as exc:
            last_error = exc
            match = re.search(r"try again in ([0-9.]+)s", str(exc), re.I)
            wait_s = float(match.group(1)) + 0.75 if match else 4.0
            print(f"Groq rate limit hit. Retrying in {wait_s:.1f}s...")
            time.sleep(wait_s)
    raise last_error

DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+psycopg://",
    "postgresql://",
    1,
)
# State
class TravelState(TypedDict):
    messages: Annotated[List[AnyMessage],operator.add]
    user_query: str
    travel_details: TravelDetails
    flight_result: str
    weather_result: dict
    hotel_result: str
    itinerary: str
    llm_calls: int

# Parser_agent
def parser_agent(state: TravelState):

    details = extract_travel_details(
        state["user_query"]
    )

    return {
        "travel_details": details,
        "llm_calls": state.get("llm_calls", 0) + 1,
    }

# flight agent
def flight_agent(state: TravelState):
    details = state["travel_details"]

    flight_data = asyncio.run(
        aviation_flight_search(
            departure_city=details.departure_city,
            destination_city=details.destination_city,
            flight_date=details.departure_date or "",
        )
    )
    print("\n===== Aviationstack MCP Flight Output =====")
    print(flight_data)
    return {
        "flight_result": flight_data,
        "messages": [
            AIMessage(content="Flight result fetched via Aviationstack MCP")
        ],
        "llm_calls": state.get('llm_calls', 0) + 1,
    }


async def get_full_weather(city:str):
    current = await current_weather_mcp_search(city)
    forecast = await forecast_weather_mcp_search(city)
    return {
        'current':current,
        'forecast':forecast
    }
#weather agent
def weather_agent(state:TravelState):
    details = state["travel_details"]
    city = details.destination_city or details.departure_city
    if not city:
        return {
            "weather_result": "",
            "messages": [
                AIMessage(content="Weather data not available: No city specified")
            ],
        }

    weather_data = asyncio.run(get_full_weather(city))
    print("\n===== OpenWeather MCP Weather Output =====")
    print(weather_data)

    return {
        "weather_result": weather_data,
        "messages": [
            AIMessage(content="Weather data fetched via OpenWeather MCP")
        ],
        "llm_calls": state.get('llm_calls', 0) + 1,
    }


# hostel agent
# hold
def hotel_agent(state: TravelState):
    details = state["travel_details"]
    user_query = state["user_query"]

    search_query = f"""
    Find hotels in {details.destination_city}.

    Budget: {details.budget if details.budget else "Not specified"}

    User requirements:
    {user_query}
    """

    hotel_data = asyncio.run(tavily_mcp_search(search_query))

    return {
        "hotel_result": hotel_data,
        "messages": [
            AIMessage(content="Hotel information fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }
    
# itinerary agent
def itinerary_agent(state: TravelState):
    prompt = f"""
    Travel Details:
    {json.dumps(state["travel_details"].model_dump(), indent=2)}
    # {state["travel_details"]}
    
    Flights:
    {json.dumps(state["flight_result"], indent=2)}

    Hotels:
    {json.dumps(state["hotel_result"], indent=2)}

    Destination Weather:
    {json.dumps(state.get("weather_result", {}), indent=2)}

    Create a personalized travel itinerary based on the information.
    Generate:
    1. A day-wise travel itinerary.
    2. Recommended sightseeing places.
    3. Local transportation suggestions.
    4. Food recommendations.
    5. Weather-appropriate travel & packing tips.
    6. Estimated travel tips.

"""

    response = invoke_llm([
        SystemMessage(
            content='You are an expert travel planner who creates detailed, practical, and personalized travel itineraries'
        ),
        HumanMessage(content=prompt),
   ])

    return{
    'itinerary':response.content,
    'messages':[response],
    'llm_calls':state.get('llm_calls',0)+1,

   }

#final response agent
def final_agent(state:TravelState):
    final_prompt = f"""
    Generate the final travel plan for the user.

    Flight Details:
    {state["flight_result"]}

    Hotel Details:
    {state["hotel_result"]}

    Travel Itinerary:
    {state["itinerary"]}

    Present the response in a clean and user-friendly format.
"""

    response = invoke_llm([
        SystemMessage(content = 'You are an expert travel assistant.'),
        HumanMessage(content =final_prompt)
    ])

    return {
        'messages':[response],
        'llm_calls': state.get('llm_calls',0) + 1
    }

# build graph
graph = StateGraph(TravelState)

graph.add_node('parser_agent',parser_agent)
graph.add_node('flight_agent',flight_agent)
graph.add_node('hotel_agent',hotel_agent)
graph.add_node('weather_agent',weather_agent)
graph.add_node('itinerary_agent',itinerary_agent)
graph.add_node('final_agent',final_agent)

graph.add_edge(START, 'parser_agent')
graph.add_edge('parser_agent', 'flight_agent')
graph.add_edge('flight_agent', 'hotel_agent')
graph.add_edge("hotel_agent",'weather_agent')
graph.add_edge("weather_agent", 'itinerary_agent')
graph.add_edge("itinerary_agent", 'final_agent')
graph.add_edge("final_agent", END)

# Database connection:
conn = psycopg.connect(DATABASE_URL, autocommit=True)
checkpointer = PostgresSaver(conn=conn)
checkpointer.setup()

app = graph.compile(
    checkpointer=checkpointer,
)

if __name__== '__main__':
    config = {
        'configurable': {
            'thread_id': str(uuid.uuid4()),
        }
    }
    user_query = input("Enter you travel request:\n")

    result = app.invoke(
        {
            "messages":[HumanMessage(content=user_query)],
            "user_query": user_query,
            "flight_result": [],
            "hotel_result": [],
            "weather_result": {},
            "itinerary": "",
            "llm_calls": 0,

        },
        config = config
    )

# its optional
    outdir_dir = Path('output')
    outdir_dir.mkdir(exist_ok=True)

    file_path = outdir_dir / 'travel_plant.md'

    with open(file_path, "w", encoding="utf-8") as file:
        for i, msg in enumerate(result["messages"], start=1):
            file.write(f"# Agent {i}\n\n")
            file.write(msg.content)
            file.write("\n\n")
            file.write("-" * 80)
            file.write("\n\n")

    print(f"Saved to {file_path}")


    print("\n========== FINAL RESPONSE ==========\n")

    for msg in result['messages']:
        print(msg.content)
