# 🌍 YatriGun — Multi-Agent AI Travel Planner with MCP

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-v1.2+-purple.svg)](https://github.com/langchain-ai/langgraph)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Protocol-orange.svg)](https://modelcontextprotocol.io/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red.svg)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg)](https://www.postgresql.org/)

**YatriGun** is an enterprise-grade, autonomous multi-agent travel planning system built on **LangGraph**, **Google Gemini**, and the **Model Context Protocol (MCP)**. It dynamically routes travel inquiries through specialized autonomous agents, fetches real-time route, stay, and weather information via MCP servers, and provides a **Human-in-the-Loop (HITL)** approval cycle before producing an exhaustive, personalized travel guide.

---

## 🏛️ System Architecture

```mermaid
graph TD
    User([User Request / Streamlit UI]) --> Supervisor[🧭 Supervisor Agent]
    
    subgraph Specialist_Layer [Specialist Agents]
        Supervisor -->|routes| Flight[🛫 Flight Agent]
        Supervisor -->|routes| Hotel[🏨 Hotel Agent]
        Supervisor -->|routes| Weather[🌤️ Weather Agent]
        Supervisor -->|routes| Budget[💰 Budget Agent]
    end

    subgraph MCP_Layer [Model Context Protocol Servers]
        Flight <-->|stdio| AvStack[Aviationstack MCP]
        Hotel <-->|streamable HTTP| Tavily[Tavily Search MCP]
        Weather <-->|stdio| OpenWthr[OpenWeather MCP]
    end

    Flight --> Itinerary[📅 Itinerary Agent]
    Hotel --> Itinerary
    Weather --> Itinerary
    Budget --> Itinerary

    Itinerary --> HITL{👤 Human-in-the-Loop Approval}
    HITL -->|Changes Requested| Itinerary
    HITL -->|Approved| FinalGuide[🎉 Final Travel Concierge Agent]
    FinalGuide --> Completed([Polished Travel Plan & Download])

    subgraph Persistence [State Persistence]
        Itinerary -.-> Postgres[(PostgreSQL Checkpointer)]
        HITL -.-> Postgres
        FinalGuide -.-> Postgres
    end
```

---

## 🌟 Key Capabilities

- **Autonomous Agent Supervisor**: Dynamically decomposes travel queries, extracts trip constraints (destination, origin, budget, duration), and routes tasks to the appropriate specialists.
- **Model Context Protocol (MCP) Standard**: Connects directly to external tools via standard MCP transports:
  - **Aviationstack MCP (`stdio`)**: Flight routes, schedules, and airport IATA lookups.
  - **OpenWeather MCP (`stdio`)**: Live weather data and multi-day meteorological forecasts.
  - **Tavily MCP (`streamable_http`)**: Neighborhood recommendations and accommodation discovery.
- **Human-in-the-Loop (HITL) Revision Loop**: Uses LangGraph `interrupt` to present a draft itinerary to the traveler. Users can approve or request revisions, and the agent adapts the draft while keeping good segments intact.
- **Dynamic Duration Engine**: Adapts dynamically to any trip length (e.g., 2-day weekend trip vs. 7-day tour) with full morning, afternoon, and evening coverage.
- **Enterprise Persistence**: Backed by `PostgresSaver` connection pooling, allowing user sessions and drafts to survive interruptions and server restarts.
- **Modern Streamlit Frontend**: Real-time status cards, specialist findings preview, interactive review/revision forms, and instant Markdown download.

---

## 📂 Project Structure

```
Multi_agent_with_MCP/
├── .env.example              # Template for API keys and configuration
├── .gitignore                # Excludes secrets, caches, and virtual environments
├── pyproject.toml            # Project metadata and dependencies (uv / pip)
├── requirements.txt          # Python package requirements
├── README.md                 # System overview and quickstart guide
│
├── config.py                 # Pydantic Settings & Gemini / LLM factory
├── state.py                  # LangGraph TravelState schema definition
├── graph.py                  # LangGraph state machine, routing, and compilation
├── agent.py                  # Agent definitions (Supervisor, Flight, Hotel, Weather, Budget, Itinerary, HITL, Final)
├── mcp_client.py             # Unified MultiServerMCPClient management (Tavily, Aviationstack, OpenWeather)
│
├── app.py                    # Streamlit interactive UI application
├── main.py                   # Terminal / CLI interactive execution script
│
├── mcp_servers/              # Standalone local MCP servers
│   └── openweather_mcp_server.py # Standalone stdio MCP server for OpenWeather
│
├── aviationstack-mcp/        # Local stdio MCP server package for Aviationstack
│
├── utils/                    # Travel helpers, airport codes & schemas
│   ├── __init__.py
│   ├── airport_codes.py      # Static IATA fallback codes
│   ├── airport_helper.py     # Airport resolution helpers
│   ├── flight_schema.py      # Flight query schemas
│   ├── flight_service.py     # Aviation service utility
│   ├── travel_parser.py      # Query parsing utilities
│   ├── travel_schema.py      # Travel data schemas
│   └── tools/                # Internal tool helpers
│
└── tests/                    # Verification & diagnostic tests
    ├── __init__.py
    ├── test_aviation_stack_mcp.py  # Aviationstack MCP verification test
    └── testing_openweather_mcp.py  # OpenWeather MCP verification test
```

---

## 🚀 Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/parchakeavinash/YatriGun.git
cd YatriGun
```

### 2. Set Up Virtual Environment

**Using `uv` (Recommended):**
```bash
uv venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux
uv sync
```

**Using `pip`:**
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
copy .env.example .env     # Windows
# cp .env.example .env     # macOS/Linux
```

Fill in your actual API credentials in `.env`:
```env
GOOGLE_API_KEY="your_google_gemini_api_key"
TAVILY_API_KEY="your_tavily_api_key"
AVIATIONSTACK_API_KEY="your_aviationstack_api_key"
OPENWEATHER_API_KEY="your_openweather_api_key"
DATABASE_URL="postgresql://postgres:password@localhost:5432/travel_agent"
```

> **Note**: Ensure a PostgreSQL instance is running on the specified `DATABASE_URL` with a database named `travel_agent` (or update the URI to match your local setup).

---

## 🖥️ Running the Application

### Option A: Launch the Streamlit Web App (Recommended)
```bash
uv run streamlit run app.py
# or
streamlit run app.py
```
Open **http://localhost:8501** in your browser to start planning trips interactively.

### Option B: Run in Terminal (CLI Mode)
```bash
uv run python main.py
# or
python main.py
```

---

## 🧭 Example Travel Queries

- *"Plan a trip from Hyderabad to Mumbai for 4 days, budget is 30K"*
- *"Weekend getaway from Delhi to Jaipur for 2 days on a 20k budget"*
- *"5-day cultural and food exploration in Bangalore from Chennai with luxury stays"*

---

## 🛡️ License
Distributed under the MIT License. See `LICENSE` for more information.
