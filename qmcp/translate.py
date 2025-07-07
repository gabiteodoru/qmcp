import parso

# Math expression translator - operator precedence levels (higher number = higher precedence)
MATH_PRECEDENCE = {
    '+': 1,
    '-': 1,
    '*': 2,
    '/': 2,
    '**': 3,
}

# Python operators to q operators
PYTHON_TO_Q_MATH = {
    '+': '+',
    '-': '-', 
    '*': '*',
    '/': '%',
    '**': ' xexp ',
}

def get_math_operator_info(node):
    """Extract operator info from a binary expression node."""
    if node.type == 'arith_expr':
        # Find the main operator (should be + or -)
        for child in node.children:
            if child.type == 'operator' and child.value in ['+', '-']:
                return child.value, MATH_PRECEDENCE[child.value]
    elif node.type == 'term':
        # Find the main operator (should be * or /)
        for child in node.children:
            if child.type == 'operator' and child.value in ['*', '/', '**']:
                return child.value, MATH_PRECEDENCE[child.value]
    elif node.type == 'power':
        # Find the main operator (should be **)
        for child in node.children:
            if child.type == 'operator' and child.value == '**':
                return child.value, MATH_PRECEDENCE[child.value]
    return None, 0

def translate_math_expr_node(node, parent_op=None, parent_prec=0, is_left_child=False):
    """
    Translate a mathematical expression node to q code.
    
    Args:
        node: The AST node to translate
        parent_op: The parent operator (for precedence decisions)
        parent_prec: The parent precedence level
        is_left_child: Whether this node is the left child of its parent
    """
    if node.type == 'number':
        return node.value
    elif node.type == 'name':
        return node.value
    elif node.type == 'atom':
        # Handle parenthesized expressions
        if len(node.children) == 3 and node.children[0].value == '(':
            # (expr) - translate the inner expression and preserve parentheses
            inner_result = translate_math_expr_node(node.children[1])
            return f"({inner_result})"
        else:
            # Other atoms, just translate first child
            return translate_math_expr_node(node.children[0], parent_op, parent_prec, is_left_child)
    elif node.type in ['arith_expr', 'term', 'power']:
        return translate_math_binary_expr(node, parent_op, parent_prec, is_left_child)
    else:
        # For non-arithmetic nodes, delegate back to the main translator
        return translate_to_q(node)

def translate_math_binary_expr(node, parent_op=None, parent_prec=0, is_left_child=False):
    """
    Translate a binary expression (arith_expr or term) to q code.
    Handles chained operations like a+b+c or a*b/c.
    """
    children = node.children
    
    if len(children) == 1:
        return translate_math_expr_node(children[0], parent_op, parent_prec, is_left_child)
    
    # Get this node's operator and precedence
    my_op, my_prec = get_math_operator_info(node)
    
    # Handle chained operations: a op b op c op d...
    # We need to build left-to-right for correct evaluation
    result = translate_math_expr_node(children[0], my_op, my_prec, True)
    
    # Process each operator-operand pair
    for i in range(1, len(children), 2):
        if i + 1 < len(children):
            op = children[i].value
            right_operand = children[i + 1]
            
            # Translate the right operand
            right_result = translate_math_expr_node(right_operand, op, MATH_PRECEDENCE[op], False)
            
            # Convert operator to q syntax
            q_op = PYTHON_TO_Q_MATH[op]
            
            # For chained operations, we need to group left-to-right
            # But only add parentheses if we have more operations after this
            if i + 2 < len(children):  # More operations follow
                result = f"({result}{q_op}{right_result})"
            else:  # Last operation
                result = f"{result}{q_op}{right_result}"
    
    # Decide if this entire expression needs parentheses
    needs_parens = False
    
    if parent_op is not None:
        # We need parentheses if:
        # 1. Parent has lower precedence and we're the left child
        #    (higher precedence on left needs parens in right-associative q)
        # 2. Same precedence but we're right child (q is right-associative)
        if parent_prec < my_prec and is_left_child:
            needs_parens = True
        elif parent_prec == my_prec and not is_left_child:
            # Right child with same precedence needs parens in right-associative language
            needs_parens = True
    
    if needs_parens:
        return f"({result})"
    else:
        return result

def translate_math_expr(node):
    """
    Translate a mathematical expression node to q code.
    Only handles pure arithmetic expressions.
    """
    return translate_math_expr_node(node)

def format_q_args(args):
    """Format a list of arguments/parameters for q syntax using semicolons"""
    return ';'.join(args)

