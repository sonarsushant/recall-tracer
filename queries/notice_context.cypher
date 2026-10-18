MATCH (l:Lot {id: $lot})
OPTIONAL MATCH (s:Supplier)-[:SUPPLIED]->(l)
OPTIONAL MATCH (n:RecallNotice)-[:FOR_LOT]->(l)
OPTIONAL MATCH (l)-[:USED_IN]->(target)
RETURN l.material AS material,
       coalesce(s.name, s.id, 'Unknown') AS supplier,
       n.id AS notice_id,
       n.text AS notice_text,
       n.severity AS notice_severity,
       count(DISTINCT target) AS used_in
