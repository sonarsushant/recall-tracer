"""
graph_view.py - Graph drawing payload builder for streamlit-agraph.
Constructs directed hierarchical graph visualization payloads using the RecallTracer palette.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

# Exact color palette specified in section 4
COLOR_RULED_OUT = "#c0392b"     # Red: Ruled out lot, or the recall notice node
COLOR_NOTICE = "#c0392b"        # Red: Recall notice node
COLOR_INCONCLUSIVE = "#6c3483"  # Purple: Inconclusive lot
COLOR_CONFIRMED = "#0e6655"     # Teal: Confirmed ingredient lot
COLOR_MIX = "#e67e22"           # Orange: Intermediate mix
COLOR_FINAL_BATCH = "#2980b9"   # Blue: Finished batch
COLOR_STORE = "#1e8449"         # Green: Store
COLOR_SECTION = "#1a5276"       # Navy: Section
COLOR_AISLE = "#5d6d7e"         # Gray-blue: Aisle
COLOR_ASSOCIATE = "#148f77"     # Light teal: Associate on duty
COLOR_NO_LINK = "#95a5a6"       # Gray: No link, or delivered with nothing on the shelf


def _make_node(node_id: str, label: str, color: str, title: Optional[str] = None, shape: str = "box") -> Dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "color": color,
        "title": title or label,
        "shape": shape
    }


def _make_edge(source: str, target: str, label: str = "", color: str = "#7f8c8d") -> Dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "label": label,
        "color": color
    }


def story(rows: List[Dict[str, Any]], complaint_items: Optional[List[Dict[str, Any]]] = None, max_nodes: int = 20) -> Dict[str, Any]:
    """
    Draws every matched lot, intermediate mix/batch path, and a complaint edge from batch to store.
    Any complaint batch that lies on no matched path is colored gray (#95a5a6) with label "no link yet".
    Caps at 20 nodes. Deduplicates edges by 'source->target:label'.
    """
    nodes_dict: Dict[str, Dict[str, Any]] = {}
    edges_set: Set[str] = set()
    edges_list: List[Dict[str, Any]] = []
    matched_batches: Set[str] = set()

    def add_edge(src: str, dst: str, lbl: str = ""):
        key = f"{src}->{dst}:{lbl}"
        if key not in edges_set:
            edges_set.add(key)
            edges_list.append(_make_edge(src, dst, lbl))

    # Add lots and their paths
    for row in rows:
        if len(nodes_dict) >= max_nodes:
            break
        lot_id = row.get("lot", "")
        status = row.get("status", "inconclusive")
        material = row.get("material", "")
        color = COLOR_CONFIRMED if status == "confirmed" else (COLOR_RULED_OUT if status == "ruled_out" else COLOR_INCONCLUSIVE)
        label = f"{material.title()}\n{lot_id}" if material else lot_id

        if lot_id and lot_id not in nodes_dict:
            nodes_dict[lot_id] = _make_node(lot_id, label, color)

        paths = row.get("paths", [])
        for p in paths:
            # p is a list of node IDs e.g. [lot, mix, batch] or [lot, batch]
            for i in range(len(p) - 1):
                if len(nodes_dict) >= max_nodes:
                    break
                curr_id = p[i]
                next_id = p[i + 1]

                # Style next node
                if next_id not in nodes_dict:
                    if i + 1 == len(p) - 1:
                        # Final batch
                        nodes_dict[next_id] = _make_node(next_id, f"Batch\n{next_id}", COLOR_FINAL_BATCH)
                        matched_batches.add(next_id)
                    else:
                        # Intermediate mix
                        nodes_dict[next_id] = _make_node(next_id, f"Mix\n{next_id}", COLOR_MIX)

                add_edge(curr_id, next_id, "USED_IN")

    # Add complaints (batch -> store)
    if complaint_items:
        for c in complaint_items:
            store = c.get("store") or c.get("code") or ""
            batch = c.get("batch") or ""

            if store and store not in nodes_dict and len(nodes_dict) < max_nodes:
                store_name = c.get("name") or store
                nodes_dict[store] = _make_node(store, f"Store\n{store_name}", COLOR_STORE)

            if batch and batch not in nodes_dict and len(nodes_dict) < max_nodes:
                # Batch on no matched path is gray with "no link yet"
                nodes_dict[batch] = _make_node(batch, f"{batch}\n(no link yet)", COLOR_NO_LINK)

            if batch and store and batch in nodes_dict and store in nodes_dict:
                add_edge(batch, store, "complaint")

    return {
        "nodes": list(nodes_dict.values())[:max_nodes],
        "edges": edges_list,
        "highlight": [r.get("lot") for r in rows if r.get("status") == "confirmed"],
        "query": "rank_lots",
        "note": "Investigation complaint attribution story"
    }


def shelves(shelf_rows: List[Dict[str, Any]], lot_id: Optional[str] = None, mix_id: Optional[str] = None, max_nodes: int = 60) -> Dict[str, Any]:
    """
    Draws lot -> mix -> batch -> store, and then section -> aisle -> associate ONLY when those IDs are present.
    A delivery with no qty stops at the store node and is labeled 'delivered, not on a shelf'.
    Caps at 60 nodes. Deduplicates edges by 'source->target:label'.
    """
    nodes_dict: Dict[str, Dict[str, Any]] = {}
    edges_set: Set[str] = set()
    edges_list: List[Dict[str, Any]] = []

    def add_edge(src: str, dst: str, lbl: str = ""):
        key = f"{src}->{dst}:{lbl}"
        if key not in edges_set:
            edges_set.add(key)
            edges_list.append(_make_edge(src, dst, lbl))

    if lot_id and lot_id not in nodes_dict:
        nodes_dict[lot_id] = _make_node(lot_id, f"Lot\n{lot_id}", COLOR_CONFIRMED)

    if mix_id and mix_id not in nodes_dict:
        nodes_dict[mix_id] = _make_node(mix_id, f"Mix\n{mix_id}", COLOR_MIX)
        if lot_id:
            add_edge(lot_id, mix_id, "USED_IN")

    for row in shelf_rows:
        if len(nodes_dict) >= max_nodes:
            break
        batch_id = row.get("batch_id") or row.get("batch") or ""
        store_code = row.get("store") or ""
        store_name = row.get("store_name") or store_code
        section = row.get("section")
        aisle = row.get("aisle")
        qty = row.get("qty")
        associate = row.get("associate")

        if batch_id and batch_id not in nodes_dict and len(nodes_dict) < max_nodes:
            nodes_dict[batch_id] = _make_node(batch_id, f"Batch\n{batch_id}", COLOR_FINAL_BATCH)
            if mix_id:
                add_edge(mix_id, batch_id, "USED_IN")
            elif lot_id:
                add_edge(lot_id, batch_id, "USED_IN")

        if store_code:
            store_node_id = f"STORE-{store_code}"
            if store_node_id not in nodes_dict and len(nodes_dict) < max_nodes:
                label = f"Store {store_code}\n{store_name}"
                if qty is None or qty == 0:
                    label += "\n(delivered, not on a shelf)"
                    nodes_dict[store_node_id] = _make_node(store_node_id, label, COLOR_NO_LINK)
                else:
                    nodes_dict[store_node_id] = _make_node(store_node_id, label, COLOR_STORE)

            if batch_id and store_node_id in nodes_dict:
                add_edge(batch_id, store_node_id, "DELIVERED_TO")

            # Only add section -> aisle -> associate if qty is present and > 0
            if qty and qty > 0:
                prev_id = store_node_id
                if section and len(nodes_dict) < max_nodes:
                    sec_node_id = f"{store_code}-SEC-{section}"
                    if sec_node_id not in nodes_dict:
                        nodes_dict[sec_node_id] = _make_node(sec_node_id, f"Sec\n{section}", COLOR_SECTION)
                    add_edge(prev_id, sec_node_id, "HAS_SECTION")
                    prev_id = sec_node_id

                if aisle and len(nodes_dict) < max_nodes:
                    aisle_node_id = f"{store_code}-LOC-{aisle}"
                    if aisle_node_id not in nodes_dict:
                        nodes_dict[aisle_node_id] = _make_node(aisle_node_id, f"Aisle {aisle}\n({qty} units)", COLOR_AISLE)
                    add_edge(prev_id, aisle_node_id, "HAS_LOCATION")
                    prev_id = aisle_node_id

                if associate and len(nodes_dict) < max_nodes:
                    assoc_node_id = f"ASC-{associate}"
                    if assoc_node_id not in nodes_dict:
                        nodes_dict[assoc_node_id] = _make_node(assoc_node_id, f"On Duty\n{associate}", COLOR_ASSOCIATE)
                    add_edge(prev_id, assoc_node_id, "LOGGED_INTO")

    return {
        "nodes": list(nodes_dict.values())[:max_nodes],
        "edges": edges_list,
        "highlight": [lot_id] if lot_id else [],
        "query": "shelf_view",
        "note": "Store shelves and inventory locations"
    }


def notice_gap(notice_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Draws supplier -> lot <- notice. Never invent a fake product node when used_in == 0.
    """
    nodes_dict: Dict[str, Dict[str, Any]] = {}
    edges_list: List[Dict[str, Any]] = []

    lot_id = notice_data.get("lot", "") or notice_data.get("lot_id", "")
    material = notice_data.get("material", "Material")
    supplier = notice_data.get("supplier", "Supplier")
    notice_id = notice_data.get("notice_id", "NOTICE")

    if supplier:
        nodes_dict[supplier] = _make_node(supplier, f"Supplier\n{supplier}", COLOR_STORE)

    if lot_id:
        nodes_dict[lot_id] = _make_node(lot_id, f"{material}\n{lot_id}", COLOR_CONFIRMED)

    if notice_id:
        nodes_dict[notice_id] = _make_node(notice_id, f"Notice\n{notice_id}", COLOR_NOTICE)

    if supplier and lot_id:
        edges_list.append(_make_edge(supplier, lot_id, "SUPPLIED"))

    if notice_id and lot_id:
        edges_list.append(_make_edge(notice_id, lot_id, "FOR_LOT"))

    return {
        "nodes": list(nodes_dict.values()),
        "edges": edges_list,
        "highlight": [lot_id] if lot_id else [],
        "query": "notice_context",
        "note": "Supplier recall notice with zero downstream product usage"
    }


def upstream(upstream_rows: List[Dict[str, Any]], max_nodes: int = 60) -> Dict[str, Any]:
    """
    Draws lots and their paths to batches. Caps at 60 nodes.
    """
    nodes_dict: Dict[str, Dict[str, Any]] = {}
    edges_set: Set[str] = set()
    edges_list: List[Dict[str, Any]] = []

    def add_edge(src: str, dst: str, lbl: str = ""):
        key = f"{src}->{dst}:{lbl}"
        if key not in edges_set:
            edges_set.add(key)
            edges_list.append(_make_edge(src, dst, lbl))

    for row in upstream_rows:
        if len(nodes_dict) >= max_nodes:
            break
        lot_id = row.get("lot", "")
        material = row.get("material", "")
        if lot_id and lot_id not in nodes_dict and len(nodes_dict) < max_nodes:
            nodes_dict[lot_id] = _make_node(lot_id, f"{material}\n{lot_id}", COLOR_CONFIRMED)

        paths = row.get("paths", [])
        if not paths and "path" in row:
            paths = [row["path"]]

        for p in paths:
            for i in range(len(p) - 1):
                if len(nodes_dict) >= max_nodes:
                    break
                curr_id = p[i]
                next_id = p[i + 1]
                if curr_id not in nodes_dict and len(nodes_dict) < max_nodes:
                    nodes_dict[curr_id] = _make_node(curr_id, curr_id, COLOR_MIX)
                if next_id not in nodes_dict and len(nodes_dict) < max_nodes:
                    nodes_dict[next_id] = _make_node(next_id, next_id, COLOR_FINAL_BATCH)
                add_edge(curr_id, next_id, "USED_IN")

    return {
        "nodes": list(nodes_dict.values())[:max_nodes],
        "edges": edges_list,
        "highlight": [r.get("lot") for r in upstream_rows if r.get("lot")],
        "query": "upstream",
        "note": "Upstream trace from batches to ingredient lots"
    }


def render_agraph(graph_payload: Dict[str, Any], height: int = 520, width: int = 1400):
    """
    Helper function to render a streamlit-agraph chart in Streamlit UI.
    Configured with directed=True, physics=False, hierarchical layout left-to-right (direction='LR').
    """
    try:
        from streamlit_agraph import agraph, Node, Edge, Config
    except ImportError:
        return None

    raw_nodes = graph_payload.get("nodes", [])
    raw_edges = graph_payload.get("edges", [])

    nodes = [
        Node(
            id=n["id"],
            label=n.get("label", n["id"]),
            color=n.get("color", "#2980b9"),
            title=n.get("title", n.get("label", n["id"])),
            shape=n.get("shape", "box")
        )
        for n in raw_nodes
    ]

    edges = [
        Edge(
            source=e["source"],
            target=e["target"],
            label=e.get("label", ""),
            color=e.get("color", "#7f8c8d")
        )
        for e in raw_edges
    ]

    config = Config(
        width=width,
        height=height,
        directed=True,
        physics=False,
        hierarchical=True,
        direction="LR"
    )

    return agraph(nodes=nodes, edges=edges, config=config)
