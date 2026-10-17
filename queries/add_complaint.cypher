MATCH (s:Store {code: $store})
MATCH (br:BatchRef {id: $batch})
CREATE (c:Complaint {id: $id, text: $text})
CREATE (c)-[:AT]->(s)
CREATE (c)-[:ABOUT]->(br)
RETURN c.id AS id
