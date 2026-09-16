#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مرحلهٔ ۴ se.md / BUG-004 — تست شکست پیام بلند بله (send_long_message)."""
import asyncio
import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.bot_helpers import send_long_message  # noqa: E402


class StubBot:
    def __init__(self):
        self.calls = []

    async def send_message(self, chat_id, text, **kwargs):
        self.calls.append({"chat_id": chat_id, "text": text, **kwargs})
        return len(self.calls)


class SendLongMessageTests(unittest.TestCase):
    def test_short_message_single_call_with_kwargs(self):
        bot = StubBot()
        asyncio.run(send_long_message(bot, 42, "سلام", reply_markup="KB", parse_mode="Markdown"))
        self.assertEqual(len(bot.calls), 1)
        self.assertEqual(bot.calls[0]["text"], "سلام")
        self.assertEqual(bot.calls[0]["reply_markup"], "KB")

    def test_long_message_split_and_markup_last_only(self):
        bot = StubBot()
        text = ("پاراگراف یک " + "ا" * 3000) + "\n\n" + ("پاراگراف دو " + "ب" * 3000) + "\n\n" + "پایان"
        asyncio.run(send_long_message(bot, 7, text, reply_markup="KB", chunk_limit=4000, delay=0))
        self.assertGreaterEqual(len(bot.calls), 2)
        for c in bot.calls:
            self.assertLessEqual(len(c["text"]), 4000)
        # reply_markup فقط تکهٔ آخر
        for c in bot.calls[:-1]:
            self.assertNotIn("reply_markup", c)
        self.assertEqual(bot.calls[-1]["reply_markup"], "KB")
        # بازسازی ترتیب محتوا
        joined = "\n\n".join(c["text"] for c in bot.calls)
        self.assertEqual(joined, text)

    def test_hard_split_for_huge_single_line(self):
        bot = StubBot()
        text = "خ" * 9000
        asyncio.run(send_long_message(bot, 1, text, chunk_limit=4000, delay=0))
        self.assertEqual(len(bot.calls), 3)
        self.assertEqual("".join(c["text"] for c in bot.calls), text)
        for c in bot.calls:
            self.assertLessEqual(len(c["text"]), 4000)


if __name__ == "__main__":
    unittest.main()
