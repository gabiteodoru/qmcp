"""
Q/kdb+ connection utilities for qmcp
Clean, minimal interface for connecting to and querying q servers
"""

from .qpython_compat import QConnection, MetaData
import os
import time
import socket
from .sugar import dmap, spl
import pandas as pd
import numpy as np


def _get_hostname():
    """Get current hostname"""
    return socket.gethostname()


class _QDecodeWrapper:
    """Wrapper for QConnection that handles pandas DataFrame encoding/decoding"""
    
    def __init__(self, q):
        self.q = q
        
    def __call__(self, *args, **kwargs):
        # Handle DataFrame arguments
        for arg in args:
            if isinstance(arg, pd.DataFrame):
                if not hasattr(arg, 'meta'):
                    arg.meta = MetaData(qtype=98)
                    
                # Set date column metadata
                for c in 'd, date'-spl:
                    if (c in arg.columns and 
                        isinstance(arg[c].dtype, np.dtype) and 
                        arg[c].dtype != np.dtype(np.object_) and
                        c not in arg.meta.__dict__):
                        arg.meta[c] = 14
                        
                # Handle string columns
                if 'strcols' in kwargs:
                    for sc in kwargs['strcols']-spl:
                        arg.meta[sc] = 0
                        
        # Execute query
        r = self.q(*args, **kwargs)
        
        # Decode string/symbol columns in result
        if type(r) == pd.DataFrame:
            rd = r.meta.as_dict()
            for col in rd:
                if rd[col] in (0, 11):  # string or symbol columns
                    r[col] = r[col].map(dmap(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x, r[col].drop_duplicates()))
                    
        return r


def connect_to_q(host=None, connection_timeout=5):
    """
    Connect to q server with flexible fallback logic for MCP
    
    Args:
        host: None, port number, 'host:port', or full connection string
        connection_timeout: seconds to wait for connection (default 5)
        
    Fallback logic:
    1. If host has colons, use directly (ignores Q_DEFAULT_HOST)
    2. If no envvar and no parameter, fail
    3. If port provided, combine with Q_DEFAULT_HOST or localhost
    4. Use Q_DEFAULT_HOST if available
    
    Returns:
        _QDecodeWrapper instance
    """
    # 4) If host has colons, use it directly (ignore Q_DEFAULT_HOST)
    if host and ':' in str(host):
        return _qConnect(str(host), True, connection_timeout)
    
    # Get Q_DEFAULT_HOST environment variable
    default_host = os.environ.get('Q_DEFAULT_HOST')
    
    # 2) Fail if no envvar and no parameter
    if not default_host and not host:
        raise ValueError("No connection info: set Q_DEFAULT_HOST or provide host parameter")
    
    # 3) If host is just a port number, combine with default host info
    if host and str(host).isdigit():
        port = str(host)
        if default_host:
            # Extract host[:user:passwd] from Q_DEFAULT_HOST, replace port
            parts = default_host.split(':')
            if len(parts) >= 2:
                # Replace port in Q_DEFAULT_HOST
                parts[1] = port
                return _qConnect(':'.join(parts), True, connection_timeout)
            else:
                # Q_DEFAULT_HOST is just hostname
                return _qConnect(f"{default_host}:{port}", True, connection_timeout)
        else:
            # No Q_DEFAULT_HOST, use localhost
            return _qConnect(f"localhost:{port}", True, connection_timeout)
    
    # 1) Use Q_DEFAULT_HOST (host, host:port, or host:port:user:passwd)
    if default_host:
        return _qConnect(default_host, True, connection_timeout)
    
    # Should never reach here due to check above
    raise ValueError("Invalid connection parameters")


def _qConnect(qCredentials, pandas, connection_timeout=5):
    """
    Connect to q server with socket timeout
    
    Args:
        qCredentials: 'host:port' or 'host:port:user:passwd'
        pandas: return pandas-enabled connection
        connection_timeout: socket timeout in seconds
        
    Returns:
        QConnection or _QDecodeWrapper
    """
    qCreds = tuple(qCredentials.split(':'))
    host, port, user, passwd = qCreds if len(qCreds) == 4 else (qCreds + (None, None))
    port = int(port)
    
    if host == _get_hostname():
        host = 'localhost'
        
    # Create connection with socket timeout
    q = QConnection(host, port, user, passwd, pandas=pandas)
    
    # Set socket timeout before opening connection
    import socket
    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(connection_timeout)
    
    try:
        q.open()
        return _QDecodeWrapper(q) if pandas else q
    finally:
        # Restore original socket timeout
        socket.setdefaulttimeout(original_timeout)