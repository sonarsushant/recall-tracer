"""
investigator.py - Deterministic scripted investigator workflow + human confirm().
Follows all rules and branching paths specified in Section 5.1.
"""

import json
from typing import Any, Dict, List, Optional, Union

import tools


def forward_trace_lot(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve and visualize a lot's downstream batch and product exposure."""
    lot = payload.get("lot") or payload.get("lot_id") or ""
    resolved = tools.resolve_lot(lot)
    if resolved["outcome"] == "unknown_entity":
        candidates = [row.get("candidate") for row in resolved["rows"] if row.get("candidate")]
        return {
            "outcome": "unknown_entity",
            "action": "forward_trace",
            "message": f"Unknown lot '{lot}'. Did you mean: {', '.join(candidates)}?",
            "candidates": candidates,
            "steps": [resolved]
        }

    trace = tools.forward_trace(lot)
    if trace["outcome"] == "not_in_graph":
        message = f"No downstream finished batches or store exposure were found for lot {lot}."
    else:
        trace_row = trace["rows"][0]
        message = (
            f"Lot {lot} reaches {len(trace_row['batches'])} finished batches "
            f"across {len(set(trace_row['stores']))} stores."
        )

    return {
        "outcome": trace["outcome"],
        "action": "forward_trace",
        "lot": lot,
        "message": message,
        "trace": trace,
        "graph_payload": trace["graph_payload"],
        "steps": [resolved, trace]
    }


def notice(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Supplier Notice path:
    1. Call resolve_lot(lot). If outcome == 'unknown_entity', name the closest lot IDs and stop.
    2. Call notice_context with issued_by, material, reason.
    3. If outcome == 'not_in_graph' (e.g. used_in == 0), write INV-NOTICE status='no_link' and stop.
    4. Otherwise run forward_trace(lot).
    """
    lot = payload.get("lot") or payload.get("lot_id") or ""
    issued_by = payload.get("issued_by") or payload.get("supplier")
    material = payload.get("material")
    reason = payload.get("reason")

    # Step 1: Resolve lot
    res_resolve = tools.resolve_lot(lot)
    if res_resolve["outcome"] == "unknown_entity":
        candidates = [r.get("candidate") for r in res_resolve["rows"] if r.get("candidate")]
        msg = f"Unknown lot '{lot}'. Did you mean: {', '.join(candidates)}?"
        return {
            "outcome": "unknown_entity",
            "message": msg,
            "candidates": candidates,
            "steps": [res_resolve]
        }

    # Step 2: Notice context
    res_context = tools.notice_context(lot, issued_by=issued_by, material=material, reason=reason)
    steps = [res_resolve, res_context]

    # Step 3: Check if not in graph (used_in == 0)
    if res_context["outcome"] == "not_in_graph":
        tools.write_investigation(
            case="notice",
            status="no_link",
            summary=f"Supplier notice for {lot} has no active product or store exposure.",
            lot_id=lot
        )
        return {
            "outcome": "not_in_graph",
            "message": f"Supplier notice for {lot} resolved with zero downstream usage. Investigation set to no_link.",
            "steps": steps,
            "checklist": res_context["rows"][0] if res_context["rows"] else {},
            "graph_payload": res_context["graph_payload"]
        }

    # Step 4: Forward trace
    res_trace = tools.forward_trace(lot)
    steps.append(res_trace)

    tools.write_investigation(
        case="notice",
        status="open",
        summary=f"Active recall notice for {lot} with downstream batches.",
        lot_id=lot,
        batch_ids=",".join(res_trace["rows"][0].get("batches", [])) if res_trace["rows"] else ""
    )

    return {
        "outcome": "answered",
        "message": f"Active recall notice for lot {lot} traced to stores and inventory.",
        "steps": steps,
        "trace": res_trace,
        "checklist": res_context["rows"][0] if res_context["rows"] else {},
        "graph_payload": res_context["graph_payload"]
    }


def complaints_from(payload: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Entry point for complaints investigation.
    Routes to notice() if payload contains notice information.
    Routes forward-trace and notice actions to their dedicated workflows.
    Otherwise executes the complaint attribution workflow.
    """
    if isinstance(payload, dict):
        if payload.get("type") == "forward_trace" or payload.get("action") == "forward_trace":
            return forward_trace_lot(payload)
        if payload.get("notice") or payload.get("type") == "notice" or "reason" in payload or "issued_by" in payload:
            return notice(payload)
        items = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        return {"outcome": "unknown_entity", "message": "Invalid complaint payload"}

    # 1. Record complaints
    res_record = tools.record_complaints(items)
    if res_record["outcome"] != "answered":
        return {
            "outcome": res_record["outcome"],
            "message": "Complaint validation failed. Store or batch reference not recognized.",
            "steps": [res_record]
        }

    recorded_batches = list({item.get("batch") or item.get("batch_id") for item in items if item.get("batch") or item.get("batch_id")})

    # 2. Upstream lots behind recorded batches
    res_upstream = tools.lots_behind(recorded_batches)
    upstream_lots = list({r.get("lot") for r in res_upstream["rows"] if r.get("lot")})
    steps = [res_record, res_upstream]

    # 3. Memory check: recall findings for each upstream lot
    for lot_id in upstream_lots:
        res_mem = tools.recall_findings(lot_id)
        if res_mem["outcome"] == "from_memory":
            steps.append(res_mem)
            tools.write_investigation(
                case="complaints",
                status="confirmed",
                summary=f"Attributed to previously confirmed lot {lot_id} from incident memory.",
                lot_id=lot_id,
                batch_ids=",".join(recorded_batches)
            )
            return {
                "outcome": "from_memory",
                "message": f"Identified confirmed root cause {lot_id} directly from memory. Skipping graph ranking.",
                "lot": lot_id,
                "findings": res_mem["rows"],
                "steps": steps,
                "graph_payload": res_upstream["graph_payload"]
            }

    # 4. Script complaints ranking
    # Try Depth 1
    res_rank1 = tools.rank_lots(depth=1)
    steps.append(res_rank1)

    confirmed_row = None
    inconclusive_exists = False

    for row in res_rank1["rows"]:
        if row.get("status") == "confirmed":
            confirmed_row = row
            break
        elif row.get("status") == "inconclusive":
            inconclusive_exists = True

    # If nothing confirmed at depth 1, try Depth 2 if inconclusive exists
    res_rank2 = None
    if not confirmed_row and inconclusive_exists:
        res_rank2 = tools.rank_lots(depth=2)
        steps.append(res_rank2)
        for row in res_rank2["rows"]:
            if row.get("status") == "confirmed":
                confirmed_row = row
                break

    # If still nothing confirmed, close investigation with no_link
    if not confirmed_row:
        tools.write_investigation(
            case="complaints",
            status="no_link",
            summary="No common root cause ingredient confirmed across reported complaints.",
            lot_id=""
        )
        return {
            "outcome": "not_in_graph",
            "message": "Investigation inconclusive. No single ingredient lot confirmed.",
            "steps": steps,
            "rank1": res_rank1,
            "rank2": res_rank2
        }

    # 5. Follow-up on confirmed lot
    lot = confirmed_row["lot"]
    res_trace = tools.forward_trace(lot)
    steps.append(res_trace)

    delivered_stores = res_trace["rows"][0].get("stores", []) if res_trace["rows"] else []
    final_batches = res_trace["rows"][0].get("batches", []) if res_trace["rows"] else []

    res_routes = tools.exposure_routes(from_stores=delivered_stores)
    steps.append(res_routes)

    res_illness = tools.illness()
    steps.append(res_illness)

    cov = confirmed_row.get("coverage", 1.0)
    summary_sentence = f"Root cause lot {lot} confirmed with coverage {cov} and score {confirmed_row.get('score')} across complaint stores."

    tools.write_investigation(
        case="complaints",
        status="open",
        summary=summary_sentence,
        lot_id=lot,
        batch_ids=",".join(final_batches)
    )

    return {
        "outcome": "answered",
        "lot": lot,
        "status": "open",
        "confirmed_row": confirmed_row,
        "message": summary_sentence,
        "steps": steps,
        "rank1": res_rank1,
        "rank2": res_rank2,
        "trace": res_trace,
        "illness": res_illness,
        "graph_payload": res_rank2["graph_payload"] if res_rank2 else res_rank1["graph_payload"]
    }


def confirm() -> Dict[str, Any]:
    """
    Human confirmation action (triggered ONLY by UI Confirm button).
    Loads INV-COMPLAINTS. If status == 'open', calls save_finding and updates status to 'confirmed'.
    """
    inv_res = tools.load_investigation("INV-COMPLAINTS")
    if not inv_res["rows"]:
        return {"status": "error", "message": "No active investigation found."}

    inv = inv_res["rows"][0]
    status = inv.get("status")
    lot_id = inv.get("lot_id", "")
    batch_str = inv.get("batch_ids", "")
    batches = [b.strip() for b in batch_str.split(",") if b.strip()]

    if status != "open":
        existing_tasks = tools.tasks_for("INV-COMPLAINTS")["rows"]
        task_names = [t.get("id") for t in existing_tasks]
        if task_names:
            return {
                "status": status,
                "message": f"Investigation is already {status}. Active tasks: {', '.join(task_names)}"
            }
        return {
            "status": status,
            "message": f"Investigation status is '{status}'. Only 'open' investigations can be confirmed."
        }

    finding_text = f"Confirmed root cause {lot_id} responsible for product recall incident."
    tools.save_finding(lot=lot_id, batch_ids=batches, text=finding_text)

    tools.write_investigation(
        case="complaints",
        status="confirmed",
        summary=inv.get("summary", ""),
        lot_id=lot_id,
        batch_ids=batch_str
    )

    return {
        "status": "confirmed",
        "lot_id": lot_id,
        "message": f"Confirmed root cause {lot_id} and saved to organizational memory."
    }
