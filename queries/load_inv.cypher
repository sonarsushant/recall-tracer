MATCH (i:Investigation {id: $id})
RETURN i.id AS id, i.status AS status, i.summary AS summary, i.lot_id AS lot_id, i.batch_ids AS batch_ids
