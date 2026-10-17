MATCH (br:BatchRef)-[d:DELIVERED_TO]->(s:Store)
WHERE br.id IN $batch_ids
OPTIONAL MATCH (s)-[:HAS_SECTION]->(sec:Section)-[:HAS_LOCATION]->(loc:Location)<-[stock:STOCKED_AT]-(br)
OPTIONAL MATCH (a:Associate)-[log:LOGGED_INTO]->(loc)
WHERE log.active = true
RETURN s.code AS store,
       s.name AS store_name,
       br.id AS batch_id,
       d.qty AS delivered_qty,
       sec.name AS section,
       loc.code AS aisle,
       stock.qty AS qty,
       a.name AS associate
ORDER BY s.code, br.id
