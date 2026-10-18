MATCH (t:Task {id: $id})
SET t.status = 'done'
RETURN t.id AS id, t.status AS status
