"""Posting engine for the new post kinds; the legacy single-media path is not touched.

Handled here (see ``handles``):
  * group media ("مدیا گروهی")   media_type "media_group", media_path = JSON item list
  * text only   ("بدون مدیا")    media_type "text", empty media_path
  * media only  ("بدون کپشن")    media_type photo/video with an empty caption

A group has ONE caption. Per platform:
  * Telegram  sendMediaGroup (true album). The Bot API has no separate album caption; a
              caption set on the FIRST item only is what Telegram clients render under the
              album, i.e. exactly what a manually sent album looks like.
  * Bale      sendMediaGroup (true album, Telegram-compatible API) with the stored Bale
              file_ids; multipart upload as fallback. Caption on the first item.
  * Eitaa     the eitaayar API only has sendMessage / sendFile (one file per call), so a
              real album is impossible: items go back-to-back, the caption on the LAST one
              so it sits under the whole series, and only that last one notifies.
  * WhatsApp  the neonize service (:3001) has only single-item /send. Items go
              back-to-back with the caption on the FIRST one: WhatsApp clients group
              consecutive images into an album and show the first image's caption on it.
  * Rubika    one by one, EACH item with the same caption (explicit requirement).
Captions longer than a platform's media-caption limit are sent as a text message right
after the album instead of being truncated.
"""
import json
import re
import time

import requests

from logger import logger
import media_group
import messenger_eitaa
import messenger_rubika
import messenger_telegram
import messenger_whatsapp

PLATFORM_ORDER = ("bale", "rubika", "eitaa", "telegram", "whatsapp")  # same order as the legacy path
FOOTER_RULE = "━━━━━━━━━━━━━━━━"
MEDIA_CAPTION_LIMIT = 1024   # Telegram and Bale media captions
TEXT_LIMIT = 4096
BALE_API = "https://tapi.bale.ai/bot{token}"
TELEGRAM_API = "https://api.telegram.org/bot{token}"
EITAA_API = "https://eitaayar.ir/api/{token}"
RUBIKA_API = "https://botapi.rubika.ir/v3/{token}"

# Bale/Telegram "/bot<id>:<secret>", Eitaa "/api/<token>", Rubika "/v3/<token>"
_SECRET_IN_URL = re.compile(r"(/bot)\d+:[^/\s'\"]+|(/api/|/v3/)[^/\s'\"]+")


def redact(text):
    """Remove bot tokens from URLs inside any text (requests puts full URLs in errors)."""
    return _SECRET_IN_URL.sub(lambda m: (m.group(1) or m.group(2)) + "<redacted>", str(text))


def safe_error(exc):
    """Short exception text without tokens."""
    return redact(f"{type(exc).__name__}: {exc}")[:300]


def handles(media_type, caption, media_path=""):
    """True for posts that need this module; everything else keeps the legacy path.

    A single photo/video counts as «بدون کپشن» only with an empty caption and a Bale
    file_id (URL / local-path media, never produced by the manual flow, stay legacy).
    """
    if media_type in (media_group.MEDIA_GROUP, media_group.TEXT_ONLY):
        return True
    if media_type not in media_group.SINGLE_TYPES or (caption or "").strip():
        return False
    return not str(media_path or "").startswith(("http://", "https://", "/"))


def post_items(media_path, media_type):
    if media_type == media_group.MEDIA_GROUP:
        return media_group.decode_items(media_path)
    if media_type in media_group.SINGLE_TYPES and media_path:
        return [{"type": media_type, "file_id": media_path}]
    return []


def with_footer(text, footer_line):
    """Same signature line as the legacy path; an empty caption stays empty (no footer)."""
    if not (text or "").strip():
        return ""
    return f"{text}\n\n{FOOTER_RULE}\n{footer_line}"


def _chunks(seq, size):
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def _file_part(item, index, data):
    if item["type"] == "video":
        return f"video{index}.mp4", data, "video/mp4"
    return f"photo{index}.jpg", data, "image/jpeg"


