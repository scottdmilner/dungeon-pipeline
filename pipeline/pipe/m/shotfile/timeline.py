from __future__ import annotations


def timeline_generator(
    pre_roll: list[tuple[str, tuple[int, int, int], int]],
    roll: list[tuple[str, tuple[int, int, int], int]],
    /,
    start_frame: int = 1001,
) -> tuple[list[int], list[tuple[int, int, int]], list[str]]:
    colors = []
    comments = []
    pre_duration = 0
    post_duration = 0

    for comment, color, duration in pre_roll:
        comments += [comment] * duration
        colors += [color] * duration
        pre_duration += duration
    for comment, color, duration in roll:
        comments += [comment] * duration
        colors += [color] * duration
        post_duration += duration

    frames = list(range(start_frame - pre_duration, start_frame + post_duration))
    return frames, colors, comments


def shot_timeline_generator(
    shot_duration: int,
) -> tuple[list[int], list[tuple[int, int, int]], list[str]]:
    return timeline_generator(
        [
            ("Rest Pose @Origin", (70, 0, 0), 15),
            ("Rest Pose -> Windup", (150, 0, 0), 15),
            ("Hold Windup", (255, 0, 0), 10),
            ("Windup", (128, 128, 0), 15),
            ("Head", (128, 255, 128), 5),
        ],
        [
            ("Animate!", (0, 255, 0), shot_duration),
            ("Tail", (100, 160, 255), 5),
        ],
        start_frame=1001,
    )
