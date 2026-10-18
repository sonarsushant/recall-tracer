"""RecallTracer agent chat and live graph companion UI (Port 8502)."""

import streamlit as st
import tools
import investigator
import graph_view
import agent_chat

# Page Config
st.set_page_config(page_title="RecallTracer — Agent Companion Data UI", layout="wide")

st.title("RecallTracer — Live Agent Companion UI")
st.caption("Chat with the Investigator or Store Operations agent here and inspect the live graph below. LangGraph Studio is optional.")
agent_chat.render_agent_chat("RecallTracer Agent Chat")

col_ref, _ = st.columns([1, 6])
if col_ref.button("🔄 Refresh Graph State", type="primary"):
    st.rerun()

# Color Legend helper
def render_legend():
    cols = st.columns(6)
    cols[0].markdown("<span style='color:#0e6655'>■</span> **Confirmed Lot** (`#0e6655`)", unsafe_allow_html=True)
    cols[1].markdown("<span style='color:#6c3483'>■</span> **Inconclusive** (`#6c3483`)", unsafe_allow_html=True)
    cols[2].markdown("<span style='color:#c0392b'>■</span> **Ruled Out / Notice** (`#c0392b`)", unsafe_allow_html=True)
    cols[3].markdown("<span style='color:#e67e22'>■</span> **Mix Batch** (`#e67e22`)", unsafe_allow_html=True)
    cols[4].markdown("<span style='color:#2980b9'>■</span> **Final Batch** (`#2980b9`)", unsafe_allow_html=True)
    cols[5].markdown("<span style='color:#1e8449'>■</span> **Store / Associate** (`#1e8449`)", unsafe_allow_html=True)


st.subheader("Quick Forward Trace")
trace_col, trace_button_col = st.columns([4, 1])
trace_lot = trace_col.text_input("Ingredient lot ID", value="GO-0611", key="quick_trace_lot")
if trace_button_col.button("Trace lot", key="quick_trace_button"):
    st.session_state.quick_trace_result = investigator.forward_trace_lot({"lot": trace_lot})

quick_trace = st.session_state.get("quick_trace_result")
if quick_trace:
    if quick_trace.get("outcome") == "unknown_entity":
        st.warning(quick_trace.get("message"))
        if quick_trace.get("candidates"):
            st.caption(f"Did you mean: {', '.join(quick_trace['candidates'])}?")
    elif quick_trace.get("outcome") == "not_in_graph":
        st.info(quick_trace.get("message"))
    else:
        st.success(quick_trace.get("message"))

    trace_result = quick_trace.get("trace", {}).get("rows", [])
    if trace_result:
        trace_row = trace_result[0]
        st.write(f"**Stores reached:** {', '.join(sorted(set(trace_row.get('stores', [])))) or 'None'}")
        st.write(f"**Purchases found:** {trace_row.get('purchases', 0)}")
        if trace_row.get("trace"):
            st.dataframe(
                [{"Batch": row.get("id"), "Product": row.get("name")} for row in trace_row["trace"]],
                use_container_width=True,
            )

    if quick_trace.get("graph_payload"):
        render_legend()
        graph_view.render_agraph(
            quick_trace["graph_payload"],
            height=520,
            width=1400,
            key="agent-quick-forward-trace",
        )

# Fetch Current Graph State
complaints = tools._run_query("bazaarmart", "complaints")
inv_complaints_res = tools.load_investigation("INV-COMPLAINTS")
inv_notice_res = tools.load_investigation("INV-NOTICE")

inv_c = inv_complaints_res["rows"][0] if inv_complaints_res["rows"] else None
inv_n = inv_notice_res["rows"][0] if inv_notice_res["rows"] else None

has_complaints = len(complaints) > 0
has_active_notice = inv_n and inv_n.get("lot_id")

if not has_complaints and not has_active_notice:
    st.info("The database has no active complaints or notice. Submit a complaint list or supplier notice in the Investigator chat above, then refresh the graph state.")