class MediaFetcher:
    """Downloads every item at most once per post (only platforms that upload need bytes)."""

    def __init__(self, bale_token, downloader):
        self._token = bale_token
        self._downloader = downloader
        self._cache = {}

    def get(self, item):
        key = item["file_id"]
        if key not in self._cache:
            data = None
            if self._downloader and self._token:
                try:
                    data = self._downloader(key, self._token)
                except Exception as exc:
                    logger.error(f"❌ media download failed: {safe_error(exc)}")
            self._cache[key] = data
        return self._cache[key]

    def pairs(self, items, platform, post_id):
        pairs = [(item, self.get(item)) for item in items]
        ready = [(item, data) for item, data in pairs if data]
        if len(ready) < len(items):
            logger.error(f"❌ {platform}: {len(items) - len(ready)}/{len(items)} media of post "
                         f"#{post_id} could not be downloaded from Bale")
        return ready


# ---------------------------------------------------------------- HTTP helpers

def _api_call(api, method, json_data=None, data=None, files=None, timeout=60):
    """One POST; returns (ok, http_status, description). Never raises."""
    try:
        if files:
            resp = requests.post(f"{api}/{method}", data=data, files=files, timeout=timeout)
        elif json_data is not None:
            resp = requests.post(f"{api}/{method}", json=json_data, timeout=timeout)
        else:
            resp = requests.post(f"{api}/{method}", data=data, timeout=timeout)
        try:
            body = resp.json()
        except ValueError:
            body = {}
        ok = resp.status_code == 200 and bool(body.get("ok"))
        description = "" if ok else str(body.get("description") or resp.text[:200])
        return ok, resp.status_code, description
    except Exception as exc:
        return False, None, safe_error(exc)


def _telegram_call(api, method, **kwargs):
    """Telegram call honouring one rate-limit/5xx retry (like the legacy helper)."""
    ok, status, description = _api_call(api, method, **kwargs)
    if not ok and (status == 429 or (status or 0) >= 500):
        time.sleep(3)
        ok, status, description = _api_call(api, method, **kwargs)
    return ok, status, description


def _send_text_chunks(call, api, chat_id, text, extra=None):
    ok_all = True
    for chunk in _chunks(text, TEXT_LIMIT):
        payload = {"chat_id": chat_id, "text": chunk}
        payload.update(extra or {})
        ok, _, description = call(api, "sendMessage", json_data=payload)
        if not ok and extra:
            ok, _, description = call(api, "sendMessage", json_data={"chat_id": chat_id, "text": chunk})
        if not ok:
            logger.error(f"❌ sendMessage failed: {description}")
            ok_all = False
    return ok_all


# ---------------------------------------------------------------- Bale

