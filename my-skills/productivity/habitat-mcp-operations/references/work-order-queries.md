# Work-order Query Notes

Read this reference only for Habitat work-order queries or analysis. Discover
the current tool schemas and enums before applying these notes.

## Query Semantics

- Call `mcp__habitat__getWorkOrderQueryEnums` before
  `mcp__habitat__listWorkOrder`, as required by the tool description.
- Categories and types are different. For a category such as deployment, use
  the returned `orderCategories` entry's `queryType` and `valueList` to build
  `orderTypeQuery`; the category code itself is not necessarily an order type.
- Use `queryFields` to map business fields to the appropriate query properties.
  String and dropdown filters use different DTO fields; inspect their schemas.

## Product-line Representation

Observed on September 14, 2026: the work-order enum returned code `1` for
SpaceSight, but code-based filters returned zero while an exact display-label
filter returned rows whose `productLine` was consistently `SpaceSight`.
The observed filter fragment was:

```json
{
  "productLineQuery": {
    "queryType": "EQ",
    "singleValue": "SpaceSight",
    "valueList": []
  }
}
```

This is an endpoint-specific observation, not a complete request template or
a rule for other Habitat objects. Use it only when SpaceSight is the requested
product line, retain the intended scope, and check the current enum and returned
field values. Handle schema errors using the main skill's reliability rules.

## Optional Work-order Metrics

- Use `statusByCategory` for display labels: the same status code can mean
  different things across categories. Preserve raw statuses before grouping.
- For a completion analysis, state which statuses count as complete.
  `COMPLETED + CLOSED` is one possible business definition, not a universal
  lifecycle rule. In the observed RND category, `COMPLETED` was labeled
  “待总结”; preserve that distinction.
- Show rejected, discarded, and canceled records separately from completed
  records. If excluding invalidated records from a rate, state the denominator.
- For requested elapsed-time analysis, verify the timestamp meaning and time
  basis before using `actualFinishTime - createTime`; exclude missing or
  negative durations and disclose the exclusions. A finish timestamp alone
  does not establish the record's current status. Report median alongside mean
  when summarizing skewed durations.
- Include active-item details only when the user needs unresolved work or
  exception analysis; use record code, title, owner, and relevant timestamps.
