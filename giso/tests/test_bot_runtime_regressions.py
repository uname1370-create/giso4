# -*- coding: utf-8 -*-
"""Regression guards for standalone Bale bot runtime failures."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_handle_text_does_not_shadow_central_db_connector():
    tree = ast.parse((ROOT / "giso/bot.py").read_text(encoding="utf-8"))
    run_async = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "_run_async")
    handle_text = next(node for node in run_async.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle_text")
    shadowing = []
    for node in ast.walk(handle_text):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name) == "get_giso_db_conn" or alias.name == "get_giso_db_conn":
                    shadowing.append(node.lineno)
    assert not shadowing, f"local import shadows global get_giso_db_conn at {shadowing}"


def test_profile_service_uses_raw_connection_for_bot_context():
    source = (ROOT / "giso/user_profile_service.py").read_text(encoding="utf-8")
    profile_block = source[source.index("def get_user_profile"):source.index("def update_user_profile")]
    update_block = source[source.index("def update_user_profile"):source.index("def get_user_activity_summary")]
    assert "get_giso_db_conn" in profile_block
    assert "User.query" not in profile_block
    assert "db.session" not in update_block


def test_bot_registers_a_global_error_handler():
    source = (ROOT / "giso/bot.py").read_text(encoding="utf-8")
    assert "async def handle_error(update, context):" in source
    assert "app.add_error_handler(handle_error)" in source


def test_profile_message_is_plain_text_for_bale_compatibility():
    source = (ROOT / "giso/bot.py").read_text(encoding="utf-8")
    block = source[source.index("async def _show_user_profile"):source.index("async def _show_user_notifications")]
    assert '"👤 <b>پروفایل من</b>"' not in block
    assert 'parse_mode="HTML"' not in block
    assert '"👤 پروفایل من"' in block


def test_all_giso_bot_surfaces_avoid_html_markup():
    files = [
        ROOT / "giso/bot.py", ROOT / "giso/bot_hair_admin.py",
        ROOT / "giso/bot_market_admin.py", ROOT / "giso/bot_chats_admin.py",
        ROOT / "giso/beauty_centers/bot_handlers.py", ROOT / "giso/hair_sale.py",
        ROOT / "giso/channel_importer.py", ROOT / "giso/shop/bot/handlers.py",
        ROOT / "giso/shop/bot/user_menu.py", ROOT / "giso/shop/bot/admin_menu.py",
        ROOT / "giso/shop/bot/super_menu.py",
    ]
    for path in files:
        source = path.read_text(encoding="utf-8")
        assert 'parse_mode="HTML"' not in source, path
        assert "parse_mode='HTML'" not in source, path
        for tag in ("<b>", "</b>", "<code>", "</code>"):
            assert tag not in source, (path, tag)
