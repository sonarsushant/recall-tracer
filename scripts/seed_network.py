
from falkordb import FalkorDB

# --------------------------------------------------
# 1. CONNECT TO FALKORDB
# --------------------------------------------------

db = FalkorDB(host="localhost", port=6379)
network = db.select_graph("network")


# --------------------------------------------------
# 2. CREATE A HELPER FUNCTION
# --------------------------------------------------

def run(query, params=None):
    """Execute a Cypher query on the network graph."""
    return network.query(query, params or {})


# --------------------------------------------------
# 3. CREATE SUPPLIERS
# --------------------------------------------------

def seed_suppliers():
    suppliers = []

    types = [
        "aggregator",
        "co_packer",
        "bottler",
        "garment_vendor",
        "packaging"
    ]

    for i in range(1, 21):
        suppliers.append({
            "id": f"SUP-{i:03d}",
            "name": f"Supplier {i:02d}",
            "type": types[(i - 1) % len(types)]
        })

    # Two garment vendors used by the apparel demo
    suppliers[12]["name"] = "ThreadWorks Garments"
    suppliers[13]["name"] = "StyleStitch Garments"

    for supplier in suppliers:
        run("""
            MERGE (s:Supplier {id: $id})
            SET s.name = $name, s.type = $type
        """, supplier)

    print("Suppliers created:", len(suppliers))
    return suppliers


# --------------------------------------------------
# 4. CREATE LOTS
# --------------------------------------------------

def seed_lots(suppliers):
    lots = []

    materials = [
        ("groundnut", "ingredient", "packaged_food"),
        ("salt", "ingredient", "packaged_food"),
        ("palm_oil", "ingredient", "packaged_food"),
        ("sugar", "ingredient", "beverage"),
        ("pet_bottle", "packaging", "beverage"),
        ("bottle_cap", "component", "beverage"),
        ("mango_concentrate", "ingredient", "beverage"),
        ("besan", "ingredient", "staples"),
        ("dye_red_14", "component", "apparel"),
        ("polyester_thread", "component", "apparel"),
        ("fabric_cotton", "component", "apparel"),
        ("zipper", "component", "apparel"),
        ("label_roll", "packaging", "staples"),
        ("button", "component", "apparel"),
        ("drawstring", "component", "apparel"),
    ]

    # Add the 15 named materials first
    for i, (material, kind, category) in enumerate(materials, 1):
        lots.append({
            "id": f"LOT-{i:03d}",
            "material": material,
            "kind": kind,
            "category": category,
            "supplier_id": suppliers[(i - 1) % len(suppliers)]["id"]
        })

    # Fill out the remaining lots deterministically
    for i in range(16, 91):
        material, kind, category = materials[(i - 1) % len(materials)]

        lots.append({
            "id": f"LOT-{i:03d}",
            "material": material,
            "kind": kind,
            "category": category,
            "supplier_id": suppliers[(i - 1) % len(suppliers)]["id"]
        })

    # Stable IDs used by the demo
    lots[0]["id"] = "GN-2214"
    lots[1]["id"] = "SL-0042"
    lots[2]["id"] = "PO-0611"
    lots[8]["id"] = "DY-0314"
    lots[11]["id"] = "ZP-0412"
    lots[9]["id"] = "TH-0099"

    for lot in lots:
        run("""
            MERGE (l:Lot {id: $id})
            SET l.material = $material,
                l.kind = $kind,
                l.category = $category,
                l.received_on = '2026-10-01'

            WITH l
            MATCH (s:Supplier {id: $supplier_id})
            MERGE (s)-[:SUPPLIED]->(l)
        """, lot)

    print("Lots created:", len(lots))
    return lots


# --------------------------------------------------
# 5. CREATE PRODUCTS
# --------------------------------------------------

def seed_products():
    products = []

    categories = {
        "staples": 15,
        "packaged_food": 20,
        "beverage": 10,
        "apparel": 15
    }

    for category, count in categories.items():
        for i in range(1, count + 1):
            product_id = f"PROD-{len(products) + 1:03d}"

            products.append({
                "id": product_id,
                "name": f"{category.replace('_', ' ').title()} Product {i:02d}",
                "brand": "BazaarSelect",
                "category": category
            })

    # Give the main outbreak products clear names
    products[15]["name"] = "Masala Peanuts"
    products[16]["name"] = "Bhujia"

    # Give four apparel products names for the zipper recall
    for i in range(45, 49):
        products[i]["name"] = f"Kidswear Style {i - 44}"

    for product in products:
        run("""
            MERGE (p:Product {id: $id})
            SET p.name = $name,
                p.brand = $brand,
                p.category = $category
        """, product)

    print("Products created:", len(products))
    return products


