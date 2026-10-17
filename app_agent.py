"""
app_agent.py - RecallTracer Agent Companion Data UI (Port 8502).
Paired with LangGraph Studio. No JSON text area and no LLM calls.
Reads live FalkorDB state and provides one-click human confirmation and visual graph inspection.
"""

import streamlit as st
import tools
import investigator
import graph_view

# Page Config
st.set_page_config(page_title="RecallTracer — Agent Companion Data UI", layout="wide")

st.title("RecallTracer — Live Agent Companion UI")
st.caption("🤖 Paired with LangGraph Studio. Run the `investigator` or `store_ops` graph in LangGraph Studio, then click **Refresh** below to inspect live graph state.")

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

# Fetch Current Graph State
complaints = tools._run_query("bazaarmart", "complaints")
inv_complaints_res = tools.load_investigation("INV-COMPLAINTS")
inv_notice_res = tools.load_investigation("INV-NOTICE")

inv_c = inv_complaints_res["rows"][0] if inv_complaints_res["rows"] else None
inv_n = inv_notice_res["rows"][0] if inv_notice_res["rows"] else None

has_complaints = len(complaints) > 0
has_active_notice = inv_n and inv_n.get("lot_id")

if not has_complaints and not has_active_notice:
    st.info("ℹ️ The database currently has neither active complaints nor an active notice. Send a complaint list or supplier notice payload in LangGraph Studio, then refresh.")
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
                graph_view.render_agraph(res_upstream["graph_payload"], height=520, width=1400)
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
                    graph_view.render_agraph(r1["graph_payload"], height=520, width=1400)
                st.dataframe(r1.get("rows", []), use_container_width=True)

            if r2 and len(tabs) > 1:
                with tabs[1]:
                    if r2.get("graph_payload"):
                        graph_view.render_agraph(r2["graph_payload"], height=520, width=1400)
                    st.dataframe(r2.get("rows", []), use_container_width=True)

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
                graph_view.render_agraph(shelf_view_data["graph_payload"], height=820, width=1400)

            tasks = tools.tasks_for("INV-COMPLAINTS").get("rows", [])
            if not tasks:
                st.info("💡 **Next Step**: Run `store_ops` agent in LangGraph Studio (e.g. prompt: *'Pull the confirmed lot'*), then click **Refresh** above to view the dispatched tasks.")
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
        if n_ctx.get("graph_payload"):
            graph_view.render_agraph(n_ctx["graph_payload"], height=400, width=1400)
        st.markdown("#### Supplier Notice Checklist")
        st.json(n_ctx.get("rows", [{}])[0])
