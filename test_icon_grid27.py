import tempfile
import unittest
from pathlib import Path

import numpy as np

from icon_grid27 import GRID_POINTS, GRID_UUID, Grid27Map, remap_values, validate_v1_metadata


class Grid27Test(unittest.TestCase):
    def metadata(self):
        return {"gridType": "unstructured_grid", "numberOfGridUsed": 27, "uuidOfHGrid": GRID_UUID, "numberOfDataPoints": GRID_POINTS}

    def test_metadata_and_remap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grid.npz"
            np.savez(path, index=np.array([0, 4], dtype=np.int32), outputIndex=np.array([1, 0], dtype=np.int32), outputLon=np.array([1., 2.]), outputLat=np.array([3.]), gridNumber=np.int32(27), uuidOfHGrid=np.array(GRID_UUID), sourcePoints=np.int32(GRID_POINTS))
            grid = Grid27Map.load(path)
            values = np.arange(GRID_POINTS, dtype=float)
            validate_v1_metadata(self.metadata(), values.size)
            self.assertTrue(np.array_equal(remap_values(values, grid), np.array([4., 0.])))
            self.assertEqual(remap_values(values, grid).shape, remap_values(values + 1, grid).shape)

    def test_out_of_bounds_index_map_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grid.npz"
            np.savez(path, index=np.array([GRID_POINTS], dtype=np.int32), outputIndex=np.array([0], dtype=np.int32), outputLon=np.array([1.]), outputLat=np.array([1.]), gridNumber=np.int32(27), uuidOfHGrid=np.array(GRID_UUID), sourcePoints=np.int32(GRID_POINTS))
            with self.assertRaisesRegex(RuntimeError, "out of bounds"):
                Grid27Map.load(path)

    def test_invalid_uuid_or_count_fails(self):
        bad = self.metadata() | {"uuidOfHGrid": "bad"}
        with self.assertRaisesRegex(RuntimeError, "uuid"): validate_v1_metadata(bad, GRID_POINTS)
        with self.assertRaisesRegex(RuntimeError, "numberOfDataPoints"): validate_v1_metadata(self.metadata(), GRID_POINTS - 1)