def translate_suite(suite_node, indent_level=0):
    """Translate a suite (block of code) with proper semicolons and whitespace"""
    body_parts = []
    for stmt in suite_node.children:
        translated = translate_to_q(stmt, indent_level)
        if translated:
            body_parts.append(translated)
    return ''.join(body_parts)

def format_block_with_proper_closing(suite_node, indent_level, open_bracket, close_bracket):
    """Format a code block with proper indentation and closing bracket"""
    # Collect all statements (ignore newlines and whitespace)
    statements = []
    stmt_indent = '    ' * (indent_level + 1)
    
    for stmt in suite_node.children:
        translated = translate_to_q(stmt, indent_level + 1)
        if translated and translated.strip():  # Only collect non-empty statements
            statements.append(translated.strip())
    
    # Join statements with semicolons BETWEEN them (not after)
    if statements:
        body_lines = []
        for i, stmt in enumerate(statements):
            if i == len(statements) - 1:
                # Last statement: no semicolon
                body_lines.append(f"{stmt_indent}{stmt}")
            else:
                # Not last statement: add semicolon
                body_lines.append(f"{stmt_indent}{stmt};")
        body = '\n' + '\n'.join(body_lines) + '\n'
    else:
        body = '\n'
    
    closing_indent = '    ' * (indent_level + 1)
    return f"{body}{closing_indent}{close_bracket}"

def translate_statement_with_suite(node, keyword, template, indent_level=0):
    """Generic handler for statements that have a condition/expr and a suite"""
    condition = None
    suite_node = None
    
    for child in node.children:
        if child.type == 'keyword' and child.value == keyword:
            continue
        elif child.type == 'keyword' and child.value == 'times':  # Handle "times" keyword in do statements
            continue
        elif child.type == 'operator' and child.value == ':':
            continue
        elif child.type == 'suite':
            suite_node = child
        elif condition is None:
            condition = translate_to_q(child, indent_level)
    
    if suite_node:
        body = format_block_with_proper_closing(suite_node, indent_level, '[', ']')
        indent = '    ' * indent_level
        
        if keyword == 'if':
            return f"{indent}if[{condition}; {body}"
        elif keyword == 'while':
            return f"{indent}while[{condition}; {body}"
        elif keyword == 'do':
            return f"{indent}do[{condition}; {body}"
        else:
            return indent + template.format(condition=condition, body=body)
    
    indent = '    ' * indent_level
    return indent + template.format(condition=condition, body="")

def analyze_closure_variables(suite_node, local_params):
    """
    Analyze a suite (block of code) to find variables that need to be captured from closure.
    
    Args:
        suite_node: The AST suite node containing the function body
        local_params: Set of parameter names that are local to this function
        
    Returns:
        Set of variable names that need to be captured from the outer scope
    """
    referenced_vars = set()
    assigned_vars = set()
    
    def collect_variables(node):
        if hasattr(node, 'type'):
            if node.type == 'name':
                # This is a variable reference
                referenced_vars.add(node.value)
            elif node.type == 'expr_stmt' and hasattr(node, 'children'):
                # Check for assignments: var = expr
                if (len(node.children) >= 3 and 
                    node.children[1].type == 'operator' and 
                    node.children[1].value == '=' and
                    node.children[0].type == 'name'):
                    assigned_vars.add(node.children[0].value)
        
        # Recursively process children
        if hasattr(node, 'children'):
            for child in node.children:
                collect_variables(child)
    
    # Analyze the suite
    collect_variables(suite_node)
    
    # Remove local parameters and any locally assigned variables
    closure_vars = referenced_vars - assigned_vars - local_params
    
    # Remove built-in functions and keywords
    builtins = {'print', 'len', 'range', 'abs', 'converge', 'True', 'False', 'None'}
    closure_vars = closure_vars - builtins
    
    return closure_vars

def translate(code):
    """
    Translate a Qython code string to q code.
    
    Args:
        code: String containing Qython code
        
    Returns:
        String containing the translated q code
    """
    # Load custom grammar with extended syntax support
    import os
    grammar_path = os.path.join(os.path.dirname(__file__), 'custom_grammar.txt')
    
    # Check if custom grammar file exists before trying to load it
    if not os.path.exists(grammar_path):
        raise FileNotFoundError(f"Custom grammar file not found: {grammar_path}")
    
    try:
        custom_grammar = parso.load_grammar(path=grammar_path)
    except Exception as e:
        raise RuntimeError(f"Failed to load custom grammar from {grammar_path}: {e}") from e
    
    # Parse the AST using custom grammar
    tree = custom_grammar.parse(code)
    
    # Translate all top-level nodes (not just function definitions)
    translated_parts = []
    
    for child in tree.children:
        if hasattr(child, 'type') and child.type != 'endmarker':
            translated = translate_to_q(child, 0)  # Start with indent level 0
            if translated and translated.strip():
                translated_parts.append(translated)
    
    # Join all translated parts
    return '\n\n'.join(translated_parts)

