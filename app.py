import uuid
import json
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command

from graph import app as travel_graph
from config import settings

# Page Configuration
st.set_page_config(
    page_title="AI Travel Planner | Multi-Agent MCP",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for rich aesthetics
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .badge-card {
        padding: 0.75rem 1rem;
        border-radius: 8px;
        background-color: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.2);
        margin-bottom: 0.75rem;
    }
    .agent-pill {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        background-color: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.4);
        margin-right: 0.35rem;
        margin-bottom: 0.35rem;
    }
    .approval-banner {
        padding: 1.2rem;
        border-radius: 10px;
        background: rgba(234, 179, 8, 0.1);
        border: 1px solid rgba(234, 179, 8, 0.4);
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "is_paused" not in st.session_state:
    st.session_state.is_paused = False
if "interrupt_data" not in st.session_state:
    st.session_state.interrupt_data = None
if "latest_state" not in st.session_state:
    st.session_state.latest_state = {}

# --- Sidebar ---
with st.sidebar:
    st.markdown("### 🧭 Travel Planner Control")
    st.caption(f"Session Thread: `{st.session_state.thread_id[:8]}...`")

    if st.button("🔄 New Trip Session", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.chat_history = []
        st.session_state.is_paused = False
        st.session_state.interrupt_data = None
        st.session_state.latest_state = {}
        st.rerun()

    st.markdown("---")
    st.markdown("#### ⚡ Connected MCP Tools")
    st.markdown("""
    - 🛫 **Aviationstack MCP** (stdio)
    - 🌤️ **OpenWeather MCP** (stdio)
    - 🔍 **Tavily Search MCP** (HTTP)
    """)

    st.markdown("---")
    st.markdown("#### 💡 Quick Test Prompts")
    sample_queries = [
        "Plan a trip from Nagpur to Mumbai for 5 days, budget is 50K",
        "Weekend getaway from Delhi to Jaipur for 2 days on a 20k budget",
        "Plan a 4-day solo trip to Goa from Bangalore with hostel options",
    ]
    for q in sample_queries:
        if st.button(q, key=f"btn_{q[:15]}", use_container_width=True):
            st.session_state.selected_prompt = q
            st.rerun()

# --- Main App ---
st.markdown('<div class="main-header">✈️ Multi-Agent AI Travel Planner</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Powered by LangGraph, Groq Qwen, and Real-Time MCP Servers</div>', unsafe_allow_html=True)

config = {"configurable": {"thread_id": st.session_state.thread_id}}

def update_session_from_graph():
    """Sync session state with current LangGraph state snapshot."""
    try:
        snapshot = travel_graph.get_state(config)
        if snapshot and snapshot.values:
            st.session_state.latest_state = snapshot.values

        # Check if paused on interrupt
        if snapshot and snapshot.tasks:
            for task in snapshot.tasks:
                if task.interrupts:
                    st.session_state.is_paused = True
                    st.session_state.interrupt_data = task.interrupts[0].value
                    return
        st.session_state.is_paused = False
        st.session_state.interrupt_data = None
    except Exception as e:
        st.error(f"Error checking graph state: {e}")

# Pre-fill query if clicked from sidebar
prefilled_query = st.session_state.pop("selected_prompt", "")
user_input = st.chat_input("Where would you like to travel? (e.g. 'Plan a trip from Nagpur to Mumbai for 5 days, budget is 50K')")
query_to_run = user_input or prefilled_query

# Handle New Query Submission
if query_to_run:
    st.session_state.chat_history.append({"role": "user", "content": query_to_run})
    st.session_state.is_paused = False
    st.session_state.interrupt_data = None
    st.session_state.latest_state = {}

    with st.status("🤖 Multi-agent team coordinate planning...", expanded=True) as status_box:
        input_payload = {
            "user_query": query_to_run,
            "messages": [HumanMessage(content=query_to_run)],
        }

        try:
            for chunk in travel_graph.stream(input_payload, config=config, stream_mode="updates"):
                for node_name, node_output in chunk.items():
                    if node_name == "supervisor":
                        agents = node_output.get("selected_agent", [])
                        st.write(f"🧭 **Supervisor** selected agents: `{', '.join(agents)}`")
                    elif node_name == "flight_agent":
                        st.write("🛫 **Flight Agent** fetched airport routes & schedules.")
                    elif node_name == "hotel_agent":
                        st.write("🏨 **Hotel Agent** retrieved accommodation options via Tavily.")
                    elif node_name == "weather_agent":
                        st.write("🌤️ **Weather Agent** fetched current weather & 5-day forecast.")
                    elif node_name == "budget_agent":
                        st.write("💰 **Budget Agent** assessed cost feasibility and financial risks.")
                    elif node_name == "itinerary_agent":
                        st.write("📝 **Itinerary Agent** synthesized the draft itinerary.")
                    elif node_name == "final_response":
                        st.write("✨ **Final Agent** compiled the complete travel guide.")

            status_box.update(label="Planning phase completed!", state="complete", expanded=False)
        except Exception as e:
            status_box.update(label=f"Execution interrupted: {e}", state="error", expanded=True)

    update_session_from_graph()
    st.rerun()

# --- Display State & Findings ---
state = st.session_state.latest_state

# Display Selected Agents & Constraints if available
if state.get("trip_constraints"):
    constraints = state.get("trip_constraints", {})
    cols = st.columns(4)
    with cols[0]:
        st.metric("🛫 Origin", constraints.get("origin") or "N/A")
    with cols[1]:
        st.metric("📍 Destination", constraints.get("destination") or "N/A")
    with cols[2]:
        st.metric("⏳ Duration", constraints.get("duration") or "N/A")
    with cols[3]:
        st.metric("💰 Budget", constraints.get("budget") or "N/A")

    if state.get("selected_agent"):
        pills_html = "".join([f'<span class="agent-pill">✓ {a}</span>' for a in state["selected_agent"]])
        st.markdown(f"**Activated Specialists:** {pills_html}", unsafe_allow_html=True)
    st.markdown("---")

# Specialist Tabs
if any([state.get("flight_result"), state.get("hotel_result"), state.get("weather_result"), state.get("budget_result")]):
    st.markdown("### 📊 Specialist Agent Findings")
    tab_flight, tab_hotel, tab_weather, tab_budget = st.tabs([
        "🛫 Flights", "🏨 Accommodation", "🌤️ Weather Forecast", "💰 Budget Analysis"
    ])

    with tab_flight:
        if state.get("flight_result"):
            st.markdown(state["flight_result"])
        else:
            st.info("Flight agent was not requested for this query.")

    with tab_hotel:
        hotel_data = state.get("hotel_result") or state.get("hostel_result")
        if hotel_data:
            st.markdown(hotel_data)
        else:
            st.info("Accommodation agent was not requested for this query.")

    with tab_weather:
        if state.get("weather_result"):
            st.markdown(state["weather_result"])
        else:
            st.info("Weather agent was not requested for this query.")

    with tab_budget:
        if state.get("budget_result"):
            st.markdown(state["budget_result"])
        else:
            st.info("Budget agent was not requested for this query.")

    st.markdown("---")

# --- Human-in-the-Loop Approval Section ---
if st.session_state.is_paused and st.session_state.interrupt_data:
    st.markdown('<div class="approval-banner">', unsafe_allow_html=True)
    st.markdown("### 🛑 Human Review Required")
    st.markdown("The **Itinerary Agent** has generated a draft travel plan. Please review it below before final confirmation.")

    # Prefer interrupt data itinerary; fallback to state itinerary
    itinerary_draft = (
        st.session_state.interrupt_data.get("review_itinerary")
        or state.get("itinerary", "")
        or st.session_state.get("last_itinerary", "")
    )

    # Persist itinerary in session so it survives reruns
    if itinerary_draft:
        st.session_state["last_itinerary"] = itinerary_draft

    with st.expander("📋 Review Draft Itinerary", expanded=True):
        st.markdown(itinerary_draft if itinerary_draft else "_Itinerary loading..._")

    # ---- Approval & Feedback buttons ----
    st.markdown("#### What would you like to do?")
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("✅ Approve & Generate Final Guide", type="primary", use_container_width=True):
            final_text = None
            error_msg = None

            with st.spinner("Finalizing your travel guide..."):
                try:
                    for chunk in travel_graph.stream(
                        Command(resume={"approved": True, "feedback": "Approved by user"}),
                        config=config,
                        stream_mode="updates",
                    ):
                        # Capture final_response directly from the stream
                        for node_name, node_output in chunk.items():
                            if node_name == "final_response" and isinstance(node_output, dict):
                                final_text = node_output.get("final_response")
                except Exception as e:
                    error_msg = str(e)

            if error_msg:
                # Store error so it survives the rerun
                st.session_state["approval_error"] = error_msg
            else:
                st.session_state.pop("approval_error", None)

            # If we captured final_response from stream, store it directly
            if final_text:
                st.session_state["captured_final_response"] = final_text

            # Also sync from graph state as a backup
            update_session_from_graph()
            st.session_state.pop("last_itinerary", None)
            st.rerun()


    with col_btn2:
        st.markdown("**Request Changes**")
        # Use a session-state-backed text area so it persists on rerun
        feedback_key = "revision_feedback_input"
        st.text_area(
            "What adjustments would you like?",
            placeholder="e.g. 'Show more places to explore and visit on Day 2'",
            key=feedback_key,
        )
        if st.button("✏️ Submit Revisions", use_container_width=True):
            feedback_text = st.session_state.get(feedback_key, "").strip()
            if feedback_text:
                with st.spinner("Sending feedback to Itinerary Agent for revision..."):
                    try:
                        for chunk in travel_graph.stream(
                            Command(resume={"approved": False, "feedback": feedback_text}),
                            config=config,
                            stream_mode="updates",
                        ):
                            # Show progress for each node that runs
                            for node_name in chunk:
                                if node_name == "itinerary_agent":
                                    st.write("📝 Itinerary Agent is revising your plan...")
                    except Exception as e:
                        st.error(f"Error submitting feedback: {e}")
                # Clear the old cached draft so fresh one from graph is used
                st.session_state.pop("last_itinerary", None)
                update_session_from_graph()
                st.rerun()
            else:
                st.warning("Please enter your feedback before submitting.")

    st.markdown('</div>', unsafe_allow_html=True)

# Show any errors from approval flow (persists through rerun)
if st.session_state.get("approval_error"):
    st.error(f"Error during finalization: {st.session_state['approval_error']}")
    if st.button("Dismiss Error"):
        st.session_state.pop("approval_error", None)
        st.rerun()

# --- Final Travel Guide Display ---
# Try state first, then fall back to directly captured stream data
final_response = (
    state.get("final_response")
    or st.session_state.get("captured_final_response")
)

if final_response:
    st.markdown("## 🎉 Final Confirmed Travel Plan")
    st.markdown(final_response)

    st.download_button(
        label="📥 Download Travel Guide (Markdown)",
        data=final_response,
        file_name="travel_itinerary.md",
        mime="text/markdown",
    )
elif not query_to_run and not state:
    st.info("👋 Enter your travel query in the chat input below or choose a sample prompt from the sidebar to get started!")
