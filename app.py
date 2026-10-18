"""RecallTracer scripted demo and optional in-app LangGraph chat (Port 8501)."""

import json
import streamlit as st

import tools
import investigator
import store_ops
import graph_view

# Streamlit Page Setup
st.set_page_config(
    page_title="RecallTracer — Incident Response Demo", layout="wide")

st.title("RecallTracer — Graph-Based Recall Investigation & Incident Response")
st.caption("The scripted demo runs deterministically without LLM calls. Use the optional agent chat below to talk to the LangGraph agents directly in Streamlit; LangGraph Studio is not required.")


@st.cache_resource(show_spinner=False)
def get_chat_agent(agent_name):
    """Create and cache a LangGraph agent for the in-app chat."""
    import agents

    if agent_name == "investigator":
        return agents.investigator()
    if agent_name == "store_ops":
        return agents.store_ops()
    raise ValueError(f"Unsupported agent: {agent_name}")


def final_agent_message(result):
    """Return the final assistant response from a LangGraph agent result."""
    for message in reversed(result.get("messages", [])):
        if getattr(message, "type", None) != "ai" or getattr(message, "tool_calls", None):
            continue
        content = message.content
        if isinstance(content, str):
            return content
        return json.dumps(content, ensure_ascii=False)
    return ""


# Color Legend helper
def render_legend():
    cols = st.columns(6)
    cols[0].markdown(
        "<span style='color:#0e6655'>■</span> **Confirmed Lot** (`#0e6655`)", unsafe_allow_html=True)
    cols[1].markdown(
        "<span style='color:#6c3483'>■</span> **Inconclusive** (`#6c3483`)", unsafe_allow_html=True)
    cols[2].markdown(
        "<span style='color:#c0392b'>■</span> **Ruled Out / Notice** (`#c0392b`)", unsafe_allow_html=True)
    cols[3].markdown(
        "<span style='color:#e67e22'>■</span> **Mix Batch** (`#e67e22`)", unsafe_allow_html=True)
    cols[4].markdown(
        "<span style='color:#2980b9'>■</span> **Final Batch** (`#2980b9`)", unsafe_allow_html=True)
    cols[5].markdown(
        "<span style='color:#1e8449'>■</span> **Store / Associate** (`#1e8449`)", unsafe_allow_html=True)


# Presets Definitions
PRESET_HERO = json.dumps([
    {"store": "TH-01", "batch": "MP-2410-01",
        "text": "Severe food poisoning and hospitalization after eating masala peanuts"},
    {"store": "TH-02", "batch": "MP-2410-02",
        "text": "Severe vomiting and fever after eating masala peanuts"},
    {"store": "TH-03", "batch": "BH-2410-03",
        "text": "Hospitalized with severe food poisoning after eating bhujia in Pune"}
], indent=2)

PRESET_SALT = json.dumps([
    {"store": "TH-05", "batch": "NK-2410-01",
        "text": "Mild stomach discomfort from namkeen mix"},
    {"store": "TH-06", "batch": "NK-2410-02",
        "text": "Salty aftertaste in namkeen"},
    {"store": "TH-07", "batch": "NK-2410-03",
        "text": "Stomach irritation from namkeen"}
], indent=2)

PRESET_NOTICE = json.dumps({
    "type": "notice",
    "lot": "RX-7781",
    "supplier": "Extracto Labs",
    "material": "raw_extract",
    "reason": "microbial_contamination"
}, indent=2)

PRESET_FORWARD_TRACE = json.dumps({
    "type": "forward_trace",
    "lot": "GO-0611"
}, indent=2)

PRESET_TYPO = json.dumps({
    "type": "notice",
    "lot": "GN-22l4",
    "supplier": "AgroNuts Ltd",
    "material": "groundnut"
}, indent=2)

PRESET_MEMORY = json.dumps([
    {"store": "TH-03", "batch": "BH-2410-03",
        "text": "Severe food poisoning in Pune FC Road store"}
], indent=2)

# Session state initialization
if "draft" not in st.session_state:
    st.session_state.draft = PRESET_HERO
if "run_result" not in st.session_state:
    st.session_state.run_result = None
if "step_logs" not in st.session_state:
    st.session_state.step_logs = []