def translate_file(filename):
    """
    Translate a Qython (.qy) file to q code.
    
    Args:
        filename: Path to the .qy file to translate
        
    Returns:
        String containing the translated q code
    """
    # Read the file
    with open(filename, 'r') as f:
        code = f.read()
    
    # Use the translate function
    return translate(code)

# Arithmetic expression translator for q
def getQOp(op_value):
    return {'+': '+', '*': '*', '-': '-', '/': '%', '**': ' xexp '}[op_value]

def hasOperators(node):
    return hasattr(node, 'type') and node.type in ['term', 'arith_expr', 'power'] and any(
        child.type == 'operator' and child.value in ['+', '*', '-', '/', '**']
        for child in getattr(node, 'children', [])
    )

def toQCode(node):
    if hasattr(node, 'type'):
        if node.type == 'number':
            return node.value
        elif node.type == 'string':
            return node.value
        elif node.type == 'name':
            return node.value
        elif node.type == 'atom' and hasattr(node, 'children'):
            # Handle parenthesized expressions: (expr)
            if len(node.children) == 3 and node.children[0].value == '(' and node.children[2].value == ')':
                # Return the inner expression with parentheses
                inner = toQCode(node.children[1])
                return f"({inner})"
            elif len(node.children) == 1:
                return toQCode(node.children[0])
            else:
                # Other atom types, process all children
                return ''.join(toQCode(child) for child in node.children if child.type != 'operator' or child.value not in ['(', ')'])
        elif node.type in ['term', 'arith_expr', 'power'] and hasattr(node, 'children'):
            # Handle binary operations
            children = node.children
            if len(children) == 1:
                return toQCode(children[0])
            elif len(children) >= 3:
                left = toQCode(children[0])
                op = children[1].value if children[1].type == 'operator' else '?'
                right = toQCode(children[2])
                
                if op in ['+', '*', '-', '/', '**']:
                    q_op = getQOp(op)
                    # Check if left side needs parentheses
                    if hasOperators(children[0]):
                        left = f"({left})"
                    return f"{left}{q_op}{right}"
                else:
                    return f"{left}{op}{right}"
            else:
                return toQCode(children[0]) if children else str(node)
        elif node.type == 'operator':
            return node.value
        elif node.type in ['power', 'atom_expr']:
            # These might be function calls, delegate to translate_to_q
            return translate_to_q(node)
        elif hasattr(node, 'children') and node.children:
            # For other node types with children, try to process them
            if len(node.children) == 1:
                return toQCode(node.children[0])
            else:
                parts = []
                for child in node.children:
                    part = toQCode(child)
                    if part:
                        parts.append(part)
                return ''.join(parts)
    
    return str(node)

# Find the function definition and extract it without docstring and defaults
def find_nodes_by_type(node, target_type, results=None):
    if results is None:
        results = []
    
    if hasattr(node, 'type') and node.type == target_type:
        results.append(node)
    
    if hasattr(node, 'children'):
        for child in node.children:
            find_nodes_by_type(child, target_type, results)
    
    return results

def extract_function_core(tree, func_name=None):
    # Find all function definitions
    funcdefs = find_nodes_by_type(tree, 'funcdef')
    
    for funcdef in funcdefs:
        # Get function name
        current_func_name = None
        for child in funcdef.children:
            if hasattr(child, 'type') and child.type == 'name':
                current_func_name = child.value
                break
        
        # If func_name is specified, only return that function
        if func_name and current_func_name != func_name:
            continue
            
        return funcdef
    
    return None

