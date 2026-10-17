"""
agents.py - LangGraph ReAct agents for LangGraph Studio and RecallTracer UI.
Exports two zero-argument factory functions: investigator() and store_ops().
"""

import os
import json
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

import tools


def _compact_res(envelope: Dict[str, Any]) -> str:
    """Format compact tool response for the LLM agent."""
    return json.dumps({
        "outcome": envelope.get("outcome", "answered"),
        "rows": envelope.get("rows", [])[:8]
    })


# ==============================================================================
# INVESTIGATOR AGENT TOOLS
# ==============================================================================

@tool
def record_complaints_tool(items: List[Dict[str, Any]]) -> str:
    """Validate and record consumer complaints into the BazaarMart database."""
    res = tools.record_complaints(items)
    return _compact_res(res)


@tool
def lots_behind_tool(batch_ids: List[str]) -> str:
    """Find upstream ingredient/component lots that were used in the given batch IDs."""
    res = tools.lots_behind(batch_ids)
    return _compact_res(res)


@tool
def recall_findings_tool(subject_id: str) -> str:
    """Check organizational memory for prior confirmed recall findings regarding this lot or batch."""
    res = tools.recall_findings(subject_id)
    return _compact_res(res)


@tool
def rank_lots_tool(depth: int = 1) -> str:
    """
    Rank candidate lots against recorded complaints by computing coverage and specificity.
    Use depth=1 for direct ingredient usage (1 hop).
    Use depth=2 to capture intermediate mixes (1..2 hops).
    """
    res = tools.rank_lots(depth=depth)
    return _compact_res(res)


@tool
def forward_trace_tool(lot: str) -> str:
    """Forward trace an ingredient lot to finished batches, delivered stores, and customer purchases."""
    res = tools.forward_trace(lot)
    return _compact_res(res)


@tool
def exposure_routes_tool(from_stores: List[str], max_days: int = 3) -> str:
    """Trace transfer lanes between stores within max_days exposure window."""
    res = tools.exposure_routes(from_stores=from_stores, max_days=max_days)
    return _compact_res(res)


@tool
def illness_tool() -> str:
    """Classify outbreak hazard severity (Class I or Class II) from complaint symptom descriptions."""
    res = tools.illness()
    return _compact_res(res)


@tool
def resolve_lot_tool(lot: str) -> str:
    """Verify if a lot ID exists in the network catalog. Suggests closest matching IDs if unknown."""
    res = tools.resolve_lot(lot)
    return _compact_res(res)


@tool
def notice_context_tool(lot: str, issued_by: Optional[str] = None, material: Optional[str] = None, reason: Optional[str] = None) -> str:
    """Retrieve supplier notice details and determine if the lot was used in any active product batches."""
    res = tools.notice_context(lot=lot, issued_by=issued_by, material=material, reason=reason)
    return _compact_res(res)


@tool
def write_investigation_tool(case: str, status: str, summary: str, lot_id: str = "", batch_ids: str = "") -> str:
    """
    Record investigation conclusion in BazaarMart graph.
    case must be 'complaints' or 'notice'.
    status must ONLY be 'open' or 'no_link'. Agent cannot set 'confirmed'.
    """
    if case not in {"complaints", "notice"}:
        return json.dumps({"error": f"Invalid case '{case}'. Must be 'complaints' or 'notice'."})
    if status not in {"open", "no_link"}:
        return json.dumps({"error": f"Invalid status '{status}'. Agent is only permitted to set 'open' or 'no_link'."})

    res = tools.write_investigation(case=case, status=status, summary=summary, lot_id=lot_id, batch_ids=batch_ids)
    return _compact_res(res)


# ==============================================================================
# STORE-OPS AGENT TOOLS
# ==============================================================================

@tool
def load_investigation_tool(id: str = "INV-COMPLAINTS") -> str:
    """Load investigation state (status, summary, lot_id, batch_ids)."""
    res = tools.load_investigation(id=id)
    return _compact_res(res)


@tool
def pull_list_tool(batch_ids: List[str]) -> str:
    """Retrieve on-duty store shelf locations with available stock for affected batches."""
    res = tools.pull_list(batch_ids)
    return _compact_res(res)


@tool
def current_tasks_tool(inv_id: str = "INV-COMPLAINTS") -> str:
    """List currently dispatched tasks for the investigation to avoid duplicate dispatching."""
    res = tools.tasks_for(id=inv_id)
    return _compact_res(res)


