"""
store_ops.py - Deterministic store-operations task dispatcher.
Loads INV-COMPLAINTS, verifies confirmed/closed status, and dispatches pull tasks.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

import tools


def run(inv_id: str = "INV-COMPLAINTS") -> Dict[str, Any]:
    """
    Executes store operations task dispatch:
    - Loads investigation.
    - Only creates tasks when investigation status is 'confirmed' or 'closed'.
    - Calls pull_list(batch_ids), checks existing tasks to skip stores that already have a task.
    - Dispatches task for each remaining row with an on-duty associate (due_by = now + 2 hours).
    """
    inv_res = tools.load_investigation(inv_id)
    if not inv_res["rows"]:
        return {
            "status": "error",
            "dispatched": [],
            "message": f"Investigation {inv_id} not found."
        }

    inv = inv_res["rows"][0]
    inv_status = inv.get("status")

    if inv_status not in {"confirmed", "closed"}:
        return {
            "status": "refused",
            "dispatched": [],
            "message": f"Store-ops task creation refused: Investigation status is '{inv_status}' (must be 'confirmed' or 'closed')."
        }

    batch_str = inv.get("batch_ids", "")
    batches = [b.strip() for b in batch_str.split(",") if b.strip()]
    if not batches and inv.get("lot_id"):
        ft = tools.forward_trace(inv["lot_id"])
        if ft["rows"]:
            batches = ft["rows"][0].get("batches", [])

    if not batches:
        return {
            "status": "noop",
            "dispatched": [],
            "message": "No affected batches found for investigation."
        }

    # Fetch available shelves with on-duty associates
    pull_res = tools.pull_list(batches)
    pull_rows = pull_res["rows"]

    # Check existing tasks to avoid duplicate dispatch
    existing_tasks = tools.tasks_for(inv_id)["rows"]
    stores_with_tasks = {t.get("store") for t in existing_tasks if t.get("store")}

    dispatched = []
    due_time_str = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")

    for shelf in pull_rows:
        store_code = shelf.get("store_code")
        if not store_code or store_code in stores_with_tasks:
            continue

        # Dispatch task for this store
        res = tools.dispatch_task(store=store_code, inv=inv_id, due_by=due_time_str)
        if res["outcome"] == "answered" and res["rows"]:
            dispatched.append({
                "store": store_code,
                "task_id": f"T-{inv_id}-{store_code}",
                "location": shelf.get("location_code"),
                "associate": shelf.get("associate_name"),
                "batch": shelf.get("batch_id"),
                "qty": shelf.get("qty"),
                "due_by": due_time_str
            })
            stores_with_tasks.add(store_code)

    return {
        "status": "success",
        "dispatched": dispatched,
        "total_dispatched": len(dispatched),
        "existing_tasks_count": len(existing_tasks),
        "message": f"Dispatched {len(dispatched)} store pull tasks."
    }
