from app.evaluation import precision_at_k, recall_at_k


def test_precision_at_k() -> None:
    assert precision_at_k(["a", "b", "c"], {"a", "x"}, 2) == 0.5


def test_recall_at_k() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "c"}, 3) == 1.0
