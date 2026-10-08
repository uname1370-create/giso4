"""Deterministic mask/composite contract for whole-frame provider responses."""
from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw

from giso.buti_ai.eyebrow import final_design, image_generation
from giso.buti_ai.image_validation import outside_mask_pixels_equal


def test_flux_provider_whole_frame_change_is_masked_and_lossless_webp_preserves_outside(tmp_path, monkeypatch):
    upload_root = tmp_path / "eyebrow-uploads"
    final_root = upload_root / "final"
    upload_root.mkdir()
    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(upload_root))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(final_root))

    source_path = tmp_path / "source.png"
    source = Image.new("RGB", (256, 256), (52, 88, 114))
    source.save(source_path, "PNG")

    raw_mask_path = tmp_path / "real-eyebrow-mask.png"
    raw_mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(raw_mask)
    draw.rectangle((62, 95, 98, 104), fill=255)
    draw.rectangle((158, 95, 194, 104), fill=255)
    raw_mask.save(raw_mask_path, "PNG")
    coverage = sum(1 for value in raw_mask.getdata() if value) / float(source.width * source.height)
    detection = {
        "ok": True,
        "method": "test_real_mask",
        "plausible": True,
        "is_fallback": False,
        "image_width": source.width,
        "image_height": source.height,
        "regions": [
            {"side": "left", "x": 62, "y": 95, "width": 37, "height": 10},
            {"side": "right", "x": 158, "y": 95, "width": 37, "height": 10},
        ],
        "mask": {
            "ok": True,
            "path": str(raw_mask_path),
            "real_mask": True,
            "is_fallback": False,
            "coverage_ratio": coverage,
            "pixel_count": int(coverage * source.width * source.height),
            "width": source.width,
            "height": source.height,
            "polarity": "white_editable",
        },
    }
    monkeypatch.setattr(image_generation, "ensure_eyebrow_mask", lambda _path, value: value)
    candidate = {"eyebrow_detection": detection}

    # Simulate Flux returning a completely different full-frame image.
    provider_bytes = BytesIO()
    Image.new("RGB", source.size, (62, 98, 124)).save(provider_bytes, "PNG")
    provider_value = "data:image/png;base64," + base64.b64encode(provider_bytes.getvalue()).decode("ascii")

    filename, meta = image_generation._save_provider_output(
        provider_value,
        timeout=5,
        source_path=str(source_path),
        candidate=candidate,
        provider_kind="cloudflare",  # Flux path
    )

    output_path = upload_root / filename
    assert filename.endswith(".webp")
    assert output_path.is_file()
    with Image.open(output_path) as final:
        assert final.format == "WEBP"
        final_rgb = final.convert("RGB")
        assert final_rgb.size == source.size

    with Image.open(source_path) as original:
        source_rgb = original.convert("RGB")
    assert outside_mask_pixels_equal(source_rgb, final_rgb, raw_mask)
    assert ImageChops.difference(source_rgb, final_rgb).getbbox() is not None
    assert meta["provider_output_constrained_to_eyebrow_mask"] is True
    assert meta["outside_mask_preserved"] is True
    assert meta["saved_outside_mask_preserved"] is True
    assert meta["saved_file_diff_validated"] is True
    assert meta["final_format"] == "WEBP"
    assert meta["final_size_bytes"] == output_path.stat().st_size
