MATCH (f:Finding)
WHERE f.lot = $subject_id OR f.lot_id = $subject_id OR (f)-[:ABOUT]->(:BatchRef {id: $subject_id})
RETURN f.text AS text, f.learned_at AS learned_at
ORDER BY f.learned_at DESC
