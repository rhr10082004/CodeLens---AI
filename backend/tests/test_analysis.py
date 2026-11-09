from app.analysis import calculate_quality_score


def test_quality_score_is_transparent_and_bounded() -> None:
    assert calculate_quality_score(0) == 100
    assert calculate_quality_score(3) == 85
    assert calculate_quality_score(100) == 0
