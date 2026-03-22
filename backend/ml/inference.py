from __future__ import annotations
import numpy as np
import torch
from ml.model import SiameseUNet
from ml.preprocessing import load_and_normalize, split_into_patches, merge_patches, PATCH_SIZE

_model: SiameseUNet | None = None


def load_model(weights_path: str | None = None) -> SiameseUNet:
    """Load (or return cached) SiameseUNet.

    If weights_path is None, returns an untrained model (for dev/testing).
    """
    global _model
    if _model is None:
        _model = SiameseUNet(in_channels=3)
        if weights_path:
            state = torch.load(weights_path, map_location="cpu")
            _model.load_state_dict(state)
        _model.eval()
    return _model


def run_inference(
    before_path: str,
    after_path: str,
    weights_path: str | None = None,
) -> np.ndarray:
    """Run the Siamese U-Net on a before/after image pair.

    Returns a (H, W) float32 change-probability mask in [0, 1],
    sized to match the 'before' image dimensions.
    """
    model = load_model(weights_path)
    before = load_and_normalize(before_path)
    after = load_and_normalize(after_path)
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
            patch_masks.append(out.squeeze().cpu().numpy())  # (256, 256)

    return merge_patches(patch_masks, positions, (H, W))
