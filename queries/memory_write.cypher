MERGE (f:Finding {id: $id})
SET f.text = $text,
    f.learned_at = $at,
    f.kind = 'root_cause',
    f.lot = $lot,
    f.lot_id = $lot
WITH f
UNWIND $batch_ids AS b_id
MATCH (br:BatchRef {id: b_id})
MERGE (f)-[:ABOUT]->(br)
RETURN f.id AS id
