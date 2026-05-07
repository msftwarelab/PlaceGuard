"""LangGraph ReAct agent for VOYGR PlaceGuard.

Architecture:
    - ReAct pattern: Reasoning + Action in a loop
    - 6 validation/enrichment tools bound to the agent
    - Custom state type with full validation context
    - Structured JSON output matching VOYGR's Business Validation API

Design decisions:
    - Use TypedDict for graph state (LangGraph convention)
    - Parse tool results in the final reporter node
    - Fallback reasoning when tools return insufficient data
    - Clear separation between graph logic and business logic
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.llm_provider import get_default_llm
from agent.schemas import PlaceDetails, PlaceQuery, ValidationIssue, ValidationResult
from agent.tools import VALIDATION_TOOLS


# ---------------------------------------------------------------------------
# Agent State
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    """State for the PlaceGuard ReAct agent."""

    # Conversation messages (accumulated via add_messages reducer)
    messages: Annotated[list, add_messages]

    # Input query context
    query: str
    context: Optional[dict[str, Any]]

    # Validation results (built up across tool calls)
    place_id: Optional[str]
    place_name: Optional[str]
    exists: Optional[bool]
    operating: Optional[bool]
    price_verified: Optional[bool]
    safety_score: Optional[float]

    # Enrichment data
    enriched_details: Optional[dict[str, Any]]

    # Final output
    validation_result: Optional[dict[str, Any]]

    # Tracking
    model_used: str
    iteration_count: int


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are PlaceGuard, a production-grade place validation agent for VOYGR —
a travel recommendation platform. Your job is to validate place recommendations to ensure
they are real, operating, correctly priced, and safe for travelers.

## Your Tools
You have access to these validation tools:
1. **validate_place_existence** - Check if a place exists (use FIRST)
2. **check_operating_hours** - Verify operating status and hours (use after getting place_id)
3. **verify_pricing** - Validate price claims (use if user mentioned price)
4. **assess_safety_and_risk** - Get safety metrics (always use this)
5. **enrich_place_data** - Get full context and reviews (use LAST before summarizing)
6. **lookup_similar_alternatives** - Find alternatives if place fails validation

## Validation Process
Follow this EXACT order:
1. Call validate_place_existence with the place name and city
2. If exists → call check_operating_hours with place_id
3. If price mentioned → call verify_pricing with place_id and max price
4. Call assess_safety_and_risk with place_id
5. Call enrich_place_data with place_id
6. If any critical failures → call lookup_similar_alternatives

## Output Format
After all tools complete, provide your final assessment in this EXACT JSON format:
```json
{
    "place_id": "<id>",
    "name": "<name>",
    "status": "valid|uncertain|invalid",
    "confidence": 0.0,
    "exists": true,
    "operating": true,
    "price_verified": true,
    "safety_score": 0.0,
    "summary": "<brief summary of findings>"
}
```

## Status Rules
- **valid**: exists=true, operating=true, no critical issues, confidence >0.7
- **invalid**: exists=false OR operating=false (permanently closed)
- **uncertain**: exists but data is stale, or confidence 0.3-0.7

## Important Guidelines
- Be conservative: when in doubt, mark as "uncertain" not "valid"
- Always explain your reasoning step by step
- Flag stale data explicitly (older than 30 days)
- If a place seems hallucinated (very low match confidence), mark as invalid
- Price verification: if price range exceeds claims, flag as issue
"""


# ---------------------------------------------------------------------------
# Node Functions
# ---------------------------------------------------------------------------

def agent_node(state: AgentState) -> dict:
    """
    Core reasoning node — the LLM thinks and decides which tool to call next.

    This is the 'reason' step in the ReAct loop. The LLM sees all messages
    so far and decides: should I call a tool, or am I done?
    """
    model_name = state.get("model_used", "gpt-4-turbo-preview")
    iteration = state.get("iteration_count", 0) + 1

    # Get the LLM with tools bound
    llm = get_default_llm(temperature=0.3)
    llm_with_tools = llm.bind_tools(VALIDATION_TOOLS)

    # Build messages: system prompt + conversation history
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)

    # Extract model name from response metadata if available
    if hasattr(response, "response_metadata"):
        model_name = response.response_metadata.get("model_name", model_name)

    return {
        "messages": [response],
        "model_used": model_name,
        "iteration_count": iteration,
    }


def should_continue(state: AgentState) -> Literal["tools", "final_report"]:
    """
    Routing function: decide whether to call more tools or generate the final report.

    Returns 'tools' if the agent wants to call a tool, 'final_report' otherwise.
    """
    last_message = state["messages"][-1]

    # If the LLM called a tool, execute it
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Safety: limit to 10 iterations to prevent runaway loops
    if state.get("iteration_count", 0) >= 10:
        return "final_report"

    return "final_report"


