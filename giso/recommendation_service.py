# -*- coding: utf-8 -*-
"""
Phase 6+7+17+25 Scenario 2: Real Recommendation Engine
- Multi-signal: hair_type, skin_type, concerns, analysis, order history
- DB-linked, no synthetic data, ownership guard
- Analysis → Recommendation → Products → Shop connection
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_recommendation")

# Phase 8 S2: Global recommendation limit — never spam user
MAX_RECOMMENDATIONS_PER_PAGE = 4
MAX_RECOMMENDATIONS_WIDGET = 3

# Phase 20: Customer Score weights (central config)
SCORE_WEIGHTS = {
    "analysis_completed": 20,
    "product_viewed": 2,
    "added_to_cart": 5,
    "purchase": 25,
    "hair_sale_request": 15,
    "consultant_request": 10,
}
SCORE_LEVELS = [
    (70, "hot"),
    (35, "warm"),
    (0, "cold"),
]


@dataclass
class NutritionItem:
    """یک آیتم خوراکی/تغذیه‌ای برای «توصیهٔ برنامهٔ زیبایی» (سفارش خاص، نه فروشگاه عمومی)."""

    product_id: int
    name: str
    reason: str = ""
    order_url: str = ""
    price: int = 0
    image_url: str = ""
    category: str = ""
    is_special_order: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "reason": self.reason,
            "order_url": self.order_url,
            "price": self.price,
            "image_url": self.image_url,
            "category": self.category,
            "is_special_order": self.is_special_order,
        }


def get_user_profile(phone: str) -> dict:
    """Extract user's beauty profile from real DB data."""
    if not phone:
        return {}
    try:
        with get_giso_db_conn() as conn:
            # Hair profile from latest hair order
            hair = conn.execute(
                "SELECT hair_type, hair_health, hair_weight, length_cm "
                "FROM hair_orders WHERE phone=? ORDER BY created_at DESC LIMIT 1",
                (phone,)
            ).fetchone()
            # Latest analysis
            ana = conn.execute(
                "SELECT type, ai_report_json FROM analyses WHERE phone=? ORDER BY created_at DESC LIMIT 1",
                (phone,)
            ).fetchone()
            # Order history
            orders = conn.execute(
                "SELECT COUNT(*) FROM product_orders WHERE phone=?", (phone,)
            ).fetchone()
            profile = {
                "hair_type": "",
                "hair_health": "",
                "hair_weight": "",
                "analysis_type": "",
                "concerns": [],
                "order_count": orders[0] if orders else 0,
            }
            if hair:
                profile["hair_type"] = str(hair[0] or "").strip()
                profile["hair_health"] = str(hair[1] or "").strip()
                profile["hair_weight"] = str(hair[2] or "").strip()
            if ana:
                profile["analysis_type"] = str(ana[0] or "")
                try:
                    report = json.loads(ana[1] or "{}")
                    if isinstance(report, dict):
                        # Extract concerns from analysis
                        for mp in report.get("main_problems") or []:
                            if isinstance(mp, dict) and mp.get("name"):
                                profile["concerns"].append(mp["name"])
                        for w in report.get("weaknesses") or []:
                            profile["concerns"].append(str(w))
                        for c in report.get("concerns") or []:
                            profile["concerns"].append(str(c))
                except Exception:
                    pass
            return profile
    except Exception as e:
        logger.error(f"get_user_profile: {e}")
        return {}


