from __future__ import annotations
import numpy as np
import torch
from typing import Any, Generator

PATCH_SIZE = 256
PATCH_OVERLAP = 32


def load_image_with_transform(path: str) -> tuple[np.ndarray, Any]:
    """Returns (CHW float32 array, rasterio.Affine transform)."""
    import rasterio
    with rasterio.open(path) as src:
        bands_to_read = min(src.count, 3)
        data = src.read(list(range(1, bands_to_read + 1))).astype(np.float32)
        transform = src.transform
    while data.shape[0] < 3:
        data = np.concatenate([data, data[-1:]], axis=0)
    data = np.clip(data, 0, 10000) / 10000.0
    return data, transform


def load_and_normalize(path: str) -> np.ndarray:
    """Load a GeoTIFF and return a float32 CHW array normalized to [0, 1].

    Uses rasterio to read up to 3 bands. If fewer than 3 bands exist,
    repeat the last band to fill 3 channels.
    Clips values to [0, 10000] then divides by 10000.
    Returns shape (3, H, W) float32.
    """
    import rasterio
    with rasterio.open(path) as src:
        bands_to_read = min(src.count, 3)
        data = src.read(list(range(1, bands_to_read + 1))).astype(np.float32)
    while data.shape[0] < 3:
        data = np.concatenate([data, data[-1:]], axis=0)
    data = np.clip(data, 0, 10000) / 10000.0
    return data  # (3, H, W)


def split_into_patches(
    image: np.ndarray,
) -> tuple[list[np.ndarray], list[tuple[int, int]]]:
    """Split a (C, H, W) image into overlapping PATCH_SIZE patches.

    Returns:
        patches: list of (C, PATCH_SIZE, PATCH_SIZE) arrays (zero-padded if needed)
        positions: list of (row_start, col_start) for each patch
    """
    _, H, W = image.shape
    step = PATCH_SIZE - PATCH_OVERLAP
    patches = []
    positions = []
    row = 0
    while row < H:
        col = 0
        while col < W:
            patch = np.zeros((image.shape[0], PATCH_SIZE, PATCH_SIZE), dtype=np.float32)
            r_end = min(row + PATCH_SIZE, H)
            c_end = min(col + PATCH_SIZE, W)
            patch[:, : r_end - row, : c_end - col] = image[:, row:r_end, col:c_end]
            patches.append(patch)
            positions.append((row, col))
            col += step
        row += step
    return patches, positions


def merge_patches(
    patch_masks: list[np.ndarray],
    positions: list[tuple[int, int]],
    image_shape: tuple[int, int],
) -> np.ndarray:
    """Merge patch-level probability masks back into full image mask.

    Overlapping regions are averaged.
    Returns (H, W) float32 array.
    """
    H, W = image_shape
    accumulator = np.zeros((H, W), dtype=np.float32)
    count = np.zeros((H, W), dtype=np.float32)
    for mask, (row, col) in zip(patch_masks, positions):
        r_end = min(row + PATCH_SIZE, H)
        c_end = min(col + PATCH_SIZE, W)
        accumulator[row:r_end, col:c_end] += mask[: r_end - row, : c_end - col]
        count[row:r_end, col:c_end] += 1.0
    count = np.maximum(count, 1.0)
    return accumulator / count
