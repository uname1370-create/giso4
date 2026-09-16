# -*- coding: utf-8 -*-
"""P0 regressions: retired referral UX and unified bot wallet."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_register_form_has_no_referral_input():
    html = _source("giso/templates/register.html")
    assert 'name="referral_code"' not in html
    assert "کد معرفی" not in html


def test_registration_does_not_create_new_referral_data():
    source = _source("giso/app.py")
    register = source[source.index('    @app.route("/register"'):source.index('    @app.route("/logout")')]
    assert "ensure_referral_code(" not in register
    assert "register_referral(" not in register
    assert 'request.args.get("ref")' not in register
    assert 'request.form.get("referral_code")' not in register


def test_bot_wallet_uses_central_cash_spend_ledger_without_referral_claims():
    # ویوی کیف پول ربات به اکشن واحد ua|wallet|main در bot_user_actions سپرده شده است
    # (لیجر مرکزی cash/spend از giso.wallet)؛ دکمه ربات فقط delegate می‌کند.
    source = _source("giso/bot.py")
    start = source.index('        if text in ("💰 کیف پول من", "💰 کیف پول"):')
    end = source.index('        if text in ("💬 پشتیبانی", "🎧 پشتیبانی"):', start)
    wallet_block = source[start:end]
    assert 'send_ua_view(msg, phone, "ua|wallet|main")' in wallet_block
    assert "referral_code" not in wallet_block
    assert "با معرفی دوستان" not in wallet_block
    assert "۱۰,۰۰۰" not in wallet_block

    actions = _source("giso/bot_user_actions.py")
    wallet_view = actions[actions.index("def wallet_main"):]
    assert "get_wallet_balances" in wallet_view
    assert "bal['cash']" in wallet_view
    assert "bal['spend']" in wallet_view
    assert "referral_code" not in wallet_view
    assert "با معرفی دوستان" not in wallet_view


def test_referral_compatibility_layer_cannot_create_new_relationship():
    import giso.referrals as referrals

    assert referrals.get_referral_settings()["enabled"] is False
    assert referrals.register_referral(1, 2, "OLD", "+989120000000") is None
