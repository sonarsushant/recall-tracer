OPTIONAL MATCH (br:BatchRef)<-[b:BOUGHT]-(c:Customer)
WHERE br.id IN $batch_ids
RETURN count(b) AS count
