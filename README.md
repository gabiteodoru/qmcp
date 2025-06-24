# qmcp Server

A Model Context Protocol server for q/kdb+ integration.

## Features

- Connect to q/kdb+ servers
- Execute q queries and commands
- Persistent connection management

## Requirements

- Python 3.8+
- qpython3 package
- Access to a q/kdb+ server

## Installation

```bash
pip install -e .
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