# Individual translator functions for each node type
def translate_funcdef(node, indent_level=0):
    """Function definition: nmsq:{[x;precision;max_iterations] ...}"""
    func_name = None
    params = []
    suite = None
    
    for child in node.children:
        if child.type == 'name':
            func_name = child.value
        elif child.type == 'parameters':
            # Extract parameter names
            for param_child in child.children:
                if param_child.type == 'param':
                    for param_part in param_child.children:
                        if param_part.type == 'name':
                            params.append(param_part.value)
        elif child.type == 'suite':
            suite = child
    
    if func_name and suite:
        # Only analyze closure variables for nested functions (indent_level > 0)
        is_nested = indent_level > 0
        
        if is_nested:
            # Analyze closure variables for nested functions
            local_params = set(params)
            closure_vars = analyze_closure_variables(suite, local_params)
            
            # Check q's 8-parameter limit (closure vars + explicit params)
            if len(closure_vars) + len(params) > 8:
                return f"// Error: Function {func_name} requires {len(closure_vars) + len(params)} parameters, but q supports max 8"
            
            # For nested functions, include closure variables in parameter list
            all_params = list(closure_vars) + params
            args = format_q_args(all_params)
        else:
            # Top-level functions don't have closure variables
            closure_vars = set()
            args = format_q_args(params)
        
        # Collect statements (skip docstring if present)
        statements = []
        stmt_indent = '    ' * (indent_level + 1)
        first_real_stmt = True
        
        for stmt in suite.children:
            # Skip docstring if it's the first statement
            if first_real_stmt and stmt.type == 'simple_stmt':
                if (hasattr(stmt, 'children') and len(stmt.children) >= 1 and 
                    stmt.children[0].type == 'string'):
                    first_real_stmt = False
                    continue
            first_real_stmt = False
            
            translated = translate_to_q(stmt, indent_level + 1)
            if translated and translated.strip():
                statements.append(translated.strip())
        
        # Format function body with semicolons between statements
        if statements:
            body_lines = []
            for i, stmt in enumerate(statements):
                if i == len(statements) - 1:
                    # Last statement: no semicolon
                    body_lines.append(f"{stmt_indent}{stmt}")
                else:
                    # Not last statement: add semicolon
                    body_lines.append(f"{stmt_indent}{stmt};")
            body = '\n' + '\n'.join(body_lines) + '\n'
        else:
            body = '\n'
        
        closing_indent = '    ' * (indent_level + 1)
        indent = '    ' * indent_level
        
        # Add closure variables after the function definition if any exist
        if closure_vars:
            closure_args = format_q_args(sorted(closure_vars))
            return f"{indent}{func_name}:{{[{args}] {body}{closing_indent}}}[{closure_args}]"
        else:
            return f"{indent}{func_name}:{{[{args}] {body}{closing_indent}}}"

def translate_if_stmt(node, indent_level=0):
    """if condition: body -> if[condition; body]"""
    return translate_statement_with_suite(node, 'if', 'if[{condition}; {body}]', indent_level)

def translate_while_stmt(node, indent_level=0):
    """while condition: body -> while[condition; body]"""
    return translate_statement_with_suite(node, 'while', 'while[{condition}; {body}]', indent_level)

def translate_converge_call(args):
    """Handle converge(step_func, starting_from=initial_value) -> step_func/[initial_value]"""
    if len(args) != 2:
        return "// Error: converge() requires exactly 2 arguments: step_func and starting_from=value"
    
    step_func = args[0]
    starting_from_arg = args[1]
    
    # Require the second argument to be a keyword argument starting_from=value
    if not starting_from_arg.startswith('starting_from='):
        return "// Error: converge() second argument must be starting_from=value"
    
    # Extract the value from starting_from=value
    starting_from_value = starting_from_arg[len('starting_from='):]
    
    # Generate q code: step_func/[starting_from_value]
    # Note: The step function should already have closure variables captured
    # when it was defined by translate_funcdef
    return f"{step_func}/[{starting_from_value}]"

def translate_reduce_call(args):
    """Handle reduce(binary_func, iterable) -> binary_func/[iterable]"""
    if len(args) != 2:
        return "// Error: reduce() requires exactly 2 arguments: binary_func and iterable"
    
    binary_func = args[0]
    iterable = args[1]
    
    # Generate q code: binary_func/[iterable]
    return f"{binary_func}/[{iterable}]"

def translate_range_call(args):
    """Handle range(n) -> til[n]"""
    if len(args) != 1:
        return "// Error: range() requires exactly 1 argument: n"
    
    # Use standard parameter formatting
    return f"til[{format_q_args(args)}]"

def translate_do_stmt(node, indent_level=0):
    """do <expr> times: body -> do[expr; body]"""
    return translate_statement_with_suite(node, 'do', 'do[{condition}; {body}]', indent_level)

