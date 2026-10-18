
from falkordb import FalkorDB

# Connect to FalkorDB running locally
db = FalkorDB(host="localhost", port=6379)

# Select our three graphs
network = db.select_graph("network")
bazaarmart = db.select_graph("bazaarmart")
citymart = db.select_graph("citymart")


def seed_network():
    print("Seeding network graph...")

    network.query("""
        CREATE
        (s:Supplier {
            id: 'SUP-01',
            name: 'AgroSource'
        }),
        (l:Lot {
            id: 'GN-2214',
            material: 'groundnut',
            kind: 'ingredient',
            category: 'packaged_food'
        }),
        (b:Batch {
            id: 'BAT-001',
            batch_no: 'MP-2409-17'
        }),
        (p:Product {
            id: 'PROD-01',
            name: 'Masala Peanuts',
            brand: 'BazaarSelect',
            category: 'packaged_food'
        }),
        (s)-[:SUPPLIED]->(l),
        (l)-[:USED_IN]->(b),
        (b)-[:OF_PRODUCT]->(p)
    """)

    print("Network graph seeded!")


def seed_chain(graph, store_code, city):
    print(f"Seeding {store_code}...")

    graph.query("""
        CREATE
        (s:Store {
            code: $store_code,
            city: $city
        }),
        (sec:Section {
            id: $section_id,
            name: 'Packaged Foods'
        }),
        (loc:Location {
            id: $location_id,
            code: 'Aisle 9-C',
            type: 'shelf'
        }),
        (b:BatchRef {
            id: 'BAT-001',
            batch_no: 'MP-2409-17',
            product_name: 'Masala Peanuts',
            category: 'packaged_food'
        }),
        (s)-[:HAS_SECTION]->(sec),
        (sec)-[:HAS_LOCATION]->(loc),
        (b)-[:DELIVERED_TO {
            on: '2026-10-10',
            qty: 65
        }]->(s),
        (b)-[:STOCKED_AT {
            qty: 22,
            status: 'available'
        }]->(loc)
    """, {
        "store_code": store_code,
        "city": city,
        "section_id": f"{store_code}-SEC-01",
        "location_id": f"{store_code}-LOC-01"
    })

    print(f"{store_code} seeded!")


def main():
    seed_network()

    seed_chain(
        bazaarmart,
        "TH-07",
        "Thane"
    )

    seed_chain(
        citymart,
        "CM-01",
        "Mumbai"
    )

    print("All three graphs seeded successfully!")

    print("Graphs:", db.list_graphs())

    db.close()


if __name__ == "__main__":
    main()
