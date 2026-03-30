# MCP Toolsets

## Purpose

Seizu exposes a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server at `/api/v1/mcp`.
LLM agents such as Claude can connect to this endpoint and call tools that run read-only Cypher queries against the Neo4j graph database.

Tools are grouped into **toolsets**. Each toolset contains one or more **tools**, where every tool is a parameterised Cypher query.
Both toolsets and tools maintain a full version history so changes can be audited and reverted.

## Managing Toolsets

Navigate to **MCP Toolsets** in the sidebar to view all toolsets.

Built-in tools provided by Seizu (the `seizu` toolset) are shown with a **Built-in** badge and cannot be edited or deleted.

> **Permissions:** Creating and editing toolsets and tools requires the `toolsets:write` / `tools:write` permission (`seizu-admin`). Deleting requires `toolsets:delete` / `tools:delete`. Restoring a historical version also requires `toolsets:write` / `tools:write`. Users with `seizu-viewer` or `seizu-editor` roles can view toolsets and tools but will not see **New toolset** / **New tool** buttons, and write/delete/restore actions in the **⋮** menu will be disabled.

From the list you can:

- Click a toolset name to view its tools.
- Open the **⋮** menu on any row to **Edit**, **View Tools**, **View history**, or **Delete** a toolset.

### Creating a toolset

Click **New toolset**. The form includes:

| Field | Description |
|-------|-------------|
| name | A user-friendly name. Used to namespace MCP tool names as `{toolset_name}__{tool_name}`. |
| description | Optional description shown in the UI. |
| enabled | When disabled, none of the toolset's tools are exposed via MCP. |

### Editing a toolset

Open the **⋮** menu and select **Edit**. An optional **comment** field records the reason for the change and appears in the version history.

### Deleting a toolset

Open the **⋮** menu and select **Delete**. Deleting a toolset permanently removes all of its tools.

## Managing Tools

Click a toolset row (or **View Tools** from the **⋮** menu) to view and manage the tools within that toolset.

### Creating a tool

Click **New tool**. The form includes:

| Field | Description |
|-------|-------------|
| name | Tool name. Combined with the toolset name to form the MCP tool name `{toolset_name}__{tool_name}`. |
| description | Description shown to the LLM agent as the tool's purpose. |
| cypher | A read-only Cypher query. Write operations (`CREATE`, `MERGE`, `DELETE`, etc.) are blocked at save time. |
| parameters | A list of typed parameters. Each parameter has a name, type (`string`, `integer`, `float`, `boolean`), description, required flag, and optional default value. Parameters are passed to the Cypher query as named parameters (e.g. `$param_name`). |
| enabled | When disabled, the tool is hidden from MCP clients. |

Cypher is validated before saving — queries with syntax errors or write operations are rejected.

### Editing a tool

Open the **⋮** menu on a tool row and select **Edit**. An optional **comment** records the reason for the change.

### Deleting a tool

Open the **⋮** menu and select **Delete**.

## Managing Toolsets and Tools via the CLI

The `seizu` CLI provides commands for managing toolsets and tools, including CRUD operations, version history, calling tools directly, and bulk seed/export via YAML.

### Toolset commands

```bash
seizu toolsets list                              # list all toolsets
seizu toolsets get <toolset_id>                 # show a toolset
seizu toolsets create "My Toolset" --description "desc"
seizu toolsets update <toolset_id> --name "New Name" --enabled
seizu toolsets delete <toolset_id>
seizu toolsets versions <toolset_id>            # version history
seizu toolsets version-get <toolset_id> <n>     # specific version
```

### Tool commands

```bash
seizu toolsets tools list <toolset_id>
seizu toolsets tools get <toolset_id> <tool_id>
seizu toolsets tools create <toolset_id> --name "Count Nodes" \
    --cypher "MATCH (n) RETURN count(n) AS total" \
    --description "Returns total node count"
seizu toolsets tools update <toolset_id> <tool_id> --name "Count Nodes" \
    --cypher "MATCH (n) RETURN count(n) AS total" --comment "Fixed query"
seizu toolsets tools delete <toolset_id> <tool_id>
seizu toolsets tools versions <toolset_id> <tool_id>
seizu toolsets tools version-get <toolset_id> <tool_id> <n>
```

