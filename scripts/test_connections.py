
from falkordb import FalkorDB

try:
    # Connect to FalkorDB
    db = FalkorDB(host="localhost", port=6379)

    # Test the connection
    graphs = db.list_graphs()

    print("Connected to FalkorDB successfully!")
    print("Existing graphs:", graphs)

    # Run a simple query
    graph = db.select_graph("network")

    result = graph.query("""
        RETURN 'Connection successful' AS message
    """)

    print(result.result_set)

except Exception as e:
    print("Connection failed!")
    print("Error:", e)
