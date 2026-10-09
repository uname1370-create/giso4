"""Output-format and validation contracts for final Buti AI images."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
def test_exact_outside_mask_preservation_is_not_rejected_as_missing_validation():
    from giso.buti_ai.service_image_generation import _validation_ok

    assert _validation_ok("lip_shading", {
        "ok": True,
        "visible_in_mask_change": True,
        "outside_preserved": True,
        "in_mask_diff_ratio": 0.5,
        "outside_mask_diff_ratio": 0.0,
    }) is True


@pytest.mark.parametrize("service_key, sample, module_path, upload_attr, generator_name", [
    ("eyebrow", "giso/buti_ai/static/brows/upload_face_sample.jpg", "giso.buti_ai.eyebrow.final_design", "EYEBROW_UPLOAD_DIR", "generate_python_guided_design"),
    ("hair_color", "giso/buti_ai/static/services/hair_color/upload_sample.jpg", "giso.buti_ai.hair_color.final_design", "UPLOAD_DIR", "generate_guided_design"),
    ("lip_shading", "giso/buti_ai/static/services/lip_shading/upload_sample.jpg", "giso.buti_ai.lip.final_design", "UPLOAD_DIR", "generate_guided_design"),
    ("nail", "giso/buti_ai/static/services/nail/upload_sample.jpg", "giso.buti_ai.nail.final_design", "UPLOAD_DIR", "generate_guided_design"),
])
def test_guided_final_output_for_each_service_is_webp(tmp_path, monkeypatch, service_key, sample, module_path, upload_attr, generator_name):
    from importlib import import_module

    module = import_module(module_path)
    upload_dir = tmp_path / service_key
    final_dir = upload_dir / "final"
    upload_dir.mkdir()
    source_path = upload_dir / "customer.jpg"
    shutil.copyfile(ROOT / sample, source_path)
    monkeypatch.setattr(module, upload_attr, str(upload_dir))
    monkeypatch.setattr(module, "FINAL_DIR" if hasattr(module, "FINAL_DIR") else "FINAL_DESIGN_DIR", str(final_dir))

    payload = {"photo_filename": source_path.name}
    if service_key in ("hair_color", "nail"):
        # Guided previews fail closed on untrusted masks (round 6). Give them a validated
        # synthetic mask so this test still checks the WebP and outside-mask contract.
        import numpy as np

        width, height = Image.open(source_path).size
        mask_path = upload_dir / "trusted_mask.png"
        mask_arr = np.zeros((height, width), np.uint8)
        mask_arr[height // 4:height // 2, width // 4:3 * width // 4] = 255
        Image.fromarray(mask_arr).save(mask_path)
        payload["detection"] = {
            "ok": True,
            "method": "test_trusted_mask",
            "detection_reliable": True,
            "is_fallback": False,
            "image_width": width,
            "image_height": height,
            "regions": [{"x": width // 4, "y": height // 4, "width": width // 2, "height": height // 4}],
            "mask": {"ok": True, "path": str(mask_path), "coverage_ratio": 0.125, "is_fallback": False, "real_mask": True},
        }

    result = getattr(module, generator_name)(payload)

    assert result["ok"] is True
    assert result["filename"].endswith(".webp")
    output_path = upload_dir / result["filename"]
    assert output_path.is_file()
    with Image.open(output_path) as final:
        assert final.format == "WEBP"
        assert final.width > 0 and final.height > 0

    from giso.buti_ai.image_validation import outside_mask_pixels_equal

    if service_key == "eyebrow":
        mask_path = result["eyebrow_detection"]["mask"]["path"]
    else:
        mask_path = result["detection"]["mask"]["path"]
    with Image.open(source_path) as source_image, Image.open(output_path) as final_image, Image.open(mask_path) as mask_image:
        assert outside_mask_pixels_equal(source_image, final_image, mask_image)
