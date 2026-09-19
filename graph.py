import psycopg
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph

from agent import (
    budget_agent,
    final_agent,
    flight_agent,
    hotel_agent,
    human_approval_agent,
    itinerary_agent,
    supervisor_agent,
    weather_agent,
)
from config import settings
from state import TravelState

DATABASE_URL = getattr(settings, "DATABASE_URL", "").replace(
    "postgresql+psycopg://",
    "postgresql://",
    1,
)

# Ordered list of specialist agents (defines execution order)
AGENT_ORDER = [
    "flight_agent",
    "hotel_agent",
    "weather_agent",
    "budget_agent",
]

# Valid routing destinations for conditional edges
ROUTE_MAP = {
    "flight_agent": "flight_agent",
    "hotel_agent": "hotel_agent",
    "weather_agent": "weather_agent",
    "budget_agent": "budget_agent",
    "itinerary_agent": "itinerary_agent",
}


def get_selected_agents(state: TravelState) -> list[str]:
    """Return ordered list of selected specialist agents (excluding itinerary_agent)."""
    selected = state.get("selected_agent", [])
    if isinstance(selected, str):
        selected = [selected]
    # Only keep agents that are in AGENT_ORDER (not itinerary_agent)
    return [agent for agent in AGENT_ORDER if agent in selected]


def route_from_supervisor(state: TravelState) -> str:
    """Route from supervisor to the first selected specialist, or straight to itinerary_agent."""
    selected = get_selected_agents(state)
    return selected[0] if selected else "itinerary_agent"


def route_after_agent(current_agent: str):
    """
    Returns a routing function that finds the NEXT selected specialist agent
    after `current_agent` in AGENT_ORDER, or falls through to `itinerary_agent`.
    """
    def route(state: TravelState) -> str:
        selected = get_selected_agents(state)  # ordered subset of AGENT_ORDER

        try:
            current_index = AGENT_ORDER.index(current_agent)
        except ValueError:
            return "itinerary_agent"

        # Walk through remaining agents in order; pick first one that is selected
        for agent in AGENT_ORDER[current_index + 1:]:
            if agent in selected:
                return agent

        # No more specialist agents — go to itinerary_agent
        return "itinerary_agent"

    return route


def route_after_approval(state: TravelState) -> str:
    """Route to final_response if approved, or loop back to itinerary_agent to revise."""
    if state.get("approved"):
        return "final_response"
    return "itinerary_agent"


def build_graph():
    graph = StateGraph(TravelState)

    # 1. Add all agent nodes
    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("flight_agent", flight_agent)
    graph.add_node("hotel_agent", hotel_agent)
    graph.add_node("weather_agent", weather_agent)
    graph.add_node("budget_agent", budget_agent)
    graph.add_node("itinerary_agent", itinerary_agent)
    graph.add_node("human_approval", human_approval_agent)
    graph.add_node("final_response", final_agent)

    # 2. Entry: START -> supervisor
    graph.add_edge(START, "supervisor")

    # 3. Supervisor -> first selected specialist (or itinerary_agent)
    graph.add_conditional_edges("supervisor", route_from_supervisor, ROUTE_MAP)

    # 4. Each specialist -> next selected specialist (or itinerary_agent)
    graph.add_conditional_edges("flight_agent", route_after_agent("flight_agent"), ROUTE_MAP)
    graph.add_conditional_edges("hotel_agent", route_after_agent("hotel_agent"), ROUTE_MAP)
    graph.add_conditional_edges("weather_agent", route_after_agent("weather_agent"), ROUTE_MAP)
    graph.add_conditional_edges("budget_agent", route_after_agent("budget_agent"), ROUTE_MAP)

    # 5. itinerary_agent -> human_approval (interrupt point)
    graph.add_edge("itinerary_agent", "human_approval")

    # 6. human_approval -> final_response (approved) or itinerary_agent (needs revision)
    graph.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "final_response": "final_response",
            "itinerary_agent": "itinerary_agent",
        },
    )

    # 7. final_response -> END
    graph.add_edge("final_response", END)

    # Checkpointer: Postgres preferred (required for human-in-the-loop interrupts),
    # fallback to MemorySaver if DB is unavailable.
    if DATABASE_URL:
        try:
            conn = psycopg.connect(DATABASE_URL, autocommit=True)
            checkpointer = PostgresSaver(conn)
            checkpointer.setup()
            print("[OK] Using PostgreSQL checkpointer.")
            return graph.compile(checkpointer=checkpointer)
        except Exception as e:
            print(f"[WARN] PostgreSQL connection failed ({e}), falling back to in-memory checkpointer.")

    return graph.compile(checkpointer=MemorySaver())


app = build_graph()
