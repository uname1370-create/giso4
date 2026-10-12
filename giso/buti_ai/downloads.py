# -*- coding: utf-8 -*-
"""Private, in-memory download helpers for Buti AI final designs."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict


def _rtl(value: Any) -> str:
    """Shape Persian text when optional project dependencies are installed."""
    text = str(value or "").strip()
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _font_path() -> str:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        if Path(path).is_file():
            return path
    return ""


def _copy_as_png(source: str, destination: str) -> None:
    from PIL import Image

    with Image.open(source) as image:
        image.convert("RGB").save(destination, "PNG", optimize=True)


def _add_image_page(pdf, image_path: str, heading: str) -> None:
    pdf.add_page()
    pdf.set_font("GisoReport", size=15)
    pdf.multi_cell(0, 9, _rtl(heading), align="R")
    y = pdf.get_y() + 5
    try:
        pdf.image(image_path, x=12, y=y, w=186, h=245, keep_aspect_ratio=True)
    except TypeError:
        pdf.image(image_path, x=12, y=y, w=186)


def build_design_report_pdf(
    service_label: str,
    candidate: Dict[str, Any],
    generation: Dict[str, Any],
    source_image_path: str,
    final_image_path: str,
) -> bytes:
    """Build a small PDF report without retaining another copy of private media."""
    from fpdf import FPDF

    font_path = _font_path()
    if not font_path:
        raise RuntimeError("font_unavailable")

    candidate = candidate if isinstance(candidate, dict) else {}
    generation = generation if isinstance(generation, dict) else {}
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("GisoReport", fname=font_path)
    pdf.add_page()
    pdf.set_font("GisoReport", size=18)
    pdf.multi_cell(0, 11, _rtl(f"گزارش آینه زیبایی گیسو — {service_label}"), align="R")
    pdf.ln(4)
    pdf.set_font("GisoReport", size=11)
    status = "خروجی AI تأییدشده" if generation.get("is_ai_generated") else "راهنمای غیر AI"
    rows = (
        ("مدل نهایی", candidate.get("final_label")),
        ("مدل انتخاب اولیه", candidate.get("selected_label")),
        ("شدت تغییر", candidate.get("change_label")),
        ("وضعیت خروجی", status),
        ("یادداشت", generation.get("message") or candidate.get("analysis_reason")),
    )
    for label, value in rows:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 8, _rtl(f"{label}: {value or '—'}"), align="R")

    pdf.ln(4)
    pdf.set_font("GisoReport", size=9)
    disclaimer = (
        "این گزارش فقط پیش‌نمایش است و نتیجه اجرای قطعی سالن یا توصیه پزشکی نیست. "
        "در خروجی غیر AI، تصویر صرفاً راهنمای محلی است."
    )
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 7, _rtl(disclaimer), align="R")

    with TemporaryDirectory(prefix="buti_ai_pdf_") as work_dir:
        before_png = str(Path(work_dir) / "before.png")
        final_png = str(Path(work_dir) / "final.png")
        _copy_as_png(source_image_path, before_png)
        _copy_as_png(final_image_path, final_png)
        _add_image_page(pdf, before_png, "عکس قبل")
        _add_image_page(pdf, final_png, "خروجی نهایی")
        return bytes(pdf.output())
