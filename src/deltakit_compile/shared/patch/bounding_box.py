# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Utility class defining a bounding box for patches."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    """A bounding box for patches."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def intersects(self, other: BoundingBox) -> bool:
        return (
            other.max_x > self.min_x
            and other.max_y > self.min_y
            and other.min_x < self.max_x
            and other.min_y < self.max_y
        )

    @property
    def bottom_left(self) -> tuple[float, float]:
        return self.min_x, self.min_y

    @property
    def bottom_right(self) -> tuple[float, float]:
        return self.max_x, self.min_y

    @property
    def top_left(self) -> tuple[float, float]:
        return self.min_x, self.max_y

    @property
    def top_right(self) -> tuple[float, float]:
        return self.max_x, self.max_y
