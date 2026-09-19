import asyncio

import json
from typing import Any
from langgraph.types import interrupt
from langchain_core.messages import(
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage
)
from config import get_llm
from mcp_client import tavily_mcp_search, aviation_flight_search,current_weather_mcp_search,forecast_weather_mcp_search
from state import TravelState

llm = get_llm()

def llm_invoke(system:str,prompt:str):
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt)
    ])
    return response.content

def json_extractor_from_llm(text:str)->dict:
    print('Raw Text from llm')
    print(text)

    start = text.index("{")
    end = text.rindex("}")
    json_str = text[start:end+1]

    print('extracted json from llm response')
    print(json_str)

    return json.loads(json_str)


def supervisor_agent(state: TravelState) -> TravelState:
    query = state['user_query']

    prompt = f"""
    You are the supervisor of a real-world multi-agent travel planning system

    Decide which specialist agent are needed for this user request.

    Specialist Agents available:
    - flight_agent: use when flights, airports, airlines, routes, or airfare guidance are needed
    - hotel_agent: use when hotels, stays, neighborhoods, or accommodation are needed
    - weather_agent: use when weather, climate, season, packing, or forecast is useful
    - budget_agent: use when budget, affordability, cost, or price constraints are mentioned
    - itinerary_agent: almost always needed to produce the travel plan
        
    Return only JSON with this schema:
    {{
        "selected_agent": ["flight_agent", "hotel_agent", "weather_agent", "budget_agent", "itinerary_agent"],
        "trip_constraints": {{
            "destination": "",
            "origin": "",
            "duration": "",
            "budget": "",
            "travel_style": "",
            "special_preferences": []
        }},
        "reasoning": ""
    }}

    user request:
    {query}
    """

    response = llm_invoke(
        """
You route work to specialist agents.

Respond with valid JSON only
""", prompt)

    parsed = json_extractor_from_llm(response)
    selected_agent = parsed.get('selected_agent', [])

    return {
        'selected_agent': selected_agent,
        'trip_constraints': parsed.get('trip_constraints', {}),
        'supervisor_agent_reasoning': parsed.get('reasoning', ''),
        'messages': [AIMessage(content="Supervisor created the agent plan")],
        'llm_calls': state.get('llm_calls', 0) + 1,
    }


def flight_agent(state: TravelState) -> dict:
    """Specialist agent that searches flight routes, airports, and provides flight advice."""
    query = state.get('user_query', '')
    constraint = state.get('trip_constraints', {})
    destination = constraint.get('destination')
    origin = constraint.get('origin')

    # If origin or destination missing in constraints, try extracting from user query
    if not destination or not origin:
        extract_prompt = f"""
        Extract the departure city (origin) and destination city from this request.
        Request: {query}

        Return ONLY a JSON object:
        {{"origin": "city_name", "destination": "city_name"}}
        If either is not mentioned, use null.
        """
        try:
            extracted_json = llm_invoke(
                "You extract travel origin and destination cities. Return valid JSON only.",
                extract_prompt
            )
            extracted = json_extractor_from_llm(extracted_json)
            origin = origin or extracted.get("origin")
            destination = destination or extracted.get("destination")
        except Exception:
            pass

    # If still missing origin or destination, return graceful message
    if not destination or not origin:
        return {
            "flight_result": "Flight search skipped: Could not determine origin or destination city.",
            "messages": [
                AIMessage(content="Could not determine origin or destination for flight search.")
            ],
            "llm_calls": state.get('llm_calls', 0) + 1,
        }

    # 1. Fetch flight routes & airports via Aviationstack MCP server
    try:
        flight_data = asyncio.run(
            aviation_flight_search(
                departure_city=origin,
                destination_city=destination,
                flight_date=constraint.get('departure_date', '') or "",
            )
        )
    except Exception as e:
        flight_data = {"error": str(e)}

    print("\n===== Aviationstack MCP Flight Data =====")
    print(json.dumps(flight_data, indent=2))

    # 2. Synthesize flight recommendations using LLM
    summary_prompt = f"""
    The user is planning a trip from {origin} to {destination}.
    User query: {query}
    Trip constraints: {json.dumps(constraint, indent=2)}

    Aviationstack MCP search result:
    {json.dumps(flight_data, indent=2)}

    Provide a concise, professional flight summary for the user:
    1. Origin & destination airports with IATA codes.
    2. Available routes and operating airlines.
    3. Practical flight tips (e.g. advance booking, direct vs connecting, luggage recommendations).
    """

    flight_summary = llm_invoke(
        "You are an expert flight specialist agent. Summarize flight options clearly for the travel itinerary.",
        summary_prompt
    )

    return {
        "flight_result": flight_summary,
        "messages": [
            AIMessage(content=f"Flight options from {origin} to {destination} analyzed.")
        ],
        "llm_calls": state.get('llm_calls', 0) + 1,
    }
    