@tool
def dispatch_task_tool(store: str) -> str:
    """Dispatch a recall pull task to the on-duty associate at the specified store."""
    res = tools.dispatch_task(store=store, inv="INV-COMPLAINTS")
    return _compact_res(res)


# ==============================================================================
# SYSTEM PROMPTS
# ==============================================================================

INVESTIGATOR_SYSTEM_PROMPT = """You are the RecallTracer Incident Investigation Agent.
Your responsibility is to investigate consumer complaints and supplier notices using graph database tools.

Strict Investigation Workflow:
1. When given a complaint list:
   a. Call record_complaints_tool with the complaints.
   b. Call lots_behind_tool on the recorded batch IDs.
   c. Call recall_findings_tool for each upstream lot.
      If any finding returns outcome == 'from_memory', report which lot was identified from memory and STOP IMMEDIATELY. Do NOT call rank_lots_tool.
   d. If not in memory, call rank_lots_tool(depth=1).
      A lot is confirmed ONLY if its row status == 'confirmed' (never guess based on opinion).
   e. If a lot is confirmed at depth 1:
      - Call forward_trace_tool for that lot.
      - Call exposure_routes_tool on the stores in the trace.
      - Call illness_tool to assess hazard severity.
      - Call write_investigation_tool(case='complaints', status='open', summary=..., lot_id=..., batch_ids=...).
      - Stop and request human confirmation.
   f. If depth 1 has 'inconclusive' rows and nothing 'confirmed':
      - Call rank_lots_tool(depth=2) to inspect intermediate mixes.
      - If a lot is confirmed at depth 2, run the follow-up steps (forward_trace, exposure_routes, illness, write_investigation status='open') and stop for human confirmation.
   g. If nothing is confirmed at depth 2:
      - Call write_investigation_tool(case='complaints', status='no_link', summary='No common root cause confirmed') and stop.

2. When given a supplier notice:
   a. Call resolve_lot_tool first. If outcome == 'unknown_entity', report closest IDs and stop.
   b. Call notice_context_tool. If outcome == 'not_in_graph' (used_in == 0):
      - Call write_investigation_tool(case='notice', status='no_link', summary=...) and stop.
   c. Otherwise call forward_trace_tool and report exposure.

Safety constraints:
- NEVER set investigation status to 'confirmed'. Status can only be 'open' or 'no_link'.
- NEVER dispatch store tasks.
"""

STORE_OPS_SYSTEM_PROMPT = """You are the RecallTracer Store Operations Agent.
Your responsibility is to coordinate on-the-ground store pull tasks for confirmed product recall investigations.

Store-Ops Execution Workflow:
1. Call load_investigation_tool('INV-COMPLAINTS').
   - STOP IMMEDIATELY unless investigation status is 'confirmed' or 'closed'.
2. Call pull_list_tool with the investigation batch IDs.
3. Call current_tasks_tool to see which stores already have dispatched tasks.
4. Call dispatch_task_tool(store) once for each on-duty store that does NOT already have a task.
5. Conclude by clearly summarizing:
   - Which stores were dispatched
   - Which associate is assigned to pull each location and batch
   - Any stores skipped because they already have active tasks
"""


# ==============================================================================
# FACTORY FUNCTIONS FOR LANGGRAPH STUDIO AND UI
# ==============================================================================

def investigator():
    """Factory function creating the Investigator ReAct agent."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing or empty. Please set it in your environment or .env file.")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0)

    tools_list = [
        record_complaints_tool,
        lots_behind_tool,
        recall_findings_tool,
        rank_lots_tool,
        forward_trace_tool,
        exposure_routes_tool,
        illness_tool,
        resolve_lot_tool,
        notice_context_tool,
        write_investigation_tool
    ]

    return create_react_agent(
        model=llm,
        tools=tools_list,
        prompt=INVESTIGATOR_SYSTEM_PROMPT
    )


def store_ops():
    """Factory function creating the Store-Ops ReAct agent."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing or empty. Please set it in your environment or .env file.")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0)

    tools_list = [
        load_investigation_tool,
        pull_list_tool,
        current_tasks_tool,
        dispatch_task_tool
    ]

    return create_react_agent(
        model=llm,
        tools=tools_list,
        prompt=STORE_OPS_SYSTEM_PROMPT
    )
