"""Shared Streamlit chat UI for RecallTracer's LangGraph agents."""

import json
from typing import Any, Dict

import streamlit as st

import investigator
import tools


@st.cache_resource(show_spinner=False)
def _get_agent(agent_name: str) -> Any:
    import agents

    if agent_name == "investigator":
        return agents.investigator()
    if agent_name == "store_ops":
        return agents.store_ops()
    raise ValueError(f"Unsupported agent: {agent_name}")


def _final_message(result: Dict[str, Any]) -> str:
    for message in reversed(result.get("messages", [])):
        if getattr(message, "type", None) != "ai" or getattr(message, "tool_calls", None):
            continue
        content = message.content
        if isinstance(content, str):
            return content
        return json.dumps(content, ensure_ascii=False)
    return ""


def render_agent_chat(title: str = "LangGraph Agent Chat") -> None:
    st.divider()
    st.subheader(title)
    st.caption(
        "Select an agent and chat here. Agent chat uses the model configured in `.env`; "
        "you do not need to open LangGraph Studio."
    )

    agent_name = st.selectbox(
        "Agent",
        options=["investigator", "store_ops"],
        format_func=lambda name: (
            "Investigator" if name == "investigator" else "Store Operations"
        ),
        key="chat_agent_name",
    )
    history_key = f"agent_chat_{agent_name}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    for message in st.session_state[history_key]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Message the selected RecallTracer agent")
    if prompt:
        if agent_name == "investigator":
            st.session_state.chat_investigation_status = None
            st.session_state.chat_investigation_lot = ""
        conversation = st.session_state[history_key] + [
            {"role": "user", "content": prompt}
        ]
        try:
            agent = _get_agent(agent_name)
        except RuntimeError as exc:
            st.error(f"Could not start the agent: {exc}")
        else:
            with st.spinner(f"{agent_name.replace('_', ' ').title()} agent is working..."):
                result = agent.invoke({"messages": conversation})

            answer = _final_message(result)
            if not answer:
                st.error("The agent returned no final response.")
            else:
                st.session_state[history_key] = conversation + [
                    {"role": "assistant", "content": answer}
                ]
                st.rerun()

    if agent_name == "investigator":
        st.caption(
            "For an open complaint investigation, refresh its status and confirm it "
            "here before asking Store Operations to dispatch tasks."
        )
        if st.button(
            "Refresh complaint investigation status",
            key="refresh_chat_investigation",
        ):
            investigation = tools.load_investigation("INV-COMPLAINTS").get("rows", [])
            st.session_state.chat_investigation_status = (
                investigation[0].get("status") if investigation else "not found"
            )
            st.session_state.chat_investigation_lot = (
                investigation[0].get("lot_id") if investigation else ""
            )

        status = st.session_state.get("chat_investigation_status")
        if status:
            lot = st.session_state.get("chat_investigation_lot")
            st.write(
                f"Complaint investigation: **{status}**"
                + (f" — lot `{lot}`" if lot else "")
            )
        if status == "open":
            if st.button(
                "Confirm root cause and save finding",
                type="primary",
                key="chat_confirm",
            ):
                confirmation = investigator.confirm()
                st.session_state.chat_investigation_status = confirmation.get("status")
                if confirmation.get("status") == "confirmed":
                    st.success(confirmation.get("message"))
                else:
                    st.warning(confirmation.get("message"))
