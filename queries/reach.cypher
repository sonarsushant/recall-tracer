MATCH (l:Lot {id: $lot})-[:USED_IN*1..2]->(b:Batch {kind: 'final'})
RETURN DISTINCT b.id AS id
ORDER BY id
