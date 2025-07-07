#!/usr/bin/env python3
"""
qmcp Server - MCP Server for q/kdb+ integration

A Model Context Protocol server that provides q/kdb+ connectivity
with flexible connection management and query execution.
"""

from mcp.server.fastmcp import FastMCP
import pandas as pd
import threading
import time
import psutil
import signal
import os
import platform
import sys
import os

# Add parent directory to path when run directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import qmcp.qlib as qlib
    from qmcp.util import getTimeoutsStr, find_process_by_port
    import qmcp.codehelper as codehelper
else:
    from . import qlib
    from .util import getTimeoutsStr, find_process_by_port
    from . import codehelper

# Initialize the MCP server
mcp = FastMCP("qmcp")

# Register Qython grammar as MCP resource
@mcp.resource("qython://grammar")
async def get_qython_grammar():
    """Get the Qython language grammar specification"""
    import os
    grammar_path = os.path.join(os.path.dirname(__file__), 'custom_grammar.txt')
    with open(grammar_path, 'r') as f:
        return f.read()

# Global connection state
_q_connection = None
_connection_port = None
_q_process_pid = None  # Store q process PID for safe interruption

# Timeout configuration
_switch_to_async_timeout = 1     # seconds before switching to async mode
# Set interrupt timeout to None on Windows (SIGINT not supported)
_interrupt_timeout = None if platform.system() == 'Windows' else 10  # seconds before sending SIGINT to q process
_connection_timeout = 2          # seconds to wait for connection to establish

# Async task management
_current_async_task = None       # Single async task: {"thread": Thread, "status": str, "command": str, "started": float, "result_container": dict}

# Debug mode
_DEBUG = False



@mcp.tool()
def connect_to_q(host: str = None) -> str:
    """
    Connect to q server with flexible fallback logic
    
    Args:
        host: None, port number, 'host:port', or full connection string
        
    Fallback logic uses Q_DEFAULT_HOST environment variable:
    - If host has colons: use directly (ignores Q_DEFAULT_HOST)
    - If port number: combine with Q_DEFAULT_HOST or localhost
    - If no parameters: use Q_DEFAULT_HOST directly
    - If hostname only: combine with Q_DEFAULT_HOST settings
    
    Returns:
        Connection status and timeout settings
    """
    global _q_connection, _connection_port, _q_process_pid
    try:
        _q_connection = qlib.connect_to_q(host, _connection_timeout)
        
        # Store the port for process management
        if host and str(host).isdigit():
            _connection_port = int(host)
        elif host and ':' in str(host):
            _connection_port = int(host.split(':')[1])
        else:
            _connection_port = None
            
        # Find and store q process PID right after connection for safe interruption
        _q_process_pid = find_process_by_port(_connection_port)
        
        pid_status = ""
        is_windows = platform.system() == 'Windows'
        if _connection_port and (_q_process_pid is None or is_windows):
            if is_windows:
                pid_status = " Warning: Windows detected - interrupt functionality disabled."
            else:
                pid_status = " Warning: Failed to find q process PID - interrupt functionality disabled. If q server is running across WSL-Windows divide, this is expected."
            
        result = f"Connected to q server. {getTimeoutsStr(_switch_to_async_timeout, _interrupt_timeout, _connection_timeout)}){pid_status}"
        return f"[connect_to_q] {result}" if _DEBUG else result
    except Exception as e:
        _q_connection = None
        _connection_port = None
        _q_process_pid = None        
        error_msg = f"Connection failed: {str(e)}. {getTimeoutsStr(_switch_to_async_timeout, _interrupt_timeout, _connection_timeout)}"
        raise ValueError(f"[connect_to_q] {error_msg}" if _DEBUG else error_msg)


@mcp.tool()
def query_q(command: str) -> str:
    """
    Execute q command using stored connection with async timeout switching
    
    Args:
        command: q/kdb+ query or command to execute
        
    Returns:
        Query result (if fast) or async task ID (if slow)
        - Fast queries return results immediately  
        - Slow queries switch to async mode and return task ID
        - pandas DataFrames as readable string tables
        - Lists, dicts, numbers as native Python types
        - Error message string if query fails
        
    Known Limitations:
        - Keyed tables (e.g., 1!table) may fail during pandas conversion
        - Strings and symbols may appear identical in output
        - Use `meta table` and `type variable` for precise type information
        - Some q-specific structures may not convert properly to pandas
    """
    return _query_q(command)