def hotel_agent(state: TravelState):
    constraints = state.get('trip_constraints', {})
    destination = constraints.get('destination') or state.get('user_query', '')
    budget = constraints.get('budget', '')

    query = f"best hotels and areas to stay in {destination} travel"
    try:
        raw_result = asyncio.run(tavily_mcp_search(query=query))
    except Exception as e:
        raw_result = f"Search error: {e}"

    summary_prompt = f"""
    Destination: {destination}
    Budget / Travel Style: {budget}
    User Query: {state.get('user_query')}

    Search results:
    {str(raw_result)[:2000]}

    Provide a concise, practical accommodation summary for {destination}:
    1. Recommended Neighborhoods: Best 2 areas to stay for travelers.
    2. Hotel Options: 2-3 specific hotel recommendations (budget, mid-range, luxury).
    3. Stay Tips: Proximity to sights or public transit.
    Keep it structured and concise.
    """
    hotel_summary = llm_invoke(
        "You are an expert accommodation specialist.",
        summary_prompt
    )

    return {
        "hotel_result": hotel_summary,
        "messages": [
            AIMessage(content=f"Hotel options for {destination} analyzed.")
        ],
        "llm_calls": state.get('llm_calls', 0) + 1,
    }

hostel_agent = hotel_agent

def weather_agent(state: TravelState):
    city = state.get('trip_constraints', {}).get('destination')
    if not city:
        city = state.get('user_query', '')

    try:
        weather_data = asyncio.run(current_weather_mcp_search(city=city))
    except Exception as e:
        weather_data = f"Current weather unavailable: {e}"

    try:
        forecast_data = asyncio.run(forecast_weather_mcp_search(city=city))
    except Exception as e:
        forecast_data = f"Forecast unavailable: {e}"

    summary_prompt = f"""
    City: {city}
    Current Weather: {weather_data}
    Forecast: {forecast_data}

    Provide a concise 2-3 bullet point weather & packing overview for a traveler visiting {city}:
    - Current conditions & forecast temperatures
    - Practical packing essentials (e.g., umbrella, footwear, clothing type)
    """
    weather_summary = llm_invoke(
        "You are a travel meteorologist. Provide concise weather advice.",
        summary_prompt
    )

    return {
        'weather_result': weather_summary,
        'messages': [AIMessage(content=f'Weather for {city} analyzed.')],
        'llm_calls': state.get('llm_calls', 0) + 1,
    }


def budget_agent(state:TravelState):

    prompt = f'''
    You are an expert budgeting agent
    Analyze whether this trip plan is realistic for the user's budget.
    
    User request:
    {state['user_query']}

    Constraints:
    {state.get('trip_constraints', {})}

    Flight results:
    {state.get('flight_result', '')}

    Hotel results:
    {state.get('hotel_result', '')}

    Weather results:
    {state.get('weather_result', '')}

    Return a concise budget assessment with:
    1. estimated cost categories
    2. risk areas
    3. money-saving suggestions
    4. whether the plan seems feasible

    
    '''

    result = llm_invoke(
        "You are a practical travel budget analyst.",
        prompt
    )
    return{
        'budget_result':result,
        'messages':[AIMessage(content='budget agent completed')],
        'llm_calls': state.get('llm_calls', 0) + 1,
    }


