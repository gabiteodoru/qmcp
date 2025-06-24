# qmcp Server

A Model Context Protocol (MCP) server for q/kdb+ integration.

MCP is an open protocol created by Anthropic that enables AI systems to interact with external tools and data sources. While currently supported by Claude (Desktop and CLI), the open standard allows other LLMs to adopt it in the future.

## Features

- Connect to q/kdb+ servers
- Execute q queries and commands
- Persistent connection management

## Requirements

- Python 3.8+
- Access to a q/kdb+ server
- `uv` (for lightweight installation) or `pip` (for full installation)

## Quick Start

For first-time users, the fastest way to get started:

1. Start a q server:
   ```bash
   q -p 5001
   ```
2. Add qmcp to Claude CLI:
   ```bash
   claude mcp add qmcp "uv run qmcp/server.py"
   ```
3. Start using Claude CLI:
   ```bash
   claude
   ```
   Then interact with qmcp:
   ```
   > connect to port 5001 and compute 2+2

   ● qmcp:connect_to_q (MCP)(host: "5001")
     ⎿  true

   ● qmcp:query_q (MCP)(command: "2+2")
     ⎿  4
   ```

## Installation

### Lightweight Installation (Claude CLI only)

Run directly with uv (no pip installation required, may be slower on startup; best for trying it out at first):

```bash
claude mcp add qmcp "uv run qmcp/server.py"
```

### Full Installation

#### Option 1: pip (recommended for global use)

```bash
pip install qmcp
```

*Note: Consider using a virtual environment to avoid dependency conflicts:*
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install qmcp
```

#### Option 2: uv (for project-specific use)

```bash
# One-time execution (downloads dependencies each time)
uv run qmcp

# Or for frequent use, sync dependencies first
uv sync
uv run qmcp
```

##### Adding to Claude CLI

After full installation, add the server to Claude CLI:

```bash
claude mcp add qmcp qmcp
```

##### Adding to Claude Desktop

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

### Starting the MCP Server

**After full installation:**
```bash
qmcp
```

**With lightweight installation:**
The server starts automatically when Claude CLI uses it (no manual start needed).


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

## Known Limitations

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

## WSL2 Port Communication (Windows Users)

*Skip this section if you're not on Windows.*

Since Claude CLI is WSL-only on Windows, but you might want to use Windows IDEs or tools to connect to your q server, you need proper port communication between WSL2 and Windows.

### WSL2 Configuration for Port Communication

#### .wslconfig File Setup
Location: `C:\Users\{YourUsername}\.wslconfig`

Add mirrored networking configuration:
```ini
# Mirrored networking mode for seamless port communication
networkingMode=mirrored
dnsTunneling=true
firewall=true
autoProxy=true
```

#### Restart WSL2
Run from Windows PowerShell/CMD (NOT from within WSL):
```powershell
wsl --shutdown
# Wait a few seconds, then start WSL again
```

#### Verify Configuration
Check if mirrored networking is active:
```bash
ip addr show
cat /etc/resolv.conf
```

#### Test Port Communication

Test WSL2 → Windows (localhost):
```bash
# In WSL2, start a server
python3 -m http.server 8000

# In Windows browser or PowerShell
curl http://localhost:8000
```

Test Windows → WSL2 (localhost):
```powershell
# In Windows PowerShell
python -m http.server 8001

# In WSL2
curl http://localhost:8001
```

#### What Mirrored Networking Provides

- ✅ Direct localhost communication both ways
- ✅ No manual port forwarding needed
- ✅ Better VPN compatibility
- ✅ Simplified networking (Windows and WSL2 share network interfaces)
- ✅ Firewall rules automatically handled

### ⚠️ Port 5000 Special Case

**Issue**: Port 5000 has limited mirrored networking support due to Windows service binding.

**Root Cause**:
- Windows `svchost` service binds to `127.0.0.1:5000` (localhost only)
- Localhost-only bindings are not fully mirrored between Windows and WSL2
- This creates an exception to the general mirrored networking functionality

**Port 5000 Communication Matrix**:
- ✅ Windows ↔ Windows: Works (same localhost)
- ❌ WSL2 ↔ Windows: Fails (different localhost interpretation)
- ✅ WSL2 ↔ WSL2: Works (same environment)

**Solutions for Port 5000**:
1. **Use different ports**: 5001, 5002, etc. (recommended)
2. **Stop Windows service**: If not needed
3. **Traditional port forwarding**: For specific use cases

#### Common Services That May Have Localhost-Only Binding
- **Flask development servers** (default `127.0.0.1:5000`)
- **UPnP Device Host service**
- **Windows Media Player Network Sharing**
- **Various development tools**

#### Known Limitations of Mirrored Networking
1. **Localhost-only services**: Not fully mirrored (as confirmed with port 5000)
2. **mDNS doesn't work** in mirrored mode
3. **Some Docker configurations** may have issues
4. **Requires Windows 11 22H2+** (build 22621+)