def get_recommendation_for_user(user_phone: str = "", max_items: int = 4) -> dict:
    """Phase 6+7: Multi-signal recommendation from real DB."""
    if not isinstance(max_items, int) or max_items < 1 or max_items > 20:
        max_items = 4
    try:
        profile = get_user_profile(user_phone)
        hair_type = profile.get("hair_type", "").lower()
        concerns = profile.get("concerns", [])
        analysis_type = profile.get("analysis_type", "")

        with get_giso_db_conn() as conn:
            products = []
            match_source = "general"

            # Signal 1: Match by hair_type from hair_orders
            if hair_type:
                rows = conn.execute(
                    "SELECT id, name, price, image_path, category, description, short_description "
                    "FROM products WHERE in_stock=1 AND publish_status='published' "
                    "AND (hair_type LIKE ? OR category LIKE ? OR subcategory LIKE ? OR name LIKE ? OR suitable_for LIKE ?) "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (f"%{hair_type}%", f"%{hair_type}%", f"%{hair_type}%",
                     f"%{hair_type}%", f"%{hair_type}%", max_items)
                ).fetchall()
                if rows:
                    products = rows
                    match_source = "hair_profile"

            # Signal 2: Match by analysis concerns
            if not products and concerns:
                like_conds = " OR ".join(["name LIKE ?" for _ in concerns[:3]])
                params = [f"%{c}%" for c in concerns[:3]]
                params.append(max_items)
                rows = conn.execute(
                    f"SELECT id, name, price, image_path, category, description, short_description "
                    f"FROM products WHERE in_stock=1 AND publish_status='published' "
                    f"AND ({like_conds}) ORDER BY updated_at DESC LIMIT ?",
                    params
                ).fetchall()
                if rows:
                    products = rows
                    match_source = "analysis_concerns"

            # Signal 3: Match by analysis type (hair/skin)
            if not products and analysis_type:
                rows = conn.execute(
                    "SELECT id, name, price, image_path, category, description, short_description "
                    "FROM products WHERE in_stock=1 AND publish_status='published' "
                    "AND (category LIKE ? OR concerns LIKE ?) "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (f"%{analysis_type}%", f"%{analysis_type}%", max_items)
                ).fetchall()
                if rows:
                    products = rows
                    match_source = "analysis_type"

            # Fallback: newest products
            if not products:
                products = conn.execute(
                    "SELECT id, name, price, image_path, category, description, short_description "
                    "FROM products WHERE in_stock=1 AND publish_status='published' "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (max_items,)
                ).fetchall()

            recommendations = [
                {
                    "product_id": r[0],
                    "name": r[1],
                    "price": r[2],
                    "image_path": r[3],
                    "category": r[4],
                    "description": (r[5] or "")[:100],
                    "short_description": r[6] or "",
                    "match_source": match_source,
                    "personalized": match_source != "general",
                }
                for r in products
            ]

            return {
                "status": "ok",
                "analysis_based": bool(hair_type or concerns or analysis_type),
                "match_source": match_source,
                "profile": {
                    "hair_type": profile.get("hair_type"),
                    "concerns": profile.get("concerns", [])[:5],
                },
                "recommendations": recommendations,
                "count": len(recommendations),
            }
    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        return {
            "status": "error",
            "message": "Recommendation service unavailable",
            "recommendations": []
        }


def get_product_recommendation(product_id: int, user_phone: str = "", max_items: int = 4) -> dict:
    """Phase 17: Smart recommendation on product page (related to current product + user profile)."""
    try:
        with get_giso_db_conn() as conn:
            product = conn.execute(
                "SELECT category, subcategory, hair_type, skin_type, concerns FROM products WHERE id=?",
                (product_id,)
            ).fetchone()
            if not product:
                return {"status": "ok", "recommendations": [], "reason": "product_not_found"}

            cat = str(product[0] or "")
            subcat = str(product[1] or "")
            p_hair = str(product[2] or "")
            p_skin = str(product[3] or "")
            p_concerns = str(product[4] or "")

            # Get user profile
            profile = get_user_profile(user_phone)
            user_hair = profile.get("hair_type", "")

            # Build match: same category + compatible hair type
            conditions = ["p.in_stock=1", "p.publish_status='published'", "p.id != ?"]
            params = [product_id]

            if cat:
                conditions.append("p.category LIKE ?")
                params.append(f"%{cat}%")

            if user_hair and p_hair:
                conditions.append("(p.hair_type LIKE ? OR p.hair_type = '' OR p.suitable_for LIKE ?)")
                params.extend([f"%{user_hair}%", f"%{user_hair}%"])

            params.append(max_items)
            where = " AND ".join(conditions)
            rows = conn.execute(
                f"SELECT p.id, p.name, p.price, p.image_path, p.category, p.short_description "
                f"FROM products p WHERE {where} ORDER BY p.views DESC, p.updated_at DESC LIMIT ?",
                params
            ).fetchall()

            return {
                "status": "ok",
                "personalized": bool(user_hair),
                "recommendations": [
                    {
                        "product_id": r[0], "name": r[1], "price": r[2],
                        "image_path": r[3], "category": r[4],
                        "short_description": r[5] or "",
                        "match_source": "product_page",
                        "personalized": bool(user_hair),
                    }
                    for r in rows
                ],
                "count": len(rows),
            }
    except Exception as e:
        logger.error(f"get_product_recommendation: {e}")
        return {"status": "error", "recommendations": []}


