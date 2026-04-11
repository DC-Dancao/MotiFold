# backend/tests/fixtures/golden_loader.py
import json
from pathlib import Path
from typing import Any


def load_golden_cases(category: str, name: str) -> list[dict[str, Any]]:
    """
    Load golden test cases from JSON file.

    Args:
        category: subdirectory under fixtures/golden/, e.g. 'research', 'blackboard'
        name: filename without .json, e.g. 'clarify_topic'

    Returns:
        List of test case dicts from the 'test_cases' field.
    """
    path = Path(__file__).parent / "golden" / category / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Golden file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_cases", [])
