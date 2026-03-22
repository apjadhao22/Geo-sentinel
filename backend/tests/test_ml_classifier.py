import pytest
from ml.classifier import classify_change, EXCAVATION, EXTENSION, NEW_STRUCTURE, UNKNOWN


def test_classify_small_area_is_excavation():
    result = classify_change([], area_sq_meters=200.0, nearby_buildings=False)
    assert result == EXCAVATION


def test_classify_medium_with_buildings_is_extension():
    result = classify_change([], area_sq_meters=1000.0, nearby_buildings=True)
    assert result == EXTENSION


def test_classify_large_is_new_structure():
    result = classify_change([], area_sq_meters=3000.0, nearby_buildings=False)
    assert result == NEW_STRUCTURE


def test_classify_medium_no_buildings_is_new_structure():
    # area >= EXCAVATION_MAX but < EXTENSION_MAX, no nearby buildings → NEW_STRUCTURE
    result = classify_change([], area_sq_meters=1000.0, nearby_buildings=False)
    assert result == NEW_STRUCTURE


def test_classify_excavation_threshold_boundary():
    # Exactly at EXCAVATION_MAX_SQ_M (500) → NOT excavation
    result = classify_change([], area_sq_meters=500.0, nearby_buildings=False)
    assert result == NEW_STRUCTURE


def test_classify_extension_threshold_boundary():
    # Exactly at EXTENSION_MAX_SQ_M (2000) → NEW_STRUCTURE (not extension)
    result = classify_change([], area_sq_meters=2000.0, nearby_buildings=True)
    assert result == NEW_STRUCTURE