# Preset loader bar
st.subheader("1. Incident Input & Scenario Presets")
col1, col2, col3 = st.columns(3)
if col1.button("📋 Load Groundnut Oil Outbreak", key="btn_hero"):
    st.session_state.draft = PRESET_HERO
    st.session_state.run_result = None
if col2.button("🧂 Load Salt-Only Complaints", key="btn_salt"):
    st.session_state.draft = PRESET_SALT
    st.session_state.run_result = None
if col3.button("⚠️ Load Supplier Notice (RX-7781)", key="btn_notice"):
    st.session_state.draft = PRESET_NOTICE
    st.session_state.run_result = None

with st.expander("🔍 More Scenarios (Forward Trace, Typo Handling & Memory Replay)"):
    subcol1, subcol2, subcol3 = st.columns(3)
    if subcol1.button("🔤 Load Typo Lot (GN-22l4)", key="btn_typo"):
        st.session_state.draft = PRESET_TYPO
        st.session_state.run_result = None
    if subcol2.button("🧠 Load Memory Replay (Pune / BH-2410-03)", key="btn_memory"):
        st.session_state.draft = PRESET_MEMORY
        st.session_state.run_result = None
    if subcol3.button("➡️ Load Forward Trace (GO-0611)", key="btn_forward_trace"):
        st.session_state.draft = PRESET_FORWARD_TRACE
        st.session_state.run_result = None

draft_input = st.text_area(
    "Incident JSON Payload", height=180, key="draft")

# Action bar
run_btn = st.button("🚀 Run Graph Investigation", type="primary", key="btn_run")

if run_btn:
    try:
        payload = json.loads(draft_input)
    except Exception as e:
        st.error(f"Invalid JSON payload: {e}")
        payload = None

    if payload is not None:
        logs = []
        tools.STEP_COLLECTOR.set(logs)
        with st.spinner("Executing graph algorithms and cross-graph queries in FalkorDB..."):
            res = investigator.complaints_from(payload)
            # Automatic store_ops run if confirmed and not from memory
            ops_res = None
            if res.get("status") in {"confirmed", "closed"}:
                ops_res = store_ops.run()

        st.session_state.run_result = res
        st.session_state.step_logs = logs
        st.session_state.ops_res = ops_res

