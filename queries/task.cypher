MATCH (i:Investigation {id: $inv})
MATCH (s:Store {code: $store})-[:HAS_SECTION]->(:Section)-[:HAS_LOCATION]->(loc:Location {code: $location_code})
MATCH (a:Associate {name: $assignee_name})
MERGE (t:Task {id: $task_id})
SET t.due_by = $due_by,
    t.batch = $batch,
    t.qty = $qty,
    t.store = $store,
    t.location = $location_code,
    t.assignee = $assignee_name,
    t.status = 'pending'
MERGE (t)-[:FROM]->(i)
MERGE (t)-[:FOR_LOCATION]->(loc)
MERGE (t)-[:ASSIGNED_TO]->(a)
SET i.status = 'closed'
RETURN t.id AS id, t.status AS status