def _query_q(command: str, low_level = False, expr = None) -> str:
    """
    Execute q command using stored connection with async timeout switching
    
    Args:
        command: q/kdb+ query or command to execute
        
    Returns:
        Query result (if fast) or async task ID (if slow)
        - Fast queries return results immediately  
        - Slow queries switch to async mode and return task ID
        - pandas DataFrames as readable string tables
        - Lists, dicts, numbers as native Python types
        - Error message string if query fails
        
    Known Limitations:
        - Keyed tables (e.g., 1!table) may fail during pandas conversion
        - Strings and symbols may appear identical in output
        - Use `meta table` and `type variable` for precise type information
        - Some q-specific structures may not convert properly to pandas
    """
    global _q_connection, _current_async_task
    
    if _q_connection is None:
        result = "No active connection. Use connect_to_q first."
        return f"[_query_q] {result}" if _DEBUG else result
    
    # Check for existing running task
    if _current_async_task and _current_async_task["thread"].is_alive():
        elapsed = time.time() - _current_async_task["started"]
        result = f"Another query is already running ({elapsed:.1f}s elapsed). Check status with get_current_task_status()."
        return f"[_query_q] {result}" if _DEBUG else result
    
    if low_level: return _q_connection(command) if expr is None else _q_connection(command, expr)
    
    # Start query in thread immediately
    result_container = {"result": None, "error": None}
    
    def execute():
        try:
            result = _q_connection(command)
            # Handle pandas DataFrames specially for readability
            if isinstance(result, pd.DataFrame):
                result_container["result"] = result.to_string()
            else:
                result_container["result"] = str(result)
        except Exception as e:
            result_container["error"] = str(e)
    
    def monitor_and_interrupt():
        """Monitor task and send SIGINT if it exceeds interrupt timeout"""
        if not _interrupt_timeout:
            return
            
        time.sleep(_interrupt_timeout)
        
        # Check if task is still running
        if _current_async_task and _current_async_task["thread"].is_alive() and _q_process_pid:
            try:
                # Verify the stored PID still matches the process on our port
                current_pid = find_process_by_port(_connection_port)
                
                # Only send SIGINT if it's the same q process we connected to
                if current_pid == _q_process_pid:
                    proc = psutil.Process(_q_process_pid)
                    proc.send_signal(signal.SIGINT)
                    result_container["error"] = f"Query interrupted after {_interrupt_timeout}s timeout"
                    _current_async_task["status"] = "Timed out"
                # If PIDs don't match, the q process we connected to is gone
                    
            except Exception as e:
                # If SIGINT fails, at least mark the task as timed out
                if _current_async_task and _current_async_task["thread"].is_alive():
                    result_container["error"] = f"Query timed out after {_interrupt_timeout}s (SIGINT failed: {e})"
                    _current_async_task["status"] = "Failed to time out"
    
    # Start the query execution thread
    thread = threading.Thread(target=execute, daemon=True)
    thread.start()
    
    # Start the interrupt monitor thread if timeout is configured AND we have PID AND not on Windows
    if _interrupt_timeout and _q_process_pid and platform.system() != 'Windows':
        interrupt_thread = threading.Thread(target=monitor_and_interrupt, daemon=True)
        interrupt_thread.start()
    
    # Wait for switch_to_async_timeout (default 1s)
    if _switch_to_async_timeout:
        thread.join(timeout=_switch_to_async_timeout)
    
    if not thread.is_alive():
        # Fast query - return result immediately
        if result_container["error"]:
            result = f"Query failed: {result_container['error']}"
            return f"[_query_q] {result}" if _DEBUG else result
        result = result_container["result"]
        return f"[_query_q] {result}" if _DEBUG else result
    else:
        # Slow query - switch to async mode
        _current_async_task = {
            "thread": thread, 
            "status": "Running",
            "command": command,
            "started": time.time(),
            "result_container": result_container
        }
        interrupt_msg = ""
        if _interrupt_timeout and _q_process_pid and platform.system() != 'Windows':
            interrupt_msg = f" Will auto-interrupt after {_interrupt_timeout}s."
        elif _interrupt_timeout and platform.system() == 'Windows':
            interrupt_msg = " (Auto-interrupt disabled on Windows)"
        elif _interrupt_timeout and not _q_process_pid:
            interrupt_msg = " (Auto-interrupt disabled - no process PID)"
        
        result = f"Query taking longer than {_switch_to_async_timeout}s, switched to async mode.{interrupt_msg} Check status with get_current_task_status()."
        return f"[_query_q] {result}" if _DEBUG else result