else:
    # --------------------------------------------------------------------------
    # 1. COMPLAINT & ATTRIBUTION SECTION
    # --------------------------------------------------------------------------
    if has_complaints:
        st.subheader("1. Active Incident Complaints & Upstream Attribution")
        st.markdown(f"**Recorded Complaints in BazaarMart:** {len(complaints)} items")
        st.dataframe(complaints, use_container_width=True)

        batch_ids = list({c["batch"] for c in complaints})
        res_upstream = tools.lots_behind(batch_ids)
        upstream_lots = list({r.get("lot") for r in res_upstream["rows"] if r.get("lot")})

        # Check organizational memory
        memory_found = False
        memory_lot = None
        for l in upstream_lots:
            mem_res = tools.recall_findings(l)
            if mem_res["outcome"] == "from_memory":
                memory_found = True
                memory_lot = l
                st.info(f"🧠 **Organizational Memory Match**: Lot `{l}` was previously confirmed as a contaminated root cause.")
                st.dataframe(mem_res["rows"], use_container_width=True)
                break

        if memory_found:
            st.markdown("#### Upstream Trace Graph (from Memory)")
            render_legend()
            if res_upstream.get("graph_payload"):
                graph_view.render_agraph(
                    res_upstream["graph_payload"],
                    height=520,
                    width=1400,
                    key="agent-memory-upstream",
                )
        else:
            # Graph Ranking
            st.markdown("#### Candidate Lot Attribution")
            render_legend()

            r1 = tools.rank_lots(depth=1)
            confirmed_in_r1 = any(r.get("status") == "confirmed" for r in r1.get("rows", []))

            r2 = None
            if not confirmed_in_r1:
                r2 = tools.rank_lots(depth=2)

            tabs = st.tabs(["Depth 1 (Direct Ingredients)", "Depth 2 (Intermediate Mixes)"] if r2 else ["Depth 1 (Direct Ingredients)"])
            with tabs[0]:
                if r1.get("graph_payload"):
                    graph_view.render_agraph(
                        r1["graph_payload"],
                        height=520,
                        width=1400,
                        key="agent-candidate-depth-1",
                    )
                st.dataframe(r1.get("rows", []), use_container_width=True)

            if r2 and len(tabs) > 1:
                with tabs[1]:
                    if r2.get("graph_payload"):
                        graph_view.render_agraph(
                            r2["graph_payload"],
                            height=520,
                            width=1400,
                            key="agent-candidate-depth-2",
                        )
                    st.dataframe(r2.get("rows", []), use_container_width=True)

            ranked_rows = r1.get("rows", []) + (r2.get("rows", []) if r2 else [])
            if (
                not any(row.get("status") == "confirmed" for row in ranked_rows)
                and any(row.get("status") == "ruled_out" for row in ranked_rows)
            ):
                st.info(
                    "No ingredient met the recall threshold. The shared candidate is ruled out for low specificity; no root cause is confirmed and no recall tasks are authorized."
                )

        # ----------------------------------------------------------------------
        # Human Confirmation Button
        # ----------------------------------------------------------------------
        if inv_c and inv_c.get("status") == "open" and inv_c.get("lot_id"):
            st.markdown("---")
            st.warning(f"⚠️ Investigation for lot **{inv_c.get('lot_id')}** is **OPEN**. Human confirmation is required before store pull dispatch.")
            if st.button(f"🛡️ Confirm Class I Recall for {inv_c.get('lot_id')}", type="primary"):
                c_res = investigator.confirm()
                st.success(c_res.get("message"))
                st.rerun()

        # ----------------------------------------------------------------------
        # Shelf View & Task Monitor
        # ----------------------------------------------------------------------
        if inv_c and inv_c.get("status") in {"confirmed", "closed"}:
            st.divider()
            st.subheader("2. Store Shelves & Pull Task Coordination")
            render_legend()

            shelf_view_data = tools.shelf_view("INV-COMPLAINTS")
            if shelf_view_data.get("graph_payload"):
                graph_view.render_agraph(
                    shelf_view_data["graph_payload"],
                    height=820,
                    width=1400,
                    key="agent-shelf-view",
                )

            tasks = tools.tasks_for("INV-COMPLAINTS").get("rows", [])
            if not tasks:
                st.info("Select **Store Operations** in the agent chat above and ask it to pull the confirmed lot, then refresh the graph state.")
            else:
                st.markdown(f"#### Active Dispatched Tasks ({len(tasks)} Stores)")
                cols = st.columns(min(len(tasks), 4))
                for idx, t in enumerate(tasks):
                    with cols[idx % len(cols)]:
                        st.markdown(f"**Task**: `{t.get('id')}`")
                        st.write(f"🏢 Store: **{t.get('store')}**")
                        st.write(f"📍 Location: **{t.get('location_code')}**")
                        st.write(f"👤 Associate: **{t.get('assignee_name')}**")
                        st.write(f"📦 Batch: `{t.get('batch')}` ({t.get('qty')} units)")
                        st.write(f"⏰ Due: {t.get('due_by')}")
                        st.write(f"Status: `{t.get('status').upper()}`")
                        if t.get("status") != "done":
                            if st.button("Mark Done", key=f"agent_done_{t.get('id')}"):
                                tools.mark_done(t.get("id"))
                                st.rerun()

    # --------------------------------------------------------------------------
    # 2. SUPPLIER RECALL NOTICE SECTION
    # --------------------------------------------------------------------------
    if has_active_notice:
        st.divider()
        st.subheader("Supplier Notice Context & Exposure")
        lot_id = inv_n.get("lot_id")
        n_ctx = tools.notice_context(lot_id)
        checklist = n_ctx.get("rows", [{}])[0]
        notice_status = inv_n.get("status", "unknown")
        if checklist.get("used_in_a_product"):
            st.info(
                f"Notice investigation status: **{notice_status}**. The lot has downstream product use; review its trace and shelf exposure before acting."
            )
        else:
            st.info(
                f"Notice investigation status: **{notice_status}**. The graph shows the supplier and notice linked to `{lot_id}`, with no outgoing product-use links; no store recall tasks are needed."
            )

        if n_ctx.get("graph_payload"):
            graph_view.render_agraph(
                n_ctx["graph_payload"],
                height=400,
                width=1400,
                key="agent-notice-context",
            )
        st.markdown("#### Supplier Notice Checklist")
        st.dataframe([checklist], use_container_width=True)
