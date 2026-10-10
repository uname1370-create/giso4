"""Live eyebrow check: runs the PRODUCTION eyebrow final-image path once on a real photo.

Run on the machine that has the Aineh Giso central AI settings (mirror_image_design):

    cd <repo root>
    SECRET_KEY=<your app secret> PYTHONPATH=bot_edu:. python tools/eyebrow_live_check.py \
        --photo path/to/face.jpg --out eyebrow_live_out

Providers come from the central AI management panel (same as the app). No keys are
read from this script or printed. Exit code 0 only when a real AI-inpainted image was
produced and saved; otherwise the exact provider error is printed and the exit code is 1.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from urllib.parse import urlparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--photo", required=True, help="real face photo (JPG/PNG)")
    parser.add_argument("--style", default="natural", help="natural | microblading | powder | combination | giso_suggested")
    parser.add_argument("--change", default="medium", help="very_natural | medium | clear")
    parser.add_argument("--out", default="eyebrow_live_out", help="folder for the saved result")
    args = parser.parse_args()

    if not os.path.isfile(args.photo):
        print(f"photo not found: {args.photo}")
        return 1

    from giso.buti_ai.eyebrow import final_design, image_generation as ig

    work = tempfile.mkdtemp(prefix="eyebrow_live_")
    upload_dir = os.path.join(work, "upload")
    final_dir = os.path.join(work, "final")
    os.makedirs(upload_dir)
    os.makedirs(final_dir)
    shutil.copy(args.photo, os.path.join(upload_dir, "live_face" + os.path.splitext(args.photo)[1].lower()))
    final_design.EYEBROW_UPLOAD_DIR = upload_dir
    final_design.FINAL_DESIGN_DIR = final_dir

    candidate = {
        "photo_filename": os.path.basename(os.path.join(upload_dir, os.listdir(upload_dir)[0])),
        "final_style": args.style,
        "selected_style": args.style,
        "change_key": args.change,
        "final_label": args.style,
        "selected_label": args.style,
        "service_label": "آینه ابرو گیسو",
    }

    providers = ig.configured_image_providers(None, service_key="eyebrow")
    print("providers (central panel, keys hidden):")
    for p in providers:
        print(f"  - id={p.id} kind={p.kind} model={p.model} host={urlparse(p.endpoint).netloc}")
    if not providers:
        print("no image provider configured in the central AI panel (mirror_image_design)")
        return 1

    result = ig.generate_final_design(candidate, env=None)

    print("attempts:")
    for attempt in result.get("attempts") or []:
        print(f"  - provider={attempt.get('provider')} ok={attempt.get('ok')} error={str(attempt.get('error') or '')[:300]}")
    detection = result.get("eyebrow_detection") or {}
    print(f"mask method: {detection.get('method')}")
    print(f"ok={result.get('ok')} status={result.get('status')} ai_inpainting={result.get('ai_inpainting')} "
          f"is_ai_generated={result.get('is_ai_generated')} fallback_used={result.get('fallback_used')}")
    if result.get("error"):
        print(f"error: {str(result.get('error'))[:400]}")

    real_ai = bool(result.get("ok")) and bool(result.get("is_ai_generated")) and bool(result.get("ai_inpainting"))
    if real_ai and result.get("filename"):
        os.makedirs(args.out, exist_ok=True)
        # the production writer stores output at EYEBROW_UPLOAD_DIR/<filename>, filename starts with "final/"
        src = os.path.join(upload_dir, result["filename"])
        dst = os.path.join(args.out, os.path.basename(src))
        shutil.copy(src, dst)
        print(f"REAL AI RESULT SAVED: {os.path.abspath(dst)}")
        return 0

    print("NOT A REAL AI RESULT. Nothing was saved as success.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
