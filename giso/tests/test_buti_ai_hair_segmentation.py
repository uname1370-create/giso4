"""Hair segmentation gate and detector routing for the hair_color service.

Mock tests (synthetic probability maps) check internal gate logic only; they are
NOT evidence of real AI quality. Real-photo tests run only when the audit photos
are present locally (BUTI_AI_REAL_PHOTO_DIR, default /home/user/buti_ai_audit/photos_hair2).
"""
import os

import numpy as np
import pytest
from PIL import Image

from giso.buti_ai.hair_color import final_design as hair
from giso.buti_ai.hair_color import segmentation as seg

REAL_DIR = os.environ.get("BUTI_AI_REAL_PHOTO_DIR", "/home/user/buti_ai_audit/photos_hair2")
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(seg.__file__))), "models")


def _probs(w, h, hair_box=None, skin_box=None, clothes_box=None):
    skin = np.zeros((h, w), np.float32)
    clothes = np.zeros((h, w), np.float32)
    hair_p = np.zeros((h, w), np.float32)
    for box, arr, val in ((skin_box, skin, 0.9), (clothes_box, clothes, 0.9), (hair_box, hair_p, 0.9)):
        if box:
            x0, y0, x1, y1 = box
            arr[y0:y1, x0:x1] = val
    return skin, clothes, hair_p


def _run_gate(monkeypatch, w, h, face_box, **boxes):
    skin, clothes, hair_p = _probs(w, h, **boxes)
    monkeypatch.setattr(seg, "class_probabilities", lambda img: (skin, clothes, hair_p))
    return seg.segment_hair(Image.new("RGB", (w, h), (120, 120, 120)), face_box)


def test_model_and_licence_are_vendored():
    assert os.path.getsize(os.path.join(MODEL_DIR, "hair_skin_clothes_mobilenetv3_small.onnx")) > 1_000_000
    licence = open(os.path.join(MODEL_DIR, "LICENSE-hair_skin_clothes_Kazuhito00-MIT.txt"), encoding="utf-8").read()
    assert "MIT License" in licence


def test_missing_face_anchor_is_rejected_with_reason():
    with pytest.raises(seg.HairSegmentationError) as info:
        seg.segment_hair(Image.new("RGB", (200, 200)), None)
    assert info.value.reason == "face_anchor_missing"


def test_mock_hair_above_and_beside_face_passes(monkeypatch):
    # face box (80,80,40,50); hair band above the head and down both sides, skin in the face.
    result = _run_gate(
        monkeypatch, 240, 240, (80, 80, 40, 50),
        hair_box=(60, 30, 140, 80), skin_box=(85, 90, 115, 125),
    )
    assert result["stats"]["above_face_share"] >= seg.MIN_ABOVE_FACE_SHARE
    assert result["stats"]["below_chin_centre_share"] <= seg.MAX_BELOW_CHIN_CENTRE_SHARE
    assert result["mask"].size == (240, 240)


def test_mock_hair_below_chin_centre_is_rejected(monkeypatch):
    # Hair-channel leakage onto the neck/collar directly under the chin.
    with pytest.raises(seg.HairSegmentationError) as info:
        _run_gate(
            monkeypatch, 240, 240, (80, 60, 40, 50),
            hair_box=(60, 130, 140, 200),
        )
    assert info.value.reason in {"hair_not_above_face", "hair_on_neck_or_clothes"}


def test_mock_skin_dominant_pixels_are_not_hair(monkeypatch):
    # Hair channel present but skin channel wins everywhere: no hair pixels touch the head zone.
    skin = np.full((200, 200), 0.9, np.float32)
    clothes = np.zeros((200, 200), np.float32)
    hair_p = np.full((200, 200), 0.6, np.float32)
    monkeypatch.setattr(seg, "class_probabilities", lambda img: (skin, clothes, hair_p))
    with pytest.raises(seg.HairSegmentationError) as info:
        seg.segment_hair(Image.new("RGB", (200, 200)), (80, 80, 40, 50))
    assert info.value.reason == "hair_not_detected"


def test_detector_failure_stays_untrusted(monkeypatch, tmp_path):
    # When segmentation rejects the photo, the colour detector runs and must NOT be trusted.
    img_path = tmp_path / "photo.jpg"
    Image.new("RGB", (240, 240), (150, 140, 130)).save(img_path)

    def _reject(image_path):
        raise seg.HairSegmentationError("hair_not_detected", "test")

    monkeypatch.setattr(hair, "_try_detect_hair_by_segmentation", _reject)
    detection = hair.detect_regions(str(img_path), allow_fallback=True)
    assert detection.get("detection_reliable") is not True
    assert detection.get("segmentation_rejected") == "hair_not_detected"


def test_detector_success_writes_mask_and_is_trusted(monkeypatch, tmp_path):
    img_path = tmp_path / "photo.jpg"
    Image.new("RGB", (240, 240), (150, 140, 130)).save(img_path)
    mask = Image.new("L", (240, 240), 0)
    mask.paste(255, (60, 30, 140, 80))

    def _ok(image_path):
        return {
            "ok": True, "method": "segmentation_hair_v1", "detection_reliable": True,
            "untrusted_reason": "", "is_fallback": False, "image_width": 240, "image_height": 240,
            "regions": [{"side": "hair", "x": 60, "y": 30, "width": 80, "height": 50}],
            "_mask_image": mask,
        }

    monkeypatch.setattr(hair, "_try_detect_hair_by_segmentation", _ok)
    detection = hair.detect_regions(str(img_path), allow_fallback=False)
    assert detection["detection_reliable"] is True
    assert detection["mask"]["ok"] is True
    assert detection["mask"]["real_mask"] is True
    assert os.path.exists(detection["mask"]["path"])


def _real_photos():
    if not os.path.isdir(REAL_DIR):
        return []
    return sorted(
        os.path.join(REAL_DIR, f) for f in os.listdir(REAL_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )


@pytest.mark.skipif(not _real_photos(), reason="real hair photos not present (BUTI_AI_REAL_PHOTO_DIR)")
def test_real_photos_are_not_trusted_by_default(tmp_path):
    """Production path: segmentation trust is off, so no real photo gets a trusted hair mask."""
    assert hair.SEGMENTATION_TRUSTED is False
    for src in _real_photos():
        dst = tmp_path / os.path.basename(src)
        Image.open(src).convert("RGB").save(dst)
        detection = hair.detect_regions(str(dst), allow_fallback=True)
        assert detection.get("detection_reliable") is not True, src
        assert detection.get("segmentation_rejected") == "segmentation_not_validated", src


@pytest.mark.skipif(not _real_photos(), reason="real hair photos not present (BUTI_AI_REAL_PHOTO_DIR)")
def test_real_photos_segmentation_runs_without_error(monkeypatch, tmp_path):
    """Diagnostic: the segmentation gate runs on real photos; trust is not asserted here."""
    pytest.importorskip("onnxruntime")
    monkeypatch.setattr(hair, "SEGMENTATION_TRUSTED", True)
    outcomes = []
    for src in _real_photos():
        dst = tmp_path / os.path.basename(src)
        Image.open(src).convert("RGB").save(dst)
        try:
            detection = hair._try_detect_hair_by_segmentation(str(dst))
            outcomes.append(("ok", detection["segmentation_stats"]["coverage"]))
        except seg.HairSegmentationError as exc:
            outcomes.append(("rejected", exc.reason))
    assert len(outcomes) == len(_real_photos())