def translate_simple_stmt(node, indent_level=0):
    """Handle simple statements that contain other statements"""
    if hasattr(node, 'children') and len(node.children) > 0:
        parts = []
        for child in node.children:
            translated = translate_to_q(child, indent_level)
            if translated and translated.strip():  # Only collect non-empty parts
                parts.append(translated.strip())
        
        # Join multiple parts if needed (shouldn't normally happen)
        return ' '.join(parts) if parts else ""
    return ""

def translate_expr_stmt(node):
    """Handle expression statements (assignments, etc.)"""
    if hasattr(node, 'children') and len(node.children) >= 3:
        # Look for assignment pattern: name = expr
        if node.children[1].type == 'operator' and node.children[1].value == '=':
            target = translate_to_q(node.children[0])
            value = translate_to_q(node.children[2])
            return f"{target}:{value}"
    return translate_to_q(node.children[0]) if node.children else ""

def translate_return_stmt(node):
    """return expr -> :expr"""
    if hasattr(node, 'children') and len(node.children) > 1:
        return f":{translate_to_q(node.children[1])}"
    else:
        return ":"

def translate_name(node):
    """Variable names"""
    return node.value

def translate_number(node):
    """Numbers"""
    return node.value

def translate_string(node):
    """Strings"""
    return node.value

def translate_keyword(node):
    """Keywords like True, False"""
    if node.value == 'True':
        return '1b'
    elif node.value == 'False':
        return '0b'
    else:
        return node.value

def translate_comparison(node):
    """Handle comparison expressions"""
    if hasattr(node, 'children') and len(node.children) >= 3:
        left = translate_to_q(node.children[0])
        op = node.children[1].value
        right = translate_to_q(node.children[2])
        
        if op == '<':
            return f"{left}<{right}"
        elif op == '==':
            return f"{left}={right}"
        else:
            return f"{left}{op}{right}"
    return str(node)

def translate_raise_stmt(node):
    """raise ValueError("msg") -> `$"msg" """
    if hasattr(node, 'children') and len(node.children) > 1:
        # Look for the error message
        for child in node.children:
            if child.type == 'atom' or child.type == 'power':
                # This is a function call like ValueError("message")
                # Extract the string argument
                for grandchild in child.children:
                    if hasattr(grandchild, 'children'):
                        for ggchild in grandchild.children:
                            if ggchild.type == 'string':
                                return f"`${ggchild.value}"
    return '`$"Error"'

def translate_term(node):
    """Handle arithmetic terms like x/2, (guess + x/guess) / 2"""
    return toQCode(node)

def translate_power(node):
    """Handle function calls (power nodes with trailers)"""
    if hasattr(node, 'children') and len(node.children) > 0:
        base = translate_to_q(node.children[0])
        
        if len(node.children) > 1 and node.children[1].type == 'trailer':
            # This is a function call like abs(...) or converge(...)
            trailer = node.children[1]
            if hasattr(trailer, 'children') and len(trailer.children) >= 2:
                if trailer.children[0].value == '(':
                    # Function call: base(args) -> base[args]
                    args = []
                    for child in trailer.children:
                        if child.type == 'arglist':
                            for arg_child in child.children:
                                if arg_child.type == 'argument':
                                    # Handle keyword arguments like starting_from=initial_state
                                    if (hasattr(arg_child, 'children') and len(arg_child.children) >= 3 and
                                        arg_child.children[1].type == 'operator' and arg_child.children[1].value == '='):
                                        key = arg_child.children[0].value
                                        value = translate_to_q(arg_child.children[2])
                                        args.append(f"{key}={value}")
                                    else:
                                        args.append(translate_to_q(arg_child))
                                elif arg_child.type != 'operator' or arg_child.value != ',':
                                    args.append(translate_to_q(arg_child))
                        elif child.type not in ['operator'] or child.value not in ['(', ')']:
                            translated = translate_to_q(child)
                            if translated:
                                args.append(translated)
                    # Filter out empty args
                    args = [arg for arg in args if arg and arg.strip()]
                    
                    # Special handling for converge function
                    if base == 'converge':
                        return translate_converge_call(args)
                    
                    # Special handling for reduce function
                    if base == 'reduce':
                        return translate_reduce_call(args)
                    
                    # Special handling for range function
                    if base == 'range':
                        return translate_range_call(args)
                    
                    return f"{base}[{format_q_args(args)}]"
        return base
    return str(node)

