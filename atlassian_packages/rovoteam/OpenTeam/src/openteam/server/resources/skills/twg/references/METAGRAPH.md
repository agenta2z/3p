# Metagraph Cypher Reference

The **metagraph** is the schema/ontology graph for the Teamwork Graph (TWG). It represents all registered node types and their relationships as a graph itself — query it to discover what entities exist and how they connect.

- **~140 node types**, **~260+ edges**
- Query via Cypher (read-only)

---

## Schema

| Element | Cypher Label / Type | Description |
|---|---|---|
| Node | `NodeType` | A registered node type (e.g., JiraIssue) |
| Edge | `meta_relationship_type` | Connects source NodeType → target NodeType |
| Node property | `n.typeName` | Human-readable name (e.g., "JiraIssue") |
| Edge property | `r.typeName` | Relationship name (e.g., "issue-has-assignee") |
| Edge property | `r.category` | Category code (0=Canonical, 1=Activity, 2=Inferred, 3=Materialized, 4=Dynamic, 5=Logical) |

---

## Syntax Rules

1. **Match by `typeName`** — use `MATCH (n:NodeType {typeName: 'JiraIssue'})` to anchor queries. No need for ARI lookups.
2. **Label-only scans work** — `MATCH (n:NodeType) RETURN n.typeName LIMIT 200` lists all registered types.
3. **Always use directed edges** — `->` or `<-`. Bidirectional `--` is not supported.
4. **Use underscores** — `meta_relationship_type` not `meta-relationship-type` (hyphens = subtraction in Cypher).
5. **Do NOT use `end` as a variable name** — it is a reserved keyword. Use `dest`, `target`, etc.
6. **ORDER BY only works on properties** — e.g., `ORDER BY n.typeName`. NOT on computed values like `length(p)`.
7. **Relationship variables must be unique** — across UNION branches, use distinct names (`r1`, `r2`) or omit them (`[:meta_relationship_type]`).
8. **Integer IN-lists are not supported** — use `OR` instead (e.g., `WHERE r.category = 0 OR r.category = 1`).
9. **List comprehensions are not supported** — `[x IN nodes(p) | x.typeName]` will fail.
10. **Always use `LIMIT`** — especially on multi-hop and variable-length queries.
11. **Bound variable-length paths** — use `*1..3` not unbounded `*`.
12. **Always include `operationName`** — as a query parameter in the REST URL.

---

## Sample Queries

### 1. List all registered node types

```cypher
MATCH (n:NodeType)
RETURN n.typeName AS nodeType
LIMIT 200
```

### 2. Outbound connections from a node type

What does JiraIssue connect to?

```cypher
MATCH (from:NodeType {typeName: 'JiraIssue'})
OPTIONAL MATCH (from)-[r:meta_relationship_type]->(to:NodeType)
RETURN from.typeName AS sourceType, r.typeName AS relationship, to.typeName AS targetType, r.category AS category
```

### 3. Inbound connections to a node type

What connects TO IdentityUser?

```cypher
MATCH (to:NodeType {typeName: 'IdentityUser'})
OPTIONAL MATCH (from:NodeType)-[r:meta_relationship_type]->(to)
RETURN from.typeName AS sourceType, r.typeName AS relationship, to.typeName AS targetType, r.category AS category
```

### 4. Filter by relationship category

Only canonical (core) relationships from IdentityUser:

```cypher
MATCH (from:NodeType {typeName: 'IdentityUser'})-[r:meta_relationship_type]->(to:NodeType)
WHERE r.category = 0
RETURN from.typeName AS sourceType, r.typeName AS relationship, to.typeName AS targetType
```

Category codes: `0`=Canonical, `1`=Activity, `2`=Inferred, `3`=Materialized, `4`=Dynamic, `5`=Logical.

Multiple categories (use OR, not IN with integers):
```cypher
WHERE r.category = 0 OR r.category = 1
```

### 5. Both directions using UNION

All connections (in + out) for JiraIssue:

```cypher
MATCH (center:NodeType {typeName: 'JiraIssue'})
OPTIONAL MATCH (center)-[r:meta_relationship_type]->(neighbor:NodeType)
RETURN 'outbound' AS direction, center.typeName AS centerType, r.typeName AS relationship, neighbor.typeName AS connectedType
UNION
MATCH (center:NodeType {typeName: 'JiraIssue'})
OPTIONAL MATCH (neighbor:NodeType)-[r:meta_relationship_type]->(center)
RETURN 'inbound' AS direction, center.typeName AS centerType, r.typeName AS relationship, neighbor.typeName AS connectedType
```

### 6. Find relationship between two specific node types

What connects JiraIssue to IdentityUser?

```cypher
MATCH (from:NodeType {typeName: 'JiraIssue'})-[r:meta_relationship_type]->(to:NodeType {typeName: 'IdentityUser'})
RETURN from.typeName AS sourceType, r.typeName AS relationship, to.typeName AS targetType
```

### 7. Variable-length path traversal

Find paths from JiraIssue to ConfluencePage within 1–3 hops:

```cypher
MATCH p = (start:NodeType {typeName: 'JiraIssue'})-[:meta_relationship_type*1..3]->(dest:NodeType {typeName: 'ConfluencePage'})
RETURN start.typeName AS startType, dest.typeName AS destType, length(p) AS hops
LIMIT 10
```

Note: Variable-length paths don't expose per-hop edge names. Use explicit chained hops (query 8) for that.

### 8. Multi-hop paths with edge names at each step

**1-hop** — all outbound edges from JiraIssue:

```cypher
MATCH (from:NodeType {typeName: 'JiraIssue'})-[r:meta_relationship_type]->(to:NodeType)
RETURN from.typeName AS sourceType, r.typeName AS relationship, to.typeName AS targetType
LIMIT 20
```

**2-hop** — JiraIssue → ? → ConfluencePage, showing intermediate node and both edge names:

```cypher
MATCH (start:NodeType {typeName: 'JiraIssue'})-[r1:meta_relationship_type]->(mid:NodeType)-[r2:meta_relationship_type]->(dest:NodeType {typeName: 'ConfluencePage'})
RETURN start.typeName AS startType, r1.typeName AS edge1, mid.typeName AS via, r2.typeName AS edge2, dest.typeName AS destType
LIMIT 20
```

**3-hop** — JiraIssue → ? → ? → ConfluencePage:

```cypher
MATCH (start:NodeType {typeName: 'JiraIssue'})-[r1:meta_relationship_type]->(m1:NodeType)-[r2:meta_relationship_type]->(m2:NodeType)-[r3:meta_relationship_type]->(dest:NodeType {typeName: 'ConfluencePage'})
RETURN start.typeName AS startType, r1.typeName AS edge1, m1.typeName AS via1, r2.typeName AS edge2, m2.typeName AS via2, r3.typeName AS edge3, dest.typeName AS destType
LIMIT 20
```

### 9. 2-hop neighborhood exploration

Find all node types reachable within 2 hops from JiraIssue:

```cypher
MATCH p = (center:NodeType {typeName: 'JiraIssue'})-[:meta_relationship_type*1..2]->(neighbor:NodeType)
RETURN center.typeName AS startType, neighbor.typeName AS reachableType, length(p) AS hops
LIMIT 50
```
