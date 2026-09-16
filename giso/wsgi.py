# Phase 13 — WSGI entry point for Gunicorn
# مسیر نسبی بر اساس محل همین فایل تا deploy روی هر سرور کار کند
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from giso.app import app

# پچ گزارش نهایی آنالیز (session + auth order)
try:
    from giso.analysis_final_override import install as _install_analysis_final
    _install_analysis_final()
except Exception as _e:
    import logging
    logging.getLogger("giso_wsgi").warning("analysis final override not applied: %s", _e)

application = app
