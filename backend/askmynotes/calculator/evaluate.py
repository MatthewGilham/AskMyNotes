"""A safe calculator: reads an expression with Python's `ast` module and works
it out exactly with SymPy.

The model writes the expression, and the model may have read web pages and
documents, so the text is never run. Not with `eval`, and not with SymPy's own
parser either (which uses `eval`). `ast.parse` only builds a tree of what was
written; this module walks the tree and accepts numbers, a few operators and a
fixed list of functions. Anything else is refused with a message that says what
was wrong, which goes back to the model so it can correct itself.
"""

import ast
import math
from collections.abc import Callable
from dataclasses import dataclass

import sympy

MAX_EXPRESSION_CHARACTERS = 500
MAX_NODES = 300
MAX_LIST_ITEMS = 200
# A power such as 2^100000 would take far too long to work out exactly.
MAX_EXPONENT = 1000
# Bigger exact numbers than this (in bits) are refused, so repeated powers can't
# make one that takes forever to work out.
MAX_BITS = 10_000
SIGNIFICANT_DIGITS = 12
# "(exact p/q)" is only shown when it is short enough to be worth reading.
MAX_EXACT_CHARACTERS = 40
ZERO = sympy.Integer(0)
TEN = sympy.Integer(10)


class CalculationError(Exception):
    """The expression can't be worked out; the message says why."""


@dataclass
class Result:
    """A worked-out value, and how to show it."""

    value: sympy.Basic
    text: str


# Names a student's formula may use.
CONSTANTS: dict[str, sympy.Basic] = {"pi": sympy.pi, "e": sympy.E}


def check_size(value: sympy.Basic) -> sympy.Basic:
    """Refuse an exact number too big to be worth working out."""
    if isinstance(value, sympy.Rational):
        bits = max(abs(int(value.p)).bit_length(), int(value.q).bit_length())
        if bits > MAX_BITS:
            raise CalculationError("That number is too large to work out.")
    return value


def as_real(value: sympy.Basic) -> sympy.Basic:
    """The value if it is a real, finite number; otherwise a clear refusal."""
    if value in (sympy.zoo, sympy.oo, -sympy.oo) or value.has(sympy.nan):
        raise CalculationError(
            "The result is infinite or undefined (division by zero?)."
        )
    if value.is_real is False or value.has(sympy.I):
        raise CalculationError("The result isn't a real number.")
    return value


def number_list(value: object, name: str) -> list[sympy.Basic]:
    if not isinstance(value, list) or not value:
        raise CalculationError(f"{name} needs a list of numbers such as [1, 2, 3].")
    return value


def mean(numbers: list[sympy.Basic]) -> sympy.Basic:
    return sympy.Add(*numbers) / len(numbers)


def variance(numbers: list[sympy.Basic]) -> sympy.Basic:
    """The sample variance: squared distances from the mean over n - 1."""
    if len(numbers) < 2:
        raise CalculationError("variance and stdev need at least two numbers.")
    centre = mean(numbers)
    return sympy.Add(*[(n - centre) ** 2 for n in numbers]) / (len(numbers) - 1)


def npv(rate: sympy.Basic, cash_flows: list[sympy.Basic]) -> sympy.Basic:
    """Net present value. The first cash flow is at time 0 and isn't discounted."""
    number_list(cash_flows, "npv")
    return sympy.Add(*[cf / (1 + rate) ** t for t, cf in enumerate(cash_flows)])


def irr(cash_flows: list[sympy.Basic]) -> sympy.Basic:
    """The rate that makes the NPV zero, found as a root of a polynomial in
    x = 1 / (1 + rate). With several answers the one nearest zero is given."""
    number_list(cash_flows, "irr")
    if len(cash_flows) < 2:
        raise CalculationError("irr needs at least two cash flows.")
    x = sympy.Symbol("x")
    polynomial = sympy.Poly(sum(cf * x**t for t, cf in enumerate(cash_flows)), x)
    rates = [
        1 / root - 1
        for root in polynomial.nroots(n=SIGNIFICANT_DIGITS + 4, maxsteps=200)
        if abs(sympy.im(root)) < 1e-9 and sympy.re(root) > 0
    ]
    if not rates:
        raise CalculationError("These cash flows have no internal rate of return.")
    return sympy.Float(sympy.re(min(rates, key=abs)), SIGNIFICANT_DIGITS)


def annuity_factor(rate: sympy.Basic, periods: sympy.Basic) -> sympy.Basic:
    """What a payment of 1 at the end of each period is worth now."""
    if rate == 0:
        return periods
    return (1 - (1 + rate) ** -periods) / rate


def pv(
    rate: sympy.Basic,
    periods: sympy.Basic,
    payment: sympy.Basic,
    future: sympy.Basic = ZERO,
) -> sympy.Basic:
    """Present value of equal payments at the end of each period, plus a
    lump sum `future` at the end. All amounts are positive, as written."""
    return payment * annuity_factor(rate, periods) + future / (1 + rate) ** periods


