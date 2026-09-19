import sys
from pathlib import Path

# Add project root to sys.path so config can be loaded
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp.server.fastmcp import FastMCP
import requests
from config import settings

mcp = FastMCP(
    "openweather_mcp",
    instructions="MCP server for OpenWeatherMap API"
)

@mcp.tool()
def get_current_weather(city: str) -> dict:
    """Get current weather for a given city."""
    api_key = settings.OPENWEATHER_API_KEY
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={api_key}"

    try:
        response = requests.get(url=url, timeout=10)
        data = response.json()
    except Exception as e:
        return {"error": str(e)}

    if response.status_code != 200:
        return {"error": data.get("message", "Unknown error")}

    weather_data = {
        "city": data.get("name"),
        "country": data.get("sys", {}).get("country"),
        "temperature": data.get("main", {}).get("temp"),
        "feels_like": data.get("main", {}).get("feels_like"),
        "humidity": data.get("main", {}).get("humidity"),
        "weather_description": data.get("weather", [{}])[0].get("description"),
    }

    return weather_data


@mcp.tool()
def get_forecast(city: str) -> dict:
    """Get weather forecast for a given city."""
    api_key = settings.OPENWEATHER_API_KEY
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&units=metric&appid={api_key}"

    try:
        response = requests.get(url=url, timeout=10)
        data = response.json()
    except Exception as e:
        return {"error": str(e)}

    if response.status_code != 200:
        return {"error": data.get("message", "Unknown error")}

    forecast_data = {
        "city": data.get("city", {}).get("name"),
        "forecast_list": data.get("list", [])[:5],
    }

    return forecast_data


if __name__ == "__main__":
    mcp.run()