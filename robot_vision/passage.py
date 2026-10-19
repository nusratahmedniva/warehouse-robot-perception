"""Step 6 occupancy and passage-width provider.

The provider consumes already-fused world observations. It does not load a
dataset or reference data, so the same code can be fed by THUD replay or
Unity. Unseen cells are blocked by design.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from decision import PassageState, RouteCorridor


@dataclass(frozen=True)
class PassageConfig:
    cell_size_m: float = 0.10
    floor_height_tolerance_m: float = 0.08
    sample_step_m: float = 0.10

    def __post_init__(self) -> None:
        if self.cell_size_m <= 0 or self.sample_step_m <= 0:
            raise ValueError("cell_size_m and sample_step_m must be positive")
        if self.floor_height_tolerance_m < 0:
            raise ValueError("floor_height_tolerance_m must not be negative")


@dataclass
class _Cell:
    seen: bool = False
    free: bool = False


class OccupancyGrid:
    """A finite x-z grid whose cells are free only for valid floor observations."""

    def __init__(self, config: PassageConfig):
        self.config = config
        self._cells: dict[tuple[int, int], _Cell] = {}

    def _key(self, x: float, z: float) -> tuple[int, int]:
        size = self.config.cell_size_m
        return math.floor(x / size), math.floor(z / size)

    def observe(self, x: float, z: float, *, label: str, height_m: float | None,
                floor_height_m: float | None) -> None:
        """Record one world observation; invalid floor evidence blocks the cell."""
        key = self._key(float(x), float(z))
        cell = self._cells.setdefault(key, _Cell())
        cell.seen = True
        cell.free = (
            label == "floor"
            and height_m is not None
            and floor_height_m is not None
            and math.isfinite(height_m)
            and math.isfinite(floor_height_m)
            and abs(height_m - floor_height_m) <= self.config.floor_height_tolerance_m
        )

    def cell_free(self, x: float, z: float) -> bool:
        cell = self._cells.get(self._key(x, z))
        return bool(cell and cell.seen and cell.free)

    def cell_seen(self, x: float, z: float) -> bool:
        cell = self._cells.get(self._key(x, z))
        return bool(cell and cell.seen)


class PassageProvider:
    """Compute the minimum available width along a route corridor."""

    def __init__(self, grid: OccupancyGrid):
        self.grid = grid

    def passage_at(self, corridor: RouteCorridor) -> PassageState:
        required = corridor.width_m
        polyline = _Polyline(corridor.centreline_xz)
        if polyline.length <= 0:
            return PassageState("unknown", None, required)

        widths: list[float] = []
        for s in _samples(polyline.length, self.grid.config.sample_step_m):
            x, z, nx, nz = polyline.point_and_normal(s)
            width, centre_free = self._width_at(x, z, nx, nz, required)
            if not centre_free:
                return PassageState("blocked", 0.0, required)
            widths.append(width)
        available = round(min(widths), 6)
        status = "clear" if available + 1e-9 >= required else "too_narrow"
        return PassageState(status, available, required)

    def _width_at(self, x: float, z: float, nx: float, nz: float,
                  max_width: float) -> tuple[float, bool]:
        half_cells = max(1, math.ceil(max_width / self.grid.config.cell_size_m))
        offsets = range(-half_cells, half_cells + 1)
        free = [self.grid.cell_free(x + nx * i * self.grid.config.cell_size_m,
                                     z + nz * i * self.grid.config.cell_size_m) for i in offsets]
        centre = half_cells
        if not free[centre]:
            return 0.0, False
        start = centre
        while start > 0 and free[start - 1]:
            start -= 1
        end = centre
        while end + 1 < len(free) and free[end + 1]:
            end += 1
        return (end - start + 1) * self.grid.config.cell_size_m, True


class _Polyline:
    def __init__(self, points: tuple[tuple[float, float], ...]):
        self.points = points
        self.lengths = [0.0]
        for a, b in zip(points, points[1:]):
            self.lengths.append(self.lengths[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.length = self.lengths[-1]

    def point_and_normal(self, distance: float) -> tuple[float, float, float, float]:
        distance = min(max(distance, 0.0), self.length)
        for i, (a, b) in enumerate(zip(self.points, self.points[1:])):
            segment = self.lengths[i + 1] - self.lengths[i]
            if distance <= self.lengths[i + 1] or i == len(self.points) - 2:
                ratio = 0.0 if segment == 0 else (distance - self.lengths[i]) / segment
                dx, dz = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dz)
                if length == 0:
                    continue
                return (a[0] + ratio * dx, a[1] + ratio * dz, -dz / length, dx / length)
        raise AssertionError("polyline has no segment")


def _samples(length: float, step: float) -> list[float]:
    count = max(1, math.ceil(length / step))
    return [min(length, i * length / count) for i in range(count + 1)]
