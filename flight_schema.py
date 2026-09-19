from pydantic import BaseModel

class FlightSearchRequest(BaseModel):
    departure_city: str
    destination_city: str
    departure_date: str | None = None