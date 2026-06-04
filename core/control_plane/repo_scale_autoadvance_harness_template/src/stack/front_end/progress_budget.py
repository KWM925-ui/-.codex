"""Front-end sampling budget helper used by the harness validation."""


def choose_sample_count(
    total_traj_time_sec: float,
    sample_dt_sec: float,
    structural_floor: int,
) -> int:
    """Pick the effective sample count for a predicted path shell."""

    if sample_dt_sec <= 0:
        raise ValueError("sample_dt_sec must be positive")
    if structural_floor <= 0:
        raise ValueError("structural_floor must be positive")

    time_based_sample_num = max(1, int(total_traj_time_sec / sample_dt_sec))
    return min(time_based_sample_num, structural_floor)