# Display Results
res = st.session_state.run_result
if res:
    st.divider()
    st.subheader("2. Investigation Outcome & Attribution")

    outcome = res.get("outcome")
    msg = res.get("message", "")
    confirmed_row = res.get("confirmed_row")

    # Guardrail check on message
    rows_for_guardrail = [confirmed_row] if confirmed_row else []
    safe_msg = tools.sentence_ok(
        msg,
        rows_for_guardrail,
        allow_list=[res["lot"]] if res.get("lot") else None,
    )

    if res.get("action") == "forward_trace":
        if outcome == "unknown_entity":
            st.warning(f"⚠️ {safe_msg}")
            if res.get("candidates"):
                st.info(f"Did you mean one of these existing lots? **{', '.join(res['candidates'])}**")
        elif outcome == "not_in_graph":
            st.info(f"ℹ️ {safe_msg}")
        else:
            st.success(f"➡️ **Forward Trace**: {safe_msg}")
    elif outcome == "from_memory":
        st.info(f"🧠 **Memory Recall**: {safe_msg}")
        if res.get("findings"):
            st.write("**Prior Findings Retrieved:**", res["findings"])
    elif res.get("checklist") and outcome == "not_in_graph":
        st.info(f"ℹ️ **No downstream exposure found**: {res.get('message', safe_msg)}")
    elif outcome in {"unknown_entity", "not_in_graph"}:
        st.warning(f"⚠️ {safe_msg}")
        if res.get("candidates"):
            st.info(
                f"Did you mean one of these existing lots? **{', '.join(res['candidates'])}**")
    else:
        st.success(f"🎯 **Attribution Result**: {safe_msg}")

    if res.get("action") == "forward_trace":
        st.markdown(f"### Downstream Trace for `{res.get('lot')}`")
        trace_rows = res.get("trace", {}).get("rows", [])
        if trace_rows:
            trace_row = trace_rows[0]
            st.write(f"**Stores reached:** {', '.join(sorted(set(trace_row.get('stores', [])))) or 'None'}")
            st.write(f"**Purchases found:** {trace_row.get('purchases', 0)}")
            batch_rows = trace_row.get("trace", [])
            if batch_rows:
                st.dataframe(
                    [{"Batch": row.get("id"), "Product": row.get("name")} for row in batch_rows],
                    use_container_width=True,
                )
        if res.get("graph_payload"):
            render_legend()
            graph_view.render_agraph(
                res["graph_payload"],
                height=520,
                width=1400,
                key="demo-forward-trace",
            )

    if res.get("checklist"):
        st.markdown("### Supplier Notice Checklist")
        st.dataframe([res["checklist"]], use_container_width=True)
        if res.get("graph_payload"):
            st.markdown("### Supplier Notice Context Graph")
            render_legend()
            graph_view.render_agraph(
                res["graph_payload"],
                height=420,
                width=1400,
                key="demo-notice-context",
            )

        if outcome == "not_in_graph":
            st.info(
                "No product batches or stores are downstream of this lot, so there is no product exposure to recall and no store pull task is dispatched."
            )

    # Ranking Visualizations & Table
    rank1 = res.get("rank1")
    rank2 = res.get("rank2")

    if rank1 or rank2:
        ranking_rows = (rank1 or {}).get("rows", []) + (rank2 or {}).get("rows", [])
        if outcome == "not_in_graph" and any(row.get("status") == "ruled_out" for row in ranking_rows):
            st.info(
                "No ingredient met the recall threshold. The shared candidate is ruled out for low specificity; no root cause is confirmed and no recall tasks are authorized."
            )

        st.markdown("### Graph Attribution Analysis")
        render_legend()

        tabs = st.tabs(["Depth 1 (Direct Ingredients)", "Depth 2 (Intermediate Mixes)"] if rank2 else [
                       "Depth 1 (Direct Ingredients)"])

        with tabs[0]:
            if rank1 and rank1.get("graph_payload"):
                graph_view.render_agraph(
                    rank1["graph_payload"],
                    height=520,
                    width=1400,
                    key="demo-candidate-depth-1",
                )
            st.markdown("#### Candidate Lot Rankings (Depth 1)")
            if rank1 and rank1.get("rows"):
                st.dataframe(rank1["rows"], use_container_width=True)

        if rank2 and len(tabs) > 1:
            with tabs[1]:
                if rank2.get("graph_payload"):
                    graph_view.render_agraph(
                        rank2["graph_payload"],
                        height=520,
                        width=1400,
                        key="demo-candidate-depth-2",
                    )
                st.markdown(
                    "#### Candidate Lot Rankings (Depth 2 — Multi-Hop Mix Attribution)")
                if rank2.get("rows"):
                    st.dataframe(rank2["rows"], use_container_width=True)

        # Human Confirmation Button directly beneath ranking
        inv_data = tools.load_investigation("INV-COMPLAINTS").get("rows", [])
        inv_status = inv_data[0].get("status") if inv_data else None

        if inv_status == "open":
            st.markdown("---")
            st.warning(
                "⚠️ Investigation status is currently **OPEN**. Human confirmation is required before store pull tasks can be dispatched.")
            if st.button("✅ Confirm Root Cause & Save Finding", type="primary", key="btn_confirm"):
                conf_res = investigator.confirm()
                st.success(conf_res.get("message"))
                # Automatically run store_ops
                st.session_state.ops_res = store_ops.run()
                st.rerun()

    # Store Operations & Shelves Block
    inv_data = tools.load_investigation("INV-COMPLAINTS").get("rows", [])
    current_status = inv_data[0].get("status") if inv_data else None

    if current_status in {"confirmed", "closed"}:
        st.divider()
        st.subheader("3. Store Operations & Shelf Pull Visualizer")
        render_legend()

        shelf_data = tools.shelf_view("INV-COMPLAINTS")
        if shelf_data.get("graph_payload"):
            graph_view.render_agraph(
                shelf_data["graph_payload"],
                height=820,
                width=1400,
                key="demo-shelf-view",
            )

        # Dispatched tasks
        tasks = tools.tasks_for("INV-COMPLAINTS").get("rows", [])
        if tasks:
            st.markdown(f"#### Active Dispatched Tasks ({len(tasks)} Stores)")
            tcols = st.columns(min(len(tasks), 4))
            for idx, task in enumerate(tasks):
                col_idx = idx % len(tcols)
                with tcols[col_idx]:
                    st.markdown(f"**Task ID**: `{task.get('id')}`")
                    st.write(f"🏢 **Store**: {task.get('store')}")
                    st.write(f"📍 **Location**: {task.get('location_code')}")
                    st.write(f"👤 **Assignee**: {task.get('assignee_name')}")
                    st.write(
                        f"📦 **Batch**: `{task.get('batch')}` ({task.get('qty')} units)")
                    st.write(f"⏰ **Due By**: {task.get('due_by')}")
                    st.write(f"Status: **{task.get('status').upper()}**")
                    if task.get("status") != "done":
                        if st.button(f"Mark Done", key=f"btn_done_{task.get('id')}"):
                            tools.mark_done(task.get("id"))
                            st.success(
                                f"Task {task.get('id')} marked as done!")
                            st.rerun()

