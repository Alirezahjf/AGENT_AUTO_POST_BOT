"""Group media ("مدیا گروهی") helpers: pure functions, no network, no database.

Storage (no schema change at all):
  * A group is ONE row of the existing ``content_media`` table with
    ``media_type = "media_group"`` and ``file_id`` holding a JSON list of the album
    items in upload order, e.g. ``[{"type": "photo", "file_id": "..."}, ...]``.
  * A scheduled post copies that JSON into ``scheduled_posts.media_path``, exactly like a
    single media copies its Bale file_id, so drafts / archive / history / restore keep
    working unchanged.
  * A text-only post ("بدون مدیا") uses ``media_type = "text"`` and an empty media_path.

Rows with media_type "photo" / "video" are never touched or reinterpreted here.
"""
import json
import threading
import time

MEDIA_GROUP = "media_group"
TEXT_ONLY = "text"
SINGLE_TYPES = ("photo", "video")
ALBUM_MAX_ITEMS = 10  # Telegram / Bale accept 2..10 items per sendMediaGroup call

# States in which the bot is waiting for an upload; only there are album items folded.
ALBUM_UPLOAD_STATES = ("awaiting_media_file", "awaiting_media_file_for_post")


# ---------------------------------------------------------------- items / JSON

def encode_items(items):
    """Serialize album items (list of {"type", "file_id"}) for the DB."""
    clean = [{"type": it["type"], "file_id": it["file_id"]}
             for it in items if it.get("type") in SINGLE_TYPES and it.get("file_id")]
    return json.dumps(clean, ensure_ascii=False, separators=(",", ":"))


def decode_items(value):
    """Parse the JSON written by encode_items; anything invalid yields []."""
    if isinstance(value, list):
        raw = value
    else:
        try:
            raw = json.loads(value or "[]")
        except (TypeError, ValueError):
            return []
    if not isinstance(raw, list):
        return []
    return [{"type": it["type"], "file_id": it["file_id"]}
            for it in raw
            if isinstance(it, dict) and it.get("type") in SINGLE_TYPES and it.get("file_id")]


def item_from_message(message):
    """One album item from a Bale message (largest photo size / the video), else None."""
    if not isinstance(message, dict):
        return None
    photos = message.get("photo")
    if isinstance(photos, list) and photos and photos[-1].get("file_id"):
        return {"type": "photo", "file_id": photos[-1]["file_id"]}
    video = message.get("video")
    if isinstance(video, dict) and video.get("file_id"):
        return {"type": "video", "file_id": video["file_id"]}
    return None


def items_from_messages(messages):
    return [item for item in (item_from_message(m) for m in messages or []) if item]


def album_items_from_message(message):
    """Items of an album upload, or None when the message is not part of an album.

    The polling loop attaches every message of one album to the first one as
    ``_media_group``; a lone album message (rest not arrived yet) is used as-is.
    """
    if not isinstance(message, dict) or not message.get("media_group_id"):
        return None
    return items_from_messages(message.get("_media_group") or [message])


def group_count(value):
    return len(decode_items(value))


# ---------------------------------------------------------------- labels

def library_button_text(content_id, media_type, file_id, title, lang="fa"):
    """Row text in the media library. Photo/video rows are byte-identical to the old ones."""
    display_title = title if title else f"ID:{content_id}"
    if media_type == MEDIA_GROUP:
        kind = "مدیا گروهی" if lang == "fa" else "Group media"
        return f"📸 {display_title} · {kind} ({group_count(file_id)})"
    icon = "🖼️" if media_type == "photo" else "🎥"
    return f"{icon} {display_title}"


def post_icon(media_type):
    """Compact icon for post lists (drafts / archive). Photo/video unchanged."""
    if media_type == "photo":
        return "📸"
    if media_type == MEDIA_GROUP:
        return "🗂️"
    if media_type == TEXT_ONLY:
        return "📝"
    return "🎥"


def type_label(media_type, media_path="", lang="fa"):
    """Post type label. Photo/video return exactly the strings used before."""
    fa = lang == "fa"
    if media_type == "photo":
        return "📸 عکس" if fa else "📸 Photo"
    if media_type == MEDIA_GROUP:
        n = group_count(media_path)
        return f"🗂️ مدیا گروهی ({n})" if fa else f"🗂️ Group media ({n})"
    if media_type == TEXT_ONLY:
        return "📝 فقط متن" if fa else "📝 Text only"
    return "🎥 ویدیو" if fa else "🎥 Video"


# ---------------------------------------------------------------- polling-loop folding

def album_key(message):
    if not isinstance(message, dict) or not message.get("media_group_id"):
        return None
    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is None:
        return None
    return chat_id, str(message["media_group_id"])


def collect_album(updates, index):
    """Messages of the album whose first item is ``updates[index]`` (arrival order) and the
    update ids of its later items in the same getUpdates batch, which the caller skips.

    The caller decides eligibility at processing time, so a title typed just before the
    album in the same batch still puts the user into the upload state first.
    """
    first = updates[index].get("message") if isinstance(updates[index], dict) else None
    key = album_key(first)
    messages, later_ids = [first], set()
    if key is None:
        return messages, later_ids
    for update in updates[index + 1:]:
        message = update.get("message") if isinstance(update, dict) else None
        if album_key(message) == key:
            messages.append(message)
            later_ids.add(update["update_id"])
    return messages, later_ids


def count_album_items(updates, is_eligible):
    total = 0
    for update in updates or []:
        message = update.get("message") if isinstance(update, dict) else None
        if album_key(message) is not None and is_eligible(message):
            total += 1
    return total


class AlbumRegistry:
    """Remembers recently saved albums so items that arrive late join the same group."""

    def __init__(self, ttl_seconds=900, clock=time.monotonic):
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries = {}
        self._lock = threading.Lock()

    def remember(self, chat_id, media_group_id, content_id, title=None):
        if chat_id is None or not media_group_id:
            return
        with self._lock:
            self._prune()
            self._entries[(chat_id, str(media_group_id))] = {
                "content_id": content_id, "title": title, "at": self._clock()}

    def lookup(self, chat_id, media_group_id):
        if chat_id is None or not media_group_id:
            return None
        with self._lock:
            self._prune()
            entry = self._entries.get((chat_id, str(media_group_id)))
            return dict(entry) if entry else None

    def _prune(self):
        now = self._clock()
        for key in [k for k, v in self._entries.items() if now - v["at"] > self._ttl]:
            del self._entries[key]
