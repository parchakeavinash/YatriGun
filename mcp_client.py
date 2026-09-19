import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient

from config import settings

client = MultiServerMCPClient(
    {
        'tavily':{
               'transport':'streamable_http',
               'url': f'https://mcp.tavily.com/mcp/?tavilyApiKey={settings.TAVILY_API_KEY}'
        },
        'aviationstack':{
            'transport':'stdio',
            'command':r"D:\Multi_agent_with_MCP\aviationstack-mcp\.venv\Scripts\python.exe",
            'args':[
                '-m',
                'aviationstack_mcp',
            ],
            'cwd': r"D:\Multi_agent_with_MCP\aviationstack-mcp",
            'env':{
                'AVIATION_STACK_API_KEY':settings.AVIATIONSTACK_API_KEY
            }
        },
        'weather':{
            'transport':'stdio',
            'command':r"D:\Multi_agent_with_MCP\.venv\Scripts\python.exe",
            'args':[r"D:\Multi_agent_with_MCP\openweather_mcp_server.py"],
            'env':{
                'OPENWEATHER_API_KEY':settings.OPENWEATHER_API_KEY
            }
        }
    }
)

# async def main():

#     tools = await client.get_tools()

#     print("Available MCP Tools \n")
#     for tool in tools:
#         print(tool.name)


import json

search_tool = None
aviationstack_tools = {}
weather_tools={}

async def initialize_mcp():
    global search_tool, aviationstack_tools,weather_tools

    if search_tool is not None and aviationstack_tools and weather_tools:
        return

    # 1. Fetch Tavily tools directly by server_name
    tavily_tools = await client.get_tools(server_name='tavily')
    search_tool = next((t for t in tavily_tools if t.name == 'tavily_search'), None)
    if not search_tool:
        raise RuntimeError("tavily_search tool not found on Tavily MCP server")

    # 2. Fetch Aviationstack tools directly by server_name
    av_tools = await client.get_tools(server_name='aviationstack')
    aviationstack_tools = {tool.name: tool for tool in av_tools}

    # 3. weather api tool
    wthr_tools = await client.get_tools(server_name='weather')
    weather_tools = {tool.name: tool for tool in wthr_tools}


def parse_mcp_response(res):
    """Safely parse JSON response from MCP tools if returned as string."""
    if isinstance(res, str):
        try:
            return json.loads(res)
        except Exception:
            return res
    return res


async def tavily_mcp_search(query: str):
    await initialize_mcp()
    result = await search_tool.ainvoke({
        "query": query,
    })
    return result

async def current_weather_mcp_search(city: str):
    await initialize_mcp()
    tool = weather_tools.get('get_current_weather')
    if not tool:
        raise ValueError(
            f"Tool 'get_current_weather' not found. Available weather tools: {list(weather_tools.keys())}"
        )
    result = await tool.ainvoke({
        'city': city,
    })
    return result

async def forecast_weather_mcp_search(city:str):
    await initialize_mcp()
    tool = weather_tools.get('get_forecast')
    if not tool:
        raise ValueError(
            f"Tool 'get_forecast' not found. Available weather tools: {list(weather_tools.keys())}"
        )
    result = await tool.ainvoke({
        'city': city,
    })
    return result

async def aviationstack_mcp_call(tool_name: str, params: dict | None = None):
    """Call any Aviationstack MCP tool by name with the given parameters."""
    await initialize_mcp()
    tool = aviationstack_tools.get(tool_name)
    if not tool:
        raise ValueError(
            f"Tool '{tool_name}' not found. Available aviationstack tools: {list(aviationstack_tools.keys())}"
        )

    raw_result = await tool.ainvoke(params or {})
    return parse_mcp_response(raw_result)


async def aviation_get_airports(search: str, limit: int = 5):
    """Dynamically search for airports and their IATA codes by city or airport name."""
    return await aviationstack_mcp_call("list_airports", {
        "search": search,
        "limit": limit,
    })


