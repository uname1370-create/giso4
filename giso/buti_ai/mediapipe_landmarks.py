"""MediaPipe FaceMesh helper for the lip region detector.

MediaPipe is optional. When it is missing, the helper returns None and the lip
detector stays untrusted (fail-closed): no AI call and no guided output is
produced from a colour-only guess. The FaceMesh model ships inside the MediaPipe
wheel, so no network access is needed.
"""
from __future__ import annotations

import threading
from typing import List, Optional, Tuple

_LOCK = threading.Lock()
_MP = None
_MP_CHECKED = False


def _mediapipe():
    global _MP, _MP_CHECKED
    with _LOCK:
        if not _MP_CHECKED:
            _MP_CHECKED = True
            try:
                import mediapipe as mp  # type: ignore

                _ = mp.solutions  # legacy solutions API must exist
                _MP = mp
            except Exception:
                _MP = None
        return _MP


def available() -> bool:
    return _mediapipe() is not None


def face_mesh_points(image_path: str) -> Optional[Tuple[List[Tuple[float, float]], int, int]]:
    """Return (468 landmark pixel points, width, height) for the largest single face, or None."""
    mp = _mediapipe()
    if mp is None:
        return None
    import numpy as np  # type: ignore
    from PIL import Image

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        w, h = rgb.size
        arr = np.asarray(rgb)
    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as mesh:
        result = mesh.process(arr)
    if not result.multi_face_landmarks:
        return None
    landmarks = result.multi_face_landmarks[0].landmark
    return [(float(lm.x) * w, float(lm.y) * h) for lm in landmarks], w, h
