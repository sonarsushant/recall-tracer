MATCH (b:Batch)
OPTIONAL MATCH (b)-[:OF_PRODUCT]->(p:Product)
RETURN b.id AS id, coalesce(p.name, b.name, b.id) AS name, coalesce(b.kind, 'final') AS kind
ORDER BY b.id
