"""Photo check: blur (Laplacian variance) and brightness. No model, so a bad photo costs nothing.

Pillow + numpy rather than OpenCV: OpenCV bundles its own FFmpeg, which clashes with the
one PyAV (used by the speech-to-text) loads into the same process on macOS.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import settings


@dataclass
class PhotoCheck:
    ok: bool
    problem: str | None  # "blurry" | "dark" | "unreadable"


def check_photo(path: str | Path) -> PhotoCheck:
    try:
        img = ImageOps.exif_transpose(Image.open(path)).convert("L")
    except (UnidentifiedImageError, OSError):
        return PhotoCheck(False, "unreadable")
    img.thumbnail((800, 800))  # so the blur score doesn't depend on camera resolution
    g = np.asarray(img, dtype=np.float64)
    if g.mean() < settings.dark_threshold:
        return PhotoCheck(False, "dark")
    # 4-neighbour Laplacian; its variance is low when there are no sharp edges.
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1]
    if lap.var() < settings.blur_threshold:
        return PhotoCheck(False, "blurry")
    return PhotoCheck(True, None)
