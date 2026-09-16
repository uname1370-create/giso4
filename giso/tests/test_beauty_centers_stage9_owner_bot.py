# -*- coding: utf-8 -*-
"""Stage 9: Center-owner Bale entry point without duplicating the web panel."""
import asyncio

from giso.beauty_centers import bot_handlers
from giso.beauty_centers import services
from giso.bot import _profile_inline_kb


class FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))


class FakeQuery:
    def __init__(self):
        self.message = FakeMessage()
        self.answers = []

    async def answer(self, text="", **kwargs):
        self.answers.append((text, kwargs))


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_profile_shows_registration_cta_before_center_and_owner_actions_after_it():
    guest_buttons = _buttons(_profile_inline_kb("https://giso.test", False))
    assert any(button.text == "🏥 ثبت رایگان مرکز" and button.url.endswith("/beauty-centers/register")
               for button in guest_buttons)
    assert not any(button.callback_data == "bcowner|show" for button in guest_buttons)

    owner_buttons = _buttons(_profile_inline_kb("https://giso.test", True))
    assert any(button.text == "🏥 وضعیت مرکز من" and button.callback_data == "bcowner|show"
               for button in owner_buttons)
    assert any(button.text == "🌐 پنل مرکز" and button.url.endswith("/dashboard/beauty-center")
               for button in owner_buttons)
    assert not any(button.text == "🏥 ثبت رایگان مرکز" for button in owner_buttons)


def test_owner_callback_uses_authenticated_owner_id_and_real_center_data(monkeypatch):
    monkeypatch.setattr(services, "get_owner_center", lambda owner_id: {
        "id": 41, "owner_user_id": owner_id, "name": "مرکز واقعی مالک",
        "status": "published", "status_label": "منتشرشده", "slug": "real-center",
        "city": "تهران", "region": "مرکز", "views_count": 12,
        "price_inquiry_clicks": 3, "analysis_impressions": 4,
    })
    query = FakeQuery()
    handled = asyncio.run(bot_handlers.handle_beauty_owner_callback(
        query, 77, "https://giso.test/",
    ))
    assert handled
    text, kwargs = query.message.replies[-1]
    assert "مرکز واقعی مالک" in text and "منتشرشده" in text
    assert "ویرایش اطلاعات و پاسخ به پیام‌ها فقط در پنل امن سایت" in text
    buttons = _buttons(kwargs["reply_markup"])
    assert any(button.url == "https://giso.test/dashboard/beauty-center?tab=messages" for button in buttons)
    assert any(button.url == "https://giso.test/beauty-centers/real-center" for button in buttons)


def test_owner_callback_fails_closed_when_center_does_not_belong_to_account(monkeypatch):
    monkeypatch.setattr(services, "get_owner_center", lambda _owner_id: {})
    query = FakeQuery()
    handled = asyncio.run(bot_handlers.handle_beauty_owner_callback(query, 88, "https://giso.test"))
    assert not handled
    assert query.answers and "ثبت نشده" in query.answers[-1][0]
    assert not query.message.replies
