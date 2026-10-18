"""
eval.py - Automated Evaluation Suite for RecallTracer.
Executes 7 end-to-end checks in order, prints a 7-row summary table,
and exits with code 0 if all pass (or non-zero if any check fails).
"""

import sys
import os
from typing import List, Tuple

import tools
import investigator
import store_ops
from scripts.seed_clean import seed_database


def run_eval() -> int:
    print("=" * 80)
    print("RECALLTRACER END-TO-END EVALUATION SUITE")
    print("=" * 80)

    # Clean seed before evaluation
    print("Seeding database to pristine state...")
    seed_database()
    print("Seeding complete. Beginning 7 evaluation checks.\n")

    results: List[Tuple[int, str, bool, str]] = []

    # --------------------------------------------------------------------------
    # Check 1: Hero complaints, depth 1
    # Condition: salt reaches all complaints but is low-specificity and ruled out at depth 1.
    # --------------------------------------------------------------------------
    hero_complaints = [
        {"store": "TH-01", "batch": "MP-2410-01", "text": "Severe food poisoning and hospitalization after eating masala peanuts"},
        {"store": "TH-02", "batch": "MP-2410-02", "text": "Severe vomiting and fever after eating masala peanuts"},
        {"store": "TH-03", "batch": "BH-2410-03", "text": "Hospitalized with severe food poisoning after eating bhujia in Pune"}
    ]
    tools.record_complaints(hero_complaints)
    d1_res = tools.rank_lots(depth=1)
    d1_rows = d1_res.get("rows", [])

    salt_row = next((r for r in d1_rows if r.get("material") == "salt" or r.get("lot") == "SL-0042"), None)
    oil_row_d1 = next((r for r in d1_rows if r.get("lot") == "GO-0611"), None)

    c1_pass = (
        salt_row is not None
        and salt_row.get("coverage") == 1.0
        and salt_row.get("score", 1.0) < 0.40
        and salt_row.get("status") == "ruled_out"
        and oil_row_d1 is None
    )
    details_1 = f"salt status={salt_row.get('status') if salt_row else None}, coverage={salt_row.get('coverage') if salt_row else None}, score={salt_row.get('score') if salt_row else None}, groundnut oil absent={oil_row_d1 is None}"
    results.append((1, "Hero complaints, depth 1 rejects salt", c1_pass, details_1))

    # --------------------------------------------------------------------------
    # Check 2: Groundnut oil is confirmed at depth 2 and all downstream stock is recalled.
    # --------------------------------------------------------------------------
    d2_res = tools.rank_lots(depth=2)
    d2_rows = d2_res.get("rows", [])

    oil_row_d2 = next((r for r in d2_rows if r.get("lot") == "GO-0611"), None)
    oil_paths = str(oil_row_d2.get("paths", [])) if oil_row_d2 else ""
    c2_rank_pass = (
        oil_row_d2 is not None
        and oil_row_d2.get("coverage") == 1.0
        and oil_row_d2.get("score", 0.0) >= 0.40
        and oil_row_d2.get("status") == "confirmed"
        and "GOM-2409-04" in oil_paths
    )

    investigation = investigator.complaints_from(hero_complaints)
    investigation_row = tools.load_investigation("INV-COMPLAINTS").get("rows", [])
    investigation_open = (
        investigation.get("lot") == "GO-0611"
        and investigation.get("status") == "open"
        and bool(investigation_row)
        and investigation_row[0].get("status") == "open"
    )
    forward_trace = tools.forward_trace("GO-0611")
    traced_rows = forward_trace.get("rows", [{}])[0].get("trace", [])
    traced_batches = {row.get("id") for row in traced_rows}
    traced_products = {row.get("name") for row in traced_rows}
    expected_downstream_batches = {
        "MP-2410-01",
        "MP-2410-02",
        "MP-2410-03",
        "BH-2410-03",
        "BH-2410-04",
        "BH-2410-05",
        "GC-2410-01",
    }
    full_trace_pass = (
        traced_batches == expected_downstream_batches
        and "Groundnut Chikki" in traced_products
    )
    confirmation = investigator.confirm() if investigation_open else {}
    dispatch = store_ops.run() if confirmation.get("status") == "confirmed" else {}
    dispatched_rows = dispatch.get("dispatched", [])
    dispatched_stores = {row.get("store") for row in dispatched_rows}
    recalled_batches = {row.get("batch") for row in dispatched_rows}
    dispatch_pass = (
        dispatched_stores == {"TH-01", "TH-02", "TH-03", "TH-04", "TH-05", "TH-06"}
        and recalled_batches == {
            "MP-2410-01",
            "MP-2410-02",
            "MP-2410-03",
            "BH-2410-03",
            "BH-2410-05",
            "GC-2410-01",
        }
    )
    c2_pass = c2_rank_pass and investigation_open and full_trace_pass and dispatch_pass
    details_2 = (
        f"oil status={oil_row_d2.get('status') if oil_row_d2 else None}, "
        f"coverage={oil_row_d2.get('coverage') if oil_row_d2 else None}, "
        f"score={oil_row_d2.get('score') if oil_row_d2 else None}, "
        f"blend path={'GOM-2409-04' in oil_paths}, "
        f"confirmed lot={confirmation.get('lot_id')}, "
        f"downstream batches traced={len(traced_batches)}, "
        f"unreported product traced={'Groundnut Chikki' in traced_products}, "
        f"stores dispatched={sorted(dispatched_stores)}, "
        f"batches recalled={sorted(recalled_batches)}"
    )
    results.append((2, "Depth 2 groundnut-oil recall dispatch", c2_pass, details_2))

    # --------------------------------------------------------------------------
    # Check 3: Salt-only complaints on three namkeen batches
    # Condition: Zero rows have status == "confirmed"
    # --------------------------------------------------------------------------
    salt_complaints = [
        {"store": "TH-05", "batch": "NK-2410-01", "text": "Mild stomach discomfort from namkeen mix"},
        {"store": "TH-06", "batch": "NK-2410-02", "text": "Salty aftertaste in namkeen"},
        {"store": "TH-07", "batch": "NK-2410-03", "text": "Stomach irritation from namkeen"}
    ]
    tools.record_complaints(salt_complaints)
    c3_rank1 = tools.rank_lots(depth=1)
    c3_rank2 = tools.rank_lots(depth=2)
    c3_d1 = c3_rank1.get("rows", [])
    c3_d2 = c3_rank2.get("rows", [])
    salt_d1 = next((row for row in c3_d1 if row.get("lot") == "SL-0042"), None)
    depth2_mix_candidate = next((row for row in c3_d2 if row.get("lot") == "LOT-011"), None)
    has_confirmed = any(r.get("status") == "confirmed" for r in (c3_d1 + c3_d2))
    has_distinct_depth_graphs = (
        c3_rank1.get("graph_payload", {}).get("edges")
        != c3_rank2.get("graph_payload", {}).get("edges")
    )
    c3_pass = (
        not has_confirmed
        and salt_d1 is not None
        and salt_d1.get("status") == "ruled_out"
        and depth2_mix_candidate is not None
        and depth2_mix_candidate.get("status") == "inconclusive"
        and depth2_mix_candidate.get("coverage", 1.0) < 1.0
        and any("NKM-2409-01" in path for path in depth2_mix_candidate.get("paths", []))
        and has_distinct_depth_graphs
    )
    details_3 = (
        f"salt depth-1={salt_d1.get('status') if salt_d1 else None}, "
        f"LOT-011 depth-2 path through mix="
        f"{any('NKM-2409-01' in path for path in depth2_mix_candidate.get('paths', [])) if depth2_mix_candidate else False}, "
        f"depth-1/depth-2 graphs differ={has_distinct_depth_graphs}, "
        f"confirmed candidates={sum(1 for r in (c3_d1 + c3_d2) if r.get('status') == 'confirmed')}"
    )
    results.append((3, "Salt-only complaints on three namkeen batches", c3_pass, details_3))

    # --------------------------------------------------------------------------
    # Check 4: notice("RX-7781") then store_ops.run()
    # Condition: INV-NOTICE status is "no_link" and store_ops.run() dispatches zero new tasks
    # --------------------------------------------------------------------------
    res_notice = investigator.notice({"lot": "RX-7781"})
    inv_notice = tools.load_investigation("INV-NOTICE").get("rows", [])
    notice_status = inv_notice[0].get("status") if inv_notice else None

    # Verify store_ops.run() dispatches zero tasks on INV-NOTICE (or dispatches zero new tasks)
    tasks_before = len(tools.tasks_for("INV-COMPLAINTS").get("rows", []))
    ops_res = store_ops.run("INV-NOTICE")
    tasks_after = len(tools.tasks_for("INV-COMPLAINTS").get("rows", []))

    c4_pass = (notice_status == "no_link") and (len(ops_res.get("dispatched", [])) == 0) and (tasks_after == tasks_before)
    details_4 = f"INV-NOTICE status={notice_status}, new tasks dispatched={len(ops_res.get('dispatched', []))}"
    results.append((4, "notice('RX-7781') then store_ops.run()", c4_pass, details_4))

    # --------------------------------------------------------------------------
    # Check 5: notice("GN-22l4") (lowercase L typo)
    # Condition: outcome == "unknown_entity", candidate rows mention GN-2214, and forward_trace is NOT called
    # --------------------------------------------------------------------------
    res_typo = investigator.notice({"lot": "GN-22l4"})
    step_tools_5 = [s.get("trace", {}).get("tool") for s in res_typo.get("steps", []) if "trace" in s]
    forward_trace_called = "forward_trace" in step_tools_5
    candidates_mention = any("GN-2214" in str(c) for c in res_typo.get("candidates", []))

    c5_pass = (
        res_typo.get("outcome") == "unknown_entity"
        and candidates_mention
        and not forward_trace_called
    )
    details_5 = f"outcome={res_typo.get('outcome')}, candidates={res_typo.get('candidates')}, forward_trace_called={forward_trace_called}"
    results.append((5, "notice('GN-22l4') (lowercase L typo)", c5_pass, details_5))

    # --------------------------------------------------------------------------
    # Check 6: forward_trace("RP-0099")
    # Condition: purchases count is 2
    # --------------------------------------------------------------------------
    ft_res = tools.forward_trace("RP-0099")
    ft_scenario = investigator.complaints_from({"type": "forward_trace", "lot": "RP-0099"})
    pur_count = ft_res.get("rows", [{}])[0].get("purchases", -1)
    graph_has_product_link = any(
        edge.get("label") == "OF_PRODUCT"
        for edge in ft_scenario.get("graph_payload", {}).get("edges", [])
    )
    c6_pass = (
        pur_count == 2
        and ft_scenario.get("action") == "forward_trace"
        and ft_scenario.get("outcome") == "answered"
        and graph_has_product_link
    )
    details_6 = (
        f"purchases={pur_count}, standalone scenario outcome={ft_scenario.get('outcome')}, "
        f"graph includes product link={graph_has_product_link}"
    )
    results.append((6, "forward_trace('RP-0099')", c6_pass, details_6))

    # --------------------------------------------------------------------------
    # Check 7: Save a GO-0611 finding, then run complaints_from for Pune / BH-2410-03
    # Condition: outcome == "from_memory", tool trace includes lots_behind and does NOT include rank_lots
    # --------------------------------------------------------------------------
    tools.save_finding(
        lot="GO-0611",
        batch_ids=["BH-2410-03"],
        text="Incident root cause GO-0611 (groundnut oil) confirmed from previous investigation."
    )
    pune_complaint = [
        {"store": "TH-03", "batch": "BH-2410-03", "text": "Severe food poisoning in Pune FC Road store"}
    ]
    res_mem = investigator.complaints_from(pune_complaint)
    step_tools_7 = [s.get("trace", {}).get("tool") for s in res_mem.get("steps", []) if "trace" in s]

    has_lots_behind = "lots_behind" in step_tools_7
    has_rank_lots = "rank_lots" in step_tools_7
    c7_pass = (
        res_mem.get("outcome") == "from_memory"
        and has_lots_behind
        and not has_rank_lots
    )
    details_7 = f"outcome={res_mem.get('outcome')}, lots_behind_in_trace={has_lots_behind}, rank_lots_in_trace={has_rank_lots}"
    results.append((7, "Save GO-0611 finding & memory replay Pune / BH-2410-03", c7_pass, details_7))

    # --------------------------------------------------------------------------
    # SUMMARY TABLE
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f"{'#':<3} | {'Check Description':<48} | {'Status':<6} | {'Details'}")
    print("-" * 80)
    all_passed = True
    for num, desc, passed, det in results:
        status_str = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"{num:<3} | {desc:<48} | {status_str:<6} | {det}")
    print("=" * 80)

    if all_passed:
        print("\nALL 7 EVALUATION CHECKS PASSED SUCCESSFULLY (Exit Code 0)\n")
        return 0
    else:
        print("\nSOME EVALUATION CHECKS FAILED (Exit Code 1)\n")
        return 1


if __name__ == "__main__":
    code = run_eval()
    sys.exit(code)