def bale_send_album(token, chat_id, items, caption, fetcher=None):
    """Send 1..N items to a Bale chat as an album (file_ids first, upload as fallback).

    Also used for the in-bot preview of a group. Returns True when every part was sent.
    """
    api = BALE_API.format(token=token)
    album_caption = caption if len(caption) <= MEDIA_CAPTION_LIMIT else ""
    chunks = _chunks(items, media_group.ALBUM_MAX_ITEMS)
    for index, chunk in enumerate(chunks):
        chunk_caption = album_caption if index == 0 else ""
        if len(chunk) == 1:
            item = chunk[0]
            payload = {"chat_id": chat_id, item["type"]: item["file_id"]}
            if chunk_caption:
                payload["caption"] = chunk_caption
            method = "sendPhoto" if item["type"] == "photo" else "sendVideo"
            ok, _, description = _api_call(api, method, json_data=payload, timeout=30)
            if not ok and fetcher:
                data = fetcher.get(item)
                if data:
                    form = {"chat_id": chat_id}
                    if chunk_caption:
                        form["caption"] = chunk_caption
                    name, blob, mime = _file_part(item, 0, data)
                    ok, _, description = _api_call(api, method, data=form,
                                                   files={item["type"]: (name, blob, mime)})
        else:
            media = [{"type": item["type"], "media": item["file_id"]} for item in chunk]
            if chunk_caption:
                media[0]["caption"] = chunk_caption
            ok, _, description = _api_call(api, "sendMediaGroup",
                                           json_data={"chat_id": chat_id, "media": media}, timeout=60)
            if not ok and fetcher:
                files, media_up = {}, []
                for i, item in enumerate(chunk):
                    data = fetcher.get(item)
                    if not data:
                        continue
                    files[f"file{i}"] = _file_part(item, i, data)
                    media_up.append({"type": item["type"], "media": f"attach://file{i}"})
                if len(media_up) >= 2:
                    if chunk_caption:
                        media_up[0]["caption"] = chunk_caption
                    ok, _, description = _api_call(
                        api, "sendMediaGroup", files=files,
                        data={"chat_id": chat_id, "media": json.dumps(media_up, ensure_ascii=False)})
        if not ok:
            logger.error(f"❌ Bale album part {index + 1}/{len(chunks)} failed: {description}")
            return False
    if caption and not album_caption:
        return _send_text_chunks(_api_call, api, chat_id, caption)
    return True


def _send_bale(post_id, items, text, user_config, global_config, fetcher):
    cfg = user_config.get("messengers", {}).get("bale", {})
    token = cfg.get("bot_token") or global_config["messengers"]["bale"]["bot_token"]
    channel_id = cfg.get("channel_id")
    if not (token and channel_id):
        logger.warning(f"⚠️ Bale not fully configured for post #{post_id}")
        return False
    caption = with_footer(text, f"🔹 Bale: @{channel_id.replace('@', '')}")
    if not items:
        return bool(caption) and _send_text_chunks(_api_call, BALE_API.format(token=token), channel_id, caption)
    return bale_send_album(token, channel_id, items, caption, fetcher)


# ---------------------------------------------------------------- Telegram

def _send_telegram(post_id, items, text, user_config, global_config, fetcher):
    cfg = user_config.get("messengers", {}).get("telegram", {})
    if not (cfg.get("bot_token") and cfg.get("chat_id")):
        logger.warning(f"⚠️ Telegram not fully configured for post #{post_id}")
        return False
    chat = cfg["chat_id"]
    shown = chat if chat.startswith(("-", "@")) else f"@{chat}"
    caption = with_footer(text, f"✈️ Telegram: {shown}")
    if not items:
        return bool(caption) and messenger_telegram.send_manual_post(caption, None, media_group.TEXT_ONLY, user_config)

    ready = fetcher.pairs(items, "Telegram", post_id)
    if not ready:
        return False
    api = TELEGRAM_API.format(token=cfg["bot_token"])
    album_caption = caption if len(caption) <= MEDIA_CAPTION_LIMIT else ""
    chunks = _chunks(ready, media_group.ALBUM_MAX_ITEMS)
    for index, chunk in enumerate(chunks):
        chunk_caption = album_caption if index == 0 else ""
        if len(chunk) == 1:
            item, data = chunk[0]
            method = "sendPhoto" if item["type"] == "photo" else "sendVideo"
            name, blob, mime = _file_part(item, 0, data)
            form = {"chat_id": chat}
            if chunk_caption:
                form.update({"caption": chunk_caption, "parse_mode": "Markdown"})
            ok, _, description = _telegram_call(api, method, data=form, files={item["type"]: (name, blob, mime)})
            if not ok and chunk_caption:  # e.g. unbalanced Markdown: keep the media, drop formatting
                form.pop("parse_mode", None)
                ok, _, description = _telegram_call(api, method, data=form, files={item["type"]: (name, blob, mime)})
        else:
            files, media = {}, []
            for i, (item, data) in enumerate(chunk):
                files[f"file{i}"] = _file_part(item, i, data)
                media.append({"type": item["type"], "media": f"attach://file{i}"})
            if chunk_caption:
                media[0].update({"caption": chunk_caption, "parse_mode": "Markdown"})
            ok, _, description = _telegram_call(
                api, "sendMediaGroup", files=files,
                data={"chat_id": chat, "media": json.dumps(media, ensure_ascii=False)})
            if not ok and chunk_caption:
                media[0].pop("parse_mode", None)
                ok, _, description = _telegram_call(
                    api, "sendMediaGroup", files=files,
                    data={"chat_id": chat, "media": json.dumps(media, ensure_ascii=False)})
        if not ok:
            logger.error(f"❌ Telegram album part {index + 1}/{len(chunks)} of post #{post_id} failed: {description}")
            return False
    if caption and not album_caption:
        return _send_text_chunks(_telegram_call, api, chat, caption, {"parse_mode": "Markdown"})
    return True


