from pydantic import BaseModel
from typing import Optional


class TravelDetails(BaseModel):
    departure_city: str = ""
    destination_city: str = ""
    departure_date: str = ""
    return_date: Optional[str] = None

    budget: int | None = None