def translate_atom_expr(node):
    """Handle function calls like abs(x)"""
    if hasattr(node, 'children') and len(node.children) >= 2:
        # Should have name + trailer for function calls
        func_name = translate_to_q(node.children[0])
        
        for child in node.children[1:]:
            if child.type == 'trailer':
                # Function call trailer: (args)
                if hasattr(child, 'children') and len(child.children) >= 2:
                    if child.children[0].value == '(':
                        # Extract arguments using the same logic as translate_power
                        args = []
                        for trailer_child in child.children:
                            if trailer_child.type == 'arglist':
                                for arg_child in trailer_child.children:
                                    if arg_child.type == 'argument':
                                        # Handle keyword arguments like starting_from=initial_state
                                        if (hasattr(arg_child, 'children') and len(arg_child.children) >= 3 and
                                            arg_child.children[1].type == 'operator' and arg_child.children[1].value == '='):
                                            key = arg_child.children[0].value
                                            value = translate_to_q(arg_child.children[2])
                                            args.append(f"{key}={value}")
                                        else:
                                            args.append(translate_to_q(arg_child))
                                    elif arg_child.type != 'operator' or arg_child.value != ',':
                                        args.append(translate_to_q(arg_child))
                            elif trailer_child.type not in ['operator'] or trailer_child.value not in ['(', ')']:
                                translated = translate_to_q(trailer_child)
                                if translated:
                                    args.append(translated)
                        # Filter out empty args
                        args = [arg for arg in args if arg and arg.strip()]
                        
                        # Special handling for converge function
                        if func_name == 'converge':
                            return translate_converge_call(args)
                        
                        # Special handling for reduce function
                        if func_name == 'reduce':
                            return translate_reduce_call(args)
                        
                        # Special handling for range function
                        if func_name == 'range':
                            return translate_range_call(args)
                        
                        return f"{func_name}[{format_q_args(args)}]"
        
        # If not a function call, just return the first child
        return func_name
    
    return str(node)

def translate_atom(node):
    """Handle atomic expressions including lists [a, b, ...] -> (a; b; ...)"""
    if hasattr(node, 'children') and len(node.children) > 0:
        # Check if this is a list: [...]
        if (len(node.children) >= 3 and 
            node.children[0].type == 'operator' and node.children[0].value == '[' and
            node.children[-1].type == 'operator' and node.children[-1].value == ']'):
            
            # Extract list elements
            elements = []
            for child in node.children[1:-1]:  # Skip [ and ]
                if child.type == 'testlist_comp':
                    # Handle comma-separated list elements
                    for elem in child.children:
                        if elem.type != 'operator' or elem.value != ',':
                            elements.append(translate_to_q(elem))
                elif child.type not in ['operator']:
                    elements.append(translate_to_q(child))
            
            # Return q list format: (a; b; c)
            return f"({';'.join(elements)})"
        
        return translate_to_q(node.children[0])
    return str(node)

# Main translator function - now just a dispatcher
def translate_to_q(node, indent_level=0):
    if not hasattr(node, 'type'):
        return str(node)
    
    # Handle whitespace/formatting nodes - ignore them, structure handles formatting
    if node.type in ['newline', 'indent', 'dedent']:
        return ''
        
    # For mathematical expressions, delegate to the clean math translator
    # Only delegate if it's actually an arithmetic expression with operators
    if node.type in ['arith_expr', 'term'] and hasattr(node, 'children'):
        return translate_math_expr(node)
    elif node.type == 'power' and hasattr(node, 'children'):
        # For power nodes, only delegate if it contains ** operator (not function calls)
        has_power_op = any(
            child.type == 'operator' and child.value == '**' 
            for child in node.children
        )
        if has_power_op:
            return translate_math_expr(node)
    
    translators = {
        'funcdef': translate_funcdef,
        'if_stmt': translate_if_stmt,
        'while_stmt': translate_while_stmt,
        'do_stmt': translate_do_stmt,
        'simple_stmt': translate_simple_stmt,
        'expr_stmt': translate_expr_stmt,
        'return_stmt': translate_return_stmt,
        'raise_stmt': translate_raise_stmt,
        'name': translate_name,
        'number': translate_number,
        'string': translate_string,
        'keyword': translate_keyword,
        'comparison': translate_comparison,
        'term': translate_term,
        'power': translate_power,
        'atom_expr': translate_atom_expr,
        'atom': translate_atom,
    }
    
    if node.type in translators:
        if node.type in ['funcdef', 'if_stmt', 'while_stmt', 'do_stmt', 'simple_stmt']:
            return translators[node.type](node, indent_level)
        else:
            return translators[node.type](node)
    elif 'expr' in node.type:
        return toQCode(node)
    else:
        return f"// Unsupported: {node.type}"

