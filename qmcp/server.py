#!/usr/bin/env python3
"""
qmcp Server - MCP Server for q/kdb+ integration

A Model Context Protocol server that provides q/kdb+ connectivity
with flexible connection management and query execution.
"""

from mcp.server.fastmcp import FastMCP
import pandas as pd
from . import qlib

# Initialize the MCP server
mcp = FastMCP("qmcp")

# Global connection state
_q_connection = None


@mcp.tool()
def connect_to_q(host: str = None) -> bool:
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
        True if connection successful, False otherwise
    """
    global _q_connection
    try:
        _q_connection = qlib.connect_to_q(host)
        return True
    except Exception as e:
        _q_connection = None
        print(f"Connection failed: {str(e)}")
        return False


@mcp.tool()
def query_q(command: str) -> str:
    """
    Execute q command using stored connection
    
    Args:
        command: q/kdb+ query or command to execute
        
    Returns:
        Query result in native format:
        - pandas DataFrames as readable string tables
        - Lists, dicts, numbers as native Python types
        - Error message string if query fails
        
    Known Limitations:
        - Keyed tables (e.g., 1!table) may fail during pandas conversion
        - Strings and symbols may appear identical in output
        - Use `meta table` and `type variable` for precise type information
        - Some q-specific structures may not convert properly to pandas
    """
    global _q_connection
    if _q_connection is None:
        return "No active connection. Use connect_to_q first."
    
    try:
        result = _q_connection(command)
        
        # Handle pandas DataFrames specially for readability
        if isinstance(result, pd.DataFrame):
            return result.to_string()
        
        # Return everything else as string representation
        return str(result)
    except Exception as e:
        return f"Query failed: {str(e)}"


def main():
    """Main entry point for the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()