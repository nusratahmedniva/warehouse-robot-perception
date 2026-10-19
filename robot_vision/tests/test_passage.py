import unittest

from decision import RouteCorridor
from passage import OccupancyGrid, PassageConfig, PassageProvider


class PassageTests(unittest.TestCase):
    def setUp(self):
        self.grid = OccupancyGrid(PassageConfig(cell_size_m=0.1, floor_height_tolerance_m=0.05))
        self.route = RouteCorridor(((0.05, 0.05), (0.05, 1.05)), 0.8)

    def observe_strip(self, half_width=0.5, height=0.0):
        for i in range(-6, 7):
            for j in range(11):
                x, z = 0.05 + i * 0.1, 0.05 + j * 0.1
                if abs(x - 0.05) <= half_width:
                    self.grid.observe(x, z, label="floor", height_m=height, floor_height_m=0.0)

    def test_clear_floor_has_required_width(self):
        self.observe_strip()
        result = PassageProvider(self.grid).passage_at(self.route)
        self.assertEqual(result.status, "clear")
        self.assertGreaterEqual(result.available_width_m, 0.8)

    def test_narrow_floor_is_not_clear(self):
        self.observe_strip(half_width=0.3)
        result = PassageProvider(self.grid).passage_at(self.route)
        self.assertEqual(result.status, "too_narrow")

    def test_unseen_cells_are_blocked(self):
        result = PassageProvider(self.grid).passage_at(self.route)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.available_width_m, 0.0)

    def test_height_outside_tolerance_blocks_cell(self):
        self.observe_strip(height=0.2)
        result = PassageProvider(self.grid).passage_at(self.route)
        self.assertEqual(result.status, "blocked")

    def test_non_floor_observation_blocks_cell(self):
        self.grid.observe(0.05, 0.05, label="person", height_m=0.0, floor_height_m=0.0)
        result = PassageProvider(self.grid).passage_at(self.route)
        self.assertEqual(result.status, "blocked")


if __name__ == "__main__":
    unittest.main()
