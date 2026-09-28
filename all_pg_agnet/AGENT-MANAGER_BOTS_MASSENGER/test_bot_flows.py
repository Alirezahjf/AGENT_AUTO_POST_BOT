#!/usr/bin/env python3
"""End-to-end regression tests for bot.py flows touched by this change.

Covers the reported ticket bug (tapping a ticket category froze the user until restart),
answerCallbackQuery, per-update error isolation, update logging, group media upload
(album -> ONE library item, late items), «بدون مدیا» / «بدون کپشن» and the unchanged
single-media upload.

Safety: the test copies the *.py files into a temporary directory and re-runs itself
there, so bot.py gets its own auth.db, users/, config.json and bot.log. The real
databases/config are never opened, and requests is faked (no network at all).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX_ENV = "BOT_FLOW_TEST_SANDBOX"
FAKE_CONFIG = {
    "messengers": {"bale": {"bot_token": "123:TESTTOKEN", "channel_id": ""}},
    "user_languages": {"5001": "fa", "5002": "fa", "7001": "fa"},
}

if __name__ == "__main__" and not os.environ.get(SANDBOX_ENV):
    sandbox = Path(tempfile.mkdtemp(prefix="bot-flow-test-"))
    try:
        for source in HERE.glob("*.py"):
            shutil.copy2(source, sandbox / source.name)
        (sandbox / "config.json").write_text(json.dumps(FAKE_CONFIG), encoding="utf-8")
        env = dict(os.environ, **{SANDBOX_ENV: str(sandbox)})
        code = subprocess.call([sys.executable, str(sandbox / Path(__file__).name)] + sys.argv[1:],
                               cwd=str(sandbox), env=env)
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    sys.exit(code)

# ------------------------------------------------------------------ inside the sandbox copy
import sqlite3  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

SANDBOX = Path(os.environ.get(SANDBOX_ENV, "/nonexistent")).resolve()
if HERE != SANDBOX:
    raise SystemExit("refusing to run outside the sandbox copy")
os.chdir(SANDBOX)

import requests  # noqa: E402

NET = []


class _Resp:
    status_code = 200
    text = '{"ok": true}'

    def json(self):
        return {"ok": True, "result": {"message_id": 1}}


def _fake_http(method):
    def call(url, *args, **kwargs):
        NET.append((method, url, kwargs))
        return _Resp()
    return call


requests.post = _fake_http("POST")
requests.get = _fake_http("GET")

import bot  # noqa: E402
import media_group  # noqa: E402

assert Path(bot.__file__).resolve().parent == SANDBOX
assert Path(bot.auth_manager.auth_db_path).resolve().parent == SANDBOX

USER, OTHER, ADMIN = 5001, 5002, 7001
SENT = []


def _record(kind):
    def fn(chat_id, text, keyboard=None, *args, **kwargs):
        SENT.append({"kind": kind, "chat": chat_id, "text": text, "keyboard": keyboard})
        return True
    return fn


bot.send_message = _record("send")
bot.edit_message = lambda chat_id, message_id, text, keyboard=None: SENT.append(
    {"kind": "edit", "chat": chat_id, "text": text, "keyboard": keyboard}) or True
bot.send_photo = lambda chat_id, file_id, caption=None, keyboard=None: SENT.append(
    {"kind": "photo", "chat": chat_id, "text": caption, "file": file_id}) or True
bot.send_video = lambda chat_id, file_id, caption=None, keyboard=None: SENT.append(
    {"kind": "video", "chat": chat_id, "text": caption, "file": file_id}) or True
bot.auth_manager.setup_initial_admin(ADMIN, "tester")


def msg(chat, text=None, **extra):
    m = {"message_id": 1, "chat": {"id": chat, "type": "private"}, "from": {"id": chat, "username": f"u{chat}"}}
    if text is not None:
        m["text"] = text
    m.update(extra)
    return m


def press(chat, data, parent_text="(bot message with the keyboard)"):
    bot.handle_message(msg(chat, parent_text), callback_data=data)


def say(chat, text):
    bot.handle_message(msg(chat, text))


def callbacks_in(entry):
    keyboard = (entry or {}).get("keyboard") or {}
    return [b.get("callback_data") for row in keyboard.get("inline_keyboard", []) for b in row]


def album_update(uid, chat, group, file_id, kind="photo"):
    media = {"photo": [{"file_id": f"thumb-{file_id}"}, {"file_id": file_id}]} if kind == "photo" \
        else {"video": {"file_id": file_id}}
    return {"update_id": uid, "message": msg(chat, None, media_group_id=group, **media)}


def run_loop(*responses):
    """Run bot.run() against scripted getUpdates responses, then stop it."""
    queue = [{"ok": True, "result": r} for r in responses]

    def fake_get_updates(offset=None, timeout=30):
        if not queue:
            raise KeyboardInterrupt
        return queue.pop(0)

    with mock.patch.object(bot, "get_updates", fake_get_updates), \
            mock.patch.object(bot.scheduler, "start_scheduler", lambda cfg: None), \
            mock.patch("time.sleep", lambda *_: None):
        bot.run()


class BotTestCase(unittest.TestCase):
    def setUp(self):
        SENT.clear()
        NET.clear()
        bot.user_states.clear()

    def texts(self, chat=None):
        return [e["text"] or "" for e in SENT if chat is None or e["chat"] == chat]


class TicketFlowTests(BotTestCase):
    """The reported bug: new ticket -> tap a category -> nothing happens, bot 'dead'."""

    def test_category_tap_moves_on_to_the_subject(self):
        press(USER, "support_new", "🎫 پشتیبانی و تیکت‌ها")
        self.assertEqual(bot.user_states[USER]["state"], "support_new_category")
        SENT.clear()
        press(USER, "support_category_technical", "موضوع تیکت را انتخاب کنید:")
        self.assertEqual(bot.user_states[USER], {"state": "support_new_subject", "category": "technical"})
        self.assertIn("موضوع تیکت را بنویسید", self.texts(USER)[-1])

    def test_user_is_not_stuck_after_the_category_step(self):
        press(USER, "support_new")
        SENT.clear()
        say(USER, "/start")  # used to be swallowed silently until restart
        self.assertNotIn(USER, bot.user_states)

    def test_cancel_never_creates_a_garbage_ticket(self):
        bot.user_states[USER] = {"state": "support_new_subject", "category": "technical"}
        press(USER, "support_cancel", "موضوع تیکت را بنویسید (۳ تا ۱۲۰ نویسه):")
        self.assertNotIn(USER, bot.user_states)
        bot.user_states[USER] = {"state": "support_new_body", "category": "technical", "subject": "abc"}
        press(USER, "support_cancel", "شرح دقیق مشکل یا درخواست را بنویسید (حداقل ۵ نویسه):")
        self.assertEqual(bot.auth_manager.list_tickets(owner_chat_id=USER, status="all"), [])

    def test_complete_ticket_flow_creates_the_ticket(self):
        press(OTHER, "support_new")
        press(OTHER, "support_category_account")
        say(OTHER, "ورود به حساب")
        say(OTHER, "نمی‌توانم وارد حساب شوم")
        tickets = bot.auth_manager.list_tickets(owner_chat_id=OTHER, status="all")
        self.assertEqual([(t["subject"], t["category"]) for t in tickets], [("ورود به حساب", "account")])
        self.assertNotIn(OTHER, bot.user_states)
        self.assertIn("ثبت شد", self.texts(OTHER)[-1])

    def test_typed_text_on_the_category_step_gets_the_buttons_again(self):
        press(USER, "support_new")
        SENT.clear()
        say(USER, "مشکل پرداخت")
        self.assertIn("support_category_payment", callbacks_in(SENT[-1]))
        self.assertEqual(bot.user_states[USER]["state"], "support_new_category")

    def test_menu_button_or_other_inline_button_leaves_the_form(self):
        bot.user_states[ADMIN] = {"state": "support_new_subject", "category": "other"}
        say(ADMIN, bot.t(ADMIN, "posting_management"))
        self.assertNotIn(ADMIN, bot.user_states)
        self.assertIn("مدیریت پست‌ها", self.texts(ADMIN)[-1])
        bot.user_states[ADMIN] = {"state": "support_reply", "ticket_id": 1}
        press(ADMIN, "posting_new")
        self.assertNotIn(ADMIN, bot.user_states)

    def test_every_support_button_gets_a_visible_answer(self):
        ticket_id = bot.auth_manager.create_ticket(ADMIN, "admin", "Admin issue", "Details of the issue", "other")["ticket_id"]
        buttons = ["support_home", "support_new", "support_category_technical", "support_category_bogus",
                   "support_mine_active_0", "support_mine_closed_0", "support_mine_0", "support_admin_home",
                   "support_adminlist_active_0", "support_ticket_999", "support_ticket_x", "support_reply_999",
                   "support_close_999", "support_reopen_999", "support_progress_999", "support_priority_999",
                   "support_assign_999", "support_cancel", "support_unknownaction", "support_"]
        for chat in (USER, ADMIN):
            for data in buttons + [f"support_ticket_{ticket_id}", f"support_priority_{ticket_id}",
                                   f"support_assign_{ticket_id}", f"support_progress_{ticket_id}"]:
                SENT.clear()
                press(chat, data)
                self.assertTrue(self.texts(chat), f"no visible answer for {data!r} (chat {chat})")

    def test_support_errors_are_reported_to_the_user(self):
        with mock.patch.object(bot.auth_manager, "get_ticket", side_effect=sqlite3.OperationalError("locked")):
            press(USER, "support_ticket_1")
        self.assertIn("خطایی", self.texts(USER)[-1])


class PollingLoopTests(BotTestCase):
    def test_every_callback_is_answered_even_if_its_handler_fails(self):
        real = bot.handle_message

        def flaky(message, callback_data=None):
            if callback_data == "boom":
                raise RuntimeError("handler exploded")
            return real(message, callback_data)

        updates = [{"update_id": 1, "callback_query": {"id": "cbq-1", "from": {"id": USER}, "data": "boom",
                                                         "message": msg(USER, "x")}},
                   {"update_id": 2, "callback_query": {"id": "cbq-2", "from": {"id": USER}, "data": "support_new",
                                                         "message": msg(USER, "x")}}]
        with mock.patch.object(bot, "handle_message", flaky), \
                mock.patch.object(bot, "notify_admins_about_error") as alert:
            run_loop(updates)
        answered = [kw["json"]["callback_query_id"] for m, url, kw in NET if url.endswith("/answerCallbackQuery")]
        self.assertEqual(answered, ["cbq-1", "cbq-2"])
        self.assertTrue(any("خطایی رخ داد" in t for t in self.texts(USER)), "user was not told about the error")
        self.assertEqual(bot.user_states[USER]["state"], "support_new_category", "next update was not processed")
        alert.assert_called_once()

    def test_updates_are_logged_without_message_text(self):
        secret = "987654:SECRET-TOKEN-PASTED-BY-USER"
        run_loop([{"update_id": 10, "message": msg(ADMIN, secret)},
                  {"update_id": 11, "callback_query": {"id": "c", "from": {"id": ADMIN}, "data": "support_new",
                                                         "message": msg(ADMIN, "x")}}])
        log = (SANDBOX / "bot.log").read_text(encoding="utf-8")
        self.assertIn(f"message chat={ADMIN} text(len={len(secret)})", log)
        self.assertIn(f"callback chat={ADMIN} data='support_new'", log)
        self.assertNotIn("SECRET-TOKEN", log)


class GroupMediaFlowTests(BotTestCase):
    def start_upload(self, title, state="awaiting_media_file"):
        bot.user_states[ADMIN] = {"state": state, "title": title, "content_upload_media": True, "new_post": True}

    def groups(self):
        return [r for r in bot.get_user_db(ADMIN).get_media_contents() if r[1] == media_group.MEDIA_GROUP]

    def test_album_arriving_in_one_batch_is_one_library_item(self):
        self.start_upload("آلبوم یک")
        batch = [album_update(100 + i, ADMIN, "g-one", f"one-{i}") for i in range(3)]
        run_loop(batch, batch)  # second response = the re-read with no new items
        rows = [r for r in self.groups() if r[3] == "آلبوم یک"]
        self.assertEqual(len(rows), 1)
        self.assertEqual([i["file_id"] for i in media_group.decode_items(rows[0][2])], ["one-0", "one-1", "one-2"])
        self.assertEqual(sum("با 3 مورد ذخیره شد" in t for t in self.texts(ADMIN)), 1)
        self.assertNotIn(ADMIN, bot.user_states)

    def test_album_split_across_polls_and_late_item_join_the_same_group(self):
        self.start_upload("آلبوم دو")
        first = [album_update(200 + i, ADMIN, "g-two", f"two-{i}") for i in range(2)]
        more = first + [album_update(202, ADMIN, "g-two", "two-2", kind="video")]
        run_loop(first, more, more)
        row = [r for r in self.groups() if r[3] == "آلبوم دو"][0]
        self.assertEqual(len(media_group.decode_items(row[2])), 3)
        late = [album_update(300, ADMIN, "g-two", "two-3")]  # much later, state already cleared
        run_loop(late, late)
        row = [r for r in self.groups() if r[3] == "آلبوم دو"][0]
        self.assertEqual([i["file_id"] for i in media_group.decode_items(row[2])], ["two-0", "two-1", "two-2", "two-3"])
        self.assertTrue(any("مجموع 4" in t for t in self.texts(ADMIN)))
        self.assertEqual(len([r for r in self.groups() if r[3] == "آلبوم دو"]), 1)

    def test_single_photo_upload_is_unchanged(self):
        self.start_upload("عکس تکی")
        say_photo = msg(ADMIN, None, photo=[{"file_id": "small"}, {"file_id": "large"}])
        bot.handle_message(say_photo)
        rows = [r for r in bot.get_user_db(ADMIN).get_media_contents() if r[3] == "عکس تکی"]
        self.assertEqual([(r[1], r[2]) for r in rows], [("photo", "large")])
        self.assertIn("رسانه با عنوان 'عکس تکی' ذخیره شد", self.texts(ADMIN)[0])

    def test_group_row_in_media_list_and_album_preview(self):
        db = bot.get_user_db(ADMIN)
        gid = db.add_media_group([{"type": "photo", "file_id": "p1"}, {"type": "photo", "file_id": "p2"}], "نمایش")
        rows = bot.create_media_list_keyboard(ADMIN, db)["inline_keyboard"]
        self.assertIn("📸 نمایش · مدیا گروهی (2)", [row[0]["text"] for row in rows])
        press(ADMIN, f"view_media_{gid}")
        album = [kw["json"] for m, url, kw in NET if url.endswith("/sendMediaGroup")]
        self.assertEqual(len(album), 1)
        self.assertEqual(album[0]["chat_id"], ADMIN)
        self.assertEqual([m["media"] for m in album[0]["media"]], ["p1", "p2"])

    def submit(self, **fields):
        bot.user_states[ADMIN].update(selected_date="2026-12-01", selected_time="10:30",
                                      selected_messengers=["bale"], **fields)
        press(ADMIN, "submit_messenger_selection")
        return bot.get_user_db(ADMIN).get_scheduled_posts()[-1]

    def test_group_post_without_caption(self):
        db = bot.get_user_db(ADMIN)
        items = [{"type": "photo", "file_id": f"q{i}"} for i in range(4)]
        gid = db.add_media_group(items, "برای پست")
        press(ADMIN, "posting_new")
        self.assertIn("post_no_media", callbacks_in(SENT[-1]))
        press(ADMIN, f"select_media_{gid}")
        self.assertIn("post_no_caption", callbacks_in(SENT[-1]))
        self.assertEqual(bot.user_states[ADMIN]["media_type"], media_group.MEDIA_GROUP)
        press(ADMIN, "post_no_caption")
        self.assertEqual(bot.user_states[ADMIN]["state"], "awaiting_date")
        self.assertEqual(bot.user_states[ADMIN]["caption"], "")
        post = self.submit()
        self.assertEqual(post[2], media_group.MEDIA_GROUP)
        self.assertEqual(media_group.decode_items(post[1]), items)
        self.assertEqual(post[3], "")

    def test_text_only_post(self):
        press(ADMIN, "posting_new")
        press(ADMIN, "post_no_media")
        self.assertNotIn("post_no_caption", callbacks_in(SENT[-1]))
        press(ADMIN, "post_no_caption")  # a text-only post needs text: refused, state kept
        self.assertEqual(bot.user_states[ADMIN]["state"], "select_caption")
        press(ADMIN, "write_new_caption")
        say(ADMIN, "متن تنهای پست")
        self.assertEqual(bot.user_states[ADMIN]["state"], "awaiting_date")
        post = self.submit()
        self.assertEqual(post[1:4], ("", media_group.TEXT_ONLY, "متن تنهای پست"))

    def test_uploading_an_album_inside_the_post_flow(self):
        self.start_upload("آلبوم پست", state="awaiting_media_file_for_post")
        batch = [album_update(400 + i, ADMIN, "g-post", f"post-{i}") for i in range(2)]
        run_loop(batch, batch)
        state = bot.user_states[ADMIN]
        self.assertEqual(state["state"], "select_caption")
        self.assertEqual(state["media_type"], media_group.MEDIA_GROUP)
        self.assertEqual(len(media_group.decode_items(state["media_id"])), 2)
        self.assertIn("post_no_caption", callbacks_in(SENT[-1]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
