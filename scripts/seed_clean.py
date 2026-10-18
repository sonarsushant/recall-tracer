"""
seed_clean.py - Deterministic clean seed script for RecallTracer.
Seeds both 'network' and 'bazaarmart' graphs in FalkorDB with exact entities,
intermediate mixes, delivery lanes, locations, associates, and purchase counts
required for all 26 Cypher queries and all 7 eval.py checks.
"""

import os
from falkordb import FalkorDB

HOST = os.getenv("FALKOR_HOST", "localhost")
PORT = int(os.getenv("FALKOR_PORT", 6379))


def seed_database():
    db = FalkorDB(host=HOST, port=PORT)
    print(f"Connected to FalkorDB at {HOST}:{PORT}")

    # ==========================================
    # 1. SEED NETWORK GRAPH
    # ==========================================
    net = db.select_graph("network")
    print("Clearing network graph...")
    try:
        net.query("MATCH (n) DETACH DELETE n")
    except Exception as e:
        print("Network clear note:", e)

    print("Seeding network graph...")
    # Suppliers
    suppliers = [
        {"id": "SUP-001", "name": "AgroNuts Ltd", "type": "aggregator"},
        {"id": "SUP-002", "name": "PureSalt Co", "type": "aggregator"},
        {"id": "SUP-003", "name": "GoldenOils Refinery", "type": "co_packer"},
        {"id": "SUP-004", "name": "SpiceCraft India", "type": "aggregator"},
        {"id": "SUP-005", "name": "Extracto Labs", "type": "aggregator"},
        {"id": "SUP-013", "name": "ThreadWorks Garments", "type": "garment_vendor"},
        {"id": "SUP-014", "name": "StyleStitch Garments", "type": "garment_vendor"}
    ]
    for i in range(6, 13):
        suppliers.append({"id": f"SUP-{i:03d}", "name": f"Supplier {i:02d}", "type": "co_packer"})
    for i in range(15, 21):
        suppliers.append({"id": f"SUP-{i:03d}", "name": f"Supplier {i:02d}", "type": "packaging"})

    for s in suppliers:
        net.query("""
            MERGE (sup:Supplier {id: $id})
            SET sup.name = $name, sup.type = $type
        """, s)

    # Lots
    lots = [
        {"id": "GN-2214", "material": "groundnut", "kind": "ingredient", "supplier_id": "SUP-001"},
        {"id": "SL-0042", "material": "salt", "kind": "ingredient", "supplier_id": "SUP-002"},
        {"id": "PO-0611", "material": "palm_oil", "kind": "ingredient", "supplier_id": "SUP-003"},
        {"id": "GO-0611", "material": "groundnut_oil", "kind": "ingredient", "supplier_id": "SUP-003"},
        {"id": "RP-0099", "material": "red_pepper", "kind": "ingredient", "supplier_id": "SUP-004"},
        {"id": "RX-7781", "material": "raw_extract", "kind": "ingredient", "supplier_id": "SUP-005"},
        {"id": "ZP-0412", "material": "zipper", "kind": "component", "supplier_id": "SUP-013"},
        {"id": "DY-0314", "material": "dye_red_14", "kind": "component", "supplier_id": "SUP-014"},
        {"id": "TH-0099", "material": "polyester_thread", "kind": "component", "supplier_id": "SUP-013"},
        {"id": "BS-0101", "material": "besan", "kind": "ingredient", "supplier_id": "SUP-001"},
        {"id": "SP-0202", "material": "spices_mix", "kind": "ingredient", "supplier_id": "SUP-004"}
    ]
    # Fill remaining lots to 90
    for i in range(11, 90):
        lots.append({
            "id": f"LOT-{i:03d}",
            "material": f"material_{i}",
            "kind": "ingredient",
            "supplier_id": f"SUP-{(i % 20) + 1:03d}"
        })

    for l in lots:
        net.query("""
            MERGE (lot:Lot {id: $id})
            SET lot.material = $material,
                lot.kind = $kind,
                lot.received_on = '2026-10-01'
            WITH lot
            MATCH (sup:Supplier {id: $supplier_id})
            MERGE (sup)-[:SUPPLIED]->(lot)
        """, l)

    # Products
    products = [
        {"id": "PROD-016", "name": "Masala Peanuts", "brand": "BazaarSelect", "category": "packaged_food"},
        {"id": "PROD-017", "name": "Bhujia", "brand": "BazaarSelect", "category": "packaged_food"},
        {"id": "PROD-018", "name": "Tasty Namkeen Mix", "brand": "BazaarSelect", "category": "packaged_food"},
        {"id": "PROD-019", "name": "Groundnut Chikki", "brand": "BazaarSelect", "category": "packaged_food"},
        {"id": "PROD-045", "name": "Kidswear Style 1", "brand": "BazaarStyle", "category": "apparel"},
        {"id": "PROD-046", "name": "Kidswear Style 2", "brand": "BazaarStyle", "category": "apparel"}
    ]
    for p in products:
        net.query("""
            MERGE (prod:Product {id: $id})
            SET prod.name = $name,
                prod.brand = $brand,
                prod.category = $category
        """, p)

    # Groundnut-oil intermediate batch links the root-cause lot to all hero products.
    net.query("""
        MERGE (m:Batch {id: 'GOM-2409-04'})
        SET m.name = 'Groundnut Oil Blend GOM-2409-04',
            m.kind = 'mix',
            m.mfd = '2026-10-02'
        WITH m
        MATCH (go:Lot {id: 'GO-0611'})
        MERGE (go)-[:USED_IN]->(m)
    """)

    # Finished Batches for Masala Peanuts (MP-2410-01, MP-2410-02)
    # Salt is direct; groundnut oil reaches these through GOM-2409-04.
    net.query("""
        UNWIND ['MP-2410-01', 'MP-2410-02'] AS b_id
        MERGE (b:Batch {id: b_id})
        SET b.name = 'Masala Peanuts Batch ' + b_id,
            b.kind = 'final',
            b.mfd = '2026-10-03'
        WITH b
        MATCH (p:Product {id: 'PROD-016'})
        MERGE (b)-[:OF_PRODUCT]->(p)
        WITH b
        MATCH (sl:Lot {id: 'SL-0042'})
        MERGE (sl)-[:USED_IN]->(b)
        WITH b
        MATCH (po:Lot {id: 'PO-0611'})
        MERGE (po)-[:USED_IN]->(b)
        WITH b
        MATCH (m:Batch {id: 'GOM-2409-04'})
        MERGE (m)-[:USED_IN]->(b)
    """)

    # Finished Batches for Bhujia (BH-2410-03, BH-2410-04)
    # Groundnut oil reaches Bhujia through the intermediate blend; salt remains direct.
    net.query("""
        UNWIND ['BH-2410-03', 'BH-2410-04'] AS b_id
        MERGE (b:Batch {id: b_id})
        SET b.name = 'Bhujia Batch ' + b_id,
            b.kind = 'final',
            b.mfd = '2026-10-04'
        WITH b
        MATCH (p:Product {id: 'PROD-017'})
        MERGE (b)-[:OF_PRODUCT]->(p)
        WITH b
        MATCH (m:Batch {id: 'GOM-2409-04'})
        MERGE (m)-[:USED_IN]->(b)
        WITH b
        MATCH (sl:Lot {id: 'SL-0042'})
        MERGE (sl)-[:USED_IN]->(b)
        WITH b
        MATCH (bs:Lot {id: 'BS-0101'})
        MERGE (bs)-[:USED_IN]->(b)
    """)

    # Additional downstream products with no complaints yet, but still in recall scope.
    extra_oil_batches = [
        {"id": "MP-2410-03", "product": "PROD-016", "name": "Masala Peanuts Batch MP-2410-03"},
        {"id": "BH-2410-05", "product": "PROD-017", "name": "Bhujia Batch BH-2410-05"},
        {"id": "GC-2410-01", "product": "PROD-019", "name": "Groundnut Chikki Batch GC-2410-01"},
    ]
    net.query("""
        UNWIND $batches AS item
        MERGE (b:Batch {id: item.id})
        SET b.name = item.name,
            b.kind = 'final',
            b.mfd = '2026-10-05'
        WITH b, item
        MATCH (p:Product {id: item.product})
        MERGE (b)-[:OF_PRODUCT]->(p)
        WITH b
        MATCH (m:Batch {id: 'GOM-2409-04'})
        MERGE (m)-[:USED_IN]->(b)
    """, {"batches": extra_oil_batches})

    # Three namkeen batches for salt-only complaints (NK-2410-01, NK-2410-02, NK-2410-03)
    # SL-0042 is common to all 3; LOT-011 reaches only NK-01 through an intermediate mix.
    net.query("""
        MERGE (b1:Batch {id: 'NK-2410-01'})
        SET b1.name = 'Namkeen Mix NK-01', b1.kind = 'final'
        WITH b1
        MATCH (p:Product {id: 'PROD-018'}) MERGE (b1)-[:OF_PRODUCT]->(p)
        WITH b1
        MATCH (sl:Lot {id: 'SL-0042'}) MERGE (sl)-[:USED_IN]->(b1)
        WITH b1
        MERGE (m:Batch {id: 'NKM-2409-01'})
        SET m.name = 'Namkeen Seasoning Mix NKM-2409-01',
            m.kind = 'mix'
        WITH b1, m
        MATCH (l1:Lot {id: 'LOT-011'})
        MERGE (l1)-[:USED_IN]->(m)
        MERGE (m)-[:USED_IN]->(b1)

        MERGE (b2:Batch {id: 'NK-2410-02'})
        SET b2.name = 'Namkeen Mix NK-02', b2.kind = 'final'
        WITH b2
        MATCH (p:Product {id: 'PROD-018'}) MERGE (b2)-[:OF_PRODUCT]->(p)
        WITH b2
        MATCH (sl:Lot {id: 'SL-0042'}) MERGE (sl)-[:USED_IN]->(b2)
        WITH b2
        MATCH (l2:Lot {id: 'LOT-012'}) MERGE (l2)-[:USED_IN]->(b2)

        MERGE (b3:Batch {id: 'NK-2410-03'})
        SET b3.name = 'Namkeen Mix NK-03', b3.kind = 'final'
        WITH b3
        MATCH (p:Product {id: 'PROD-018'}) MERGE (b3)-[:OF_PRODUCT]->(p)
        WITH b3
        MATCH (sl:Lot {id: 'SL-0042'}) MERGE (sl)-[:USED_IN]->(b3)
        WITH b3
        MATCH (l3:Lot {id: 'LOT-013'}) MERGE (l3)-[:USED_IN]->(b3)

        MERGE (b4:Batch {id: 'NK-2410-04'})
        SET b4.name = 'Namkeen Mix NK-04', b4.kind = 'final'
        WITH b4
        MATCH (p:Product {id: 'PROD-018'}) MERGE (b4)-[:OF_PRODUCT]->(p)
        WITH b4
        MATCH (sl:Lot {id: 'SL-0042'}) MERGE (sl)-[:USED_IN]->(b4)

        MERGE (b5:Batch {id: 'NK-2410-05'})
        SET b5.name = 'Namkeen Mix NK-05', b5.kind = 'final'
        WITH b5
        MATCH (p:Product {id: 'PROD-018'}) MERGE (b5)-[:OF_PRODUCT]->(p)
        WITH b5
        MATCH (sl:Lot {id: 'SL-0042'}) MERGE (sl)-[:USED_IN]->(b5)

        MERGE (b6:Batch {id: 'NK-2410-06'})
        SET b6.name = 'Namkeen Mix NK-06', b6.kind = 'final'
        WITH b6
        MATCH (p:Product {id: 'PROD-018'}) MERGE (b6)-[:OF_PRODUCT]->(p)
        WITH b6
        MATCH (sl:Lot {id: 'SL-0042'}) MERGE (sl)-[:USED_IN]->(b6)
    """)

    # Batch for RP-0099 (RP-2410-01)
    net.query("""
        MERGE (b:Batch {id: 'RP-2410-01'})
        SET b.name = 'Spicy Mix RP-01', b.kind = 'final'
        WITH b
        MATCH (p:Product {id: 'PROD-018'}) MERGE (b)-[:OF_PRODUCT]->(p)
        WITH b
        MATCH (rp:Lot {id: 'RP-0099'}) MERGE (rp)-[:USED_IN]->(b)
    """)

    # Recall Notice for ZP-0412
    net.query("""
        MERGE (n:RecallNotice {id: 'NOTICE-ZIP-001'})
        SET n.reason = 'faulty_part',
            n.severity = 'I',
            n.text = 'Zipper lot ZP-0412 may detach, creating a choking risk.',
            n.source = 'supplier',
            n.issued_on = '2026-10-15'
        WITH n
        MATCH (l:Lot {id: 'ZP-0412'})
        MERGE (n)-[:FOR_LOT]->(l)
        WITH n
        MATCH (s:Supplier {id: 'SUP-013'})
        MERGE (n)-[:ISSUED_BY]->(s)
    """)

    # Notice for RX-7781 (has used_in == 0)
    net.query("""
        MERGE (n:RecallNotice {id: 'NOTICE-RAW-7781'})
        SET n.reason = 'microbial_contamination',
            n.severity = 'I',
            n.text = 'Raw extract lot RX-7781 failed microbial purity test.',
            n.source = 'supplier',
            n.issued_on = '2026-10-16'
        WITH n
        MATCH (l:Lot {id: 'RX-7781'})
        MERGE (n)-[:FOR_LOT]->(l)
        WITH n
        MATCH (s:Supplier {id: 'SUP-005'})
        MERGE (n)-[:ISSUED_BY]->(s)
    """)

    print("Network graph seeded successfully!")

    # ==========================================
    # 2. SEED BAZAARMART GRAPH
    # ==========================================
    bm = db.select_graph("bazaarmart")
    print("Clearing bazaarmart graph...")
    try:
        bm.query("MATCH (n) DETACH DELETE n")
    except Exception as e:
        print("BazaarMart clear note:", e)

    print("Seeding bazaarmart graph...")
    # Stores TH-01 through TH-12
    stores = [
        {"code": "TH-01", "name": "BazaarMart Thane West", "city": "Thane"},
        {"code": "TH-02", "name": "BazaarMart Mulund", "city": "Mumbai"},
        {"code": "TH-03", "name": "BazaarMart Pune FC Road", "city": "Pune"},
        {"code": "TH-04", "name": "BazaarMart Navi Mumbai", "city": "Navi Mumbai"},
        {"code": "TH-05", "name": "BazaarMart Andheri East", "city": "Mumbai"},
        {"code": "TH-06", "name": "BazaarMart Borivali", "city": "Mumbai"},
        {"code": "TH-07", "name": "BazaarMart Kalyan", "city": "Kalyan"},
        {"code": "TH-08", "name": "BazaarMart Dombivli", "city": "Dombivli"},
        {"code": "TH-09", "name": "BazaarMart Vashi", "city": "Navi Mumbai"},
        {"code": "TH-10", "name": "BazaarMart Pune Kothrud", "city": "Pune"},
        {"code": "TH-11", "name": "BazaarMart Nashik City", "city": "Nashik"},
        {"code": "TH-12", "name": "BazaarMart Nagpur Central", "city": "Nagpur"}
    ]
    for s in stores:
        bm.query("""
            MERGE (st:Store {code: $code})
            SET st.name = $name, st.city = $city
        """, s)

    # TRANSFER_LANE edges between stores
    transfer_lanes = [
        {"from": "TH-01", "to": "TH-02", "weight": 1},
        {"from": "TH-02", "to": "TH-03", "weight": 2},
        {"from": "TH-01", "to": "TH-04", "weight": 2},
        {"from": "TH-03", "to": "TH-10", "weight": 1},
        {"from": "TH-04", "to": "TH-09", "weight": 1},
        {"from": "TH-05", "to": "TH-06", "weight": 1},
        {"from": "TH-07", "to": "TH-08", "weight": 1}
    ]
    for tl in transfer_lanes:
        bm.query("""
            MATCH (s1:Store {code: $from})
            MATCH (s2:Store {code: $to})
            MERGE (s1)-[:TRANSFER_LANE {weight: $weight}]->(s2)
        """, tl)

    # Sections and Locations for all 12 stores
    for s in stores:
        code = s["code"]
        bm.query("""
            MATCH (st:Store {code: $store_code})
            MERGE (sec1:Section {id: $store_code + '-SEC-PackagedFoods'})
            SET sec1.name = 'Packaged Foods'
            MERGE (st)-[:HAS_SECTION]->(sec1)
            MERGE (loc1:Location {id: $store_code + '-LOC-Aisle-01'})
            SET loc1.code = 'Aisle-01', loc1.type = 'Shelf'
            MERGE (sec1)-[:HAS_LOCATION]->(loc1)

            MERGE (loc2:Location {id: $store_code + '-LOC-Aisle-02'})
            SET loc2.code = 'Aisle-02', loc2.type = 'Shelf'
            MERGE (sec1)-[:HAS_LOCATION]->(loc2)

            MERGE (sec2:Section {id: $store_code + '-SEC-Staples'})
            SET sec2.name = 'Staples'
            MERGE (st)-[:HAS_SECTION]->(sec2)
            MERGE (loc3:Location {id: $store_code + '-LOC-Shelf-01'})
            SET loc3.code = 'Shelf-01', loc3.type = 'Shelf'
            MERGE (sec2)-[:HAS_LOCATION]->(loc3)
        """, {"store_code": code})

    # Associates and Active Shift Logging
    associates = [
        {"id": "ASC-001", "name": "Associate 001", "store": "TH-01", "loc": "TH-01-LOC-Aisle-01"},
        {"id": "ASC-002", "name": "Associate 002", "store": "TH-02", "loc": "TH-02-LOC-Aisle-01"},
        {"id": "ASC-003", "name": "Associate 003", "store": "TH-03", "loc": "TH-03-LOC-Aisle-01"},
        {"id": "ASC-004", "name": "Associate 004", "store": "TH-04", "loc": "TH-04-LOC-Aisle-01"},
        {"id": "ASC-005", "name": "Associate 005", "store": "TH-05", "loc": "TH-05-LOC-Aisle-01"},
        {"id": "ASC-006", "name": "Associate 006", "store": "TH-06", "loc": "TH-06-LOC-Aisle-01"},
        {"id": "ASC-007", "name": "Associate 007", "store": "TH-07", "loc": "TH-07-LOC-Aisle-01"}
    ]
    for a in associates:
        bm.query("""
            MATCH (st:Store {code: $store})
            MATCH (loc:Location {id: $loc})
            MERGE (asc:Associate {id: $id})
            SET asc.name = $name, asc.role = 'Stock Associate'
            MERGE (asc)-[:WORKS_AT]->(st)
            MERGE (asc)-[:LOGGED_INTO {active: true}]->(loc)
        """, a)

    # Batch References
    batch_ref_ids = [
        "MP-2410-01", "MP-2410-02", "MP-2410-03",
        "BH-2410-03", "BH-2410-04", "BH-2410-05", "GC-2410-01",
        "NK-2410-01", "NK-2410-02", "NK-2410-03", "NK-2410-04", "NK-2410-05", "NK-2410-06",
        "RP-2410-01"
    ]
    for i in range(1, 51):
        batch_ref_ids.append(f"BAT-{i:03d}-01")

    for b_id in batch_ref_ids:
        bm.query("""
            MERGE (br:BatchRef {id: $id})
            SET br.network_batch_id = $id
        """, {"id": b_id})

    # Deliveries and Stock for hero groundnut-oil batches.
    # MP-2410-01 -> TH-01
    bm.query("""
        MATCH (br:BatchRef {id: 'MP-2410-01'})
        MATCH (st:Store {code: 'TH-01'})
        MATCH (loc:Location {id: 'TH-01-LOC-Aisle-01'})
        MERGE (br)-[:DELIVERED_TO {qty: 50, on: '2026-10-10'}]->(st)
        MERGE (br)-[:STOCKED_AT {qty: 25, status: 'available'}]->(loc)
    """)

    # MP-2410-02 -> TH-02
    bm.query("""
        MATCH (br:BatchRef {id: 'MP-2410-02'})
        MATCH (st:Store {code: 'TH-02'})
        MATCH (loc:Location {id: 'TH-02-LOC-Aisle-01'})
        MERGE (br)-[:DELIVERED_TO {qty: 50, on: '2026-10-10'}]->(st)
        MERGE (br)-[:STOCKED_AT {qty: 30, status: 'available'}]->(loc)
    """)

    # BH-2410-03 -> TH-03
    bm.query("""
        MATCH (br:BatchRef {id: 'BH-2410-03'})
        MATCH (st:Store {code: 'TH-03'})
        MATCH (loc:Location {id: 'TH-03-LOC-Aisle-01'})
        MERGE (br)-[:DELIVERED_TO {qty: 50, on: '2026-10-10'}]->(st)
        MERGE (br)-[:STOCKED_AT {qty: 20, status: 'available'}]->(loc)
    """)

    # BH-2410-04 -> TH-04 (delivered BUT NOT STOCKED - tests unstocked store shelf_view!)
    bm.query("""
        MATCH (br:BatchRef {id: 'BH-2410-04'})
        MATCH (st:Store {code: 'TH-04'})
        MERGE (br)-[:DELIVERED_TO {qty: 50, on: '2026-10-10'}]->(st)
    """)

    # Unreported downstream exposure: stock is still available at three more stores.
    additional_oil_deliveries = [
        ("MP-2410-03", "TH-04", 18),
        ("BH-2410-05", "TH-05", 22),
        ("GC-2410-01", "TH-06", 16),
    ]
    for batch_id, store_code, quantity in additional_oil_deliveries:
        bm.query("""
            MATCH (br:BatchRef {id: $batch_id})
            MATCH (st:Store {code: $store_code})
            MATCH (loc:Location {id: $location_id})
            MERGE (br)-[:DELIVERED_TO {qty: 40, on: '2026-10-11'}]->(st)
            MERGE (br)-[:STOCKED_AT {qty: $quantity, status: 'available'}]->(loc)
        """, {
            "batch_id": batch_id,
            "store_code": store_code,
            "location_id": f"{store_code}-LOC-Aisle-01",
            "quantity": quantity,
        })

    # Deliveries for namkeen / salt batches to stores TH-05 through TH-10
    namkeen_deliveries = [
        ("NK-2410-01", "TH-05", "TH-05-LOC-Aisle-01"),
        ("NK-2410-02", "TH-06", "TH-06-LOC-Aisle-01"),
        ("NK-2410-03", "TH-07", "TH-07-LOC-Aisle-01"),
        ("NK-2410-04", "TH-08", "TH-08-LOC-Aisle-01"),
        ("NK-2410-05", "TH-09", "TH-09-LOC-Aisle-01"),
        ("NK-2410-06", "TH-10", "TH-10-LOC-Aisle-01")
    ]
    for b_id, s_code, l_id in namkeen_deliveries:
        bm.query("""
            MATCH (br:BatchRef {id: $b_id})
            MATCH (st:Store {code: $s_code})
            MATCH (loc:Location {id: $l_id})
            MERGE (br)-[:DELIVERED_TO {qty: 30, on: '2026-10-10'}]->(st)
            MERGE (br)-[:STOCKED_AT {qty: 15, status: 'available'}]->(loc)
        """, {"b_id": b_id, "s_code": s_code, "l_id": l_id})

    # Delivery and Stock for RP-2410-01 -> TH-01
    bm.query("""
        MATCH (br:BatchRef {id: 'RP-2410-01'})
        MATCH (st:Store {code: 'TH-01'})
        MATCH (loc:Location {id: 'TH-01-LOC-Aisle-01'})
        MERGE (br)-[:DELIVERED_TO {qty: 40}]->(st)
        MERGE (br)-[:STOCKED_AT {qty: 20, status: 'available'}]->(loc)
    """)

    # Purchases for RP-2410-01: EXACTLY 2 BOUGHT relationships for Check 6
    bm.query("""
        MERGE (c1:Customer {id: 'CUST-0001', name: 'Customer 0001'})
        MERGE (c2:Customer {id: 'CUST-0002', name: 'Customer 0002'})
        WITH c1, c2
        MATCH (br:BatchRef {id: 'RP-2410-01'})
        MERGE (c1)-[:BOUGHT {qty: 1, on: '2026-10-11'}]->(br)
        MERGE (c2)-[:BOUGHT {qty: 2, on: '2026-10-12'}]->(br)
    """)

    # General purchases for MP and BH batches
    bm.query("""
        MERGE (c3:Customer {id: 'CUST-0003', name: 'Customer 0003'})
        MERGE (c4:Customer {id: 'CUST-0004', name: 'Customer 0004'})
        WITH c3, c4
        MATCH (b1:BatchRef {id: 'MP-2410-01'})
        MATCH (b2:BatchRef {id: 'BH-2410-03'})
        MERGE (c3)-[:BOUGHT {qty: 1, on: '2026-10-12'}]->(b1)
        MERGE (c4)-[:BOUGHT {qty: 1, on: '2026-10-13'}]->(b2)
    """)

    print("BazaarMart graph seeded successfully!")
    print("\nDatabase is fully seeded and ready for eval.py!")


if __name__ == "__main__":
    seed_database()
