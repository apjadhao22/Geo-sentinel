from __future__ import annotations
import threading
import numpy as np
import torch
from typing import Any
from ml.model import SiameseUNet
from ml.preprocessing import load_image_with_transform, load_and_normalize, split_into_patches, merge_patches, PATCH_SIZE

_model: SiameseUNet | None = None
_model_lock = threading.Lock()
_model_weights_path: str | None = None


def load_model(weights_path: str | None = None) -> SiameseUNet:
    """Load (or return cached) SiameseUNet.

    If weights_path is None, returns an untrained model (for dev/testing).
    Uses double-checked locking for thread safety.
    """
    global _model, _model_weights_path
    if _model is None or _model_weights_path != weights_path:
        with _model_lock:
            if _model is None or _model_weights_path != weights_path:
                _model = SiameseUNet(in_channels=3)
                if weights_path:
                    state = torch.load(weights_path, map_location="cpu")
                    _model.load_state_dict(state)
                _model.eval()
                _model_weights_path = weights_path
    return _model


def run_inference(
    before_path: str,
    after_path: str,
    weights_path: str | None = None,
) -> tuple[np.ndarray, Any]:
    """Run the Siamese U-Net on a before/after image pair.

    Returns a tuple of:
    - (H, W) float32 change-probability mask in [0, 1]
    - rasterio.Affine transform from the 'before' image
    """
    model = load_model(weights_path)
    before, before_transform = load_image_with_transform(before_path)
    after, _ = load_image_with_transform(after_path)

    if before.shape != after.shape:
        raise ValueError(
            f"Image shape mismatch: before={before.shape}, after={after.shape}"
        )

    _, H, W = before.shape

    before_patches, positions = split_into_patches(before)
    after_patches, _ = split_into_patches(after)

    patch_masks = []
    device = next(model.parameters()).device
    with torch.no_grad():
        for bp, ap in zip(before_patches, after_patches):
            b_t = torch.from_numpy(bp).unsqueeze(0).to(device)  # (1, 3, 256, 256)
            a_t = torch.from_numpy(ap).unsqueeze(0).to(device)
            out = model(b_t, a_t)  # (1, 1, 256, 256)
            patch_masks.append(out[0, 0].cpu().numpy())  # (256, 256)

    return merge_patches(patch_masks, positions, (H, W)), before_transform
