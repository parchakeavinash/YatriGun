from typing import List, TypedDict, Annotated, Any
import operator
from langchain_core.messages import AnyMessage


class TravelState(TypedDict, total=False):
    messages: Annotated[List[AnyMessage], operator.add]
    user_id: str
    user_query: str

    trip_constraints: dict[str,Any]
    selected_agent: str
    supervisor_agent_reasoning:str


    flight_result: str
    weather_result: dict
    hotel_result: str
    itinerary: str
    budget_result:str
    llm_calls: int

    approval_request: str
    human_feedback:str
    approved:bool

    final_response: str
