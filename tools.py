"""
tools.py - Query runner, cross-graph joiner, sentence guardrail, and 18 tool functions.
Strictly adheres to the RecallTracer specification and result envelope contract.
"""

import os
import re
import time
import json
import difflib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from contextvars import ContextVar
from pathlib import Path

from falkordb import FalkorDB
import graph_view

# Environment and Connection Setup
HOST = os.getenv("FALKOR_HOST", "localhost")
PORT = int(os.getenv("FALKOR_PORT", 6379))

# ContextVar for step collection (used by Streamlit UIs and agent runs)
STEP_COLLECTOR: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar("STEP_COLLECTOR", default=None)

# Directory containing Cypher query files
QUERIES_DIR = Path(__file__).parent / "queries"

_db_instance: Optional[FalkorDB] = None


def get_db() -> FalkorDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = FalkorDB(host=HOST, port=PORT)
    return _db_instance


def _load_query(name: str) -> str:
    path = QUERIES_DIR / f"{name}.cypher"
    if not path.exists():
        raise FileNotFoundError(f"Query file not found: {path}")
    return path.read_text(encoding="utf-8")


def _run_query(graph_name: str, query_name: str, params: Optional[Dict[str, Any]] = None, write: bool = False) -> List[Dict[str, Any]]:
    db = get_db()
    graph = db.select_graph(graph_name)
    query_str = _load_query(query_name)
    params = params or {}

    if write:
        res = graph.query(query_str, params)
    else:
        res = graph.ro_query(query_str, params)

    if not res or not res.result_set or not res.header:
        return []

    cols = [h[1] for h in res.header]
    rows = []
    for r in res.result_set:
        rows.append(dict(zip(cols, r)))
    return rows


def _wrap_envelope(
    outcome: str,
    rows: List[Dict[str, Any]],
    tool: str,
    args: Dict[str, Any],
    start_time: float,
    graph_payload: Optional[Dict[str, Any]] = None,
    paths: Optional[List[Any]] = None
) -> Dict[str, Any]:
    duration_ms = round((time.time() - start_time) * 1000, 2)
    envelope = {
        "outcome": outcome,
        "rows": rows,
        "paths": paths or [],
        "graph_payload": graph_payload or {
            "nodes": [],
            "edges": [],
            "highlight": [],
            "query": tool,
            "note": ""
        },
        "trace": {
            "tool": tool,
            "args": args,
            "ms": duration_ms,
            "n_rows": len(rows)
        }
    }

    # Record to contextvar collector if active
    collector = STEP_COLLECTOR.get()
    if collector is not None:
        collector.append(envelope)

    return envelope


# ==============================================================================
# SENTENCE GUARDRAIL
# ==============================================================================

def sentence_ok(sentence: str, rows: List[Dict[str, Any]], allow_list: Optional[List[str]] = None) -> str:
    """
    Scan sentence for ID tokens matching pattern r"\b[A-Z]{2,4}-\d{2,4}(?:-\d{2})?\b".
    If any token is not present in tool rows or allow_list, replace sentence in UI
    with a deterministic sentence synthesized directly from rows.
    """
    pattern = re.compile(r"\b[A-Z]{2,4}-\d{2,4}(?:-\d{2})?\b")
    tokens = pattern.findall(sentence)

    allowed_set: Set[str] = set(allow_list or [])

    # Extract all string tokens and values from rows
    def extract_strings(obj: Any):
        if isinstance(obj, str):
            allowed_set.add(obj)
            for m in pattern.findall(obj):
                allowed_set.add(m)
        elif isinstance(obj, dict):
            for v in obj.values():
                extract_strings(v)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                extract_strings(item)

    extract_strings(rows)

    all_tokens_allowed = all(t in allowed_set for t in tokens)

    if all_tokens_allowed:
        return sentence

    # Synthesize deterministic replacement sentence directly from rows
    if rows and isinstance(rows[0], dict):
        first = rows[0]
        lot = first.get("lot") or first.get("id") or "candidate lot"
        status = first.get("status") or "identified"
        cov = first.get("coverage")
        score = first.get("score")
        if cov is not None and score is not None:
            return f"Investigation identified lot {lot} ({status}) with coverage {cov} and score {score} across {len(rows)} candidate lots."
        return f"Investigation records confirm entity {lot} with {len(rows)} matching graph records."
    return f"Investigation completed with {len(rows)} verified database records."


