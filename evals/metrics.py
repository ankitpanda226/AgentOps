"""Deterministic evaluation metrics for AgentOps Copilot."""

from numbers import Number
from typing import Any


def keyword_coverage(output_text: str, expected_keywords: list[str]) -> float:
    """Return the fraction of expected keywords present in output text."""
    if not expected_keywords:
        return 1.0

    normalized_output = output_text.lower()
    matched = sum(
        1 for keyword in expected_keywords if keyword.lower() in normalized_output
    )
    return matched / len(expected_keywords)


def required_fields_score(output: dict, expected_fields: list[str]) -> float:
    """Return the fraction of required fields present in an output dictionary."""
    if not expected_fields:
        return 1.0

    matched = sum(1 for field in expected_fields if _has_path(output, field))
    return matched / len(expected_fields)


def tool_coverage(actual_tools: list[str], expected_tools: list[str]) -> float:
    """Return the fraction of expected tools found in actual tools."""
    if not expected_tools:
        return 1.0

    normalized_actual = {tool.lower() for tool in actual_tools}
    matched = sum(1 for tool in expected_tools if tool.lower() in normalized_actual)
    return matched / len(expected_tools)


def aggregate_score(scores: dict) -> float:
    """Average all numeric metric values in a score dictionary."""
    numeric_scores = [
        float(value)
        for value in scores.values()
        if isinstance(value, Number) and not isinstance(value, bool)
    ]
    if not numeric_scores:
        return 0.0
    return sum(numeric_scores) / len(numeric_scores)


def _has_path(value: Any, path: str) -> bool:
    current = value
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current or current[part] is None:
                return False
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current) or current[index] is None:
                return False
            current = current[index]
            continue
        return False
    return True
