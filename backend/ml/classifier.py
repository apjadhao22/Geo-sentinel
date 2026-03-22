from __future__ import annotations

# Classification labels
EXCAVATION = "excavation"
EXTENSION = "extension"
NEW_STRUCTURE = "new_structure"
UNKNOWN = "unknown"

# Thresholds
EXCAVATION_MAX_SQ_M = 500.0   # small disturbed area → likely excavation
EXTENSION_MAX_SQ_M = 2000.0   # medium area → likely extension of existing building


def classify_change(
    polygon: list,
    area_sq_meters: float,
    nearby_buildings: bool = False,
) -> str:
    """Classify a detected change region using simple rules.

    Rules (in priority order):
    1. area < EXCAVATION_MAX_SQ_M → EXCAVATION
    2. area < EXTENSION_MAX_SQ_M and nearby_buildings → EXTENSION
    3. otherwise → NEW_STRUCTURE
    """
    if area_sq_meters < EXCAVATION_MAX_SQ_M:
        return EXCAVATION
    if area_sq_meters < EXTENSION_MAX_SQ_M and nearby_buildings:
        return EXTENSION
    return NEW_STRUCTURE
