from __future__ import annotations
import numpy as np
from scipy import ndimage
from skimage import measure

INTERVAL_THRESHOLDS = {
    "1d": 0.85,
    "7d": 0.70,
    "15d": 0.60,
    "30d": 0.50,
}

MIN_AREA_SQ_METERS = 25.0  # ~5m x 5m minimum detectable construction
SENTINEL2_RESOLUTION = 10.0  # meters per pixel


def threshold_mask(prob_mask: np.ndarray, interval: str) -> np.ndarray:
    """Apply interval-specific threshold to probability mask.

    Returns a boolean mask (True = changed).
    Raises KeyError if interval not in INTERVAL_THRESHOLDS.
    """
    threshold = INTERVAL_THRESHOLDS[interval]
    return prob_mask >= threshold


def apply_morphology(binary_mask: np.ndarray) -> np.ndarray:
    """Clean up binary mask with morphological operations.

    1. Binary closing (fill small holes): structure size 3x3
    2. Binary opening (remove noise): structure size 3x3
    Returns boolean mask.
    """
    struct = ndimage.generate_binary_structure(2, 1)
    mask = ndimage.binary_closing(binary_mask, structure=struct, iterations=2)
    mask = ndimage.binary_opening(mask, structure=struct, iterations=2)
    return mask


def extract_regions(binary_mask: np.ndarray) -> list[dict]:
    """Extract connected regions from binary mask.

    Returns list of dicts with keys:
      - 'bbox': (min_row, min_col, max_row, max_col)
      - 'centroid': (row, col) floats
      - 'area_pixels': int
      - 'polygon': list of [col, row] pixel coordinates (exterior contour)
    """
    labeled = measure.label(binary_mask, connectivity=2)
    regions = []
    for prop in measure.regionprops(labeled):
        contours = measure.find_contours(labeled == prop.label, 0.5)
        if not contours:
            continue
        contour = contours[0]  # largest contour
        polygon = [[float(c[1]), float(c[0])] for c in contour]  # [col, row] = [x, y]
        regions.append({
            "bbox": prop.bbox,
            "centroid": prop.centroid,
            "area_pixels": prop.area,
            "polygon": polygon,
        })
    return regions


def filter_by_area(
    regions: list[dict],
    resolution_meters: float = SENTINEL2_RESOLUTION,
    min_area_sq_meters: float = MIN_AREA_SQ_METERS,
) -> list[dict]:
    """Filter regions below minimum area threshold.

    area_sq_meters = area_pixels * resolution_meters^2
    Adds 'area_sq_meters' key to each kept region dict.
    """
    kept = []
    for region in regions:
        area_sq_m = region["area_pixels"] * (resolution_meters ** 2)
        if area_sq_m >= min_area_sq_meters:
            region = dict(region)
            region["area_sq_meters"] = area_sq_m
            kept.append(region)
    return kept