def get_product_reason(product_id: int, user_phone: str = "") -> str:
    """Phase 16+17: Generate 'why this product is recommended for you' text."""
    if not user_phone:
        return ""
    try:
        profile = get_user_profile(user_phone)
        if not profile.get("hair_type") and not profile.get("concerns"):
            return ""

        with get_giso_db_conn() as conn:
            product = conn.execute(
                "SELECT name, category, hair_type, suitable_for FROM products WHERE id=?",
                (product_id,)
            ).fetchone()
            if not product:
                return ""

            reasons = []
            if profile.get("hair_type") and (product[2] or product[3]):
                reasons.append(f"این محصول مناسب موی {profile['hair_type']} شماست")
            if profile.get("concerns"):
                for c in profile["concerns"][:2]:
                    reasons.append(f"با توجه به نگرانی «{c}» شما")
            if profile.get("analysis_type"):
                reasons.append("بر اساس نتیجه آنالیز هوشمند شما")

            return " • ".join(reasons) if reasons else ""
    except Exception as e:
        logger.error(f"get_product_reason: {e}")
        return ""


def _extract_profile_signals(profile: Optional[dict], analysis_data: Optional[Any]) -> dict:
    """استخراج سیگنال‌های تطبیق (نوع مو/پوست/نگرانی) از پروفایل + گزارش آنالیز (هر دو منبع)."""
    signals = {
        "hair_type": str((profile or {}).get("hair_type") or "").strip().lower(),
        "skin_type": str((profile or {}).get("skin_type") or "").strip().lower(),
        "concerns": [],
    }
    try:
        _concerns = list((profile or {}).get("concerns") or [])
        for c in _concerns:
            c = str(c).strip()
            if c:
                signals["concerns"].append(c)
        if isinstance(analysis_data, dict):
            for key in ("concerns", "main_problems", "problems", "weaknesses", "labels"):
                raw = analysis_data.get(key)
                if isinstance(raw, dict):
                    raw = list(raw.values())
                for item in (raw or []):
                    if isinstance(item, dict):
                        nm = item.get("name") or item.get("title") or item.get("label")
                        if nm:
                            signals["concerns"].append(str(nm).strip())
                    else:
                        signals["concerns"].append(str(item).strip())
            if not signals["hair_type"]:
                signals["hair_type"] = str(analysis_data.get("hair_type") or "").strip().lower()
            if not signals["skin_type"]:
                signals["skin_type"] = str(analysis_data.get("skin_type") or "").strip().lower()
    except Exception:
        pass
    signals["concerns"] = [c for c in signals["concerns"] if c]
    signals["hair_type"] = signals["hair_type"]
    signals["skin_type"] = signals["skin_type"]
    return signals


def _nutrition_match_score(signals: dict, row: Any) -> int:
    """امتیاز تطبیقِ یک رکورد special_order با سیگنال‌های کاربر (۰ یعنی بی‌ارتباط)."""
    blob = " ".join([
        str(row[1] or ""), str(row[3] or ""), str(row[4] or ""), str(row[5] or ""),
        str(row[6] or ""), str(row[7] or ""), str(row[8] or ""), str(row[9] or ""),
    ]).lower()
    score = 0
    # تطبیق نگرانی‌ها: هر کدام که در متن محصول باشد +۲
    for c in signals["concerns"][:5]:
        if c.lower() and c.lower() in blob:
            score += 2
    # تطبیق نوع مو/پوست از فیلدهای `hair_type`/`skin_type` یا متن: +۳
    if signals["hair_type"] and signals["hair_type"] in blob:
        score += 3
    if signals["skin_type"] and signals["skin_type"] in blob:
        score += 3
    return score


