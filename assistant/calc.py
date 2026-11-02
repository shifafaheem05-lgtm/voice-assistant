"""Safe calculator for spoken or typed maths such as 'twelve times 7' or '2 to the power of 8'."""
from __future__ import annotations

import ast
import operator
import re

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
       ast.FloorDiv: operator.floordiv}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90}

PHRASES = [  # longest first so 'divided by' wins over 'by'
    (r"\bto the power of\b", " ** "), (r"\braised to\b", " ** "), (r"\bmultiplied by\b", " * "),
    (r"\bdivided by\b", " / "), (r"\bplus\b", " + "), (r"\bminus\b", " - "), (r"\btimes\b", " * "),
    (r"\bover\b", " / "), (r"\bmod\b", " % "), (r"(?<=\d)\s*x\s*(?=\d)", " * "), (r"\^", " ** "),
]
MAX_POWER = 100
MAX_ABS = 10 ** 15


class CalcError(Exception):
    """The text is not a calculation we can evaluate."""


def _number_words(text: str) -> str:
    def tens_unit(m):
        return str(TENS[m.group(1)] + UNITS[m.group(2)])
    text = re.sub(r"\b(" + "|".join(TENS) + r")[ -](" + "|".join(k for k in UNITS if 0 < UNITS[k] < 10) + r")\b",
                  tens_unit, text)
    for word, value in {**UNITS, **TENS}.items():
        text = re.sub(rf"\b{word}\b", str(value), text)
    return text


def to_expression(text: str) -> str:
    expr = text.lower().replace(",", "")
    expr = _number_words(expr)
    for pattern, repl in PHRASES:
        expr = re.sub(pattern, repl, expr)
    return re.sub(r"\s+", " ", expr).strip()


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_POWER:
            raise CalcError("that exponent is too large")
        try:
            result = OPS[type(node.op)](left, right)
        except ZeroDivisionError:
            raise CalcError("I can't divide by zero") from None
        if isinstance(result, complex):
            raise CalcError("I can't work with that kind of number")
        if abs(result) > MAX_ABS:
            raise CalcError("that number is too large")
        return result
    raise CalcError("I can only do simple arithmetic")


def calculate(text: str):
    """Return the numeric result, or raise CalcError."""
    expr = to_expression(text)
    if not re.search(r"\d", expr) or not re.search(r"[-+*/%]", expr):
        raise CalcError("not a calculation")
    if re.search(r"[^\d\s.+\-*/%()]", expr):
        raise CalcError("not a calculation")
    try:
        value = _eval(ast.parse(expr, mode="eval"))
    except SyntaxError:
        raise CalcError("I couldn't understand that calculation") from None
    return round(value, 6) if isinstance(value, float) else value


def format_number(value) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}" if isinstance(value, int) else f"{value:g}"
