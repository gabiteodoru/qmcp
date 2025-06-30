"""
Compatibility layer for bundled qpython without modifying the original source.
This module provides a clean interface to the bundled qpython package.
"""

import sys
import os
import importlib.util

# Get the path to the bundled qpython directory
_qpython_dir = os.path.join(os.path.dirname(__file__), 'qpython')

# Add qpython directory to sys.path if not already there
if _qpython_dir not in sys.path:
    sys.path.insert(0, _qpython_dir)

# Also add the parent of qpython so 'qpython' can be found as a module
_parent_dir = os.path.dirname(_qpython_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

try:
    # Import from the bundled qpython
    import qpython.qconnection as _qconnection
    from qpython import MetaData as _MetaData
    from qpython import qtype
    
    # Create our exports
    QConnection = _qconnection.QConnection
    MetaData = _MetaData
    
except ImportError as e:
    # Fallback: try to manually load the modules
    import importlib.util
    
    # Load qpython.__init__.py manually
    qpython_init_path = os.path.join(_qpython_dir, '__init__.py')
    spec = importlib.util.spec_from_file_location("qpython", qpython_init_path)
    qpython_module = importlib.util.module_from_spec(spec)
    sys.modules['qpython'] = qpython_module
    spec.loader.exec_module(qpython_module)
    
    # Load qconnection module
    qconnection_path = os.path.join(_qpython_dir, 'qconnection.py')
    spec = importlib.util.spec_from_file_location("qpython.qconnection", qconnection_path)
    qconnection_module = importlib.util.module_from_spec(spec)
    sys.modules['qpython.qconnection'] = qconnection_module
    spec.loader.exec_module(qconnection_module)
    
    # Export what we need
    QConnection = qconnection_module.QConnection
    MetaData = qpython_module.MetaData