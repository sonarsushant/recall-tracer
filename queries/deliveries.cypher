MATCH (br:BatchRef)-[:DELIVERED_TO]->(s:Store)
WHERE br.id IN $batch_ids
RETURN DISTINCT s.code AS store
ORDER BY store
