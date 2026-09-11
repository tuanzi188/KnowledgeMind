import math
from typing import List


def recall_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    hit = sum(1 for cid in retrieved_ids[:k] if cid in relevant)
    return hit / len(relevant)


def ndcg_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0

    dcg = 0.0
    for i, cid in enumerate(retrieved_ids[:k]):
        if cid in relevant:
            dcg += 1.0 / math.log2(i + 2)

    ideal_count = min(len(relevant), k)
    ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))
    return dcg / ideal_dcg if ideal_dcg else 0.0