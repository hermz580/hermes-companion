"""Headless surface — records poses and positions for deterministic QA
(spec rev1 §34.9) without opening a window."""
from __future__ import annotations

import time


class HeadlessSurface:
    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.pose_log: list[tuple[float, str]] = []      # (t, pose)
        self.x_log: list[int] = []
        self.state_log: list[str] = []

    def set_pose(self, pose: str, progress: float = 0.0) -> None:
        self.pose_log.append((round(self.clock(), 2), pose))

    def set_x(self, x: int) -> None:
        self.x_log.append(x)

    def set_state(self, state: str) -> None:
        if not self.state_log or self.state_log[-1] != state:
            self.state_log.append(state)

    # -- proof helpers ------------------------------------------------------
    def pose_sequence(self) -> list[str]:
        seen: list[str] = []
        for _t, p in self.pose_log:
            if not seen or seen[-1] != p:
                seen.append(p)
        return seen

    def max_travel(self) -> int:
        return max(self.x_log) - min(self.x_log) if self.x_log else 0