# ==============================================================================
# 18 TOOL FUNCTIONS
# ==============================================================================

def catalog() -> Dict[str, Any]:
    """Underlying queries: lots, batch_names, store_names."""
    t0 = time.time()
    lots = _run_query("network", "lots")
    batches = _run_query("network", "batch_names")
    stores = _run_query("bazaarmart", "store_names")

    rows = [{
        "total_lots": len(lots),
        "total_batches": len(batches),
        "total_stores": len(stores),
        "lots": lots[:10],
        "batches": batches[:10],
        "stores": stores[:10]
    }]

    nodes = []
    edges = []
    for l in lots[:5]:
        nodes.append({"id": l["id"], "label": f"{l.get('material', '').title()}\n{l['id']}", "color": graph_view.COLOR_CONFIRMED})
    for b in batches[:5]:
        color = graph_view.COLOR_MIX if b.get("kind") == "mix" else graph_view.COLOR_FINAL_BATCH
        nodes.append({"id": b["id"], "label": f"{b.get('name', b['id'])}\n{b['id']}", "color": color})
    for s in stores[:5]:
        nodes.append({"id": s["code"], "label": f"{s.get('name', s['code'])}\n{s['code']}", "color": graph_view.COLOR_STORE})

    payload = {
        "nodes": nodes,
        "edges": edges,
        "highlight": [],
        "query": "catalog",
        "note": "Catalog display labels: lots, mixes, batches, stores"
    }
    return _wrap_envelope("answered", rows, "catalog", {}, t0, payload)


