import re
import time

from groq import RateLimitError
from langchain_core.messages import HumanMessage, SystemMessage
from config import settings
from travel_schema import TravelDetails
from langchain_groq import ChatGroq


llm = ChatGroq(
    model = "qwen/qwen3.8-27b",
    api_key=settings.GROQ_API_KEY,
    max_tokens=400,
    max_retries=0,
)

structured_llm = llm.with_structured_output(TravelDetails)

def extract_travel_details(user_query: str) -> TravelDetails:

    last_error = None
    for _ in range(6):
        try:
            response = structured_llm.invoke(
        [
            SystemMessage(
                content="""
You are an expert travel planner.

Extract the following fields.

- departure_city
- destination_city
- departure_date
- return_date
- travelers
- budget
- hotel_type
- location_preference

If a field is not mentioned,
return an empty string or null.
"""
            ),
            HumanMessage(content=user_query),
        ]
            )
            return response
        except RateLimitError as exc:
            last_error = exc
            match = re.search(r"try again in ([0-9.]+)s", str(exc), re.I)
            wait_s = float(match.group(1)) + 0.75 if match else 4.0
            print(f"Groq rate limit hit. Retrying in {wait_s:.1f}s...")
            time.sleep(wait_s)
    raise last_error