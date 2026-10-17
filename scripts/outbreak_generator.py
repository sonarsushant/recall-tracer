
from falkordb import FalkorDB

# Connect to FalkorDB
db = FalkorDB(host="localhost", port=6379)

# Select our two graphs
network = db.select_graph("network")
bazaarmart = db.select_graph("bazaarmart")

print("Connected to FalkorDB!")

print("Network and BazaarMart graphs selected.")



# Find products and batches linked to the suspected lot
query = """
MATCH (l:Lot {id: 'GN-2214'})-[:USED_IN]->(b:Batch)-[:OF_PRODUCT]->(p:Product)
RETURN DISTINCT p.name AS product, b.id AS batch_id
ORDER BY product, batch_id
"""

result = network.query(query)

print("\nProducts and batches affected by GN-2214:")

for row in result.result_set:
    print("Product:", row[0], "| Batch:", row[1])


# Find affected batches in BazaarMart
query = """
MATCH (br:BatchRef)
WHERE br.network_batch_id IN $batch_ids
RETURN DISTINCT br.id, br.network_batch_id
ORDER BY br.network_batch_id
"""

# Collect the affected network batch IDs
network_query = """
MATCH (l:Lot {id: 'GN-2214'})-[:USED_IN]->(b:Batch)
RETURN DISTINCT b.id
"""

network_result = network.query(network_query)
batch_ids = [row[0] for row in network_result.result_set]

# Search for matching references in BazaarMart
result = bazaarmart.query(query, {"batch_ids": batch_ids})

print("\nAffected batch references in BazaarMart:")

for row in result.result_set:
    print("Reference:", row[0], "| Network batch:", row[1])

print("\nTotal affected batch references:", len(result.result_set))


# Find affected stores and customers in BazaarMart
query = """
MATCH (br:BatchRef)
WHERE br.network_batch_id IN $batch_ids

OPTIONAL MATCH (br)-[stock:STOCKED_AT]->(loc:Location)
OPTIONAL MATCH (loc)<-[:HAS_LOCATION]-(sec:Section)<-[:HAS_SECTION]-(s:Store)

OPTIONAL MATCH (c:Customer)-[purchase:BOUGHT]->(br)

RETURN
    br.id AS reference_id,
    br.network_batch_id AS network_batch,
    s.code AS store,
    loc.id AS location,
    stock.qty AS stock_qty,
    count(purchase) AS purchase_count,
    count(DISTINCT c) AS customer_count

ORDER BY network_batch
"""

# Get the affected batch IDs from the network graph
network_query = """
MATCH (l:Lot {id: 'GN-2214'})-[:USED_IN]->(b:Batch)
RETURN DISTINCT b.id
"""

network_result = network.query(network_query)
batch_ids = [row[0] for row in network_result.result_set]

# Query the BazaarMart graph
result = bazaarmart.query(query, {"batch_ids": batch_ids})

print("\nAffected stock and customer records:")

for row in result.result_set:
    print(
        f"Reference: {row[0]} | "
        f"Network batch: {row[1]} | "
        f"Store: {row[2]} | "
        f"Location: {row[3]} | "
        f"Stock: {row[4]} | "
        f"Purchases: {row[5]} | "
        f"Customers: {row[6]}"
    )

# Calculate overall recall impact

# Calculate overall recall impact

print("\n===== RECALL IMPACT REPORT =====")

# Get affected network batch IDs
query = """
MATCH (l:Lot {id: 'GN-2214'})-[:USED_IN]->(b:Batch)
RETURN DISTINCT b.id
"""

result = network.query(query)
batch_ids = [row[0] for row in result.result_set]

# Get matching BazaarMart references
query = """
MATCH (br:BatchRef)
WHERE br.network_batch_id IN $batch_ids
RETURN br.id, br.network_batch_id
"""

result = bazaarmart.query(query, {"batch_ids": batch_ids})
references = result.result_set

reference_ids = [row[0] for row in references]

print("Affected network batches:", len(batch_ids))
print("Affected BazaarMart references:", len(reference_ids))

# Calculate stock using the reference IDs
query = """
MATCH (br:BatchRef)-[r:STOCKED_AT]->(:Location)
WHERE br.id IN $reference_ids
RETURN sum(r.qty)
"""

result = bazaarmart.query(query, {"reference_ids": reference_ids})
total_stock = result.result_set[0][0]

print("Total stock quantity:", total_stock)

# Count distinct customers
query = """
MATCH (c:Customer)-[:BOUGHT]->(br:BatchRef)
WHERE br.id IN $reference_ids
RETURN count(DISTINCT c)
"""

result = bazaarmart.query(query, {"reference_ids": reference_ids})
customers = result.result_set[0][0]

print("Distinct linked customers:", customers)

# Store-level recall report

print("\n===== STORE RECALL REPORT =====")

