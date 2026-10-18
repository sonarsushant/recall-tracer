MERGE (i:Investigation {id: $id})
SET i.status = $status,
    i.summary = $summary,
    i.lot_id = $lot_id,
    i.batch_ids = $batch_ids,
    i.updated_at = timestamp()
RETURN i.id AS id, i.status AS status
