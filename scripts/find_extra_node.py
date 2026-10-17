
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("network")

queries = [
    ("Suppliers", """
        MATCH (n:Supplier)
        RETURN n.id, n.name
        ORDER BY n.id
    """),
    ("Products", """
        MATCH (n:Product)
        RETURN n.id, n.name
        ORDER BY n.id
    """),
    ("Batches", """
        MATCH (n:Batch)
        RETURN n.id, n.batch_no
        ORDER BY n.id
    """)
]

for title, query in queries:
    print(f"\n--- {title} ---")
    result = graph.ro_query(query)

    for row in result.result_set:
        print(row)