#@mcp.tool()
def parse(expr: str) -> str:
    """
    Parse a q expression and return a human-readable representation
    
    This tool analyzes q code syntax and structure. Use this when q queries fail 
    and you suspect syntax issues - it can help identify structural problems.
    
    Args:
        expr: q expression to parse and analyze
        
    Returns:
        Human-readable string representation of the parsed expression
        
    Example:
        parse("a lj 2!select min s, maxs t from c") 
        -> "[Func[lj], Symbol[a], [Func[!], Long[2], [Func[?], Symbol[c], [], Bool[0], Dict(LSymbol[s, t]: [[Func[min], Symbol[s]], [Func[maxs], Symbol[t]]])]]]"
    """
    result = codehelper.parse(_query_q, expr)
    return f"[parse] {result}" if _DEBUG else result

@mcp.tool()
def set_timeout_switch_to_async(seconds: int = None) -> str:
    """
    Set timeout to switch query to async mode
    
    Args:
        seconds: Timeout in seconds, or None to disable async switching
        
    Returns:
        Status message
    """
    global _switch_to_async_timeout
    
    if seconds is not None and seconds < 0:
        result = "Error: Timeout cannot be negative"
        return f"[set_timeout_switch_to_async] {result}" if _DEBUG else result
    
    if seconds is None:
        _switch_to_async_timeout = None
        result = "Async switching disabled"
        return f"[set_timeout_switch_to_async] {result}" if _DEBUG else result
    
    _switch_to_async_timeout = seconds
    result = f"Will switch to async mode after {seconds} seconds"
    return f"[set_timeout_switch_to_async] {result}" if _DEBUG else result


@mcp.tool()
def set_timeout_interrupt_q(seconds: int = None) -> str:
    """
    Set timeout to send SIGINT to q process
    
    Args:
        seconds: Timeout in seconds, or None to disable auto-interrupt
        
    Returns:
        Status message
    """
    global _interrupt_timeout
    
    if seconds is not None and seconds < 0:
        result = "Error: Timeout cannot be negative"
        return f"[set_timeout_interrupt_q] {result}" if _DEBUG else result
    
    if seconds is None:
        _interrupt_timeout = None
        result = "Auto-interrupt disabled"
        return f"[set_timeout_interrupt_q] {result}" if _DEBUG else result
    
    _interrupt_timeout = seconds
    result = f"Will send SIGINT after {seconds} seconds"
    return f"[set_timeout_interrupt_q] {result}" if _DEBUG else result


@mcp.tool()
def set_timeout_connection(seconds: int = None) -> str:
    """
    Set timeout for establishing connection to q server
    
    Args:
        seconds: Timeout in seconds, or None to use default (5s)
        
    Returns:
        Status message
    """
    global _connection_timeout
    
    if seconds is not None and seconds <= 0:
        result = "Error: Connection timeout must be positive"
        return f"[set_timeout_connection] {result}" if _DEBUG else result
    
    if seconds is None:
        _connection_timeout = 5  # Default to qpython's original 5s
        result = "Connection timeout reset to default (5s)"
        return f"[set_timeout_connection] {result}" if _DEBUG else result
    
    _connection_timeout = seconds
    result = f"Connection timeout set to {seconds} seconds"
    return f"[set_timeout_connection] {result}" if _DEBUG else result


