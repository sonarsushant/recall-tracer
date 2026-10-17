UNWIND $store_batches AS sb
UNWIND sb.batch_ids AS b_id
MATCH (b:Batch {id: b_id})
WITH sb.store AS store, b
MATCH path = (l:Lot)-[:USED_IN*1..1]->(b)
RETURN l.id AS lot,
       l.material AS material,
       collect(DISTINCT store) AS stores,
       collect(DISTINCT [n in nodes(path) | coalesce(n.id, n.name)]) AS paths
ORDER BY lot
