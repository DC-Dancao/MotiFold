"""
Reciprocal Rank Fusion for combining multiple retrieval strategies.
"""
from collections import defaultdict
from typing import List, Dict, Any


def rrf_fusion(
    result_lists: List[List[Dict[str, Any]]],
    k: int = 60,
) -> List[Dict[str, Any]]:
    """
    Combine ranked results from multiple retrieval strategies using RRF.

    RRF formula: score(d) = sum(1 / (k + rank(d)))

    Args:
        result_lists: List of ranked result lists (each sorted by rank)
        k: RRF constant (default 60, higher = less weight to rank)

    Returns:
        Combined ranked list of results
    """
    scores = defaultdict(float)
    item_data = {}  # Store full item data by id

    for results in result_lists:
        for rank, item in enumerate(results):
            item_id = item["id"]
            # RRF score contribution
            scores[item_id] += 1 / (k + rank + 1)
            # Store item data (prefer first occurrence)
            if item_id not in item_data:
                item_data[item_id] = item

    # Sort by RRF score descending
    ranked_ids = sorted(scores.keys(), key=lambda x: -scores[x])

    return [
        {**item_data[id], "rrf_score": scores[id]}
        for id in ranked_ids
    ]