GRADE_CUTOFFS = [96, 89, 77, 60, 40, 23, 11, 4]


def calculate_grade(score: float) -> int:
    """Calculate 9-grade rank from raw score (절대평가 참고값)."""
    for rank, cutoff in enumerate(GRADE_CUTOFFS, start=1):
        if score >= cutoff:
            return rank
    return 9

