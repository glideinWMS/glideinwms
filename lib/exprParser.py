# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description: general purpose python expression parser and unparser
#
# Author:
#  Igor Sfiligoi
#


import ast
import itertools
from io import StringIO

from .unparser import Unparser

# Keeping this line from the Python 2 version to have a list of the objects supported
# NOTE: compiler.ast is slightly different from the concrete tree in ast
# from compiler.ast import Name, Const, Keyword, List, Tuple, And, Or, Not, UnaryAdd, UnarySub, Compare, Add, Sub, Mul, FloorDiv, Div, Mod, Power, LeftShift, RightShift, Bitand, Bitor, Bitxor, CallFunc, Getattr, Subscript, Slice, Lambda

# These are used in modules importing exprParser, like frontend_match_ana
from ast import And, Or, Not


def exp_parse(expression):
    """Convert an expression string into an ast object

    Args:
        expression (str): expression string

    Returns:
        ast.AST: ast tree from the expression, starting from ast.Expression node

    """
    # mode='exec' (default) for sequence of statements
    # eval - single expression
    # single - single interactive statement
    return ast.parse(expression, '<string>', mode='eval')


def exp_compile(obj):
    """Convert an ast object into a code object

    Args:
        obj (ast.AST): AST object to compile

    Returns:
        code object

    """
    return compile(obj, '<string>', mode='eval')


def exp_unparse(obj, raise_on_unknown=False):
    """Convert an ast object back into a string

    Args:
        obj (ast.AST): ast object to convert back to string
        raise_on_unknown (bool):

    Returns:
        str: string with the expression

    """
    with StringIO() as output:
        Unparser(obj, output)
        outstr = output.getvalue()
    return outstr.strip()


def exp_compare(node1, node2):
    """Compare 2 AST trees to verify if they are the same

    Args:
        node1 (ast.AST): AST tree
        node2 (ast.AST): AST tree

    Returns:
        bool: True if node1 and node2 are the same expression

    """
    if type(node1) is not type(node2):
        return False
    if isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in ('lineno', 'col_offset', 'ctx', 'end_lineno', 'end_col_offset'):
                continue
            if not exp_compare(v, getattr(node2, k)):
                return False
        return True
    elif isinstance(node1, list):
        return all(itertools.starmap(exp_compare, zip(node1, node2)))
    else:
        return node1 == node2
