MATCH (br:BatchRef)-[stock:STOCKED_AT]->(loc:Location)
WHERE br.id IN $batch_ids AND stock.status = 'available'
MATCH (s:Store)-[:HAS_SECTION]->(sec:Section)-[:HAS_LOCATION]->(loc)
MATCH (a:Associate)-[log:LOGGED_INTO]->(loc)
WHERE log.active = true
RETURN loc.code AS location_code,
       stock.qty AS qty,
       s.code AS store_code,
       a.name AS associate_name,
       br.id AS batch_id
ORDER BY s.code, loc.code
