# Query Console

The Query Console is an interactive Cypher editor accessible from the sidebar at `/app/query-console`.
It is designed for ad-hoc exploration of the Neo4j graph without requiring a saved report.

## Layout

The console is split into three areas:

- **Database browser** (left, collapsible) — shows the available schema from Neo4j.
- **Result panel** (top right) — displays query results in Graph, Table, or Raw format.
- **Query editor** (bottom right) — a multi-line Cypher editor with a Run button.

Press **Ctrl+Enter** (or **Cmd+Enter** on macOS) to run the query without reaching for the mouse.

## Database Browser

The collapsible left panel queries Neo4j on load to discover the current schema:

| Section | Source | Click action |
|---------|--------|--------------|
| **NODES** | `CALL db.labels()` | Runs a path query for that label: `MATCH path = (n:\`Label\`)-[r]-(m) RETURN path LIMIT 25` |
| **RELATIONSHIPS** | `CALL db.relationshipTypes()` | Runs a path query for that type: `MATCH path = (a)-[r:\`TYPE\`]->(b) RETURN path LIMIT 25` |
| **PROPERTY KEYS** | `CALL db.propertyKeys()` | Runs a node query for that property: `MATCH (n) WHERE n.\`key\` IS NOT NULL RETURN n LIMIT 25` |

Clicking any item inserts the generated query into the editor and runs it immediately.
Node labels are colour-coded using the same palette as the graph panel, so colours are consistent across the UI.

## Result Tabs

Results are shown in up to three tabs depending on what the query returns:

| Tab | When shown | Description |
|-----|-----------|-------------|
| **Graph** | Only when the query returns graph-compatible data | Interactive node-link diagram. Clicking a node or relationship opens the detail panel. |
| **Table** | Always | Tabular view. Columns are auto-detected from the result shape — no specific return alias required. |
| **Raw** | Always | Full JSON response from the API. |

The console defaults to the Graph tab when the data supports it, otherwise the Table tab.

## Graph View

The graph view is the same panel used in reports. It supports:

- **`RETURN path`** queries — Neo4j path objects are automatically unpacked into nodes and relationships.
- **Explicit map format** — `RETURN {nodes: [...], links: [...]}` with any alias (or none).

When a node or relationship is clicked, a detail panel slides in from the right showing its properties.
Clicking the canvas background deselects the item and shows a graph summary (node counts by label, relationship counts by type).

## Table View

The table view accepts any query return shape:

- `RETURN n.name AS name, n.org AS org` — named columns used directly.
- `RETURN n` — Neo4j node objects are unwrapped; properties become columns.
- `RETURN {key: value, ...}` — map values are unwrapped; keys become columns.

Nested objects (such as node or relationship values inside a path) are rendered in a human-readable format:
- Nodes → `(Label) name`
- Relationships → `[TYPE]`
- Paths → `(StartLabel) name → (EndLabel) name`