st.divider()
st.subheader("4. Optional LangGraph Agent Chat")
st.caption("Choose an agent and send a message here. The scripted controls above do not use an LLM; agent chat requires the model configured in `.env` to be available.")

agent_name = st.selectbox(
    "Agent",
    options=["investigator", "store_ops"],
    format_func=lambda name: "Investigator" if name == "investigator" else "Store Operations",
    key="chat_agent_name",
)
chat_state_key = f"agent_chat_{agent_name}"
if chat_state_key not in st.session_state:
    st.session_state[chat_state_key] = []

for chat_message in st.session_state[chat_state_key]:
    with st.chat_message(chat_message["role"]):
        st.markdown(chat_message["content"])

chat_prompt = st.chat_input("Message the selected RecallTracer agent")
if chat_prompt:
    if agent_name == "investigator":
        st.session_state.chat_investigation_status = None
        st.session_state.chat_investigation_lot = ""
    conversation = st.session_state[chat_state_key] + [
        {"role": "user", "content": chat_prompt}
    ]
    try:
        chat_agent = get_chat_agent(agent_name)
    except RuntimeError as exc:
        st.error(f"Could not start the agent: {exc}")
    else:
        with st.spinner(f"{agent_name.replace('_', ' ').title()} agent is working..."):
            response = chat_agent.invoke({"messages": conversation})

        answer = final_agent_message(response)
        if not answer:
            st.error("The agent returned no final response.")
        else:
            st.session_state[chat_state_key] = conversation + [
                {"role": "assistant", "content": answer}
            ]
            st.rerun()

if agent_name == "investigator":
    st.caption("For an open complaint investigation, refresh its status below and confirm it here before asking Store Operations to dispatch tasks.")
    if st.button("Refresh complaint investigation status", key="refresh_chat_investigation"):
        investigation = tools.load_investigation(
            "INV-COMPLAINTS").get("rows", [])
        st.session_state.chat_investigation_status = (
            investigation[0].get("status") if investigation else "not found"
        )
        st.session_state.chat_investigation_lot = (
            investigation[0].get("lot_id") if investigation else ""
        )

    investigation_status = st.session_state.get("chat_investigation_status")
    if investigation_status:
        st.write(
            f"Complaint investigation: **{investigation_status}**"
            + (
                f" — lot `{st.session_state.get('chat_investigation_lot')}`"
                if st.session_state.get("chat_investigation_lot")
                else ""
            )
        )
    if investigation_status == "open":
        if st.button("Confirm root cause and save finding", type="primary", key="chat_confirm"):
            confirmation = investigator.confirm()
            st.session_state.chat_investigation_status = confirmation.get(
                "status")
            if confirmation.get("status") == "confirmed":
                st.success(confirmation.get("message"))
            else:
                st.warning(confirmation.get("message"))

# Tool Trace Table Expander
with st.expander("🛠️ Tool Execution Trace (Telemetry & Timing)"):
    logs = st.session_state.get("step_logs", [])
    if logs:
        trace_table = []
        for l in logs:
            tr = l.get("trace", {})
            trace_table.append({
                "Tool": tr.get("tool"),
                "Outcome": l.get("outcome"),
                "Rows": tr.get("n_rows"),
                "Execution (ms)": tr.get("ms"),
                "Arguments": json.dumps(tr.get("args", {}))
            })
        st.dataframe(trace_table, use_container_width=True)
    else:
        st.write("No execution trace logs in session yet.")