@mcp.tool()
def get_timeout_settings() -> str:
    """
    Show current timeout settings
    
    Returns:
        Current timeout configuration
    """
    result = getTimeoutsStr(_switch_to_async_timeout, _interrupt_timeout, _connection_timeout)
    return f"[get_timeout_settings] {result}" if _DEBUG else result


@mcp.tool()
def get_current_task_status(wait_seconds: int = None) -> str:
    """
    Check status of current async task, optionally waiting for completion
    
    Args:
        wait_seconds: Max seconds to wait for completion (default: async_switch_timeout)
    
    Returns:
        Task status information or "No task running"
    """
    global _current_async_task
    
    if not _current_async_task:
        result = "No async task running"
        return f"[get_current_task_status] {result}" if _DEBUG else result
    
    # Set default wait time to async switch timeout
    if wait_seconds is None:
        wait_seconds = _switch_to_async_timeout or 0
    
    task = _current_async_task
    start_wait = time.time()
    
    # Wait for completion or timeout
    while time.time() - start_wait < wait_seconds:
        elapsed = time.time() - task["started"]
        
        # Check if task completed by checking thread status
        if not task["thread"].is_alive():
            if task["result_container"]["error"]:
                result = f"Query FAILED after {elapsed:.1f}s. Status: {task['status']}. Error: {task['result_container']['error']}"
                return f"[get_current_task_status] {result}" if _DEBUG else result
            else:
                task["status"] = "Finished successfully" 
                result = f"Query COMPLETED after {elapsed:.1f}s. Use get_current_task_result() to retrieve result."
                return f"[get_current_task_status] {result}" if _DEBUG else result
        
        # Small polling interval to avoid busy waiting
        time.sleep(0.1)
    
    # Return running status after wait timeout
    elapsed = time.time() - task["started"]
    result = f"Query RUNNING ({elapsed:.1f}s elapsed). Command: {task['command'][:50]}{'...' if len(task['command']) > 50 else ''}"
    return f"[get_current_task_status] {result}" if _DEBUG else result


@mcp.tool()
def interrupt_current_query() -> str:
    """
    Send SIGINT to interrupt the currently running query
    
    Returns:
        Status message indicating success or failure
    """
    global _current_async_task, _q_process_pid, _connection_port
    
    if not _current_async_task:
        result = "No async task running to interrupt"
        return f"[interrupt_current_query] {result}" if _DEBUG else result
    
    if platform.system() == 'Windows':
        result = "Cannot interrupt: interrupt functionality disabled on Windows"
        return f"[interrupt_current_query] {result}" if _DEBUG else result
    
    if not _q_process_pid:
        result = "Cannot interrupt: no process PID available"
        return f"[interrupt_current_query] {result}" if _DEBUG else result
        
    if not _connection_port:
        result = "Cannot interrupt: no connection port available"
        return f"[interrupt_current_query] {result}" if _DEBUG else result
    
    task = _current_async_task
    
    # Check if task is already completed
    if not task["thread"].is_alive():
        if task["result_container"]["error"]:
            if task["status"] == "Timed out":
                result = f"Query already timed out: {task['result_container']['error']}"
            else:
                result = f"Query already failed: {task['result_container']['error']}"
        else:
            result = "Query already completed successfully, nothing to interrupt"
        return f"[interrupt_current_query] {result}" if _DEBUG else result
    
    try:
        # Verify the stored PID still matches the process on our port
        current_pid = find_process_by_port(_connection_port)
        
        if current_pid != _q_process_pid:
            raise ValueError(f"Process PID mismatch: stored PID {_q_process_pid} but port {_connection_port} has PID {current_pid}. The q process may have been restarted.")
        
        # Send SIGINT to interrupt the query
        proc = psutil.Process(_q_process_pid)
        proc.send_signal(signal.SIGINT)
        
        # Mark task as interrupted
        task["result_container"]["error"] = "Query manually interrupted"
        task["status"] = "Interrupted"
        
        elapsed = time.time() - task["started"]
        result = f"Query interrupted after {elapsed:.1f}s"
        return f"[interrupt_current_query] {result}" if _DEBUG else result
        
    except ValueError as e:
        # Re-raise PID mismatch errors
        raise e
    except Exception as e:
        result = f"Failed to interrupt query: {str(e)}"
        return f"[interrupt_current_query] {result}" if _DEBUG else result


