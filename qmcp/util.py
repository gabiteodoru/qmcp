"""
Utility functions for qmcp server
"""

import psutil


def getTimeoutsStr(_switch_to_async_timeout, _interrupt_timeout, _connection_timeout):
    """Format timeout settings as a readable string"""
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