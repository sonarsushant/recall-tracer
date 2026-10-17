
from falkordb import FalkorDB

# Connect to FalkorDB
db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("citymart")


def run(query, params=None):
    return graph.query(query, params or {})


def seed_stores():
    cities = ["Pune", "Mumbai", "Nashik", "Thane", "Nagpur"]

    for i in range(1, 6):
        code = f"CM-{i:02d}"

        run("""
            MERGE (s:Store {code: $code})
            SET s.city = $city
        """, {
            "code": code,
            "city": cities[i - 1]
        })

    print("5 CityMart stores created.")


def seed_sections_and_locations():
    sections = [
        "Staples",
        "Packaged Foods",
        "Beverages",
        "Apparel",
        "Godown",
        "Returns Desk"
    ]

    for i in range(1, 6):
        store_code = f"CM-{i:02d}"

        for j, section_name in enumerate(sections, start=1):
            section_id = f"{store_code}-SEC-{j:02d}"

            run("""
                MATCH (s:Store {code: $store_code})
                MERGE (sec:Section {id: $section_id})
                SET sec.name = $section_name
                MERGE (s)-[:HAS_SECTION]->(sec)
            """, {
                "store_code": store_code,
                "section_id": section_id,
                "section_name": section_name
            })

            for k in range(1, 4):
                location_id = f"{section_id}-LOC-{k:02d}"

                run("""
                    MATCH (sec:Section {id: $section_id})
                    MERGE (loc:Location {id: $location_id})
                    SET loc.code = $location_code
                    MERGE (sec)-[:HAS_LOCATION]->(loc)
                """, {
                    "section_id": section_id,
                    "location_id": location_id,
                    "location_code": f"LOC-{k:02d}"
                })

    print("30 sections and 90 locations created.")


def seed_batch_references():
    for product_number in range(1, 61):
        for batch_number in range(1, 6):
            network_batch_id = (
                f"BAT-{product_number:03d}-{batch_number:02d}"
            )

            reference_id = (
                f"CM-BREF-{product_number:03d}-{batch_number:02d}"
            )

            store_code = f"CM-{((product_number + batch_number - 2) % 5) + 1:02d}"

            run("""
                MERGE (br:BatchRef {id: $reference_id})
                SET br.network_batch_id = $network_batch_id

                WITH br
                MATCH (s:Store {code: $store_code})
                MERGE (br)-[:DELIVERED_TO {
                    on: '2026-10-10',
                    qty: 20
                }]->(s)
            """, {
                "reference_id": reference_id,
                "network_batch_id": network_batch_id,
                "store_code": store_code
            })

    print("300 batch references created and mapped.")


def seed_stock():
    result = run("""
        MATCH (br:BatchRef)
        RETURN br.id, br.network_batch_id
    """)

    for row in result.result_set:
        reference_id = row[0]

        # Choose one existing location for the stock record
        run("""
            MATCH (br:BatchRef {id: $reference_id})
            MATCH (loc:Location)
            WITH br, loc
            ORDER BY loc.id
            WITH br, collect(loc)[0] AS loc
            MERGE (br)-[r:STOCKED_AT]->(loc)
            SET r.qty = 10, r.status = 'in_stock'
        """, {"reference_id": reference_id})

    print("Stock relationships created.")


def verify_graph():
    result = run("""
        MATCH (n)
        RETURN labels(n)[0] AS node_type, count(n) AS total
        ORDER BY node_type
    """)

    print("\nCITYMART GRAPH SUMMARY")

    for row in result.result_set:
        print(f"{row[0]}: {row[1]}")


def main():
    print("Starting CityMart setup...\n")

    seed_stores()
    seed_sections_and_locations()
    seed_batch_references()
    seed_stock()
    verify_graph()

    print("\nCityMart setup completed!")


if __name__ == "__main__":
    main()