async def aviation_get_airport_code(city_or_name: str) -> str | None:
    """Resolve a city or airport name to its 3-letter IATA code."""
    if not city_or_name:
        return None

    # 1. First attempt: Aviationstack MCP list_airports
    try:
        res = await aviation_get_airports(city_or_name, limit=5)
        if isinstance(res, dict) and res.get("ok"):
            airports = res.get("data", [])
            for ap in airports:
                code = ap.get("iata_code") or ap.get("city_iata_code")
                if code and len(code) == 3:
                    return code.upper()
    except Exception as e:
        print(f"Error querying list_airports for '{city_or_name}': {e}")

    # 2. Fallback: local static airport codes
    try:
        from airport_helper import get_airport_code
        return get_airport_code(city_or_name)
    except Exception:
        return None


async def aviation_get_airlines(search: str, limit: int = 5):
    """Search airlines by name or code using Aviationstack MCP."""
    return await aviationstack_mcp_call("list_airlines", {
        "search": search,
        "limit": limit,
    })


async def aviation_flight_search(
    departure_city: str,
    destination_city: str,
    dep_iata: str | None = None,
    arr_iata: str | None = None,
    flight_date: str = "",
    airline_name: str = "",
):
    """
    Comprehensive flight search using Aviationstack MCP tools:
    1. Resolves departure & arrival IATA codes via list_airports.
    2. If airline_name is provided, looks up airline details with list_airlines.
    3. Queries list_routes for available flights/routes between the airports.
    4. If flight_date is provided, queries future flight schedules.
    """
    # 1. Resolve IATA codes if not already provided
    if not dep_iata and departure_city:
        dep_iata = await aviation_get_airport_code(departure_city)

    if not arr_iata and destination_city:
        arr_iata = await aviation_get_airport_code(destination_city)

    result = {
        "departure_city": departure_city,
        "destination_city": destination_city,
        "dep_iata": dep_iata,
        "arr_iata": arr_iata,
        "flight_date": flight_date,
        "routes": None,
        "schedules": None,
        "airline_info": None,
    }

    # 2. Optional airline lookup
    airline_iata = ""
    if airline_name:
        try:
            airline_res = await aviation_get_airlines(airline_name, limit=1)
            result["airline_info"] = airline_res
            if isinstance(airline_res, dict) and airline_res.get("ok"):
                airlines = airline_res.get("data", [])
                if airlines:
                    airline_iata = airlines[0].get("iata_code") or ""
        except Exception as e:
            result["airline_info"] = {"error": str(e)}

    # 3. Route lookup between airports
    if dep_iata and arr_iata:
        route_params = {
            "dep_iata": dep_iata,
            "arr_iata": arr_iata,
            "limit": 5,
        }
        if airline_iata:
            route_params["airline_iata"] = airline_iata

        try:
            result["routes"] = await aviationstack_mcp_call("list_routes", route_params)
        except Exception as e:
            result["routes"] = {"error": str(e)}

    # 4. Schedule lookup if date is provided
    if dep_iata and flight_date:
        schedule_params = {
            "airport_iata_code": dep_iata,
            "schedule_type": "departure",
            "date": flight_date,
            "number_of_flights": 5,
        }
        if airline_iata:
            schedule_params["airline_iata"] = airline_iata

        try:
            result["schedules"] = await aviationstack_mcp_call(
                "future_flights_arrival_departure_schedule",
                schedule_params,
            )
        except Exception as e:
            result["schedules"] = {"error": str(e)}

    return result


async def main():
    await initialize_mcp()
    print(f"Tavily Tool: {search_tool.name}\n")
    print("Available Aviationstack MCP Tools:")
    for name in aviationstack_tools:
        print(f" - {name}")

    print("\n1. Testing list_airports:")
    airports = await aviation_get_airports("London", limit=2)
    print("Airports for London:", airports)

    print("\n2. Testing list_airlines:")
    airlines = await aviation_get_airlines("Emirates", limit=1)
    print("Airlines for Emirates:", airlines)

    print("\n3. Testing aviation_flight_search (New York -> London):")
    flights = await aviation_flight_search(
        departure_city="New York",
        destination_city="London",
        flight_date="2026-10-01",
    )
    print("Flight Search Results:", json.dumps(flights, indent=2))


if __name__ == '__main__':
    asyncio.run(main())

