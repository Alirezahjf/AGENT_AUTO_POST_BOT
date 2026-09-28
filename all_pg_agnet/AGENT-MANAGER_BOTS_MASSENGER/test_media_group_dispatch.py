#!/usr/bin/env python3
"""Platform dispatch tests for group media / text-only / media-only posts.

No network (requests is faked), no real database, no config.json: everything runs from a
temporary working directory, so bot.log/errors.log of these imports never reach the bot dir.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_WORKDIR = tempfile.TemporaryDirectory(prefix="group-dispatch-test-")
os.chdir(_WORKDIR.name)

import group_posting  # noqa: E402
import media_group  # noqa: E402
import messenger_rubika  # noqa: E402
import messenger_whatsapp  # noqa: E402
import requests  # noqa: E402
import scheduler  # noqa: E402

RULE = group_posting.FOOTER_RULE
ITEMS = [{"type": "photo", "file_id": f"bale-file-{i}"} for i in range(1, 7)]
GROUP_PATH = media_group.encode_items(ITEMS)
CAPTION = "کپشن واحد گروه"
GLOBAL = {"messengers": {"bale": {"bot_token": "111:GLOBAL"}}}


def user_config(*platforms):
    all_cfg = {
        "bale": {"bot_token": "222:BALE", "channel_id": "@balechan"},
        "rubika": {"bot_token": "RUBIKA", "chat_id": "@rubichan"},
        "eitaa": {"bot_token": "EITAA", "chat_id": "eitaachan"},
        "telegram": {"bot_token": "333:TG", "chat_id": "@tgchan"},
        "whatsapp": {"chat_id": "120363000000000000@g.us", "provider": "neonize",
                     "service_url": "http://localhost:3001"},
    }
    cfg = {"messengers": {name: dict(all_cfg[name]) for name in platforms}}
    cfg["_bale_user_id"] = "7001"
    return cfg


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True, "result": True}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


class FakeNet:
    """Records every HTTP call; answers like a healthy API."""

    def __init__(self):
        self.calls = []

    def post(self, url, *args, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if "botapi.rubika.ir" in url:
            return FakeResponse({"status": "OK", "data": {"message_id": "m1"}})
        return FakeResponse({"ok": True, "result": {"message_id": 1}})

    def get(self, url, *args, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeResponse({"ok": True, "connected": True, "exists": True})

    def methods(self, host_part):
        return [url.rsplit("/", 1)[-1] for verb, url, _ in self.calls if verb == "POST" and host_part in url]

    def posts(self, host_part, method):
        return [kw for verb, url, kw in self.calls
                if verb == "POST" and host_part in url and url.endswith("/" + method)]


class DispatchTestCase(unittest.TestCase):
    def setUp(self):
        self.net = FakeNet()
        self.downloads = []
        patches = [
            mock.patch.object(requests, "post", self.net.post),
            mock.patch.object(requests, "get", self.net.get),
            mock.patch("time.sleep", lambda *_: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def download(self, file_id, token):
        self.downloads.append((file_id, token))
        return f"bytes-of-{file_id}".encode()

    def send(self, media_path, media_type, caption, platforms):
        return group_posting.send_to_platforms(
            42, media_path, media_type, caption, list(platforms), user_config(*platforms), GLOBAL,
            downloader=self.download, pause=lambda *_: None)


class GroupDispatchTests(DispatchTestCase):
    def test_telegram_one_album_call_caption_only_on_first_item(self):
        self.assertEqual(self.send(GROUP_PATH, "media_group", CAPTION, ["telegram"]), ["telegram"])
        calls = self.net.posts("api.telegram.org", "sendMediaGroup")
        self.assertEqual(len(calls), 1, self.net.methods("api.telegram.org"))
        media = json.loads(calls[0]["data"]["media"])
        self.assertEqual(len(media), 6)
        self.assertEqual(len(calls[0]["files"]), 6)
        self.assertEqual(media[0]["caption"], f"{CAPTION}\n\n{RULE}\n✈️ Telegram: @tgchan")
        self.assertTrue(all("caption" not in m for m in media[1:]))
        self.assertEqual([m["media"] for m in media], [f"attach://file{i}" for i in range(6)])

    def test_bale_one_album_call_with_file_ids_and_no_download(self):
        self.assertEqual(self.send(GROUP_PATH, "media_group", CAPTION, ["bale"]), ["bale"])
        calls = self.net.posts("tapi.bale.ai/bot222:BALE", "sendMediaGroup")
        self.assertEqual(len(calls), 1, self.net.methods("tapi.bale.ai"))
        body = calls[0]["json"]
        self.assertEqual(body["chat_id"], "@balechan")
        self.assertEqual([m["media"] for m in body["media"]], [it["file_id"] for it in ITEMS])
        self.assertEqual(body["media"][0]["caption"], f"{CAPTION}\n\n{RULE}\n🔹 Bale: @balechan")
        self.assertTrue(all("caption" not in m for m in body["media"][1:]))
        self.assertEqual(self.downloads, [], "Bale must reuse the stored file_ids")

    def test_eitaa_items_back_to_back_single_caption_on_last(self):
        self.assertEqual(self.send(GROUP_PATH, "media_group", CAPTION, ["eitaa"]), ["eitaa"])
        calls = self.net.posts("eitaayar.ir", "sendFile")
        self.assertEqual(len(calls), 6)
        captions = [c["data"].get("caption") for c in calls]
        self.assertEqual(captions[:5], [None] * 5)
        self.assertEqual(captions[5], f"{CAPTION}\n\n{RULE}\n🔹 Eitaa: @eitaachan")
        self.assertEqual([c["data"].get("disable_notification") for c in calls], ["1"] * 5 + [None])
        self.assertEqual(self.net.posts("eitaayar.ir", "sendMessage"), [])

    def test_whatsapp_items_back_to_back_caption_on_first(self):
        with mock.patch.object(messenger_whatsapp, "check_connection_status",
                               return_value={"connected": True, "exists": True}):
            self.assertEqual(self.send(GROUP_PATH, "media_group", CAPTION, ["whatsapp"]), ["whatsapp"])
        calls = self.net.posts("localhost:3001", "send")
        self.assertEqual(len(calls), 6)
        texts = [c["json"]["text"] for c in calls]
        self.assertEqual(texts, [CAPTION] + [""] * 5)  # no footer on WhatsApp, like the legacy path
        self.assertTrue(all(c["json"].get("imageBase64") for c in calls))
        self.assertEqual({c["json"]["userId"] for c in calls}, {"7001"})

    def test_rubika_one_by_one_every_item_with_the_same_caption(self):
        uploads = []
        with mock.patch.object(messenger_rubika, "_upload_file_from_bytes",
                               side_effect=lambda data, token, kind: uploads.append(data) or f"rf-{len(uploads)}"):
            self.assertEqual(self.send(GROUP_PATH, "media_group", CAPTION, ["rubika"]), ["rubika"])
        calls = self.net.posts("botapi.rubika.ir", "sendFile")
        self.assertEqual(len(calls), 6)
        expected = f"{CAPTION}\n\n{RULE}\n🔹 Rubika: @rubichan"
        self.assertEqual([c["json"]["text"] for c in calls], [expected] * 6)
        self.assertEqual([c["json"]["file_id"] for c in calls], [f"rf-{i}" for i in range(1, 7)])
        self.assertEqual(len(uploads), 6)

    def test_all_platforms_download_each_item_once(self):
        with mock.patch.object(messenger_whatsapp, "check_connection_status", return_value={"connected": True}), \
                mock.patch.object(messenger_rubika, "_upload_file_from_bytes", return_value="rf"):
            sent = self.send(GROUP_PATH, "media_group", CAPTION, group_posting.PLATFORM_ORDER)
        self.assertEqual(sent, list(group_posting.PLATFORM_ORDER))
        self.assertEqual(sorted(f for f, _ in self.downloads), sorted(it["file_id"] for it in ITEMS))
        self.assertEqual({t for _, t in self.downloads}, {"111:GLOBAL"})

    def test_long_caption_is_sent_after_the_album_not_truncated(self):
        long_caption = "ا" * 1500
        self.send(GROUP_PATH, "media_group", long_caption, ["telegram"])
        media = json.loads(self.net.posts("api.telegram.org", "sendMediaGroup")[0]["data"]["media"])
        self.assertTrue(all("caption" not in m for m in media))
        texts = [c["json"]["text"] for c in self.net.posts("api.telegram.org", "sendMessage")]
        self.assertEqual("".join(texts), f"{long_caption}\n\n{RULE}\n✈️ Telegram: @tgchan")

    def test_album_with_more_than_ten_items_is_split(self):
        items = [{"type": "photo", "file_id": f"f{i}"} for i in range(11)]
        self.send(media_group.encode_items(items), "media_group", CAPTION, ["bale"])
        self.assertEqual(len(self.net.posts("tapi.bale.ai", "sendMediaGroup")), 1)
        self.assertEqual(len(self.net.posts("tapi.bale.ai", "sendPhoto")), 1)


class TextAndCaptionOptionTests(DispatchTestCase):
    def test_text_only_goes_to_every_platform_as_text(self):
        with mock.patch.object(messenger_whatsapp, "check_connection_status", return_value={"connected": True}):
            sent = self.send("", media_group.TEXT_ONLY, "فقط متن", group_posting.PLATFORM_ORDER)
        self.assertEqual(sent, list(group_posting.PLATFORM_ORDER))
        self.assertEqual(self.downloads, [])
        self.assertEqual(self.net.posts("tapi.bale.ai", "sendMessage")[0]["json"]["text"],
                         f"فقط متن\n\n{RULE}\n🔹 Bale: @balechan")
        self.assertEqual(len(self.net.posts("botapi.rubika.ir", "sendMessage")), 1)
        self.assertEqual(len(self.net.posts("eitaayar.ir", "sendMessage")), 1)
        self.assertEqual(len(self.net.posts("api.telegram.org", "sendMessage")), 1)
        self.assertEqual(self.net.posts("localhost:3001", "send")[0]["json"]["text"], "فقط متن")

    def test_no_caption_single_photo_has_no_caption_and_no_footer(self):
        with mock.patch.object(messenger_whatsapp, "check_connection_status", return_value={"connected": True}), \
                mock.patch.object(messenger_rubika, "_upload_file_from_bytes", return_value="rf"):
            sent = self.send("bale-photo", "photo", "", group_posting.PLATFORM_ORDER)
        self.assertEqual(sent, list(group_posting.PLATFORM_ORDER))
        bale = self.net.posts("tapi.bale.ai", "sendPhoto")[0]["json"]
        self.assertEqual(bale, {"chat_id": "@balechan", "photo": "bale-photo"})
        self.assertNotIn("caption", self.net.posts("api.telegram.org", "sendPhoto")[0]["data"])
        self.assertNotIn("caption", self.net.posts("eitaayar.ir", "sendFile")[0]["data"])
        self.assertEqual(self.net.posts("botapi.rubika.ir", "sendFile")[0]["json"]["text"], "")
        self.assertEqual(self.net.posts("localhost:3001", "send")[0]["json"]["text"], "")
        every_text = json.dumps([c[2] for c in self.net.calls], default=str, ensure_ascii=False)
        self.assertNotIn("Manual Post", every_text)
        self.assertNotIn(RULE, every_text)

    def test_handles_only_new_post_kinds(self):
        self.assertTrue(group_posting.handles("media_group", "x"))
        self.assertTrue(group_posting.handles("text", "x"))
        self.assertTrue(group_posting.handles("photo", ""))
        self.assertTrue(group_posting.handles("video", "   "))
        self.assertFalse(group_posting.handles("photo", "caption"))
        self.assertFalse(group_posting.handles("video", "caption"))
        self.assertFalse(group_posting.handles("document", ""))
        self.assertFalse(group_posting.handles("photo", "", "https://example.com/a.jpg"))
        self.assertTrue(group_posting.handles("photo", "", "AgADbalefileid"))


class SchedulerRoutingTests(DispatchTestCase):
    def test_single_photo_with_caption_keeps_the_legacy_path(self):
        with mock.patch.object(group_posting, "send_to_platforms", side_effect=AssertionError("must not be used")):
            sent = scheduler._send_to_platforms(
                7, "bale-photo", "photo", "Hello", None, ["bale"], user_config("bale"), GLOBAL)
        self.assertEqual(sent, ["bale"])
        body = self.net.posts("tapi.bale.ai/bot222:BALE", "sendPhoto")[0]["json"]
        self.assertEqual(body, {"chat_id": "@balechan", "photo": "bale-photo",
                                "caption": f"Hello\n\n{RULE}\n🔹 Bale: @balechan"})

    def test_group_post_routes_to_group_engine(self):
        with mock.patch.object(group_posting, "send_to_platforms", return_value=["bale"]) as engine:
            sent = scheduler._send_to_platforms(
                8, GROUP_PATH, "media_group", CAPTION, None, ["bale"], user_config("bale"), GLOBAL)
        self.assertEqual(sent, ["bale"])
        args, kwargs = engine.call_args
        self.assertEqual(args[:4], (8, GROUP_PATH, "media_group", CAPTION))
        self.assertIs(kwargs["downloader"], scheduler.download_bale_file)

    def test_scheduled_group_post_is_not_predownloaded_as_one_file(self):
        now = scheduler.TEHRAN_TZ.localize(datetime(2026, 10, 1, 12, 0, 30))
        post = (99, GROUP_PATH, "media_group", CAPTION, "", "2026-10-01", "12:00", "manual", "bale")

        class FakeDB:
            posted, failed = [], []

            def get_scheduled_posts(self):
                return [post]

            def mark_post_as_posted(self, post_id):
                self.posted.append(post_id)

            def mark_post_as_failed(self, post_id):
                self.failed.append(post_id)

        fake_db = FakeDB()
        with mock.patch.object(scheduler, "get_user_db", return_value=fake_db), \
                mock.patch.object(scheduler, "load_user_config", return_value=user_config("bale")), \
                mock.patch.object(scheduler, "tehran_now", return_value=now), \
                mock.patch.object(scheduler, "tehran_today", return_value=now.date()), \
                mock.patch.object(scheduler, "download_bale_file", side_effect=AssertionError("no pre-download")), \
                mock.patch.object(scheduler, "notify_post_success"), \
                mock.patch.object(group_posting, "send_to_platforms", return_value=["bale"]) as engine:
            scheduler._executed_posts.clear()
            scheduler.post_scheduled_posts_for_user(7001, GLOBAL)
        engine.assert_called_once()
        self.assertEqual(fake_db.posted, [99])
        self.assertEqual(fake_db.failed, [])


class HelperTests(unittest.TestCase):
    def test_items_round_trip_and_invalid_input(self):
        self.assertEqual(media_group.decode_items(media_group.encode_items(ITEMS)), ITEMS)
        self.assertEqual(media_group.decode_items("not json"), [])
        self.assertEqual(media_group.decode_items('[{"type": "doc", "file_id": "x"}]'), [])

    def test_album_items_from_folded_message(self):
        msgs = [{"media_group_id": "g", "chat": {"id": 1}, "photo": [{"file_id": "s"}, {"file_id": f"big{i}"}]}
                for i in range(3)]
        msgs.append({"media_group_id": "g", "chat": {"id": 1}, "video": {"file_id": "vid"}})
        first = dict(msgs[0], _media_group=msgs)
        self.assertEqual(media_group.album_items_from_message(first),
                         [{"type": "photo", "file_id": "big0"}, {"type": "photo", "file_id": "big1"},
                          {"type": "photo", "file_id": "big2"}, {"type": "video", "file_id": "vid"}])
        self.assertIsNone(media_group.album_items_from_message({"photo": [{"file_id": "x"}]}))

    def test_collect_album_only_same_chat_and_group(self):
        def upd(uid, chat, group):
            return {"update_id": uid, "message": {"chat": {"id": chat}, "media_group_id": group,
                                                  "photo": [{"file_id": f"p{uid}"}]}}
        batch = [upd(1, 5, "a"), {"update_id": 2, "message": {"chat": {"id": 5}, "text": "hi"}},
                 upd(3, 6, "a"), upd(4, 5, "a"), upd(5, 5, "b")]
        messages, later = media_group.collect_album(batch, 0)
        self.assertEqual([m["photo"][0]["file_id"] for m in messages], ["p1", "p4"])
        self.assertEqual(later, {4})

    def test_labels_keep_legacy_strings(self):
        self.assertEqual(media_group.library_button_text(3, "photo", "x", "t"), "🖼️ t")
        self.assertEqual(media_group.library_button_text(3, "video", "x", None), "🎥 ID:3")
        self.assertEqual(media_group.type_label("photo"), "📸 عکس")
        self.assertEqual(media_group.type_label("video", "", "en"), "🎥 Video")
        self.assertEqual(media_group.post_icon("photo"), "📸")
        self.assertEqual(media_group.post_icon("video"), "🎥")
        self.assertEqual(media_group.type_label("media_group", GROUP_PATH), "🗂️ مدیا گروهی (6)")

    def test_registry_expires(self):
        clock = [0.0]
        reg = media_group.AlbumRegistry(ttl_seconds=10, clock=lambda: clock[0])
        reg.remember(1, "g", 55, "t")
        self.assertEqual(reg.lookup(1, "g")["content_id"], 55)
        self.assertIsNone(reg.lookup(2, "g"))
        clock[0] = 11
        self.assertIsNone(reg.lookup(1, "g"))

    def test_error_text_never_contains_tokens(self):
        err = requests.exceptions.ConnectionError(
            "Max retries exceeded with url: /bot123456:SECRETtoken/sendMediaGroup")
        self.assertNotIn("SECRETtoken", group_posting.safe_error(err))
        self.assertNotIn("TOK", group_posting.redact("https://eitaayar.ir/api/TOK/sendFile https://botapi.rubika.ir/v3/TOK/x"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
