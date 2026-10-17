MATCH (l:Lot)
RETURN l.id AS id, l.material AS material
ORDER BY l.id