# ---------------------------------------------------------------- Eitaa

def _send_eitaa(post_id, items, text, user_config, global_config, fetcher):
    cfg = user_config.get("messengers", {}).get("eitaa", {})
    if not (cfg.get("bot_token") and cfg.get("chat_id")):
        logger.warning(f"⚠️ Eitaa not fully configured for post #{post_id}")
        return False
    chat = cfg["chat_id"]
    caption = with_footer(text, f"🔹 Eitaa: @{chat.replace('@', '')}")
    if not items:
        return bool(caption) and messenger_eitaa.send_manual_post(caption, None, media_group.TEXT_ONLY, user_config)

    ready = fetcher.pairs(items, "Eitaa", post_id)
    if not ready:
        return False
    base = EITAA_API.format(token=cfg["bot_token"])
    sent, caption_sent = 0, not caption
    for index, (item, data) in enumerate(ready):
        last = index == len(ready) - 1
        form = {"chat_id": chat}
        if last and caption:
            form["caption"] = caption
        if not last:
            form["disable_notification"] = "1"  # one notification per series, like an album
        if messenger_eitaa._send_with_retry(f"{base}/sendFile", form, {"file": _file_part(item, index, data)}):
            sent += 1
            caption_sent = caption_sent or bool(form.get("caption"))
        else:
            logger.error(f"❌ Eitaa: item {index + 1}/{len(ready)} of post #{post_id} failed")
    if sent and not caption_sent:  # the captioned item failed: do not lose the text
        messenger_eitaa._send_with_retry(f"{base}/sendMessage", {"chat_id": chat, "text": caption})
    if 0 < sent < len(items):
        logger.error(f"❌ Eitaa: only {sent}/{len(items)} items of post #{post_id} were sent")
    return sent > 0


# ---------------------------------------------------------------- Rubika

def _send_rubika(post_id, items, text, user_config, global_config, fetcher):
    cfg = user_config.get("messengers", {}).get("rubika", {})
    if not (cfg.get("bot_token") and cfg.get("chat_id")):
        logger.warning(f"⚠️ Rubika not fully configured for post #{post_id}")
        return False
    chat = cfg["chat_id"]
    caption = with_footer(text, f"🔹 Rubika: @{chat.replace('@', '')}")
    if not items:
        return bool(caption) and messenger_rubika.send_manual_post(caption, None, media_group.TEXT_ONLY, user_config)

    ready = fetcher.pairs(items, "Rubika", post_id)
    base = RUBIKA_API.format(token=cfg["bot_token"])
    sent = 0
    for index, (item, data) in enumerate(ready):
        if index:
            time.sleep(0.5)
        file_id = messenger_rubika._upload_file_from_bytes(data, cfg["bot_token"], item["type"])
        payload = {"chat_id": chat, "file_id": file_id, "text": caption}  # same caption on EVERY item
        if file_id and messenger_rubika._send_with_retry(f"{base}/sendFile", payload):
            sent += 1
        else:
            logger.error(f"❌ Rubika: item {index + 1}/{len(ready)} of post #{post_id} failed")
    if 0 < sent < len(items):
        logger.error(f"❌ Rubika: only {sent}/{len(items)} items of post #{post_id} were sent")
    return sent > 0


