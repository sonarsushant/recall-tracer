MATCH path = (l:Lot {id: $lot})-[:USED_IN*1..2]->(b:Batch {kind: 'final'})-[:OF_PRODUCT]->(p:Product)
RETURN b.id AS id, p.name AS name, [n in nodes(path) | coalesce(n.id, n.name)] AS path
ORDER BY b.id
