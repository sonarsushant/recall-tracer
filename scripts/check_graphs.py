
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)

for name in ["network", "bazaarmart", "citymart"]:
    graph = db.select_graph(name)

    result = graph.ro_query("""
        MATCH (n)
        RETURN labels(n) AS labels, count(n) AS total
    """)

    print(f"\n{name}:")

    for row in result.result_set:
        print(row)


