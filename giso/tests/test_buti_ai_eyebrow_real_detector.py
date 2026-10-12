import shutil
from pathlib import Path

from giso.buti_ai.eyebrow.landmarks import detect_eyebrow_regions


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "giso" / "buti_ai" / "static" / "brows" / "upload_face_sample.jpg"


def test_project_eyebrow_sample_produces_trusted_real_mask(tmp_path):
    photo = tmp_path / SAMPLE.name
    shutil.copyfile(SAMPLE, photo)
    detection = detect_eyebrow_regions(str(photo), allow_fallback=False)
    mask = detection.get("mask") if isinstance(detection.get("mask"), dict) else {}

    assert detection["ok"] is True
    assert detection["method"] == "mediapipe_face_mesh"
    assert detection["detection_reliable"] is True
    assert detection["is_fallback"] is False
    assert len(detection["regions"]) == 2
    assert mask["ok"] is True
    assert mask["real_mask"] is True
    assert mask["is_fallback"] is False
    assert Path(mask["path"]).exists()
    assert 0 < float(mask["coverage_ratio"]) < 0.045