def fv(
    rate: sympy.Basic,
    periods: sympy.Basic,
    payment: sympy.Basic,
    present: sympy.Basic = ZERO,
) -> sympy.Basic:
    """Future value of equal payments at the end of each period, plus a lump
    sum `present` invested now."""
    return (
        payment * annuity_factor(rate, periods) * (1 + rate) ** periods
        + present * (1 + rate) ** periods
    )


def pmt(
    rate: sympy.Basic,
    periods: sympy.Basic,
    present: sympy.Basic,
    future: sympy.Basic = ZERO,
) -> sympy.Basic:
    """The equal payment at the end of each period that pays off `present`
    now (and a lump sum `future` at the end)."""
    return (present - future / (1 + rate) ** periods) / annuity_factor(rate, periods)


def rounded(value: sympy.Basic, digits: sympy.Basic = ZERO) -> sympy.Basic:
    """Round to a number of decimal places (halves round up in size)."""
    places = int(digits)
    scale = sympy.Integer(10) ** places
    return (
        sympy.floor(abs(value) * scale + sympy.Rational(1, 2))
        * sympy.sign(value)
        / scale
    )


def real_log(value: sympy.Basic, base: sympy.Basic = TEN) -> sympy.Basic:
    return sympy.log(value, base)


# name -> (function, number of arguments allowed)
FUNCTIONS: dict[str, tuple[Callable[..., sympy.Basic], range]] = {
    "sqrt": (sympy.sqrt, range(1, 2)),
    "ln": (sympy.log, range(1, 2)),
    "log": (real_log, range(1, 3)),
    "exp": (sympy.exp, range(1, 2)),
    "abs": (sympy.Abs, range(1, 2)),
    "round": (rounded, range(1, 3)),
    "min": (lambda *a: sympy.Min(*a), range(2, 20)),
    "max": (lambda *a: sympy.Max(*a), range(2, 20)),
    "sum": (lambda a: sympy.Add(*number_list(a, "sum")), range(1, 2)),
    "mean": (lambda a: mean(number_list(a, "mean")), range(1, 2)),
    "variance": (lambda a: variance(number_list(a, "variance")), range(1, 2)),
    "stdev": (lambda a: sympy.sqrt(variance(number_list(a, "stdev"))), range(1, 2)),
    "npv": (npv, range(2, 3)),
    "irr": (irr, range(1, 2)),
    "pv": (pv, range(3, 5)),
    "fv": (fv, range(3, 5)),
    "pmt": (pmt, range(3, 5)),
}
# Functions that return something other than a plain number can't be used inside
# solve_equation, which needs expressions it can differentiate and solve.
SOLVABLE_FUNCTIONS = {"sqrt", "ln", "log", "exp", "abs"}


class Evaluator:
    """Walks an expression's tree, working out each part exactly."""

    def __init__(self, unknown: str | None = None) -> None:
        self._source = ""
        self._unknown = unknown
        self.symbol = sympy.Symbol(unknown) if unknown else None

    def read(self, text: str) -> sympy.Basic | list:
        """Read a piece of text and work it out."""
        # In Python `^` is "exclusive or", which binds more loosely than + and
        # *. A student means a power, so it becomes `**` before reading.
        self._source = text.strip().replace("^", "**")
        return self.evaluate(parse(self._source))

    def evaluate(self, node: ast.AST) -> sympy.Basic | list:
        match node:
            case ast.Expression(body=body):
                return self.evaluate(body)
            case ast.Constant(value=value) if isinstance(
                value, int | float
            ) and not isinstance(value, bool):
                # Read from the text as written, so 0.1 is exactly a tenth.
                text = ast.get_source_segment(self._source, node) or str(value)
                return sympy.Rational(text.replace("_", ""))
            case ast.Name(id=name):
                if name in CONSTANTS:
                    return CONSTANTS[name]
                if self.symbol is not None and name == self._unknown:
                    return self.symbol
                raise CalculationError(f"I don't know the name '{name}'.")
            case ast.UnaryOp(op=ast.USub(), operand=operand):
                return -self._number(operand)
            case ast.UnaryOp(op=ast.UAdd(), operand=operand):
                return self._number(operand)
            case ast.BinOp(left=left, op=op, right=right):
                return self._binary(left, op, right)
            case ast.Call(func=ast.Name(id=name), args=args, keywords=[]):
                return self._call(name, args)
            case ast.List(elts=items):
                if len(items) > MAX_LIST_ITEMS:
                    raise CalculationError(
                        f"Lists can have at most {MAX_LIST_ITEMS} items."
                    )
                return [self._number(item) for item in items]
        raise CalculationError(
            f"'{ast.unparse(node)}' isn't something the calculator can do."
        )

    def _number(self, node: ast.AST) -> sympy.Basic:
        value = self.evaluate(node)
        if isinstance(value, list):
            raise CalculationError(
                "A list can only be used inside a function such as sum or npv."
            )
        return value

    def _binary(self, left: ast.AST, op: ast.operator, right: ast.AST) -> sympy.Basic:
        a, b = self._number(left), self._number(right)
        match op:
            case ast.Add():
                result = a + b
            case ast.Sub():
                result = a - b
            case ast.Mult():
                result = a * b
            case ast.Div():
                if b == 0:
                    raise CalculationError("Division by zero.")
                result = a / b
            case ast.Pow():
                if b.is_number and abs(b) > MAX_EXPONENT:
                    raise CalculationError(
                        f"Exponents above {MAX_EXPONENT} are refused."
                    )
                result = a**b
            case _:
                raise CalculationError(
                    f"The operator '{type(op).__name__}' isn't allowed."
                )
        return check_size(result)

    def _call(self, name: str, args: list[ast.expr]) -> sympy.Basic:
        if name not in FUNCTIONS:
            raise CalculationError(f"I don't know the function '{name}'.")
        if self._unknown is not None and name not in SOLVABLE_FUNCTIONS:
            raise CalculationError(f"{name} can't be used inside an equation to solve.")
        function, allowed = FUNCTIONS[name]
        if len(args) not in allowed:
            raise CalculationError(
                f"{name} was given {len(args)} argument(s), which it can't take."
            )
        values = [self.evaluate(a) for a in args]
        try:
            return check_size(function(*values))
        except CalculationError:
            raise
        except (
            TypeError,
            ValueError,
            ZeroDivisionError,
            sympy.PolynomialError,
        ) as error:
            raise CalculationError(f"{name} couldn't be worked out: {error}") from error


