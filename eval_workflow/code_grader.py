import ast
import json
import re


def validate_python(text: str) -> int:
    if not text.strip():
        return 0
    try:
        ast.parse(text.strip())
        return 10
    except SyntaxError:
        return 0


def validate_json(text: str) -> int:
    try:
        json.loads(text.strip())
        return 10
    except json.JSONDecodeError:
        return 0


def validate_regex(text: str) -> int:
    if not text.strip():
        return 0
    try:
        re.compile(text.strip())
        return 10
    except re.error:
        return 0


def grade_syntax(output: str, test_case: dict) -> int | None:
    """Check raw output syntax without executing it. Prose has no syntax score."""
    output_format = test_case.get("format", "text")
    if output_format == "text":
        return None
    validators = {"python": validate_python, "json": validate_json, "regex": validate_regex}
    if output_format not in validators:
        raise ValueError(f"Unsupported output format: {output_format}")
    return validators[output_format](output)
