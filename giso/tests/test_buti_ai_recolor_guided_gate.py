"""Regression tests: hair/nail guided previews must fail closed on untrusted masks.

Before round 6, generic_service.generate_final_design() fell back to
module.generate_guided_design() when the service image path raised. The guided
functions did not check trust, so an untrusted nail/hair mask produced a
'non_ai_guided_preview_ready' image with ok=True. These tests pin the fixed behaviour.
Internal-logic checks only (no provider, no network, no AI output).
"""
import os

import numpy as np
import pytest
from PIL import Image

from giso.buti_ai import generic_service
from giso.buti_ai import service_image_generation as sig
from giso.buti_ai.hair_color import final_design as hair
from giso.buti_ai.nail import final_design as nail


def _photo(tmp_path, name="photo.jpg"):
    arr = np.full((240, 200, 3), 150, np.uint8)
    arr[60:200, 60:140] = (200, 150, 130)  # skin-like block
    path = tmp_path / name
    Image.fromarray(arr).save(path, "JPEG", quality=95)
    return name


def _mask_file(tmp_path, size, box, name="mask.png"):
    m = np.zeros((size[1], size[0]), np.uint8)
    x0, y0, x1, y1 = box
    m[y0:y1, x0:x1] = 255
    path = tmp_path / name
    Image.fromarray(m).save(path)
    return str(path)


def _configure(module, tmp_path):
    upload = tmp_path / "uploads"
    final = upload / "final"
    final.mkdir(parents=True)
    module.UPLOAD_DIR = str(upload)
    module.FINAL_DIR = str(final)
    return upload


def _untrusted_detection(module, photo_path):
    return module.detect_regions(photo_path, allow_fallback=True)


def _trusted_detection(tmp_path, size, box):
    return {
        "ok": True,
        "method": "test_trusted_mask",
        "detection_reliable": True,
        "is_fallback": False,
        "image_width": size[0],
        "image_height": size[1],
        "regions": [{"x": box[0], "y": box[1], "width": box[2] - box[0], "height": box[3] - box[1]}],
        "mask": {"ok": True, "path": _mask_file(tmp_path, size, box), "coverage_ratio": 0.2, "is_fallback": False, "real_mask": True},
    }


@pytest.mark.parametrize("module", [hair, nail], ids=["hair_color", "nail"])
def test_guided_refuses_untrusted_detection(module, tmp_path, monkeypatch):
    upload = _configure(module, tmp_path)
    name = _photo(upload)
    detection = _untrusted_detection(module, str(upload / name))
    assert detection.get("detection_reliable") is not True
    result = module.generate_guided_design({"photo_filename": name, "final_style": module.DEFAULT_STYLE, "detection": detection})
    assert result["ok"] is False
    assert result["status"] == "region_detection_unreliable"
    assert result["is_ai_generated"] is False
    assert not any((module.FINAL_DIR and p.name.startswith("final_")) for p in (upload / "final").iterdir())


@pytest.mark.parametrize("service_key, module", [("hair_color", hair), ("nail", nail)])
def test_exception_fallback_does_not_deliver_untrusted_preview(service_key, module, tmp_path, monkeypatch):
    upload = _configure(module, tmp_path)
    name = _photo(upload)
    detection = _untrusted_detection(module, str(upload / name))
    candidate = {"photo_filename": name, "final_style": module.DEFAULT_STYLE, "detection": detection}

    def boom(*args, **kwargs):
        raise RuntimeError("forced")

    monkeypatch.setattr(sig, "generate_final_design", boom)
    result = generic_service.generate_final_design(service_key, candidate)
    assert result.get("ok") is False
    assert result.get("status") == "region_detection_unreliable"


def test_trusted_hair_mask_recolours_inside_only(tmp_path):
    upload = _configure(hair, tmp_path)
    name = _photo(upload)
    size = (200, 240)
    box = (50, 40, 150, 120)
    detection = _trusted_detection(tmp_path, size, box)
    result = hair.generate_guided_design({"photo_filename": name, "final_style": "chocolate_nescafe", "detection": detection})
    assert result["ok"] is True, result
    assert result["is_ai_generated"] is False
    src = np.asarray(Image.open(upload / name).convert("RGB"))
    out = np.asarray(Image.open(os.path.join(hair.FINAL_DIR, os.path.basename(result["filename"]))).convert("RGB"))
    assert out.shape == src.shape
    outside = np.ones(src.shape[:2], bool)
    outside[box[1]:box[3], box[0]:box[2]] = False
    assert np.abs(out[outside].astype(int) - src[outside].astype(int)).max() <= 2  # lossless webp round-trip
    assert np.abs(out[~outside].astype(int) - src[~outside].astype(int)).mean() > 5


def test_trusted_nail_solid_style_recolours_plate_only(tmp_path):
    upload = _configure(nail, tmp_path)
    name = _photo(upload)
    size = (200, 240)
    box = (70, 70, 130, 110)
    detection = _trusted_detection(tmp_path, size, box)
    result = nail.generate_guided_design({"photo_filename": name, "final_style": "cat_eye", "detection": detection})
    assert result["ok"] is True, result
    src = np.asarray(Image.open(upload / name).convert("RGB"))
    out = np.asarray(Image.open(os.path.join(nail.FINAL_DIR, os.path.basename(result["filename"]))).convert("RGB"))
    outside = np.ones(src.shape[:2], bool)
    outside[box[1]:box[3], box[0]:box[2]] = False
    assert np.abs(out[outside].astype(int) - src[outside].astype(int)).max() <= 2


def test_trusted_nail_patterned_style_is_refused(tmp_path):
    upload = _configure(nail, tmp_path)
    name = _photo(upload)
    detection = _trusted_detection(tmp_path, (200, 240), (70, 70, 130, 110))
    result = nail.generate_guided_design({"photo_filename": name, "final_style": "classic_french", "detection": detection})
    assert result["ok"] is False
    assert result["status"] == "non_ai_style_unavailable"
