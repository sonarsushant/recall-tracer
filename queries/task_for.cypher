MATCH (t:Task)-[:FROM]->(i:Investigation {id: $id})
RETURN t.id AS id,
       t.store AS store,
       t.location AS location_code,
       t.assignee AS assignee_name,
       t.due_by AS due_by,
       t.batch AS batch,
       t.qty AS qty,
       t.status AS status
ORDER BY t.id
