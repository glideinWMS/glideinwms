# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Description: General purpose Python expression parser and unparser."""

import ast
import itertools

# These are used in modules importing exprParser, like frontend_match_ana
from ast import And, Not, Or  # noqa: F401
from io import StringIO

from .unparser import Unparser

# Keeping this line from the Python 2 version to have a list of the objects supported
# NOTE: compiler.ast is slightly different from the concrete tree in ast
# from compiler.ast import Name, Const, Keyword, List, Tuple, And, Or, Not, UnaryAdd, UnarySub, Compare, Add, Sub,
#     Mul, FloorDiv, Div, Mod, Power, LeftShift, RightShift, Bitand, Bitor, Bitxor, CallFunc, Getattr, Subscript,
#     Slice, Lambda


def exp_parse(expression):
    """Convert an expression string into an AST object.

    Args:
        expression (str): The expression string.

    Returns:
        ast.AST: AST tree from the expression, starting from ast.Expression node.
    """
    # mode='exec' (default) for sequence of statements
    # eval - single expression
    # single - single interactive statement
    return ast.parse(expression, "<string>", mode="eval")


def exp_compile(obj):
    """Convert an AST object into a code object.

    Args:
        obj (ast.AST): AST object to compile.

    Returns:
        code: Compiled code object.
    """
    return compile(obj, "<string>", mode="eval")


def exp_unparse(obj, raise_on_unknown=False):
    """Convert an AST object back into a string.

    Args:
        obj (ast.AST): AST object to convert back to string.
        raise_on_unknown (bool): Flag to raise an error on unknown nodes.

    Returns:
        str: String with the expression.
    """
    with StringIO() as output:
        Unparser(obj, output)
        outstr = output.getvalue()
    return outstr.strip()


def exp_compare(node1, node2):
    """Compare two AST trees to verify if they are the same.

    Args:
        node1 (ast.AST): First AST tree.
        node2 (ast.AST): Second AST tree.

    Returns:
        bool: True if node1 and node2 represent the same expression, False otherwise.
    """
    if type(node1) is not type(node2):
        return False
    if isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in ("lineno", "col_offset", "ctx", "end_lineno", "end_col_offset"):
                continue
            if not exp_compare(v, getattr(node2, k)):
                return False
        return True
    elif isinstance(node1, list):
        return all(itertools.starmap(exp_compare, zip(node1, node2)))
    else:
        return node1 == node2