def final_report_node(state: AgentState) -> dict:
    """
    Final report node — parse all tool results and compile the structured output.

    Extracts validation data from the conversation history and builds the
    final ValidationResult-compatible dict.
    """
    messages = state["messages"]

    tool_results: dict[str, Any] = {}
    reasoning_chain: list[str] = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            reasoning_chain.append(f"Query: {msg.content[:100]}")
        elif isinstance(msg, AIMessage):
            content = msg.content if isinstance(msg.content, str) else ""
            if content.strip():
                reasoning_chain.append(f"Reasoning: {content[:200]}")
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            reasoning_chain.append(f"Reasoning: {text[:200]}")
        elif isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                tool_name = getattr(msg, "name", "unknown_tool")
                tool_results[tool_name] = data
                if "message" in data:
                    reasoning_chain.append(f"Tool ({tool_name}): {data['message'][:200]}")
                for issue_msg in data.get("issues", []):
                    reasoning_chain.append(f"Issue: {issue_msg}")
            except (json.JSONDecodeError, Exception):
                pass

    # Extract the agent's final JSON block from the last non-tool AI message
    agent_summary: dict[str, Any] = {}
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not (
            hasattr(msg, "tool_calls") and msg.tool_calls
        ):
            content = msg.content if isinstance(msg.content, str) else ""
            if "```json" in content:
                try:
                    json_block = content.split("```json")[1].split("```")[0].strip()
                    agent_summary = json.loads(json_block)
                    break
                except (IndexError, json.JSONDecodeError):
                    pass

    # Convenience references to individual tool payloads
    existence_data = tool_results.get("validate_place_existence", {})
    hours_data = tool_results.get("check_operating_hours", {})
    pricing_data = tool_results.get("verify_pricing", {})
    safety_data = tool_results.get("assess_safety_and_risk", {})
    enrichment_data = tool_results.get("enrich_place_data", {})

    exists = bool(agent_summary.get("exists", existence_data.get("exists", False)))
    operating = bool(agent_summary.get("operating", hours_data.get("operating", False)))
    price_verified = bool(
        agent_summary.get("price_verified", pricing_data.get("price_verified", True))
    )
    safety_score = float(
        agent_summary.get("safety_score", safety_data.get("safety_score", 0.5))
    )
    confidence = float(agent_summary.get("confidence", 0.5))

    # Determine final status
    if not exists:
        status: str = "invalid"
        confidence = min(confidence, 0.3)
    elif not operating:
        status = "invalid"
    elif confidence >= 0.7 and not any(
        r.get("data_freshness") == "stale"
        for r in tool_results.values()
        if isinstance(r, dict)
    ):
        status = "valid"
    else:
        status = agent_summary.get("status", "uncertain")

    # Build issues list
    issues: list[ValidationIssue] = []
    for tool_name, result in tool_results.items():
        if isinstance(result, dict) and result.get("issues"):
            for issue_msg in result["issues"]:
                severity = (
                    "error"
                    if "🚫" in issue_msg
                    else "warning" if "⚠️" in issue_msg else "info"
                )
                issues.append(
                    ValidationIssue(
                        severity=severity,
                        field=tool_name.replace("_", " "),
                        message=issue_msg.replace("🚫 ", "").replace("⚠️ ", "").replace("ℹ️ ", ""),
                    )
                )

    place_id = (
        agent_summary.get("place_id")
        or existence_data.get("place_id")
        or enrichment_data.get("place_id")
        or f"pg-{str(uuid.uuid4())[:8]}"
    )
    place_name = (
        agent_summary.get("name")
        or existence_data.get("name")
        or enrichment_data.get("name")
        or "Unknown Place"
    )

    details = PlaceDetails(
        address=enrichment_data.get("address") or existence_data.get("address") or "Unknown",
        city=enrichment_data.get("city") or existence_data.get("city"),
        country=enrichment_data.get("country"),
        hours=hours_data.get("hours"),
        price_tier=pricing_data.get("price_tier"),
        category=enrichment_data.get("category") or "Unknown",
        reviews_summary=enrichment_data.get("reviews_summary"),
        average_rating=enrichment_data.get("average_rating")
        or safety_data.get("average_rating"),
        data_freshness=hours_data.get("data_freshness", "current"),
    )

    result = ValidationResult(
        place_id=place_id,
        name=place_name,
        status=status,
        confidence=confidence,
        exists=exists,
        operating=operating,
        price_verified=price_verified,
        safety_score=safety_score,
        details=details,
        issues=issues,
        reasoning_chain=[r for r in reasoning_chain if r.strip()][:15],
        model_used=state.get("model_used", "gpt-4"),
    )

    return {"validation_result": result.model_dump(mode="json")}


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

def build_agent_graph():
    """
    Build the PlaceGuard LangGraph ReAct agent.

    Graph structure:
        agent_node → should_continue → tools (if tool call) → agent_node (loop)
                                     → final_report (if done)

    Returns:
        Compiled LangGraph StateGraph
    """
    tool_node = ToolNode(tools=VALIDATION_TOOLS)

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("final_report", final_report_node)

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "final_report": "final_report"},
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("final_report", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def run_validation(query: PlaceQuery) -> ValidationResult:
    """
    Run the PlaceGuard validation agent on a place query.

    Args:
        query: PlaceQuery with user's natural language or LLM output

    Returns:
        Structured ValidationResult matching VOYGR's Business Validation API

    Raises:
        RuntimeError: If the agent fails to produce a valid result
    """
    compiled_graph = build_agent_graph()

    initial_state: AgentState = {
        "messages": [HumanMessage(content=query.query)],
        "query": query.query,
        "context": query.context,
        "place_id": None,
        "place_name": None,
        "exists": None,
        "operating": None,
        "price_verified": None,
        "safety_score": None,
        "enriched_details": None,
        "validation_result": None,
        "model_used": "gpt-4-turbo-preview",
        "iteration_count": 0,
    }

    final_state = compiled_graph.invoke(initial_state)

    if not final_state.get("validation_result"):
        raise RuntimeError("Agent failed to produce validation result")

    return ValidationResult(**final_state["validation_result"])


# Expose for LangGraph Studio / langgraph.json compatibility
graph = build_agent_graph()

