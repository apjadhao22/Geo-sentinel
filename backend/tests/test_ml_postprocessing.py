import numpy as np
import pytest
from ml.postprocessing import threshold_mask, filter_by_area, INTERVAL_THRESHOLDS


def test_threshold_mask_1d():
    prob = np.array([[0.90, 0.80], [0.84, 0.86]])
    mask = threshold_mask(prob, "1d")
    # threshold = 0.85
    expected = np.array([[True, False], [False, True]])
    np.testing.assert_array_equal(mask, expected)


def test_threshold_mask_30d():
    prob = np.array([[0.55, 0.49], [0.50, 0.51]])
    mask = threshold_mask(prob, "30d")
    # threshold = 0.50
    expected = np.array([[True, False], [True, True]])
    np.testing.assert_array_equal(mask, expected)


def test_threshold_mask_invalid_interval():
    prob = np.array([[0.5]])
    with pytest.raises(KeyError):
        threshold_mask(prob, "2d")


def test_filter_by_area_keeps_large():
    regions = [{"area_pixels": 100, "bbox": None, "centroid": None, "polygon": []}]
    # 100 pixels * 10^2 = 10000 sq meters → kept
    result = filter_by_area(regions, resolution_meters=10.0, min_area_sq_meters=25.0)
    assert len(result) == 1
    assert result[0]["area_sq_meters"] == pytest.approx(10000.0)


def test_filter_by_area_removes_small():
    regions = [{"area_pixels": 0, "bbox": None, "centroid": None, "polygon": []}]
    # 0 pixels → 0 sq meters → removed
    result = filter_by_area(regions, resolution_meters=10.0, min_area_sq_meters=25.0)
    assert len(result) == 0


def test_filter_by_area_boundary():
    # Exactly at minimum (25 sq meters): 25 pixels * 1m^2 = 25 sq meters → kept
    regions = [{"area_pixels": 25, "bbox": None, "centroid": None, "polygon": []}]
    result = filter_by_area(regions, resolution_meters=1.0, min_area_sq_meters=25.0)
    assert len(result) == 1
