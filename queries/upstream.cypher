MATCH path = (l:Lot)-[:USED_IN*1..2]->(b:Batch)
WHERE b.id IN $batch_ids
RETURN l.id AS lot,
       l.material AS material,
       b.id AS batch_id,
       [n in nodes(path) | coalesce(n.id, n.name)] AS path
ORDER BY l.id, b.id