### Calling a tool via the CLI

Tools can be executed directly from the CLI. Arguments are passed as `KEY=JSON_VALUE` pairs (the value is JSON-parsed, so numbers and booleans work without quoting):

```bash
# No parameters
seizu toolsets tools call <toolset_id> <tool_id>

# With parameters
seizu toolsets tools call <toolset_id> <tool_id> --arg limit=10 --arg label='"CVE"'

# Pass all arguments as a JSON object
seizu toolsets tools call <toolset_id> <tool_id> --args-json '{"limit": 10}'

# JSON output
seizu toolsets tools call <toolset_id> <tool_id> --arg limit=10 --output json
```

### Seeding toolsets from YAML

Toolsets and tools can be bulk-loaded from the same YAML config file used for reports and scheduled queries:

```yaml
toolsets:
  my-toolset:
    name: My Toolset
    description: A collection of graph tools
    enabled: true
    tools:
      count-nodes:
        name: Count Nodes
        description: Returns total node count
        cypher: "MATCH (n) RETURN count(n) AS total"
        enabled: true
      find-by-label:
        name: Find By Label
        description: Returns nodes matching a label
        cypher: "MATCH (n) WHERE $label IN labels(n) RETURN n LIMIT $limit"
        parameters:
          - name: label
            type: string
            description: Node label to filter by
            required: true
          - name: limit
            type: integer
            description: Maximum results
            required: false
            default: 25
        enabled: true
```

Seed with:

```bash
seizu seed                      # reads seed_file from ~/.config/seizu/seizu.conf
seizu seed --config path/to/config.yaml
seizu seed --dry-run            # preview without writing
seizu seed --force              # update even if content is unchanged
```

Export the current state back to YAML (including toolsets):

```bash
seizu export
seizu export --dry-run          # print YAML without overwriting the file
```

### Calling a tool via the API

Tools can be called directly via the REST API without an MCP client:

```
POST /api/v1/toolsets/{toolset_id}/tools/{tool_id}/call
Content-Type: application/json

{
  "arguments": {
    "param_name": "value"
  }
}
```

Response:

```json
{
  "results": [
    { "column1": "value1", "column2": 42 }
  ]
}
```

## Version History

Both toolsets and tools keep a full version history. Open the **⋮** menu and select **View history** to see all past versions with their timestamps, authors, and comments. Any previous version can be restored (requires `toolsets:write` / `tools:write`), which creates a new version with a `Restored from version N` comment. The Restore action is disabled in the **⋮** menu for users without the required permission.

## Built-in Tools

The `seizu` toolset is always available and provides two built-in tools:

| MCP tool name | Description |
|---------------|-------------|
| `seizu__schema` | Returns all node labels, relationship types, and property keys in the Neo4j graph database. Takes no parameters. |
| `seizu__query` | Executes an ad-hoc read-only Cypher query. Takes a single `query` parameter (string). The query is validated before execution. |

## MCP Server

The MCP server is available at `/api/v1/mcp` when `MCP_ENABLED=true` (the default).

Authentication uses the same Bearer JWT tokens as the REST API. In development, authentication can be disabled via `DEVELOPMENT_ONLY_REQUIRE_AUTH=false`.

Tool names are namespaced as `{toolset_name}__{tool_name}` (double underscore separator). Only tools in **enabled** toolsets are exposed to MCP clients.

### Connecting Claude Desktop

Add an MCP server entry to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "seizu": {
      "url": "https://your-seizu-host/api/v1/mcp"
    }
  }
}
```

If Seizu is configured with OAuth metadata (`MCP_OAUTH_AUTHORIZATION_ENDPOINT` and `MCP_OAUTH_TOKEN_ENDPOINT`), Claude Desktop will automatically discover the OIDC provider via the metadata endpoint at `/api/v1/mcp/.well-known/oauth-authorization-server` and prompt users to authenticate inside the client.

See the [backend configuration](backend.html#mcp-server) for available settings.
