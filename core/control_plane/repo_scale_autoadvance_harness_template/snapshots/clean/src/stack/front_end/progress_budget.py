"""Clean snapshot anchor used to force worktree remap in the harness."""


def choose_sample_count(
    total_traj_time_sec: float,
    sample_dt_sec: float,
    structural_floor: int,
) -> int:
    if sample_dt_sec <= 0:
        raise ValueError("sample_dt_sec must be positive")
    if structural_floor <= 0:
        raise ValueError("structural_floor must be positive")

    time_based_sample_num = max(1, int(total_traj_time_sec / sample_dt_sec))
    return min(time_based_sample_num, structural_floor)
