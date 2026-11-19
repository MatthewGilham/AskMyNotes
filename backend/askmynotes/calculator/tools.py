"""The `calculate` and `solve_equation` tools the agent can always use.

They run on this computer, cost nothing, and record each run in a `ToolRuns`
so it can be saved with the answer and listed in its "Working" panel. A run
that fails isn't an error in the app: the message goes back to the model as the
tool's answer, so it can correct itself.
"""

import sympy
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from askmynotes.calculator.evaluate import (
    CalculationError,
    Result,
    calculate,
    show_number,
    solve_equation,
)
from askmynotes.calculator.latex import to_latex
from askmynotes.chats.models import ToolRun

CALCULATE_TOOL_NAME = "calculate"
SOLVE_TOOL_NAME = "solve_equation"
CALCULATOR_TOOL_NAMES = (CALCULATE_TOOL_NAME, SOLVE_TOOL_NAME)

CALCULATE_DESCRIPTION = """\
Work out a calculation exactly. Use it for any arithmetic beyond the trivial.
Returns the result as a decimal, and as an exact fraction when that is short.

Write the expression with numbers, + - * / ^ and brackets. Write percentages as
decimals (5% is 0.05). Constants: pi, e. Functions:
- sqrt(x), ln(x) natural log, log(x) base 10 or log(x, base), exp(x), abs(x),
  round(x) or round(x, decimal_places), min(a, b, ...), max(a, b, ...)
- sum([..]), mean([..]), variance([..]) and stdev([..]), both for a SAMPLE
  (divide by n - 1)
- npv(rate, [cf0, cf1, cf2, ...]): cf0 is at time 0 and is NOT discounted, so
  include the initial outlay in the list as a negative number
- irr([cf0, cf1, ...]): the rate that makes the NPV zero
- pv(rate, periods, payment, future=0): present value of equal payments at the
  END of each period, plus a lump sum at the end
- fv(rate, periods, payment, present=0): future value of equal payments at the
  END of each period, plus a lump sum invested now
- pmt(rate, periods, present, future=0): the equal end-of-period payment that
  pays off `present` now
All amounts are positive as written; no sign flipping."""

SOLVE_DESCRIPTION = """\
Solve an equation for one unknown and return its real solutions. For example
equation "1000 = 80/(1+r) + 1080/(1+r)^2" with unknown "r". Use + - * / ^,
brackets, sqrt, ln, log, exp and abs. Percentages are decimals (5% is 0.05).
An equation can have more than one solution; say which one makes sense."""


class ToolRuns:
    """The calculations one reply made, in order."""

    def __init__(self) -> None:
        self.runs: list[ToolRun] = []


class CalculateArguments(BaseModel):
    expression: str = Field(description="The expression to work out.")


class SolveArguments(BaseModel):
    equation: str = Field(description="An equation with exactly one '=' sign.")
    unknown: str = Field(description="The name of the unknown, such as r or x.")


def latex_or_none(text: str) -> str | None:
    try:
        return to_latex(text)
    except SyntaxError:
        return None


def latex_of_result(result: Result) -> str:
    """A result as maths: the exact form, then the decimal if they differ."""
    value = result.value
    exact = sympy.latex(value)
    shown = show_number(value)
    if isinstance(value, sympy.Integer) or value.is_Float:
        return shown
    return rf"{exact} \approx {shown}"


def calculator_tools(runs: ToolRuns) -> list[BaseTool]:
    """The two tools for one reply, recording every run in `runs`."""

    def calculate_expression(expression: str) -> str:
        try:
            result = calculate(expression)
        except CalculationError as error:
            runs.runs.append(
                ToolRun(
                    tool=CALCULATE_TOOL_NAME,
                    input=expression,
                    result=str(error),
                    ok=False,
                    input_latex=latex_or_none(expression),
                    result_latex=None,
                )
            )
            return f"Error: {error}"
        runs.runs.append(
            ToolRun(
                tool=CALCULATE_TOOL_NAME,
                input=expression,
                result=result.text,
                ok=True,
                input_latex=latex_or_none(expression),
                result_latex=latex_of_result(result),
            )
        )
        return f"= {result.text}"

    def solve(equation: str, unknown: str) -> str:
        shown = f"{equation}  (for {unknown})"
        try:
            results = solve_equation(equation, unknown)
        except CalculationError as error:
            runs.runs.append(
                ToolRun(
                    tool=SOLVE_TOOL_NAME,
                    input=shown,
                    result=str(error),
                    ok=False,
                    input_latex=latex_or_none(equation),
                    result_latex=None,
                )
            )
            return f"Error: {error}"
        text = "; ".join(f"{unknown} = {r.text}" for r in results)
        maths = ",\\; ".join(f"{unknown} = {latex_of_result(r)}" for r in results)
        runs.runs.append(
            ToolRun(
                tool=SOLVE_TOOL_NAME,
                input=shown,
                result=text,
                ok=True,
                input_latex=latex_or_none(equation),
                result_latex=maths,
            )
        )
        return text

    return [
        StructuredTool.from_function(
            func=calculate_expression,
            name=CALCULATE_TOOL_NAME,
            description=CALCULATE_DESCRIPTION,
            args_schema=CalculateArguments,
        ),
        StructuredTool.from_function(
            func=solve,
            name=SOLVE_TOOL_NAME,
            description=SOLVE_DESCRIPTION,
            args_schema=SolveArguments,
        ),
    ]
