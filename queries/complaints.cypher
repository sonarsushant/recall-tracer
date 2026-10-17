MATCH (c:Complaint)-[:AT]->(s:Store)
MATCH (c)-[:ABOUT]->(br:BatchRef)
RETURN c.text AS text, s.code AS code, coalesce(s.name, s.code) AS name, br.id AS batch
ORDER BY c.id
