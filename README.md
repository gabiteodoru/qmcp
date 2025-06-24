# qmcp Server

A Model Context Protocol (MCP) server for q/kdb+ integration.

MCP is an open protocol created by Anthropic that enables AI systems to interact with external tools and data sources. While currently supported by Claude (Desktop and CLI), the open standard allows other LLMs to adopt it in the future.

## Features

- Connect to q/kdb+ servers
- Execute q queries and commands
- Persistent connection management

## Requirements

- Python 3.8+
- qpython3 package
- Access to a q/kdb+ server

## Installation

### Lightweight Installation (Claude CLI only)

Run directly with uv (no pip installation required, may be slower on startup; best for trying it out at first):

```bash
claude mcp add qmcp "uv run qmcp/server.py"
```

### Full Installation

##### Option 1: pip (recommended for global use)

```bash
pip install -e .
```

*Note: Consider using a virtual environment to avoid dependency conflicts:*
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

##### Option 2: uv (for project-specific use)

```bash
# One-time execution (downloads dependencies each time)
uv run qmcp

# Or for frequent use, sync dependencies first
uv sync
uv run qmcp
```

#### Adding to Claude CLI

After full installation, add the server to Claude CLI:

```bash
claude mcp add qmcp qmcp
```

#### Adding to Claude Desktop

Add to your Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "qmcp": {
      "command": "qmcp"
    }
  }
}
```

For uv-based installation:
```json
{
  "mcpServers": {
    "qmcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/qmcp",
        "run",
        "qmcp"
      ]
    }
  }
}
```

## Usage

Run the MCP server:

```bash
qmcp
```

### Environment Variables

- `Q_DEFAULT_HOST` - Default connection info in format: `host`, `host:port`, or `host:port:user:passwd`

### Connection Fallback Logic

The `connect_to_q(host)` tool uses flexible fallback logic:

1. **Full connection string** (has colons): Use directly, ignore `Q_DEFAULT_HOST`
   - `connect_to_q("myhost:5001:user:pass")`
2. **Port number only**: Combine with `Q_DEFAULT_HOST` or use `localhost`
   - `connect_to_q(5001)` → Uses `Q_DEFAULT_HOST` settings with port 5001
3. **No parameters**: Use `Q_DEFAULT_HOST` directly
   - `connect_to_q()` → Uses `Q_DEFAULT_HOST` as-is
4. **Hostname only**: Use as hostname with `Q_DEFAULT_HOST` port/auth or default port
   - `connect_to_q("myhost")` → Combines with `Q_DEFAULT_HOST` settings

### Tools

1. `connect_to_q(host=None)` - Connect to q server with fallback logic
2. `query_q(command)` - Execute q commands and return results

### Known Limitations

When using the MCP server, be aware of these limitations:

- **Keyed tables**: Operations like `1!table` may fail during pandas conversion
- **String vs Symbol distinction**: q strings and symbols may appear identical in output
- **Type ambiguity**: Use q's `meta` and `type` commands to determine actual data types when precision matters
- **Pandas conversion**: Some q-specific data structures may not convert properly to pandas DataFrames

For type checking, use:
```q
meta table           / Check table column types and structure
type variable        / Check variable type
```