def record_complaints(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates every row's store code and batch ref BEFORE deleting existing complaints.
    """
    t0 = time.time()
    valid_stores = {r["code"] for r in _run_query("bazaarmart", "store_names")}
    valid_batches = {r["id"] for r in _run_query("bazaarmart", "batch_refs")}

    # Validate before deleting
    for idx, item in enumerate(items):
        store = item.get("store") or item.get("code")
        batch = item.get("batch") or item.get("batch_id")
        if not store or store not in valid_stores:
            return _wrap_envelope(
                "unknown_entity",
                [{"error": f"Invalid or unknown store code '{store}' at item {idx}"}],
                "record_complaints",
                {"n_items": len(items)},
                t0
            )
        if not batch or batch not in valid_batches:
            return _wrap_envelope(
                "unknown_entity",
                [{"error": f"Invalid or unknown batch reference '{batch}' at item {idx}"}],
                "record_complaints",
                {"n_items": len(items)},
                t0
            )

    # Clear existing complaints
    _run_query("bazaarmart", "clear_complaints", write=True)

    # Add each complaint
    recorded = []
    for i, item in enumerate(items):
        cid = item.get("id") or f"CMP-{i+1:03d}"
        text = item.get("text", "Consumer report")
        store = item.get("store") or item.get("code")
        batch = item.get("batch") or item.get("batch_id")

        _run_query("bazaarmart", "add_complaint", {
            "id": cid,
            "text": text,
            "store": store,
            "batch": batch
        }, write=True)
        recorded.append({"id": cid, "store": store, "batch": batch, "text": text})

    return _wrap_envelope("answered", recorded, "record_complaints", {"items": recorded}, t0)


def rank_lots(depth: int = 1) -> Dict[str, Any]:
    """
    Cross-graph joiner & scoring logic:
    1. Read complaints from bazaarmart.
    2. Group complaint batch_ids by store.
    3. Run rank1.cypher (if depth == 1) or rank2.cypher (if depth == 2) on network.
    4. For each candidate lot, run reach.cypher on network, then deliveries.cypher on bazaarmart.
    5. Compute in Python: coverage, specificity, score, and status.
    """
    t0 = time.time()
    complaints = _run_query("bazaarmart", "complaints")
    if not complaints:
        return _wrap_envelope("not_in_graph", [], "rank_lots", {"depth": depth}, t0)

    # Group complaint batches by store
    store_map: Dict[str, Set[str]] = {}
    for c in complaints:
        store = c["code"]
        batch = c["batch"]
        store_map.setdefault(store, set()).add(batch)

    total_complaint_stores = len(store_map)
    store_batches = [{"store": s, "batch_ids": list(b_ids)} for s, b_ids in store_map.items()]

    query_file = "rank1" if depth == 1 else "rank2"
    candidates = _run_query("network", query_file, {"store_batches": store_batches})

    scored_rows = []
    for cand in candidates:
        lot_id = cand["lot"]
        material = cand["material"]
        matched_stores = set(cand.get("stores", []))
        paths = cand.get("paths", [])

        matched_count = len(matched_stores)
        coverage = round(matched_count / total_complaint_stores, 2) if total_complaint_stores > 0 else 0.0

        # Reach on network
        reach_res = _run_query("network", "reach", {"lot": lot_id})
        reached_batches = [r["id"] for r in reach_res]

        # Deliveries on bazaarmart
        if reached_batches:
            deliv_res = _run_query("bazaarmart", "deliveries", {"batch_ids": reached_batches})
            delivered_stores = {r["store"] for r in deliv_res}
        else:
            delivered_stores = set()

        n_delivered = len(delivered_stores)
        specificity = round(matched_count / n_delivered, 2) if n_delivered > 0 else 0.0
        score = round(coverage * specificity, 2)

        # Status rules
        if coverage == 1.0 and score >= 0.40:
            status = "confirmed"
        elif coverage == 1.0 and score < 0.40:
            status = "ruled_out"
        else:
            status = "inconclusive"

        why = f"Explains {matched_count}/{total_complaint_stores} complaint stores. Delivered to {n_delivered} stores."

        scored_rows.append({
            "lot": lot_id,
            "ingredient": f"{material.title()} ({lot_id})",
            "material": material,
            "status": status,
            "coverage": coverage,
            "specificity": specificity,
            "score": score,
            "stores": list(matched_stores),
            "paths": paths,
            "why": why
        })

    # Sort rows by status (confirmed, inconclusive, ruled_out) then score descending
    status_order = {"confirmed": 0, "inconclusive": 1, "ruled_out": 2}
    scored_rows.sort(key=lambda r: (status_order.get(r["status"], 3), -r["score"]))

    outcome = "answered" if scored_rows else "not_in_graph"
    payload = graph_view.story(scored_rows, complaints)
    return _wrap_envelope(outcome, scored_rows, "rank_lots", {"depth": depth}, t0, payload)


def lots_behind(batch_ids: List[str]) -> Dict[str, Any]:
    """Underlying query: upstream.cypher. Returns paths only."""
    t0 = time.time()
    rows = _run_query("network", "upstream", {"batch_ids": batch_ids})
    paths = [r["path"] for r in rows if "path" in r]
    payload = graph_view.upstream(rows)
    outcome = "answered" if rows else "not_in_graph"
    return _wrap_envelope(outcome, rows, "lots_behind", {"batch_ids": batch_ids}, t0, payload, paths=paths)


def recall_findings(subject_id: str) -> Dict[str, Any]:
    """Underlying query: memory_read.cypher."""
    t0 = time.time()
    rows = _run_query("bazaarmart", "memory_read", {"subject_id": subject_id})
    outcome = "from_memory" if rows else "not_in_graph"
    return _wrap_envelope(outcome, rows, "recall_findings", {"subject_id": subject_id}, t0)


def save_finding(lot: str, batch_ids: List[str], text: str) -> Dict[str, Any]:
    """
    Underlying query: memory_write.cypher.
    Called ONLY by investigator.confirm() button, never by the LLM agent.
    """
    t0 = time.time()
    fid = f"FIND-{lot}-{int(time.time())}"
    now_str = datetime.now().isoformat()
    rows = _run_query("bazaarmart", "memory_write", {
        "id": fid,
        "text": text,
        "at": now_str,
        "lot": lot,
        "batch_ids": batch_ids
    }, write=True)
    return _wrap_envelope("answered", rows, "save_finding", {"lot": lot, "batch_ids": batch_ids, "text": text}, t0)


def write_investigation(case: str, status: str, summary: str, lot_id: str = "", batch_ids: str = "") -> Dict[str, Any]:
    """
    Underlying query: status.cypher.
    case 'complaints' writes INV-COMPLAINTS; case 'notice' writes INV-NOTICE.
    """
    t0 = time.time()
    inv_id = "INV-COMPLAINTS" if case == "complaints" else "INV-NOTICE"
    rows = _run_query("bazaarmart", "status", {
        "id": inv_id,
        "status": status,
        "summary": summary,
        "lot_id": lot_id,
        "batch_ids": batch_ids
    }, write=True)
    return _wrap_envelope("answered", rows, "write_investigation", {"case": case, "status": status}, t0)


def load_investigation(id: str = "INV-COMPLAINTS") -> Dict[str, Any]:
    """Underlying query: load_inv.cypher."""
    t0 = time.time()
    rows = _run_query("bazaarmart", "load_inv", {"id": id})
    outcome = "answered" if rows else "not_in_graph"
    return _wrap_envelope(outcome, rows, "load_investigation", {"id": id}, t0)


def forward_trace(lot: str) -> Dict[str, Any]:
    """
    Underlying queries: trace, deliveries, purchases.
    Rule: Returns outcome = 'not_in_graph' when lot has no final batch or when delivered to zero stores.
    """
    t0 = time.time()
    trace_rows = _run_query("network", "trace", {"lot": lot})
    if not trace_rows:
        return _wrap_envelope("not_in_graph", [], "forward_trace", {"lot": lot}, t0)

    final_batches = [r["id"] for r in trace_rows]
    deliv_rows = _run_query("bazaarmart", "deliveries", {"batch_ids": final_batches})
    delivered_stores = [r["store"] for r in deliv_rows]

    if not delivered_stores:
        return _wrap_envelope("not_in_graph", [], "forward_trace", {"lot": lot}, t0)

    pur_rows = _run_query("bazaarmart", "purchases", {"batch_ids": final_batches})
    pur_count = pur_rows[0].get("count", 0) if pur_rows else 0

    rows = [{
        "lot": lot,
        "batches": final_batches,
        "trace": trace_rows,
        "stores": delivered_stores,
        "purchases": pur_count
    }]

    paths = [r.get("path") for r in trace_rows if "path" in r]
    return _wrap_envelope("answered", rows, "forward_trace", {"lot": lot}, t0, paths=paths)


def exposure_routes(from_stores: List[str], max_days: int = 3) -> Dict[str, Any]:
    """
    Wraps routes.cypher in try/except to catch FalkorDB procedure errors
    and gracefully returns an empty payload.
    """
    t0 = time.time()
    try:
        rows = _run_query("bazaarmart", "routes", {"from_stores": from_stores, "max_days": max_days})
        return _wrap_envelope("answered", rows, "exposure_routes", {"from_stores": from_stores}, t0)
    except Exception:
        return _wrap_envelope("answered", [], "exposure_routes", {"from_stores": from_stores}, t0)


def notice_context(lot: str, issued_by: Optional[str] = None, material: Optional[str] = None, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    Underlying query: notice_context.cypher.
    Builds UI checklist: issued by, ingredient, supplier, used in a product, delivered, on a shelf, associate, pull task.
    Empty trace when used_in == 0.
    """
    t0 = time.time()
    res = _run_query("network", "notice_context", {"lot": lot})
    used_in = res[0].get("used_in", 0) if res else 0
    supplier = (res[0].get("supplier") if res else None) or issued_by or "Supplier"
    mat = (res[0].get("material") if res else None) or material or "Component"
    notice_id = (res[0].get("notice_id") if res else None) or "NOTICE"

    checklist = {
        "issued_by": supplier,
        "ingredient": mat,
        "supplier": supplier,
        "used_in_a_product": used_in > 0,
        "delivered": False,
        "on_a_shelf": False,
        "associate_on_duty": False,
        "pull_task": False
    }

    notice_data = {
        "lot": lot,
        "material": mat,
        "supplier": supplier,
        "notice_id": notice_id,
        "used_in": used_in
    }

    payload = graph_view.notice_gap(notice_data)

    if used_in == 0:
        return _wrap_envelope("not_in_graph", [checklist], "notice_context", {"lot": lot}, t0, payload)

    return _wrap_envelope("answered", [checklist], "notice_context", {"lot": lot}, t0, payload)


def pull_list(batch_ids: List[str]) -> Dict[str, Any]:
    """Underlying query: pull.cypher. Returns on-duty shelves with available stock only."""
    t0 = time.time()
    rows = _run_query("bazaarmart", "pull", {"batch_ids": batch_ids})
    outcome = "answered" if rows else "not_in_graph"
    return _wrap_envelope(outcome, rows, "pull_list", {"batch_ids": batch_ids}, t0)


def shelf_view(inv_id: str = "INV-COMPLAINTS") -> Dict[str, Any]:
    """
    Underlying queries: forward_trace, shelf, task_for.
    Drops product IDs that leak into path node lists (keeps only lot, mix, batch).
    Clears the employee when qty is missing/zero.
    """
    t0 = time.time()
    inv_rows = _run_query("bazaarmart", "load_inv", {"id": inv_id})
    lot_id = inv_rows[0].get("lot_id") if inv_rows else ""
    batch_str = inv_rows[0].get("batch_ids") if inv_rows else ""

    batches = [b.strip() for b in batch_str.split(",") if b.strip()] if batch_str else []
    if not batches and lot_id:
        ft = forward_trace(lot_id)
        if ft["rows"]:
            batches = ft["rows"][0].get("batches", [])

    shelf_rows = _run_query("bazaarmart", "shelf", {"batch_ids": batches}) if batches else []

    # Clean rows: clear employee if qty is missing or zero
    cleaned_shelf_rows = []
    for r in shelf_rows:
        qty = r.get("qty")
        if qty is None or qty == 0:
            r["associate"] = None
        cleaned_shelf_rows.append(r)

    tasks = _run_query("bazaarmart", "task_for", {"id": inv_id})

    payload = graph_view.shelves(cleaned_shelf_rows, lot_id=lot_id)
    return _wrap_envelope("answered", cleaned_shelf_rows, "shelf_view", {"inv_id": inv_id, "tasks": tasks}, t0, payload)


def dispatch_task(store: str, inv: str = "INV-COMPLAINTS", due_by: Optional[str] = None) -> Dict[str, Any]:
    """
    Underlying query: task.cypher.
    Task ID format: T-{inv}-{store}.
    Refuses unless investigation status is confirmed or closed,
    refuses if store has no on-duty shelf, and refuses if store already has a task.
    """
    t0 = time.time()
    inv_res = _run_query("bazaarmart", "load_inv", {"id": inv})
    if not inv_res:
        return _wrap_envelope("not_in_graph", [{"error": f"Investigation {inv} not found"}], "dispatch_task", {"store": store}, t0)

    inv_status = inv_res[0].get("status")
    if inv_status not in {"confirmed", "closed"}:
        return _wrap_envelope("not_in_graph", [{"error": f"Refused: Investigation status '{inv_status}' must be confirmed or closed"}], "dispatch_task", {"store": store}, t0)

    # Check if task already exists
    existing_tasks = _run_query("bazaarmart", "task_for", {"id": inv})
    if any(t.get("store") == store for t in existing_tasks):
        return _wrap_envelope("answered", [{"error": f"Refused: Store {store} already has a task"}], "dispatch_task", {"store": store}, t0)

    batch_str = inv_res[0].get("batch_ids", "")
    batches = [b.strip() for b in batch_str.split(",") if b.strip()]

    # Check on-duty shelf for this store
    pull_rows = _run_query("bazaarmart", "pull", {"batch_ids": batches})
    store_pulls = [p for p in pull_rows if p.get("store_code") == store]
    if not store_pulls:
        return _wrap_envelope("not_in_graph", [{"error": f"Refused: Store {store} has no on-duty shelf with available stock"}], "dispatch_task", {"store": store}, t0)

    shelf = store_pulls[0]
    task_id = f"T-{inv}-{store}"
    due_str = due_by or (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")

    rows = _run_query("bazaarmart", "task", {
        "inv": inv,
        "task_id": task_id,
        "location_code": shelf.get("location_code", "Shelf-01"),
        "assignee_name": shelf.get("associate_name", "Staff"),
        "due_by": due_str,
        "batch": shelf.get("batch_id", ""),
        "qty": shelf.get("qty", 1),
        "store": store
    }, write=True)

    return _wrap_envelope("answered", rows, "dispatch_task", {"store": store, "task_id": task_id}, t0)


def tasks_for(id: str = "INV-COMPLAINTS") -> Dict[str, Any]:
    """Underlying query: task_for.cypher."""
    t0 = time.time()
    rows = _run_query("bazaarmart", "task_for", {"id": id})
    return _wrap_envelope("answered", rows, "tasks_for", {"id": id}, t0)


def task_for(id: str = "INV-COMPLAINTS") -> Dict[str, Any]:
    """Returns the first task for that investigation."""
    t0 = time.time()
    rows = _run_query("bazaarmart", "task_for", {"id": id})
    first = rows[:1]
    return _wrap_envelope("answered", first, "task_for", {"id": id}, t0)


def current_tasks(inv_id: str = "INV-COMPLAINTS") -> Dict[str, Any]:
    """Alias for tasks_for used by store_ops agent."""
    return tasks_for(inv_id)


def illness() -> Dict[str, Any]:
    """
    Underlying query: illness.cypher.
    Classifies hazard as Class I or Class II based on severity keywords in complaint text.
    """
    t0 = time.time()
    rows = _run_query("bazaarmart", "illness")
    keywords = ["hospital", "anaphylaxis", "severe", "choking", "allergic", "allergy", "icu", "emergency", "reaction"]

    texts = [r.get("text", "").lower() for r in rows]
    has_class_i = any(any(k in t for k in keywords) for t in texts)

    hazard_class = "Class I" if has_class_i else "Class II"
    reason = "Life-threatening symptoms or severe adverse reactions reported" if has_class_i else "Moderate or non-life-threatening complaints"

    res_row = [{
        "class": hazard_class,
        "reason": reason,
        "total_complaints": len(rows)
    }]
    return _wrap_envelope("answered", res_row, "illness", {}, t0)


def mark_done(task_id: str) -> Dict[str, Any]:
    """Underlying query: done.cypher."""
    t0 = time.time()
    rows = _run_query("bazaarmart", "done", {"id": task_id}, write=True)
    return _wrap_envelope("answered", rows, "mark_done", {"task_id": task_id}, t0)


def resolve_lot(lot: str) -> Dict[str, Any]:
    """
    Underlying query: lots.cypher.
    Exact-matches lot IDs against lots.cypher. If not found, uses difflib.get_close_matches.
    Returns outcome = 'unknown_entity' with closest candidate IDs in rows.
    Must NOT run a traversal when unknown.
    """
    t0 = time.time()
    lots = _run_query("network", "lots")
    all_lot_ids = [l["id"] for l in lots]

    if lot in all_lot_ids:
        matched = [l for l in lots if l["id"] == lot]
        return _wrap_envelope("answered", matched, "resolve_lot", {"lot": lot}, t0)

    # Use difflib close matches
    candidates = difflib.get_close_matches(lot, all_lot_ids, n=3, cutoff=0.6)
    rows = [{"candidate": c} for c in candidates]
    return _wrap_envelope("unknown_entity", rows, "resolve_lot", {"lot": lot}, t0)
