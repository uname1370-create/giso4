# -*- coding: utf-8 -*-
"""Stage 15: adversarial upload and media-serving security audit."""
import io
from pathlib import Path

from PIL import Image
from werkzeug.datastructures import FileStorage

from giso.app import create_app
from giso.beauty_centers import routes
from giso.beauty_centers.services import save_center_image

ROOT = Path(__file__).resolve().parents[2]


def _storage(image: Image.Image, image_format: str, filename: str, **save_kwargs):
    payload = io.BytesIO()
    image.save(payload, image_format, **save_kwargs)
    payload.seek(0)
    return FileStorage(stream=payload, filename=filename, content_type="application/octet-stream")


def _remove(relative_path: str):
    output = ROOT / "giso/static" / relative_path
    if output.exists():
        output.unlink()


def test_validation_uses_content_not_filename_and_strips_metadata():
    image = Image.new("RGB", (80, 40), "#c85873")
    exif = Image.Exif()
    exif[274] = 6  # orientation: rotate 90 degrees
    storage = _storage(image, "JPEG", "payload.php", exif=exif)
    path, error = save_center_image(storage)
    try:
        assert not error
        assert path.startswith("uploads/beauty_centers/center_") and path.endswith(".webp")
        assert "payload" not in path
        output = ROOT / "giso/static" / path
        with Image.open(output) as saved:
            assert saved.format == "WEBP"
            assert saved.size == (40, 80)
            assert not saved.getexif()
    finally:
        if path:
            _remove(path)


def test_rejects_unsupported_empty_animated_and_pathological_dimensions():
    bmp_path, bmp_error = save_center_image(_storage(Image.new("RGB", (20, 20)), "BMP", "image.jpg"))
    assert not bmp_path and "JPG، PNG یا WebP" in bmp_error

    empty_path, empty_error = save_center_image(FileStorage(stream=io.BytesIO(), filename="empty.png"))
    assert not empty_path and "خالی" in empty_error

    frames = [Image.new("RGB", (20, 20), color) for color in ("red", "blue")]
    animated = io.BytesIO()
    frames[0].save(animated, "WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0)
    animated.seek(0)
    animation_path, animation_error = save_center_image(FileStorage(stream=animated, filename="animated.webp"))
    assert not animation_path and "متحرک" in animation_error

    wide = _storage(Image.new("RGB", (12001, 1)), "PNG", "wide.png")
    wide_path, wide_error = save_center_image(wide)
    assert not wide_path and "طول یا عرض" in wide_error


def test_rejects_malformed_and_oversized_payloads_without_persisting_temporary_files():
    directory = ROOT / "giso/static/uploads/beauty_centers"
    directory.mkdir(parents=True, exist_ok=True)
    before = {item.name for item in directory.iterdir()}

    malformed_path, malformed_error = save_center_image(FileStorage(
        stream=io.BytesIO(b"not-an-image"), filename="fake.jpg",
    ))
    assert not malformed_path and "معتبر نیست" in malformed_error

    oversized_path, oversized_error = save_center_image(FileStorage(
        stream=io.BytesIO(b"x" * (5 * 1024 * 1024 + 1)), filename="large.jpg",
    ))
    assert not oversized_path and "۵ مگابایت" in oversized_error
    assert {item.name for item in directory.iterdir()} == before


def test_media_route_blocks_traversal_and_sets_browser_hardening_headers(monkeypatch):
    path, error = save_center_image(_storage(Image.new("RGB", (30, 30)), "PNG", "center.png"))
    assert not error
    app = create_app()
    center = {
        "id": 99115, "owner_user_id": 1, "status": "published", "is_active": 1,
        "image_path": path,
    }
    monkeypatch.setattr(routes, "get_center", lambda _center_id: dict(center))
    try:
        with app.test_client() as client:
            response = client.get("/beauty-centers/media/99115")
            assert response.status_code == 200
            assert response.mimetype == "image/webp"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["Content-Security-Policy"] == "default-src 'none'; sandbox"

            center["image_path"] = "../templates/base.html"
            blocked = client.get("/beauty-centers/media/99115")
            assert blocked.status_code == 404
    finally:
        _remove(path)


def test_upload_implementation_is_atomic_and_does_not_trust_secure_filename():
    source = (ROOT / "giso/beauty_centers/services.py").read_text(encoding="utf-8")
    assert "CENTER_IMAGE_FORMATS" in source
    assert "DecompressionBombWarning" in source
    assert "probe.verify()" in source
    assert "ImageOps.exif_transpose" in source
    assert "os.replace(temporary, output)" in source
    assert "secrets.token_hex(16)" in source
    assert "secure_filename" not in source
