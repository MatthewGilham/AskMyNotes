"""Turns a calculator expression into LaTeX, for the "Working" panel.

The panel shows what was asked as written maths, not as the text the model
typed. This only reads the same tree the calculator accepts, so it never sees
anything unusual; if it still can't write something, the panel falls back to
the plain text.
"""

import ast

# Higher binds tighter. A child that binds more loosely than its parent needs
# brackets round it.
PRECEDENCE = {ast.Add: 1, ast.Sub: 1, ast.Mult: 2, ast.Div: 2, ast.Pow: 4}
UNARY = 3

OPERATORS = {ast.Add: "+", ast.Sub: "-", ast.Mult: r"\times"}


def to_latex(text: str) -> str:
    """LaTeX for an expression, or for `left = right` (either side may be an
    equation's). Raises `SyntaxError` for text that isn't an expression."""
    source = text.strip().replace("^", "**")
    sides = [side.strip() for side in source.split("=")]
    return " = ".join(walk(ast.parse(side, mode="eval").body, side) for side in sides)


def precedence(node: ast.AST) -> int:
    if isinstance(node, ast.BinOp):
        return PRECEDENCE[type(node.op)]
    if isinstance(node, ast.UnaryOp):
        return UNARY
    return 9


def wrapped(node: ast.AST, source: str, tighter_than: int) -> str:
    """A child, in brackets if it binds more loosely than `tighter_than`."""
    inner = walk(node, source)
    if precedence(node) < tighter_than:
        return rf"\left({inner}\right)"
    return inner


def walk(node: ast.AST, source: str) -> str:
    match node:
        case ast.Constant():
            return (ast.get_source_segment(source, node) or str(node.value)).replace(
                "_", ""
            )
        case ast.Name(id="pi"):
            return r"\pi"
        case ast.Name(id=name):
            return name
        case ast.UnaryOp(op=ast.USub(), operand=operand):
            return "-" + wrapped(operand, source, UNARY)
        case ast.UnaryOp(operand=operand):
            return wrapped(operand, source, UNARY)
        case ast.BinOp(left=left, op=ast.Div(), right=right):
            return rf"\frac{{{walk(left, source)}}}{{{walk(right, source)}}}"
        case ast.BinOp(left=left, op=ast.Pow(), right=right):
            base = wrapped(left, source, PRECEDENCE[ast.Pow] + 1)
            return f"{base}^{{{walk(right, source)}}}"
        case ast.BinOp(left=left, op=op, right=right):
            level = PRECEDENCE[type(op)]
            # The right side of a subtraction needs brackets at the same level.
            right_level = level + 1 if isinstance(op, ast.Sub) else level
            return (
                f"{wrapped(left, source, level)} {OPERATORS[type(op)]} "
                f"{wrapped(right, source, right_level)}"
            )
        case ast.List(elts=items):
            return r"\left[" + ", ".join(walk(i, source) for i in items) + r"\right]"
        case ast.Call(func=ast.Name(id="sqrt"), args=[argument]):
            return rf"\sqrt{{{walk(argument, source)}}}"
        case ast.Call(func=ast.Name(id=name), args=arguments):
            shown = ", ".join(walk(a, source) for a in arguments)
            if name == "ln":
                return rf"\ln\left({shown}\right)"
            return rf"\operatorname{{{name}}}\left({shown}\right)"
    raise SyntaxError("can't be written as maths")
