"""بستهٔ backup — تقسیم ماژول بزرگ (مرحلهٔ ۹ se.md / BUG-010).

__init__ همهٔ نام‌های عمومی و خصوصیِ مصرف‌شده را re-export می‌کند تا
تمام importهای موجود بدون تغییر کار کنند (سازگاری کامل عقب‌گرد).
"""
from .helpers import *  # noqa: F401,F403
from .core import *  # noqa: F401,F403
from .helpers import _write_restart_flag  # noqa: F401 (سازگاری patch تست‌ها)
from . import core as _c, helpers as _h  # noqa: F401

# سازگاری کامل: re-export همهٔ نام‌های خصوصی زیرماژول‌ها (برای patch تست‌ها و
# importهای داخلی) — بدون این بلوک، قرارداد mock تست‌ها می‌شکست.
for _src in (_h, _c):
    for _n in dir(_src):
        if _n.startswith("_") and not _n.startswith("__"):
            globals().setdefault(_n, getattr(_src, _n))
