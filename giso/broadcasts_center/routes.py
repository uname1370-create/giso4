# -*- coding: utf-8 -*-
"""روت‌های نازک مرکز پیام — روی بلوپرینت پنل ثبت می‌شود؛ منطق در core.py."""
from flask import jsonify, request
from flask_login import current_user

from giso.broadcasts_center import core, worker

AUD_LABELS = {"all": "همه کاربران", "buyers": "خریداران مو", "sellers": "فروشندگان مو",
              "centers": "مراکز زیبایی", "regular": "کاربران عادی"}
CH_LABELS = {"site": "اعلان داخل سایت", "bale": "ربات بله", "both": "هر دو کانال"}


_REGISTERED = False


def register(bp):
    # بلوپرینت پس از اولین ثبت قفل می‌شود؛ create_appهای بعدی همان روت‌ها را می‌برند.
    global _REGISTERED
    if _REGISTERED:
        return
    _REGISTERED = True
    from giso.panel.routes import _guard, _render

    @bp.route("/broadcasts-center")
    def broadcasts_center():
        if r := _guard():
            return r
        return _render("broadcasts_center", "modules/broadcasts_center.html",
                       campaigns=core.campaign_list(), aud_labels=AUD_LABELS,
                       ch_labels=CH_LABELS)

    @bp.route("/broadcasts-center/create", methods=["POST"])
    def broadcasts_center_create():
        if r := _guard():
            return r
        data = request.get_json(silent=True) or {}
        actor = str(getattr(current_user, "phone", "") or "admin")
        ok, msg, cid = core.create_campaign(
            data.get("title"), data.get("message"),
            str(data.get("audience", "all")), str(data.get("channels", "site")),
            str(data.get("mode", "now")), str(data.get("scheduled_at", "")), actor)
        return jsonify(ok=ok, text=msg, id=cid)

    @bp.route("/broadcasts-center/status")
    def broadcasts_center_status():
        if r := _guard():
            return r
        return jsonify(ok=True, campaigns=core.campaign_list(),
                       worker_alive=worker.alive(), queue=worker.queue_size())