def get_nutrition_recommendations(phone: str = "", analysis_data: Optional[Any] = None,
                                  limit: int = 3) -> List[NutritionItem]:
    """توصیهٔ آیتم‌های خوراکی/تغذیه‌ای (`special_order`) برای برنامهٔ زیبایی کاربر.

    دقیقاً برخلاف ``get_recommendation_for_user`` که فقط ``published`` می‌خواند، این تابع
    از جدول ``products`` فقط ردیف‌های ``publish_status='special_order'`` را می‌خواند و
    حداکثر ``limit`` آیتم برمی‌گرداند (کارت «سفارش خاص» — نه فروشگاه عمومی).
    تابع قبلی و رفتار موجود دست‌نخورده می‌ماند.
    """
    if not isinstance(limit, int) or limit < 1 or limit > 20:
        limit = 3
    limit = min(limit, 3)  # قانون سناریو: حداکثر ۳ آیتم
    try:
        profile = get_user_profile(phone)
        signals = _extract_profile_signals(profile, analysis_data)
    except Exception:
        signals = {"hair_type": "", "skin_type": "", "concerns": []}

    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT id, name, price, category, subcategory, hair_type, skin_type, "
                "concerns, short_description, description, image_path "
                "FROM products WHERE in_stock=1 AND publish_status='special_order' "
                "ORDER BY updated_at DESC, id DESC"
            ).fetchall()
    except Exception as e:
        logger.error(f"get_nutrition_recommendations: {e}")
        return []

    if not rows:
        return []

    scored = []
    for r in rows:
        score = _nutrition_match_score(signals, r)
        # حتی بدون تطبیق، تنها اگر نگرانی‌ای داریم اجازه بدهیم با امتیاز صفر بیاید
        # (برای کاربر بدون آنالیز، مرتب‌سازی بر اساس جدیدترین). برای جلوگیری از اسپم،
        # فقط آیتم‌ها را به‌همراه امتیاز نگه می‌داریم.
        scored.append((score, r))

    # مرتب‌سازی: امتیاز نزولی، بعد جدیدترین
    scored.sort(key=lambda x: (-x[0], -x[1][0]))

    items: List[NutritionItem] = []
    for score, r in scored[:limit]:
        pid, name, price, category, subcategory, hair_type, skin_type, concerns, short, desc, image = (
            r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]
        )
        # ساخت دلیل شخصی کوتاه
        reasons = []
        if signals["concerns"] and any(c.lower() in str(name).lower() or c.lower() in str(short or "").lower()
                                       for c in signals["concerns"]):
            top = next((c for c in signals["concerns"] if c.lower() in str(name).lower()
                        or c.lower() in str(short or "").lower()), signals["concerns"][0])
            reasons.append(f"برای «{top}» شما مفید است")
        if signals["hair_type"] and hair_type and signals["hair_type"] in str(hair_type).lower():
            reasons.append(f"مناسب موی {signals['hair_type']} شما")
        if signals["skin_type"] and skin_type and signals["skin_type"] in str(skin_type).lower():
            reasons.append(f"مناسب پوست {signals['skin_type']} شما")
        reason_text = " • ".join(reasons) if reasons else "در برنامهٔ تغذیه‌ات به شادابی مو و پوست کمک می‌کند"

        order_url = "/analysis/plan"
        items.append(NutritionItem(
            product_id=int(pid),
            name=str(name),
            reason=reason_text,
            order_url=order_url,
            price=int(price or 0),
            image_url=str(image or ""),
            category=str(category or ""),
            is_special_order=True,
        ))

    return items


# Phase 20: Customer Score
def calculate_customer_score(user_id: int = 0, phone: str = "") -> dict:
    """Calculate customer score from real behavior data."""
    try:
        with get_giso_db_conn() as conn:
            score = 0
            details = {}

            # Analysis count
            cnt = conn.execute(
                "SELECT COUNT(*) FROM analyses WHERE phone=? OR user_id=?",
                (phone, user_id)
            ).fetchone()[0]
            details["analysis_count"] = cnt
            score += cnt * SCORE_WEIGHTS["analysis_completed"]

            # Order count
            cnt = conn.execute(
                "SELECT COUNT(*) FROM product_orders WHERE phone=? OR user_id=?",
                (phone, user_id)
            ).fetchone()[0]
            details["order_count"] = cnt
            score += cnt * SCORE_WEIGHTS["purchase"]

            # Hair sale count
            cnt = conn.execute(
                "SELECT COUNT(*) FROM hair_orders WHERE phone=? OR user_id=?",
                (phone, user_id)
            ).fetchone()[0]
            details["hair_sale_count"] = cnt
            score += cnt * SCORE_WEIGHTS["hair_sale_request"]

            # Determine level
            level = "cold"
            for threshold, lvl in SCORE_LEVELS:
                if score >= threshold:
                    level = lvl
                    break

            return {
                "score": score,
                "level": level,
                "details": details,
            }
    except Exception as e:
        logger.error(f"calculate_customer_score: {e}")
        return {"score": 0, "level": "cold", "details": {}}


def upsert_customer_score(user_id: int = 0, phone: str = "") -> dict:
    """Update or insert customer score record."""
    result = calculate_customer_score(user_id, phone)
    try:
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_giso_db_conn() as conn:
            conn.execute("""
                INSERT INTO customer_scores (user_id, phone, score, level, analysis_count, order_count, hair_sale_count, last_activity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, phone) DO UPDATE SET
                    score=excluded.score, level=excluded.level,
                    analysis_count=excluded.analysis_count, order_count=excluded.order_count,
                    hair_sale_count=excluded.hair_sale_count, last_activity=excluded.last_activity,
                    updated_at=excluded.updated_at
            """, (user_id, phone, result["score"], result["level"],
                  result["details"].get("analysis_count", 0),
                  result["details"].get("order_count", 0),
                  result["details"].get("hair_sale_count", 0),
                  now, now, now))
            conn.commit()
    except Exception as e:
        logger.error(f"upsert_customer_score: {e}")
    return result
