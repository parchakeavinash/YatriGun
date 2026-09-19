import httpx
from config import settings

def flight_search(query: str, dep_iata: str, arr_iata: str) ->str:
    BASE_URL = "https://api.aviationstack.com/v1/flights"

    params = {
        'access_key': settings.AVIATIONSTACK_API_KEY,
        "dep_iata": dep_iata,
        "arr_iata": arr_iata,
        'limit': 5
    }

    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(BASE_URL, params=params)

        response.raise_for_status()

    except httpx.HTTPStatusError as e:
        return [{
            "error": f"API returned {e.response.status_code}: {e.response.text}"
        }]

    except httpx.RequestError as e:
        return [{
            "error": f"Request failed: {e}"
        }]

    flights = response.json().get("data", [])

    if not flights:
        return [{
            "message": "No flights found."
        }]

    results = []

    for flight in flights:

        airline = flight.get("airline", {}).get("name", "Unknown")
        departure = flight.get("departure", {}).get("airport", "Unknown")
        arrival = flight.get("arrival", {}).get("airport", "Unknown")
        status = flight.get("flight_status", "Unknown")

        results.append({
            "airline": airline,
            "departure": departure,
            "arrival": arrival,
            "status": status,
        })

    return results