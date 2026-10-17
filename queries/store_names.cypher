MATCH (s:Store)
RETURN s.code AS code, coalesce(s.name, s.code) AS name
ORDER BY s.code