def itinerary_agent(state: TravelState):
    print("\n========== ITINERARY AGENT INPUT ==========")
    print("Trip Constraints:", state.get("trip_constraints"))
    print("=========================================\n")

    human_feedback = state.get('human_feedback', '')
    previous_itinerary = state.get('itinerary', '')
    duration = state.get('trip_constraints', {}).get('duration', 'the trip')
    destination = state.get('trip_constraints', {}).get('destination', 'the destination')

    if human_feedback and previous_itinerary:
        # REVISION MODE: incorporate feedback into the revised itinerary
        prompt = f"""
        You are revising an existing travel itinerary based on the traveler's feedback.

        Original Itinerary:
        {previous_itinerary}

        Traveler Feedback / Requested Changes:
        {human_feedback}

        User request:
        {state['user_query']}

        Trip constraints:
        {state.get('trip_constraints', {})}

        Please revise the itinerary to fully address the traveler's feedback.
        CRITICAL RULES:
        1. You MUST include a complete Day-by-Day plan covering each day for the traveler's requested duration ({duration}).
        2. For each day, include:
           - Morning (Activities & sights)
           - Afternoon (Sightseeing, food & culture)
           - Evening (Sunset, dinner, nightlife or relaxation)
        3. Clearly integrate the requested feedback while maintaining a practical flow.
        4. Do NOT truncate or cut off early. Output the complete itinerary.
        """
        system_msg = "You are an expert travel itinerary planner. Revise the itinerary based on traveler feedback."
    else:
        # FIRST DRAFT MODE: generate from scratch
        prompt = f"""
        Create a comprehensive, structured draft travel itinerary for {destination} for {duration}.

        User request:
        {state['user_query']}

        Trip constraints:
        {state.get('trip_constraints', {})}

        Flight details:
        {state.get('flight_result', 'Standard flight connections available.')}

        Accommodation recommendations:
        {state.get('hotel_result', 'Centrally located accommodations.')}

        Weather & Packing:
        {state.get('weather_result', 'Pleasant travel weather expected.')}

        Budget analysis:
        {state.get('budget_result', 'Balanced budget.')}

        MANDATORY STRUCTURE:
        1. 📋 Trip Overview (Destination, duration, travel style)
        2. 🛫 Flights & Transit Summary
        3. 🏨 Where to Stay (Recommended areas & hotels)
        4. 📅 Day-by-Day Itinerary:
           - Create a dedicated section for each day to cover the exact duration requested ({duration}) (e.g. Day 1, Day 2, etc.).
           - For each day, include Morning, Afternoon, and Evening activities.
        5. 💰 Estimated Daily Budget & Expenses
        6. 💡 Essential Tips for the Destination

        IMPORTANT:
        - Generate only as many days as requested ({duration})—do not add extra days or omit requested days.
        - Never stop after writing the flight or hotel section; always write out every requested day in full.
        """
        system_msg = "You are an expert travel itinerary planner who creates complete, detailed day-by-day plans."

    result = llm_invoke(system_msg, prompt)

    approval_request = f"""
Please review the following travel itinerary and provide your feedback.

Itinerary:
{result}

Would you like to approve this plan, or do you have any changes or modifications?
    """

    return {
        'itinerary': result,
        'approval_request': approval_request,
        'human_feedback': '',
        'messages': [AIMessage(content='Draft itinerary created for human review')],
        'llm_calls': state.get('llm_calls', 0) + 1,
    }

def human_approval_agent(state: TravelState):
    feedback = interrupt(
        {
            "question": "Do you approve this itinerary?",
            "review_itinerary": state.get("itinerary", ""),
            "approval_request": state.get("approval_request", ""),
            "expected_response": {
                "approved": True,
                "feedback": "Optional feedback for revision",
            },
        }
    )

    # Safely handle both dict and string responses
    if isinstance(feedback, dict):
        approved = bool(feedback.get("approved", False))
        human_feedback = feedback.get("feedback", "")
    elif isinstance(feedback, str):
        approved = feedback.strip().lower() in ["yes", "y", "approved", "ok", "looks good", "true"]
        human_feedback = "" if approved else feedback
    else:
        approved = bool(feedback)
        human_feedback = ""

    return {
        "approved": approved,
        "human_feedback": human_feedback,
        "messages": [AIMessage(content="Human approval step completed.")],
    }


def final_agent(state: TravelState) -> dict:
    """
    Final agent: polishes the approved itinerary into a clean, complete, user-ready travel guide.
    """
    user_query = state.get('user_query', '')
    constraints = state.get('trip_constraints', {})
    itinerary_info = state.get('itinerary', 'No itinerary generated.')
    human_feedback = state.get('human_feedback', '')
    approved = state.get('approved', False)

    origin = constraints.get('origin', 'Origin')
    destination = constraints.get('destination', 'Destination')
    duration = constraints.get('duration', 'Duration')
    budget = constraints.get('budget', 'Budget')

    feedback_line = f"\nTraveler note: {human_feedback}" if human_feedback else ""
    status_line = "Traveler approved this plan." if approved else "Revisions noted."

    prompt = f"""You are a master travel concierge. Transform this approved itinerary into a beautifully formatted, comprehensive final travel guide.

Trip: {origin} to {destination} | Duration: {duration} | Budget: {budget}
Request: {user_query}
{status_line}{feedback_line}

Approved Itinerary:
{itinerary_info}

Write the final complete travel guide with these sections:
1. 🌟 Trip Overview & Highlights
2. 🛫 Flight & Transit Logistics
3. 🏨 Stay & Neighborhood Guide
4. 📅 Complete Day-by-Day Itinerary (Include ALL days for the full duration of {duration}, keeping Morning, Afternoon, and Evening plans intact)
5. 💰 Budget & Cost Breakdown Snapshot
6. 🍽️ Local Dining & Must-Try Foods
7. 💡 Top Local Tips & Safety

CRITICAL: Do NOT omit the Day-by-Day plan. Ensure the entire guide covers the exact duration ({duration}) from start to finish without cutting off.
"""

    final_response = llm_invoke(
        "You write polished, comprehensive, and engaging travel guides.",
        prompt
    )

    return {
        "final_response": final_response,
        "messages": [AIMessage(content=final_response)],
        "llm_calls": state.get('llm_calls', 0) + 1,
    }