@mcp.tool()
def get_current_task_result() -> str:
    """
    Get result of current/completed async task
    
    Returns:
        Task result or status message
    """
    global _current_async_task
    
    if not _current_async_task:
        result = "No async task to get result from"
        return f"[get_current_task_result] {result}" if _DEBUG else result
    
    task = _current_async_task
    
    if task["thread"].is_alive():
        elapsed = time.time() - task["started"]
        result = f"Query still running ({elapsed:.1f}s elapsed). Check status with get_current_task_status()."
        return f"[get_current_task_result] {result}" if _DEBUG else result
    
    if task["result_container"]["error"]:
        result = f"Query failed: {task['result_container']['error']}"
        return f"[get_current_task_result] {result}" if _DEBUG else result
    
    # Return result and clear the task
    result = task["result_container"]["result"]
    _current_async_task = None
    return f"[get_current_task_result] {result}" if _DEBUG else result


@mcp.tool()
def translate_qython_to_q(qython_code: str) -> str:
    """
    ⚠️ EXPERIMENTAL: Translate Qython code to Q code - Output may be incorrect, please verify
    
    Qython is Python-like syntax with q-functional constructs:
    - `do n times:` repeat n times; same as `for _ in range(n):` but without access to iteration variable `_`
    - `converge(func, starting_from=val)` for functional convergence (built-in tolerance)
    - `reduce(binary_func, iterable)` for cumulative operations
    - `range(n)` for generating integer sequences [0, 1, ..., n-1] (single parameter only; for `range(a,b)` use `a+range(b-a)`)
    - No `for` loops, `elif`, tuple assignment, or `break/continue`
    - Use lists `[a, b, c]` instead of tuples `(a, b, c)`
    
    Examples:
    ```python
    # Compound Interest
    def compound_growth(principal, rate, years):
        amount = principal
        do years times:
            amount = amount * (1 + rate)
        return amount
    
    # Golden Section Search
    def golden_section_search(f, a, b):
        # tolerance is not provided as when using converge it's unnecessary
        phi = (1 + 5**0.5) / 2
        resphi = 2 - phi
        x1 = a + resphi * (b - a)
        x2 = b - resphi * (b - a)
        f1 = f(x1)
        f2 = f(x2)
        
        def step(state):
            # Extract state values
            state_a = state[0]
            state_b = state[1]
            state_x1 = state[2]
            state_x2 = state[3]
            state_f1 = state[4]
            state_f2 = state[5]
            
            if state_f1 > state_f2:
                new_a = state_x1
                new_x1 = state_x2
                new_f1 = state_f2
                new_x2 = state_b - resphi * (state_b - new_a)
                new_f2 = f(new_x2)
                new_b = state_b
            
            if state_f1 <= state_f2:
                new_b = state_x2
                new_x2 = state_x1
                new_f2 = state_f1
                new_x1 = state_a + resphi * (new_b - state_a)
                new_f1 = f(new_x1)
                new_a = state_a
            
            return [new_a, new_b, new_x1, new_x2, new_f1, new_f2]
        
        initial_state = [a, b, x1, x2, f1, f2]
        final_state = converge(step, starting_from=initial_state)
        result_a = final_state[0]
        result_b = final_state[1]
        return (result_a + result_b) / 2
    ```
    
    Args:
        qython_code: Qython source code to translate
        
    Returns:
        Equivalent Q code
    """
    if __name__ == "__main__":
        import qmcp.translate as translate
    else:
        from . import translate
    import os
    
    # Change to the directory containing the grammar file
    original_cwd = os.getcwd()
    try:
        os.chdir(os.path.dirname(__file__))
        return translate.translate(qython_code)
    finally:
        os.chdir(original_cwd)


def main():
    """Main entry point for the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()