query = """
MATCH (br:BatchRef)-[r:STOCKED_AT]->(loc:Location)
WHERE br.network_batch_id STARTS WITH 'BAT-016'
   OR br.network_batch_id STARTS WITH 'BAT-017'
   OR br.network_batch_id IN [
       'BAT-018-02', 'BAT-019-01', 'BAT-021-05',
       'BAT-022-04', 'BAT-023-03', 'BAT-024-02',
       'BAT-025-01', 'BAT-027-05', 'BAT-028-04',
       'BAT-029-03', 'BAT-030-02', 'BAT-031-01',
       'BAT-033-05', 'BAT-034-04', 'BAT-035-03'
   ]
MATCH (loc)<-[:HAS_LOCATION]-(sec:Section)
      <-[:HAS_SECTION]-(s:Store)
RETURN
    s.code,
    count(DISTINCT br.id),
    sum(r.qty)
ORDER BY s.code
"""

result = bazaarmart.query(query)

for row in result.result_set:
    print(
        "Store:", row[0],
        "| Affected references:", row[1],
        "| Stock quantity:", row[2]
    )
    
    
# Generate store recall action tasks

print("\n===== STORE RECALL ACTION TASKS =====")

query = """
MATCH (br:BatchRef)-[r:STOCKED_AT]->(loc:Location)
WHERE br.network_batch_id IN $batch_ids
MATCH (loc)<-[:HAS_LOCATION]-(sec:Section)
      <-[:HAS_SECTION]-(s:Store)
RETURN
    s.code AS store,
    collect(DISTINCT br.id) AS references,
    sum(r.qty) AS stock_quantity
ORDER BY s.code
"""

query_batches = """
MATCH (l:Lot {id: 'GN-2214'})-[:USED_IN]->(b:Batch)
RETURN DISTINCT b.id
"""

result = network.query(query_batches)
batch_ids = [row[0] for row in result.result_set]

result = bazaarmart.query(query, {"batch_ids": batch_ids})

for row in result.result_set:
    store = row[0]
    references = row[1]
    stock_quantity = row[2]

    print(f"\nStore: {store}")
    print(f"Affected references: {references}")
    print(f"Recorded stock quantity: {stock_quantity}")
    print("Actions:")
    print("1. Quarantine the affected stock.")
    print("2. Stop sales of affected batches.")
    print("3. Verify physical stock against the recorded quantity.")
    print("4. Report completion to the recall coordinator.")


# Save recall tasks in BazaarMart graph

print("\n===== SAVING RECALL TASKS =====")

query_batches = """
MATCH (l:Lot {id: 'GN-2214'})-[:USED_IN]->(b:Batch)
RETURN DISTINCT b.id
"""

result = network.query(query_batches)
batch_ids = [row[0] for row in result.result_set]

query_stores = """
MATCH (br:BatchRef)-[r:STOCKED_AT]->(loc:Location)
WHERE br.network_batch_id IN $batch_ids
MATCH (loc)<-[:HAS_LOCATION]-(sec:Section)
      <-[:HAS_SECTION]-(s:Store)
RETURN
    s.code AS store,
    collect(DISTINCT br.id) AS references,
    sum(r.qty) AS stock_quantity
ORDER BY store
"""

result = bazaarmart.query(
    query_stores,
    {"batch_ids": batch_ids}
)

for row in result.result_set:
    store_code = row[0]
    references = row[1]
    stock_quantity = row[2]

    save_query = """
    MATCH (s:Store {code: $store_code})
   
MERGE (t:RecallTask {task_id: $task_id})
ON CREATE SET
    t.incident_id = 'GN-2214',
    t.status = 'pending',
    t.action = 'Quarantine affected stock and stop sales',
    t.batch_references = $references,
    t.stock_quantity = $stock_quantity
ON MATCH SET
    t.incident_id = 'GN-2214',
    t.action = 'Quarantine affected stock and stop sales',
    t.batch_references = $references,
    t.stock_quantity = $stock_quantity
MERGE (s)-[:HAS_RECALL_TASK]->(t)
RETURN t.task_id

    """

    task_id = "TASK-GN2214-" + store_code

    saved = bazaarmart.query(
        save_query,
        {
            "store_code": store_code,
            "task_id": task_id,
            "references": references,
            "stock_quantity": stock_quantity
        }
    )

    print("Saved:", task_id, "| Store:", store_code)

print("\nRecall tasks saved.")


# Verify saved recall tasks

print("\n===== VERIFY SAVED RECALL TASKS =====")

query = """
MATCH (s:Store)-[:HAS_RECALL_TASK]->(t:RecallTask)
WHERE t.incident_id = 'GN-2214'
RETURN
    t.task_id,
    s.code,
    t.status,
    t.stock_quantity,
    size(t.batch_references)
ORDER BY s.code
"""

result = bazaarmart.query(query)

for row in result.result_set:
    print(
        "Task:", row[0],
        "| Store:", row[1],
        "| Status:", row[2],
        "| Stock:", row[3],
        "| References:", row[4]
    )

print("Total saved tasks:", len(result.result_set))


# Update a recall task status

task_id = "TASK-GN2214-TH-07"
new_status = "in_progress"

query = """
MATCH (t:RecallTask {task_id: $task_id})
SET t.status = $new_status
RETURN t.task_id, t.status
"""

result = bazaarmart.query(
    query,
    {
        "task_id": task_id,
        "new_status": "completed"
    }
)

print("\n===== UPDATE RECALL TASK =====")

if result.result_set:
    row = result.result_set[0]
    print("Task:", row[0])
    print("Updated status:", row[1])
else:
    print("Task not found.")
