from evaluation.metrics import ndcg_at_k, recall_at_k


def test_recall_at_k():
    assert recall_at_k(["a", "b", "c"], ["a", "d"], 3) == 0.5
    assert recall_at_k(["a", "b"], ["a", "b"], 2) == 1.0
    assert recall_at_k([], ["a"], 5) == 0.0
    assert recall_at_k(["a"], [], 5) == 0.0


def test_ndcg_at_k():
    assert ndcg_at_k(["a", "b"], ["a"], 2) == 1.0
    expected = 1.0 / __import__("math").log2(3)
    assert abs(ndcg_at_k(["b", "a"], ["a"], 2) - expected) < 1e-6
    assert ndcg_at_k(["a"], [], 5) == 0.0