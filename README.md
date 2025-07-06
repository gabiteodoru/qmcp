# qmcp Server

A Model Context Protocol (MCP) server for q/kdb+ integration.

MCP is an open protocol created by Anthropic that enables AI systems to interact with external tools and data sources. While currently supported by Claude (Desktop and CLI), the open standard allows other LLMs to adopt it in the future.

## Features

- Connect to q/kdb+ servers
- Execute q queries and commands
- Persistent connection management
- Intelligent async query handling with configurable timeouts
- Programmatic query cancellation (Ctrl+C equivalent)
- Graceful handling of long-running queries
- **NEW:** Qython language translator (Experimental Alpha)

## Windows Users: WSL Recommendation

**⚠️ Important for Windows users**: For optimal functionality, it is highly recommended to run both the MCP server and your q session inside WSL (Windows Subsystem for Linux). This ensures the server can interrupt infinite loops and runaway queries that LLMs might accidentally generate.

Running the MCP server on Windows (outside WSL) disables SIGINT-based query interruption functionality, which is critical for escaping problematic queries during AI-assisted development sessions.

## Architecture & Design Philosophy

### Intended Goals

**qmcp** is designed to provide AI coding assistants with **controlled access** to q/kdb+ databases for development and debugging workflows:

1. **Development-Focused**: Optimized for coding tools working with debug/dev q servers
2. **Query Control**: AI can interrupt long-running queries (equivalent to developer Ctrl+C)
3. **Predictable Behavior**: Sequential execution prevents resource conflicts during development
4. **Configurable Timeouts**: Customizable timing for different development scenarios

### Design Logic

The server architecture makes deliberate choices for AI-assisted development workflows:

#### **Single Connection Model**
- **Why**: Simplifies development debugging - one connection, clear state
- **Benefit**: Matches typical developer workflow with single q session
- **Implementation**: One persistent connection per MCP session

#### **Sequential Query Execution**
- **Why**: Development environments don't need concurrent query support
- **Benefit**: Predictable resource usage, easier debugging, prevents query interference
- **Implementation**: New queries rejected while another is running

#### **Smart Async Switching with Configurable Timeouts**
```
Fast Query (< async switch timeout)  →  Return result immediately
Slow Query (> async switch timeout)  →  Switch to async mode
                                     →  Auto-interrupt after interrupt timeout (if configured)
```
- **Why**: Keeps AI coding sessions responsive while allowing complex development queries
- **Benefit**: Immediate feedback for quick queries, progress tracking for analysis
- **Customization**: All timeouts configurable via MCP tools

#### **AI-Controlled Query Interruption**
- **Why**: AI coding tools need ability to cancel runaway queries (like developer Ctrl+C)
- **How**: MCP server locates q process by port and sends SIGINT after configurable timeout
- **Benefit**: Prevents development sessions from hanging on problematic queries
- **Limitations**: SIGINT functionality disabled when:
  - MCP server runs on Windows (outside WSL)
  - MCP server and q session run on opposite sides of WSL/Windows divide

#### **Development-Oriented Process Management**
- **Why**: Coding tools work with user-managed development q servers
- **Benefit**: Developer controls q server lifecycle, AI controls query execution
- **Design**: MCP server provides query interruption capability without server lifecycle management

### Why This Design Makes Sense for Coding Tools

1. **Development Workflow**: Matches how developers interact with q - single session, iterative queries
2. **AI Safety**: Prevents AI from overwhelming development environments with concurrent requests
3. **Debugging-Friendly**: Sequential execution makes it easier to trace issues
4. **Responsive**: Async handling prevents AI coding sessions from blocking
5. **Configurable**: Timeouts can be tuned for different development scenarios

This architecture provides AI coding assistants with effective q/kdb+ access while maintaining the predictable, controlled environment that development workflows require.

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

### Tool Stability Status

**Production-Ready Tools:**
- `connect_to_q` - Stable connection management with fallback logic
- `query_q` - Execute queries with intelligent async timeout control
- `set_timeout_switch_to_async` - Configure when queries switch to async mode
- `set_timeout_interrupt_q` - Configure when to send SIGINT to cancel queries  
- `set_timeout_connection` - Configure connection timeout
- `get_timeout_settings` - View current timeout configuration
- `get_current_task_status` - Check status of running async query
- `get_current_task_result` - Retrieve result of completed async query
- `interrupt_current_query` - Send SIGINT to interrupt running queries

**Experimental Tools (Alpha):**
- `translate_qython_to_q` - ⚠️ **EXPERIMENTAL**: Python-like syntax to q translator
  - Qython supports: `do n times:`, `converge()`, `reduce()`, `range()`
  - Limited vocabulary, may produce incorrect code
  - **Please verify all output before use**
  - Report bugs at [GitHub Issues](https://github.com/gabiteodoru/qmcp/issues)

## Known Limitations

When using the MCP server, be aware of these limitations:

### Query Interruption (SIGINT) Limitations
- **Windows Platform**: Query interruption disabled when MCP server runs on Windows (outside WSL)
- **Cross-Platform Setup**: Query interruption disabled when MCP server and q session run on opposite sides of WSL/Windows divide
- **Impact**: LLM cannot automatically escape infinite loops or cancel runaway queries in these configurations

### Data Conversion Limitations
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