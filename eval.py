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
    # Condition: GN-2214 is NOT confirmed (status == "inconclusive"), coverage == 0.67, and salt lot score < 0.40
    # --------------------------------------------------------------------------
    hero_complaints = [
        {"store": "TH-01", "batch": "MP-2410-01", "text": "Severe allergic reaction and hospitalization after eating masala peanuts"},
        {"store": "TH-02", "batch": "MP-2410-02", "text": "Allergic reaction to masala peanuts"},
        {"store": "TH-03", "batch": "BH-2410-03", "text": "Anaphylaxis symptoms after eating bhujia in Pune"}
    ]
    tools.record_complaints(hero_complaints)
    d1_res = tools.rank_lots(depth=1)
    d1_rows = d1_res.get("rows", [])

    gn_row_d1 = next((r for r in d1_rows if r.get("lot") == "GN-2214"), None)
    salt_row = next((r for r in d1_rows if r.get("material") == "salt" or r.get("lot") == "SL-0042"), None)

    c1_pass = (
        gn_row_d1 is not None
        and gn_row_d1.get("status") == "inconclusive"
        and gn_row_d1.get("coverage") == 0.67
        and salt_row is not None
        and salt_row.get("score", 1.0) < 0.40
    )
    details_1 = f"GN status={gn_row_d1.get('status') if gn_row_d1 else None}, cov={gn_row_d1.get('coverage') if gn_row_d1 else None}, salt score={salt_row.get('score') if salt_row else None}"
    results.append((1, "Hero complaints, depth 1", c1_pass, details_1))

    # --------------------------------------------------------------------------
    # Check 2: Hero complaints, depth 2
    # Condition: GN-2214 is "confirmed" (coverage == 1.0, score >= 0.40) and path text contains intermediate mix RG-2409-04
    # --------------------------------------------------------------------------
    d2_res = tools.rank_lots(depth=2)
    d2_rows = d2_res.get("rows", [])

    gn_row_d2 = next((r for r in d2_rows if r.get("lot") == "GN-2214"), None)
    c2_pass = False
    details_2 = ""
    if gn_row_d2:
        cov_ok = gn_row_d2.get("coverage") == 1.0
        score_ok = gn_row_d2.get("score", 0.0) >= 0.40
        status_ok = gn_row_d2.get("status") == "confirmed"
        paths_text = str(gn_row_d2.get("paths", []))
        mix_ok = "RG-2409-04" in paths_text

        c2_pass = cov_ok and score_ok and status_ok and mix_ok
        details_2 = f"GN status={gn_row_d2.get('status')}, cov={gn_row_d2.get('coverage')}, score={gn_row_d2.get('score')}, mix found={mix_ok}"
    else:
        details_2 = "GN-2214 not found in depth 2"
    results.append((2, "Hero complaints, depth 2", c2_pass, details_2))

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
    c3_d1 = tools.rank_lots(depth=1).get("rows", [])
    c3_d2 = tools.rank_lots(depth=2).get("rows", [])
    has_confirmed = any(r.get("status") == "confirmed" for r in (c3_d1 + c3_d2))
    c3_pass = not has_confirmed
    details_3 = f"Confirmed rows in depth 1: {sum(1 for r in c3_d1 if r.get('status') == 'confirmed')}, depth 2: {sum(1 for r in c3_d2 if r.get('status') == 'confirmed')}"
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
    pur_count = ft_res.get("rows", [{}])[0].get("purchases", -1)
    c6_pass = (pur_count == 2)
    details_6 = f"purchases={pur_count}"
    results.append((6, "forward_trace('RP-0099')", c6_pass, details_6))

    # --------------------------------------------------------------------------
    # Check 7: Save a GN-2214 finding, then run complaints_from for Pune / BH-2410-03
    # Condition: outcome == "from_memory", tool trace includes lots_behind and does NOT include rank_lots
    # --------------------------------------------------------------------------
    tools.save_finding(
        lot="GN-2214",
        batch_ids=["BH-2410-03"],
        text="Incident root cause GN-2214 confirmed from previous investigation."
    )
    pune_complaint = [
        {"store": "TH-03", "batch": "BH-2410-03", "text": "Allergic reaction in Pune FC Road store"}
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
    results.append((7, "Save GN-2214 finding & memory replay Pune / BH-2410-03", c7_pass, details_7))

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
