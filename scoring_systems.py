"""Scoring utilities for WRRC data analysis."""

from __future__ import annotations

from statistics import median
from typing import Dict, Iterable, List, Optional, Tuple


CATEGORY_CODES = ["BBW", "BBM", "LF", "DF", "MI"]


def _parse_score(value) -> Optional[float]:
    """Convert a score value stored with either a dot or comma decimal separator."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _scaled_median_from_scores(scores: Iterable[float]) -> Optional[float]:
    """Compute the scaled median value for a single category."""
    numeric_scores = [s for s in scores if s is not None]
    if not numeric_scores:
        return None

    med = median(numeric_scores)
    weights: List[float] = []
    weighted_values: List[float] = []

    for value in numeric_scores:
        diff = abs(value - med)
        weight = 1.0 / (1.0 + diff ** 2)
        weights.append(weight)
        weighted_values.append(value * weight)

    total_weight = sum(weights)
    if total_weight == 0:
        return None

    return sum(weighted_values) / total_weight


def _simple_average(scores: Iterable[float]) -> Optional[float]:
    numeric_scores = [s for s in scores if s is not None]
    if not numeric_scores:
        return None
    return sum(numeric_scores) / len(numeric_scores)


def _trimmed_average(scores: Iterable[float]) -> Optional[float]:
    numeric_scores = sorted(s for s in scores if s is not None)
    if len(numeric_scores) <= 2:
        # Not enough scores to trim both ends; fall back to simple average
        return _simple_average(numeric_scores)

    trimmed = numeric_scores[1:-1]
    if not trimmed:
        return _simple_average(numeric_scores)
    return sum(trimmed) / len(trimmed)


def scaled_median(categories: Dict[str, Dict]) -> Tuple[Dict[str, Optional[float]], Optional[float]]:
    """Calculate scaled-median category scores and total for a couple.

    Parameters
    ----------
    categories:
        A mapping like the "categories" field in the WRRC JSON structure where each
        entry contains a ``judge_scores`` list.

    Returns
    -------
    per_category : dict
        Mapping from category code to the scaled median score (or ``None`` if no
        judge scores were available).
    total : float or None
        Sum of the available category scores. ``None`` if no category produced a
        value.
    """

    per_category: Dict[str, Optional[float]] = {}

    for code in CATEGORY_CODES:
        category_info = categories.get(code, {}) if isinstance(categories, dict) else {}
        judge_scores = category_info.get("judge_scores", []) if isinstance(category_info, dict) else []
        numeric_scores = [_parse_score(score) for score in judge_scores]
        per_category[code] = _scaled_median_from_scores(numeric_scores)

    available_scores = [score for score in per_category.values() if score is not None]
    total_score = sum(available_scores) if available_scores else None

    return per_category, total_score


def simple_average_score(categories: Dict[str, Dict]) -> Tuple[Dict[str, Optional[float]], Optional[float]]:
    """Simple average for each category and the total sum."""

    per_category: Dict[str, Optional[float]] = {}

    for code in CATEGORY_CODES:
        category_info = categories.get(code, {}) if isinstance(categories, dict) else {}
        judge_scores = category_info.get("judge_scores", []) if isinstance(category_info, dict) else []
        numeric_scores = [_parse_score(score) for score in judge_scores]
        per_category[code] = _simple_average(numeric_scores)

    available_scores = [score for score in per_category.values() if score is not None]
    total_score = sum(available_scores) if available_scores else None

    return per_category, total_score


def trimmed_average_score(categories: Dict[str, Dict]) -> Tuple[Dict[str, Optional[float]], Optional[float]]:
    """Average after removing the lowest and highest score for each category."""

    per_category: Dict[str, Optional[float]] = {}

    for code in CATEGORY_CODES:
        category_info = categories.get(code, {}) if isinstance(categories, dict) else {}
        judge_scores = category_info.get("judge_scores", []) if isinstance(category_info, dict) else []
        numeric_scores = [_parse_score(score) for score in judge_scores]
        per_category[code] = _trimmed_average(numeric_scores)

    available_scores = [score for score in per_category.values() if score is not None]
    total_score = sum(available_scores) if available_scores else None

    return per_category, total_score


def main() -> None:
    """Run a simple demonstration of the scaled-median scoring algorithm."""

    sample_categories = {
        "BBW": {"judge_scores": ["3,75", "5,25", "5,25", "6,75", "6", "5,25", "6,75"]},
        "BBM": {"judge_scores": ["5,25", "6,75", "6", "6,75", "6", "6", "6,75"]},
        "LF": {"judge_scores": ["7,5", "12", "9,75", "9", "9,75", "10,5", "12,75"]},
        "DF": {"judge_scores": ["6", "7", "6", "5,5", "6", "7", "7"]},
        "MI": {"judge_scores": ["15", "18,75", "12,5", "13,75", "13,75", "13,75", "15"]},
    }

    methods = {
        "Scaled median": scaled_median,
        "Simple average": simple_average_score,
        "Trimmed average": trimmed_average_score,
    }

    for name, func in methods.items():
        per_category, total = func(sample_categories)
        print(f"\n{name} per category:")
        for code, value in per_category.items():
            print(f"  {code}: {value:.3f}" if value is not None else f"  {code}: N/A")
        print("Total score:")
        print(f"  {total:.3f}" if total is not None else "  N/A")


if __name__ == "__main__":
    main()