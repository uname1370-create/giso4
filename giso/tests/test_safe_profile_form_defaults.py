import sqlite3
from pathlib import Path

from giso import user_profile_service as profiles


def connect_factory(path):
    def connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    return connect


def seed(path):
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE giso_web_auth(
          id INTEGER,phone TEXT,name TEXT,first_name TEXT,last_name TEXT,city TEXT,
          region TEXT,contact_time TEXT,created_at TEXT,last_login TEXT,
          last_profile_edit_at TEXT,password_hash TEXT,security_answer TEXT)""")
        conn.execute("INSERT INTO giso_web_auth VALUES(1,'+989121234567','نام قدیمی','مینا','احمدی','مشهد','سجاد','۱۰ تا ۱۲','','','','SECRET-HASH','SECRET-ANSWER')")


def test_safe_defaults_are_minimal_and_normalized(monkeypatch, tmp_path):
    db = tmp_path / "profile.db"
    seed(db)
    monkeypatch.setattr(profiles, "get_giso_db_conn", connect_factory(db))
    user = type("User", (), {"is_authenticated": True, "phone": "09121234567"})()
    result = profiles.safe_form_defaults(user)
    assert result == {"full_name": "مینا احمدی", "phone": "+989121234567",
                      "city": "مشهد", "region": "سجاد", "contact_time": "۱۰ تا ۱۲"}
    rendered = str(result)
    assert "SECRET" not in rendered and "password" not in rendered


def test_guest_gets_no_profile_data(monkeypatch):
    monkeypatch.setattr(profiles, "get_user_profile", lambda phone: (_ for _ in ()).throw(AssertionError("DB must not be read")))
    guest = type("Guest", (), {"is_authenticated": False, "phone": "+989121234567"})()
    assert all(not value for value in profiles.safe_form_defaults(guest).values())


def test_ad_and_checkout_templates_use_safe_defaults_and_preserve_post():
    root = Path(__file__).resolve().parents[2]
    shop = (root / "giso/shop/templates/shop.html").read_text()
    cart = (root / "giso/shop/templates/cart.html").read_text()
    center = (root / "giso/beauty_centers/templates/beauty_centers/register.html").read_text()
    market = (root / "giso/panel_user/templates/user_modules/marketplace.html").read_text()
    assert "request.form.get('customer_name') or profile_defaults.full_name" in shop + cart
    assert "request.form.get('phone') or profile_defaults.phone" in shop + cart
    assert "request.form.get('business_phone') or defaults.business_phone" in center
    assert 'value="{{ profile_defaults.city or \'\' }}"' in market
    # Exact address is intentionally never derived from a broad profile region.
    assert "profile_defaults.region" not in shop + cart