def parse(text: str) -> ast.Expression:
    """Read the text into a tree, refusing an over-long or nonsensical one."""
    if not text:
        raise CalculationError("The expression is empty.")
    if len(text) > MAX_EXPRESSION_CHARACTERS:
        raise CalculationError(
            f"Expressions are limited to {MAX_EXPRESSION_CHARACTERS} characters."
        )
    try:
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as error:
        raise CalculationError(f"I couldn't read that expression: {error}") from error
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise CalculationError("That expression is too long.")
    return tree


def show_number(value: sympy.Basic) -> str:
    """A number as a student reads it: whole numbers in full, others to twelve
    significant digits without trailing zeros."""
    if isinstance(value, sympy.Integer):
        return str(value)
    number = float(sympy.N(value, SIGNIFICANT_DIGITS + 5))
    if math.isinf(number):
        return str(sympy.N(value, SIGNIFICANT_DIGITS))
    return f"{number:.{SIGNIFICANT_DIGITS}g}"


def describe(value: sympy.Basic) -> str:
    """`24691/20` becomes "1234.55 (exact 24691/20)"; a whole number is itself."""
    value = as_real(value)
    shown = show_number(value)
    if isinstance(value, sympy.Integer) or value.is_Float:
        return shown
    exact = f"{value.p}/{value.q}" if isinstance(value, sympy.Rational) else str(value)
    return shown if len(exact) > MAX_EXACT_CHARACTERS else f"{shown} (exact {exact})"


def calculate(expression: str) -> Result:
    """Work an expression out exactly; raises `CalculationError` if it can't."""
    value = Evaluator().read(expression)
    if isinstance(value, list):
        raise CalculationError("The result is a list; ask for one number.")
    value = as_real(value)
    return Result(value, describe(value))


def solve_equation(equation: str, unknown: str) -> list[Result]:
    """The real solutions of an equation for one unknown, such as
    `1000 = 80/(1+r) + 1080/(1+r)^2` for `r`."""
    if not unknown.isidentifier() or unknown in CONSTANTS or unknown in FUNCTIONS:
        raise CalculationError(f"'{unknown}' can't be used as the unknown.")
    sides = equation.split("=")
    if len(sides) != 2:
        raise CalculationError("The equation needs exactly one '=' sign.")
    evaluator = Evaluator(unknown)
    left, right = (evaluator.read(side) for side in sides)
    if isinstance(left, list) or isinstance(right, list):
        raise CalculationError("An equation can't contain a list.")
    difference = sympy.together(left - right)
    if evaluator.symbol not in difference.free_symbols:
        raise CalculationError(f"The equation doesn't contain '{unknown}'.")
    try:
        solutions = sympy.solve(difference, evaluator.symbol)
    except (NotImplementedError, TypeError, ValueError) as error:
        raise CalculationError(f"I couldn't solve that equation: {error}") from error
    real = [s for s in solutions if s.is_real and not s.has(sympy.I)]
    if not real:
        raise CalculationError("The equation has no real solutions.")
    return [Result(s, describe(s)) for s in sorted(real, key=lambda s: float(s))]
