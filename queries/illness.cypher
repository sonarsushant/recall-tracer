MATCH (c:Complaint)
RETURN c.text AS text
ORDER BY c.id
