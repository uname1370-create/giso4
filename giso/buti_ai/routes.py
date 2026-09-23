# -*- coding: utf-8 -*-
"""
giso/buti_ai/routes.py — کنترلرهای وب و ای‌پی‌آی آینه جادویی گیسو.
"""
from flask import jsonify
from giso.buti_ai import buti_ai_bp
from giso.buti_ai.schema import init_buti_ai_db


@buti_ai_bp.route("/ping", methods=["GET"])
def ping():
    """تست سلامت ماژول آینه جادویی گیسو."""
    init_buti_ai_db()
    return jsonify({
        "status": "ok",
        "module": "buti_ai_ready"
    })


@buti_ai_bp.route("", methods=["GET"])
@buti_ai_bp.route("/", methods=["GET"])
def mirror_home():
    """روت اصلی ورودی آینه جادویی گیسو."""
    init_buti_ai_db()
    return "آینه جادویی گیسو (Buti AI) - در حال آماده‌سازی ویزارد بومی"
