
from falkordb import FalkorDB

# Connect to FalkorDB
db = FalkorDB(host="localhost", port=6379)

# Select the BazaarMart graph
graph = db.select_graph("bazaarmart")


def run(query, params=None):
    return graph.query(query, params or {})


def seed_stores():
    cities = [
        "Mumbai", "Thane", "Navi Mumbai",
        "Pune", "Hyderabad"
    ]

    for i in range(1, 13):
        code = f"TH-{i:02d}"
        city = cities[(i - 1) % len(cities)]

        run("""
            MERGE (s:Store {code: $code})
            SET s.city = $city
        """, {"code": code, "city": city})

    print("12 stores created.")


def seed_sections():
    sections = [
        "Staples",
        "Packaged Foods",
        "Beverages",
        "Apparel",
        "Godown",
        "Returns Desk"
    ]

    for i in range(1, 13):
        store_code = f"TH-{i:02d}"

        for j, name in enumerate(sections, start=1):
            section_id = f"{store_code}-SEC-{j:02d}"

            run("""
                MATCH (s:Store {code: $store_code})
                MERGE (sec:Section {id: $section_id})
                SET sec.name = $name
                MERGE (s)-[:HAS_SECTION]->(sec)
            """, {
                "store_code": store_code,
                "section_id": section_id,
                "name": name
            })

    print("72 sections created.")


def seed_locations():
    location_types = {
        "Staples": ["Shelf", "Aisle"],
        "Packaged Foods": ["Shelf", "Endcap"],
        "Beverages": ["Chiller", "Shelf"],
        "Apparel": ["Rack", "Trial Room"],
        "Godown": ["Storage"],
        "Returns Desk": ["Counter"]
    }

    for i in range(1, 13):
        store_code = f"TH-{i:02d}"

        for j, section_name in enumerate([
            "Staples", "Packaged Foods", "Beverages",
            "Apparel", "Godown", "Returns Desk"
        ], start=1):

            section_id = f"{store_code}-SEC-{j:02d}"

            for k in range(1, 4):
                location_id = f"{section_id}-LOC-{k:02d}"
                location_code = f"{section_name}-{k:02d}"
                location_type = location_types[section_name][
                    (k - 1) % len(location_types[section_name])
                ]

                run("""
                    MATCH (sec:Section {id: $section_id})
                    MERGE (loc:Location {id: $location_id})
                    SET loc.code = $location_code,
                        loc.type = $location_type
                    MERGE (sec)-[:HAS_LOCATION]->(loc)
                """, {
                    "section_id": section_id,
                    "location_id": location_id,
                    "location_code": location_code,
                    "location_type": location_type
                })

    print("216 locations created.")


def seed_associates():
    roles = ["Cashier", "Manager", "Stock Associate", "Supervisor"]

    for i in range(1, 71):
        associate_id = f"ASC-{i:03d}"
        store_code = f"TH-{((i - 1) % 12) + 1:02d}"

        run("""
            MERGE (a:Associate {id: $id})
            SET a.name = $name,
                a.role = $role
            WITH a
            MATCH (s:Store {code: $store_code})
            MERGE (a)-[:WORKS_AT]->(s)
        """, {
            "id": associate_id,
            "name": f"Associate {i:03d}",
            "role": roles[(i - 1) % len(roles)],
            "store_code": store_code
        })

    print("70 associates created and connected to stores.")


def seed_customers():
    tiers = ["Basic", "Silver", "Gold"]

    for i in range(1, 1501):
        customer_id = f"CUST-{i:04d}"

        run("""
            MERGE (c:Customer {id: $id})
            SET c.name = $name,
                c.loyalty_tier = $tier
        """, {
            "id": customer_id,
            "name": f"Customer {i:04d}",
            "tier": tiers[(i - 1) % len(tiers)]
        })

    print("1500 customers created.")


def seed_purchases():
    for i in range(1, 12001):
        customer_id = f"CUST-{((i - 1) % 1500) + 1:04d}"
        store_number = ((i - 1) % 12) + 1
        store_code = f"TH-{store_number:02d}"
        batch_ref_id = f"BREF-{((i - 1) % 300) + 1:03d}"
        purchase_date = f"2026-10-{((i - 1) % 15) + 1:02d}"

        run("""
            MATCH (c:Customer {id: $customer_id})
            MATCH (s:Store {code: $store_code})
            MERGE (br:BatchRef {id: $batch_ref_id})
            MERGE (c)-[b:BOUGHT {
                purchase_id: $purchase_id
            }]->(br)
            SET b.on = $purchase_date,
                b.qty = $qty,
                b.store = $store_code
            MERGE (br)-[:DELIVERED_TO]->(s)
        """, {
            "customer_id": customer_id,
            "store_code": store_code,
            "batch_ref_id": batch_ref_id,
            "purchase_id": f"PUR-{i:05d}",
            "purchase_date": purchase_date,
            "qty": ((i - 1) % 3) + 1
        })

    print("12000 purchase relationships created.")


def link_batch_references():
    for i in range(1, 301):
        reference_id = f"BREF-{i:03d}"

        # Network batch IDs follow this pattern:
        # BAT-001-01, BAT-001-02, ... BAT-060-05
        product_number = ((i - 1) // 5) + 1
        batch_number = ((i - 1) % 5) + 1
        network_batch_id = f"BAT-{product_number:03d}-{batch_number:02d}"

        run("""
            MATCH (br:BatchRef {id: $reference_id})
            SET br.network_batch_id = $network_batch_id
        """, {
            "reference_id": reference_id,
            "network_batch_id": network_batch_id
        })

    print("Batch references mapped to network batch IDs.")


def seed_stock():
    for i in range(1, 301):
        reference_id = f"BREF-{i:03d}"
        store_number = ((i - 1) % 12) + 1
        store_code = f"TH-{store_number:02d}"

        section_number = ((i - 1) % 6) + 1
        location_number = ((i - 1) % 3) + 1

        section_id = f"{store_code}-SEC-{section_number:02d}"
        location_id = f"{section_id}-LOC-{location_number:02d}"

        run("""
            MATCH (br:BatchRef {id: $reference_id})
            MATCH (loc:Location {id: $location_id})
            MERGE (br)-[r:STOCKED_AT]->(loc)
            SET r.qty = $qty,
                r.status = 'in_stock'
        """, {
            "reference_id": reference_id,
            "location_id": location_id,
            "qty": (i % 20) + 1
        })

    print("300 stock relationships created.")


def seed_deliveries():
    for i in range(1, 301):
        reference_id = f"BREF-{i:03d}"
        store_number = ((i - 1) % 12) + 1
        store_code = f"TH-{store_number:02d}"

        run("""
            MATCH (br:BatchRef {id: $reference_id})
            MATCH (s:Store {code: $store_code})
            MERGE (br)-[r:DELIVERED_TO]->(s)
            SET r.on = '2026-10-10',
                r.qty = 100
        """, {
            "reference_id": reference_id,
            "store_code": store_code
        })

    print("300 delivery relationships created.")


def verify_graph():
    result = run("""
        MATCH (n)
        RETURN labels(n)[0] AS node_type, count(n) AS total
        ORDER BY node_type
    """)

    print("\nBAZAARMART GRAPH SUMMARY")
    for row in result.result_set:
        print(f"{row[0]}: {row[1]}")


def main():
    seed_stores()
    seed_sections()
    seed_locations()
    seed_associates()
    seed_customers()
    seed_purchases()
    link_batch_references()
    seed_stock()
    seed_deliveries()
    verify_graph()
    print("\nBazaarMart setup completed!")


if __name__ == "__main__":
    main()
