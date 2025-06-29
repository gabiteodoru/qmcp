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
from . import qlib

# Initialize the MCP server
mcp = FastMCP("qmcp")

# Global connection state
_q_connection = None
_connection_port = None
_q_process_pid = None  # Store q process PID for safe interruption

# Timeout configuration
_switch_to_async_timeout = 1     # seconds before switching to async mode
_interrupt_timeout = 10          # seconds before sending SIGINT to q process
_connection_timeout = 2          # seconds to wait for connection to establish

# Async task management
_current_async_task = None       # Single async task: {"thread": Thread, "status": str, "command": str, "started": float, "result_container": dict}

def getTimeoutsStr():
    async_setting = f"{_switch_to_async_timeout}s" if _switch_to_async_timeout else "disabled"
    interrupt_setting = f"{_interrupt_timeout}s" if _interrupt_timeout else "disabled"
    connection_setting = f"{_connection_timeout}s"
    return f"Timeouts: async_switch={async_setting}, interrupt={interrupt_setting}, connection={connection_setting}"

def find_process_by_port(port):
    """Find PID of process listening on the specified port"""
    if not port:
        return None
    try:
        for conn in psutil.net_connections():
            if (conn.laddr.port == port and 
                conn.status == 'LISTEN'):
                return conn.pid
    except Exception:
        pass
    return None

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
        if _connection_port and _q_process_pid is None:
            pid_status = " Warning: Failed to find q process PID - SIGINT functionality disabled. If q server is running across WSL-Windows divide, this is expected."
            
        return f"Connected to q server. {getTimeoutsStr()}){pid_status}"
    except Exception as e:
        _q_connection = None
        _connection_port = None
        _q_process_pid = None        
        raise ValueError(f"Connection failed: {str(e)}. {getTimeoutsStr()}")


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
    global _q_connection, _current_async_task
    
    if _q_connection is None:
        return "No active connection. Use connect_to_q first."
    
    # Check for existing running task
    if _current_async_task and _current_async_task["thread"].is_alive():
        elapsed = time.time() - _current_async_task["started"]
        return f"Another query is already running ({elapsed:.1f}s elapsed). Check status with get_current_task_status()."
    
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
    
    # Start the interrupt monitor thread if timeout is configured AND we have PID
    if _interrupt_timeout and _q_process_pid:
        interrupt_thread = threading.Thread(target=monitor_and_interrupt, daemon=True)
        interrupt_thread.start()
    
    # Wait for switch_to_async_timeout (default 1s)
    if _switch_to_async_timeout:
        thread.join(timeout=_switch_to_async_timeout)
    
    if not thread.is_alive():
        # Fast query - return result immediately
        if result_container["error"]:
            return f"Query failed: {result_container['error']}"
        return result_container["result"]
    else:
        # Slow query - switch to async mode
        _current_async_task = {
            "thread": thread, 
            "status": "Running",
            "command": command,
            "started": time.time(),
            "result_container": result_container
        }
        interrupt_msg = f" Will auto-interrupt after {_interrupt_timeout}s." if _interrupt_timeout else ""
        return f"Query taking longer than {_switch_to_async_timeout}s, switched to async mode.{interrupt_msg} Check status with get_current_task_status()."


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
        return "Error: Timeout cannot be negative"
    
    if seconds is None:
        _switch_to_async_timeout = None
        return "Async switching disabled"
    
    _switch_to_async_timeout = seconds
    return f"Will switch to async mode after {seconds} seconds"


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
        return "Error: Timeout cannot be negative"
    
    if seconds is None:
        _interrupt_timeout = None
        return "Auto-interrupt disabled"
    
    _interrupt_timeout = seconds
    return f"Will send SIGINT after {seconds} seconds"


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
        return "Error: Connection timeout must be positive"
    
    if seconds is None:
        _connection_timeout = 5  # Default to qpython's original 5s
        return "Connection timeout reset to default (5s)"
    
    _connection_timeout = seconds
    return f"Connection timeout set to {seconds} seconds"


@mcp.tool()
def get_timeout_settings() -> str:
    """
    Show current timeout settings
    
    Returns:
        Current timeout configuration
    """
    return getTimeoutsStr()


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
        return "No async task running"
    
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
                return f"Query FAILED after {elapsed:.1f}s. Status: {task['status']}. Error: {task['result_container']['error']}"
            else:
                task["status"] = "Finished successfully" 
                return f"Query COMPLETED after {elapsed:.1f}s. Use get_current_task_result() to retrieve result."
        
        # Small polling interval to avoid busy waiting
        time.sleep(0.1)
    
    # Return running status after wait timeout
    elapsed = time.time() - task["started"]
    return f"Query RUNNING ({elapsed:.1f}s elapsed). Command: {task['command'][:50]}{'...' if len(task['command']) > 50 else ''}"


@mcp.tool()
def interrupt_current_query() -> str:
    """
    Send SIGINT to interrupt the currently running query
    
    Returns:
        Status message indicating success or failure
    """
    global _current_async_task, _q_process_pid, _connection_port
    
    if not _current_async_task:
        return "No async task running to interrupt"
    
    if not _q_process_pid:
        return "Cannot interrupt: no process PID available"
        
    if not _connection_port:
        return "Cannot interrupt: no connection port available"
    
    task = _current_async_task
    
    # Check if task is already completed
    if not task["thread"].is_alive():
        return "Query already completed, nothing to interrupt"
    
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
        return f"Query interrupted after {elapsed:.1f}s"
        
    except ValueError as e:
        # Re-raise PID mismatch errors
        raise e
    except Exception as e:
        return f"Failed to interrupt query: {str(e)}"


@mcp.tool()
def get_current_task_result() -> str:
    """
    Get result of current/completed async task
    
    Returns:
        Task result or status message
    """
    global _current_async_task
    
    if not _current_async_task:
        return "No async task to get result from"
    
    task = _current_async_task
    
    if task["thread"].is_alive():
        elapsed = time.time() - task["started"]
        return f"Query still running ({elapsed:.1f}s elapsed). Check status with get_current_task_status()."
    
    if task["result_container"]["error"]:
        return f"Query failed: {task['result_container']['error']}"
    
    # Return result and clear the task
    result = task["result_container"]["result"]
    _current_async_task = None
    return result


def main():
    """Main entry point for the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()