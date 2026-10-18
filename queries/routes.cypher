CALL algo.SPpaths({
  sourceNode: $from_stores,
  relTypes: ['TRANSFER_LANE'],
  weightProp: 'weight',
  maxCost: $max_days
})
YIELD path, weight
RETURN path, weight
