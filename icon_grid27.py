"""Static official ICON grid 27 subset used for DWD v1 unstructured GRIB fields."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

GRID_NUMBER = 27
GRID_UUID = "ec13b8bcb82d11e4b13f4d55411d42e6"
GRID_POINTS = 659156


@dataclass(frozen=True)
class Grid27Map:
    index: np.ndarray
    output_index: np.ndarray
    output_lon: np.ndarray
    output_lat: np.ndarray

    @classmethod
    def load(cls, path: Path) -> "Grid27Map":
        with np.load(path) as data:
            if int(data["gridNumber"]) != GRID_NUMBER or str(data["uuidOfHGrid"]) != GRID_UUID or int(data["sourcePoints"]) != GRID_POINTS:
                raise RuntimeError("ICON grid 27 map metadata mismatch")
            index, output_index = data["index"].astype(np.int64), data["outputIndex"].astype(np.int64)
            if index.size == 0 or index.min() < 0 or index.max() >= GRID_POINTS or output_index.min() < 0 or output_index.max() >= index.size:
                raise RuntimeError("ICON grid 27 map indices out of bounds")
            return cls(index, output_index, data["outputLon"].astype(float), data["outputLat"].astype(float))


def validate_v1_metadata(metadata: dict[str, object], value_count: int) -> None:
    if metadata.get("gridType") != "unstructured_grid":
        raise RuntimeError("unsupported DWD v1 gridType")
    if int(metadata.get("numberOfGridUsed", -1)) != GRID_NUMBER:
        raise RuntimeError("unexpected ICON numberOfGridUsed")
    if str(metadata.get("uuidOfHGrid", "")).replace("-", "") != GRID_UUID:
        raise RuntimeError("unexpected ICON uuidOfHGrid")
    if int(metadata.get("numberOfDataPoints", -1)) != GRID_POINTS or value_count != GRID_POINTS:
        raise RuntimeError("unexpected ICON numberOfDataPoints")


def remap_values(values: np.ndarray, grid: Grid27Map) -> np.ndarray:
    if values.size != GRID_POINTS:
        raise RuntimeError("ICON value count does not match grid 27")
    return values[grid.index][grid.output_index]
