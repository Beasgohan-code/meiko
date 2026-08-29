"""Safe arithmetic / math expression evaluator tool (no arbitrary code exec)."""
from __future__ import annotations

import math
from typing import Any

from simpleeval import EvalWithCompoundTypes

from .base import Tool


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate a mathematical expression safely (arithmetic, trig, log, etc). Use for any precise calculation."
    parameters = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression, e.g. '(23*7)/3 + sqrt(16)'"},
        },
        "required": ["expression"],
    }

    async def run(self, expression: str, **_: Any) -> str:
        try:
            evaluator = EvalWithCompoundTypes()
            evaluator.functions.update({
                "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
                "log": math.log, "log10": math.log10, "exp": math.exp, "pi": math.pi,
                "abs": abs, "round": round, "pow": pow, "floor": math.floor, "ceil": math.ceil,
            })
            evaluator.names.update({"pi": math.pi, "e": math.e})
            result = evaluator.eval(expression)
            return str(result)
        except Exception as e:
            return f"Error evaluating expression: {e}"