# ---------------------------------------------------------------- WhatsApp

def _send_whatsapp(post_id, items, text, user_config, global_config, fetcher):
    cfg = user_config.get("messengers", {}).get("whatsapp", {})
    to = cfg.get("chat_id")
    if not to:
        logger.warning(f"⚠️ WhatsApp not fully configured for post #{post_id}")
        return False
    if not items:
        return bool(text.strip()) and messenger_whatsapp.send_manual_post(text, None, media_group.TEXT_ONLY, user_config)

    provider = cfg.get("provider", "neonize")
    if provider == "cloud":  # same limitation as the legacy path: no media upload there
        logger.warning(f"⚠️ WhatsApp Cloud API: media not supported, post #{post_id} sent as text only")
        return bool(text.strip()) and messenger_whatsapp._send_via_cloud_api(to, text, None, user_config)

    service_url = cfg.get("service_url", messenger_whatsapp.DEFAULT_SERVICE_URL)
    user_id = messenger_whatsapp._get_user_id_from_config(user_config)
    if provider in ("baileys", "neonize") and user_id:
        status = messenger_whatsapp.check_connection_status(user_id, service_url) or {}
        if not status.get("connected") and status.get("exists") is False:
            logger.error(f"❌ WhatsApp session {user_id} does not exist - needs QR reconnect")
            return False

    ready = fetcher.pairs(items, "WhatsApp", post_id)
    sent = 0
    for index, (item, data) in enumerate(ready):
        item_caption = text if index == 0 else ""  # first image's caption = album caption
        if messenger_whatsapp._send_via_neonize(to, item_caption, data, service_url, user_id, item["type"]):
            sent += 1
        else:
            logger.error(f"❌ WhatsApp: item {index + 1}/{len(ready)} of post #{post_id} failed")
    if 0 < sent < len(items):
        logger.error(f"❌ WhatsApp: only {sent}/{len(items)} items of post #{post_id} were sent")
    return sent > 0


SENDERS = {
    "bale": _send_bale,
    "rubika": _send_rubika,
    "eitaa": _send_eitaa,
    "telegram": _send_telegram,
    "whatsapp": _send_whatsapp,
}


def send_to_platforms(post_id, media_path, media_type, caption, selected_messengers,
                      user_config, global_config, downloader=None, pause=time.sleep):
    """Send one post to the selected platforms; returns the platforms that succeeded."""
    items = post_items(media_path, media_type)
    text = caption or ""
    if media_type != media_group.TEXT_ONLY and not items:
        logger.error(f"❌ Post #{post_id}: no valid media items in the stored group")
        return []
    if media_type == media_group.TEXT_ONLY and not text.strip():
        logger.error(f"❌ Post #{post_id}: text-only post without text")
        return []
    bale_token = (global_config.get("messengers", {}).get("bale", {}) or {}).get("bot_token")
    fetcher = MediaFetcher(bale_token, downloader)
    platforms_sent = []
    for platform in PLATFORM_ORDER:
        if platform not in selected_messengers:
            continue
        try:
            ok = SENDERS[platform](post_id, items, text, user_config, global_config, fetcher)
        except Exception as exc:
            logger.error(f"❌ {platform} exception for post #{post_id}: {safe_error(exc)}")
            ok = False
        if ok:
            platforms_sent.append(platform)
            logger.info(f"✅ {platform}: post #{post_id} sent ({media_type}, {max(len(items), 1)} part(s))")
        else:
            logger.error(f"❌ {platform}: post #{post_id} failed ({media_type})")
        pause(1)
    return platforms_sent