# --------------------------------------------------
# 6. CREATE BATCHES AND THEIR RELATIONSHIPS
# --------------------------------------------------

def seed_batches(suppliers, lots, products):
    batches = []

    # Index lots by material for selecting suitable ingredients
    lots_by_material = {}

    for lot in lots:
        lots_by_material.setdefault(
            lot["material"], []
        ).append(lot)

    for product_index, product in enumerate(products):
        category = product["category"]

        # Five batches per product = 300 batches
        for batch_number in range(1, 6):
            batch_id = (
                f"BAT-{product_index + 1:03d}-{batch_number:02d}"
            )

            batch = {
                "id": batch_id,
                "batch_no": batch_id,
                "product_id": product["id"],
                "supplier_id": suppliers[
                    (product_index + batch_number) % len(suppliers)
                ]["id"],
                "mfd": "2026-10-01",
                "expiry": "2027-10-01"
            }

            # Choose relevant ingredient/component lots
            if category == "packaged_food":
                chosen_materials = [
                    "groundnut", "salt", "palm_oil"
                ]
            elif category == "beverage":
                chosen_materials = [
                    "sugar", "pet_bottle", "bottle_cap"
                ]
            elif category == "apparel":
                chosen_materials = [
                    "fabric_cotton", "polyester_thread", "zipper"
                ]
            else:
                chosen_materials = ["besan", "salt", "label_roll"]

            selected_lots = []

            for material in chosen_materials:
                candidates = lots_by_material[material]
                selected_lots.append(
                    candidates[
                        (product_index + batch_number - 1)
                        % len(candidates)
                    ]
                )

            # Ensure the main outbreak lot reaches both products
            if product["name"] in ["Masala Peanuts", "Bhujia"]:
                selected_lots[0] = lots_by_material["groundnut"][0]

            # Ensure the faulty zipper lot reaches four kidswear styles
            if product["name"].startswith("Kidswear Style"):
                selected_lots[2] = next(
                    lot for lot in lots
                    if lot["id"] == "ZP-0412"
                )

            run("""
                MERGE (b:Batch {id: $id})
                SET b.batch_no = $batch_no,
                    b.mfd = $mfd,
                    b.expiry = $expiry

                WITH b
                MATCH (p:Product {id: $product_id})
                MERGE (b)-[:OF_PRODUCT]->(p)

                WITH b
                MATCH (s:Supplier {id: $supplier_id})
                MERGE (s)-[:MADE]->(b)
            """, batch)

            for lot in selected_lots:
                run("""
                    MATCH (l:Lot {id: $lot_id})
                    MATCH (b:Batch {id: $batch_id})
                    MERGE (l)-[:USED_IN]->(b)
                """, {
                    "lot_id": lot["id"],
                    "batch_id": batch_id
                })

            batches.append(batch)

    print("Batches created:", len(batches))
    return batches


# --------------------------------------------------
# 7. ADD A SAMPLE SUPPLIER RECALL NOTICE
# --------------------------------------------------

def seed_recall_notice():
    run("""
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
        MATCH (s:Supplier)
        WHERE s.type = 'garment_vendor'
        MERGE (n)-[:ISSUED_BY]->(s)
    """)

    print("Sample zipper recall notice created.")


# --------------------------------------------------
# 8. VERIFY THE DATA
# --------------------------------------------------

def verify_network():
    result = run("""
        MATCH (n)
        RETURN labels(n)[0] AS node_type, count(n) AS total
        ORDER BY node_type
    """)

    print("\nNETWORK GRAPH SUMMARY")

    for row in result.result_set:
        print(f"{row[0]}: {row[1]}")

    result = run("""
        MATCH (l:Lot {id: 'GN-2214'})-[:USED_IN]->(b:Batch)
              -[:OF_PRODUCT]->(p:Product)
        RETURN DISTINCT p.name
        ORDER BY p.name
    """)

    print("\nProducts using groundnut lot GN-2214:")
    for row in result.result_set:
        print("-", row[0])


# --------------------------------------------------
# 9. RUN EVERYTHING
# --------------------------------------------------

def main():
    print("Starting network seed...\n")

    suppliers = seed_suppliers()
    lots = seed_lots(suppliers)
    products = seed_products()
    seed_batches(suppliers, lots, products)
    seed_recall_notice()
    verify_network()

    print("\nNetwork seeding completed!")


if __name__ == "__main__":
    main()
