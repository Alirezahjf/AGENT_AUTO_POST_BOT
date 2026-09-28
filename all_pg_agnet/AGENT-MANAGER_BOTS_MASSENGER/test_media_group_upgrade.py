#!/usr/bin/env python3
"""
تست ایمنی ارتقا برای «مدیا گروهی» (سبک test_access_upgrade.py)
- ساخت posts.db قدیمی با داده (دو نسخه: اسکیمای خیلی قدیمی بدون ستون‌های messengers/title،
  و اسکیمای فعلی سرور)
- اجرای PostDatabase جدید = همان init/migration زمان استارت ربات
- بررسی: هیچ جدول/ستون/ردیفی حذف یا عوض نشد؛ تغییرات فقط افزودنی است
- بررسی: مدیا گروهی، پست «بدون مدیا» و «بدون کپشن» روی همان دیتابیس کار می‌کنند
فقط روی فایل موقت کار می‌کند؛ دیتابیس واقعی هرگز باز نمی‌شود.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
TMP = tempfile.mkdtemp(prefix="media_group_upgrade_")
os.chdir(TMP)  # nothing is written next to the real databases

from database import PostDatabase  # noqa: E402
import media_group  # noqa: E402

OLDEST_SCHEMA = [
    """CREATE TABLE scheduled_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, media_path TEXT NOT NULL,
       media_type TEXT NOT NULL, caption TEXT, hashtags TEXT, scheduled_date TEXT NOT NULL,
       scheduled_time TEXT NOT NULL, status TEXT DEFAULT 'pending', created_at TEXT NOT NULL,
       post_type TEXT DEFAULT 'manual')""",
    """CREATE TABLE posting_history (id INTEGER PRIMARY KEY AUTOINCREMENT, media_path TEXT, media_type TEXT,
       caption TEXT, hashtags TEXT, posted_at TEXT NOT NULL, post_type TEXT NOT NULL, status TEXT DEFAULT 'success')""",
    """CREATE TABLE content_media (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT NOT NULL,
       media_type TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT DEFAULT 'active')""",
    """CREATE TABLE content_text (id INTEGER PRIMARY KEY AUTOINCREMENT, text_content TEXT NOT NULL,
       created_at TEXT NOT NULL, status TEXT DEFAULT 'active')""",
    """CREATE TABLE draft_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, media_path TEXT NOT NULL,
       media_type TEXT NOT NULL, caption TEXT, hashtags TEXT, scheduled_date TEXT, scheduled_time TEXT,
       created_at TEXT NOT NULL, post_type TEXT DEFAULT 'manual')""",
    """CREATE TABLE archived_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, media_path TEXT, media_type TEXT,
       caption TEXT, hashtags TEXT, scheduled_date TEXT, scheduled_time TEXT, archived_at TEXT NOT NULL,
       original_type TEXT DEFAULT 'manual')""",
]
OLDEST_ROWS = [
    ("INSERT INTO scheduled_posts (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, status, created_at, post_type) VALUES (?,?,?,?,?,?,?,?,?)",
     ("AgADphoto1", "photo", "کپشن قدیمی", "", "2026-10-01", "10:00", "pending", "2026-09-01 10:00:00", "manual")),
    ("INSERT INTO scheduled_posts (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, status, created_at, post_type) VALUES (?,?,?,?,?,?,?,?,?)",
     ("AgADvideo1", "video", "ویدیوی قدیمی", "#tag", "2026-09-02", "11:30", "posted", "2026-09-01 11:00:00", "manual")),
    ("INSERT INTO posting_history (media_path, media_type, caption, hashtags, posted_at, post_type, status) VALUES (?,?,?,?,?,?,?)",
     ("AgADvideo1", "video", "ویدیوی قدیمی", "#tag", "2026-09-02 11:30:05", "manual", "success")),
    ("INSERT INTO content_media (file_id, media_type, created_at, status) VALUES (?,?,?,?)",
     ("AgADphoto1", "photo", "2026-08-30 09:00:00", "active")),
    ("INSERT INTO content_media (file_id, media_type, created_at, status) VALUES (?,?,?,?)",
     ("AgADold2", "video", "2026-08-30 09:05:00", "archived")),
    ("INSERT INTO content_text (text_content, created_at, status) VALUES (?,?,?)",
     ("متن آماده", "2026-08-30 09:10:00", "active")),
    ("INSERT INTO draft_posts (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, created_at, post_type) VALUES (?,?,?,?,?,?,?,?)",
     ("AgADphoto1", "photo", "پیش‌نویس", "", "2026-10-05", "08:00", "2026-09-03 08:00:00", "manual")),
    ("INSERT INTO archived_posts (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, archived_at, original_type) VALUES (?,?,?,?,?,?,?,?)",
     ("AgADphoto1", "photo", "آرشیو", "", "2026-08-01", "07:00", "2026-08-02 07:00:00", "manual")),
]


def snapshot(db_path):
    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    schema = {t: [(c[1], c[2], c[3], c[4]) for c in conn.execute(f"PRAGMA table_info({t})")] for t in tables}
    rows = {}
    for t in tables:
        cols = [c[0] for c in schema[t]]
        rows[t] = [dict(zip(cols, r)) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")]
    conn.close()
    return schema, rows


def check_additive(before, after, label):
    schema_b, rows_b = before
    schema_a, rows_a = after
    for table, cols in schema_b.items():
        assert table in schema_a, f"❌ [{label}] جدول {table} حذف شد!"
        now = {c[0]: c for c in schema_a[table]}
        for col in cols:
            assert col[0] in now, f"❌ [{label}] ستون {table}.{col[0]} حذف شد!"
            assert now[col[0]] == col, f"❌ [{label}] تعریف ستون {table}.{col[0]} عوض شد: {col} -> {now[col[0]]}"
        assert len(rows_a[table]) == len(rows_b[table]), f"❌ [{label}] تعداد ردیف {table} تغییر کرد"
        for old, new in zip(rows_b[table], rows_a[table]):
            for key, value in old.items():
                assert new[key] == value, f"❌ [{label}] مقدار {table}.{key} عوض شد: {value!r} -> {new[key]!r}"
    added = {t: [c[0] for c in schema_a[t] if c[0] not in {x[0] for x in schema_b.get(t, [])}] for t in schema_a}
    return {t: cols for t, cols in added.items() if cols}


def exercise_new_features(db):
    """Group media + «بدون مدیا» + «بدون کپشن» on the migrated database."""
    items = [{"type": "photo", "file_id": f"AgADalbum{i}"} for i in range(1, 6)] + [{"type": "video", "file_id": "AgADclip"}]
    group_id = db.add_media_group(items, "آلبوم شش‌تایی")
    listed = {row[0]: row for row in db.get_media_contents()}
    assert group_id in listed, "❌ مدیا گروهی در لیست رسانه‌ها نیست"
    _, media_type, file_id, title, _ = listed[group_id]
    assert media_type == media_group.MEDIA_GROUP and title == "آلبوم شش‌تایی"
    assert media_group.decode_items(file_id) == items, "❌ آیتم‌های گروه درست ذخیره نشدند"
    label = media_group.library_button_text(group_id, media_type, file_id, title, "fa")
    assert label == "📸 آلبوم شش‌تایی · مدیا گروهی (6)", label
    print(f"  ✅ مدیا گروهی = یک ردیف در لیست: «{label}»")

    assert db.append_media_group_items(group_id, [{"type": "photo", "file_id": "AgADlate"}, items[0]]) == 7
    assert db.append_media_group_items(10 ** 6, items) is None
    assert db.append_media_group_items(1, items) is None, "❌ نباید به ردیف تکی (photo) آیتم اضافه شود"
    print("  ✅ آیتم دیرآمده به همان گروه اضافه شد (بدون تکرار، ردیف‌های تکی دست‌نخورده)")

    row = db.get_content_by_id(group_id)
    post_id = db.add_scheduled_post(row[1], row[2], "یک کپشن برای کل گروه", "", "2026-10-10", "12:00", "manual", "bale,rubika")
    text_post = db.add_scheduled_post("", media_group.TEXT_ONLY, "فقط متن", "", "2026-10-10", "12:05", "manual", "all")
    no_caption = db.add_scheduled_post("AgADphoto1", "photo", "", "", "2026-10-10", "12:10", "manual", "all")
    pending = {p[0]: p for p in db.get_scheduled_posts()}
    assert pending[post_id][2] == media_group.MEDIA_GROUP and len(media_group.decode_items(pending[post_id][1])) == 7
    assert pending[text_post][1:4] == ("", media_group.TEXT_ONLY, "فقط متن")
    assert pending[no_caption][3] == ""
    print("  ✅ پست گروهی / بدون مدیا / بدون کپشن زمان‌بندی شد")

    db.mark_post_as_posted(post_id)
    history = db.get_posting_history()
    assert history[0][2] == media_group.MEDIA_GROUP and media_group.decode_items(history[0][1]), "❌ تاریخچه گروه"
    db.delete_scheduled_post(text_post)
    assert any(a[2] == media_group.TEXT_ONLY for a in db.get_archived_posts()), "❌ آرشیو پست متنی"
    draft = db.add_draft_post(row[1], row[2], "پیش‌نویس گروهی", "", "2026-10-11", "09:00")
    db.restore_draft_to_scheduled(draft)
    assert any(p[2] == media_group.MEDIA_GROUP and p[3] == "پیش‌نویس گروهی" for p in db.get_scheduled_posts())
    print("  ✅ تاریخچه، آرشیو و پیش‌نویس، گروه را بدون تغییر اسکیما حمل می‌کنند")


def run_scenario(label, create_statements, rows):
    print("=" * 60)
    print(f"سناریو: {label}")
    print("=" * 60)
    db_path = str(Path(TMP) / f"{label}.db")
    conn = sqlite3.connect(db_path)
    for stmt in create_statements:
        conn.execute(stmt)
    for sql, params in rows:
        conn.execute(sql, params)
    conn.commit()
    conn.close()
    before = snapshot(db_path)
    print(f"  ردیف‌های قبل: { {t: len(r) for t, r in before[1].items()} }")

    db = PostDatabase(db_path)  # startup: CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN
    after = snapshot(db_path)
    added = check_additive(before, after, label)
    print(f"  ✅ هیچ جدول/ستون/ردیفی حذف یا عوض نشد؛ ستون‌های افزوده: {added or 'هیچ'}")

    old_photo = [r for r in db.get_media_contents() if r[2] == "AgADphoto1"]
    assert old_photo and old_photo[0][1] == "photo", "❌ رسانهٔ قدیمی خوانده نشد"
    old_post = [p for p in db.get_scheduled_posts() if p[1] == "AgADphoto1"]
    assert old_post and old_post[0][3] == "کپشن قدیمی" and old_post[0][8] in ("all", None)
    print("  ✅ ردیف‌های قدیمی با API فعلی درست خوانده می‌شوند")

    PostDatabase(db_path)  # a second restart must be a no-op
    check_additive(after, snapshot(db_path), label + " (restart)")
    print("  ✅ استارت دوباره هیچ تغییری نداد (idempotent)")

    exercise_new_features(db)
    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()
    final_schema, final_rows = snapshot(db_path)
    # new rows were added on purpose; the original rows (lowest ids) must be untouched
    old_part = {t: final_rows[t][:len(before[1].get(t, []))] for t in final_rows}
    check_additive(before, (final_schema, old_part), label + " (final)")
    print("  ✅ integrity_check=ok و ردیف‌های قدیمی بعد از استفاده هم سالم ماندند")
    print()


def current_schema_statements():
    """Schema exactly as the current code creates it (what the server has today)."""
    path = str(Path(TMP) / "template.db")
    PostDatabase(path)
    conn = sqlite3.connect(path)
    stmts = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type IN ('table','index') AND sql IS NOT NULL "
        "AND name NOT LIKE 'sqlite_%' ORDER BY type DESC")]
    conn.close()
    return stmts


try:
    run_scenario("oldest_schema", OLDEST_SCHEMA, OLDEST_ROWS)
    current_rows = [(sql, params) for sql, params in OLDEST_ROWS]
    current_rows.append((
        "INSERT INTO scheduled_posts (media_path, media_type, caption, hashtags, scheduled_date, scheduled_time, messengers, status, created_at, post_type) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("AgADphoto9", "photo", "با پیام‌رسان", "", "2026-10-02", "09:00", "bale,telegram", "pending", "2026-09-05 09:00:00", "manual")))
    current_rows.append((
        "INSERT INTO content_media (file_id, media_type, title, created_at, status) VALUES (?,?,?,?,?)",
        ("AgADtitled", "photo", "عنوان‌دار", "2026-09-05 10:00:00", "active")))
    run_scenario("current_schema", current_schema_statements(), current_rows)
    print("=" * 60)
    print("🎉 همهٔ تست‌های ارتقای مدیا گروهی موفق بود!")
    print("=" * 60)
    print("نتیجه:")
    print("  ✅ هیچ ردیف، ستون یا جدولی حذف/عوض نشد (مهاجرت فقط افزودنی است؛ این قابلیت اسکیما را تغییر نمی‌دهد)")
    print("  ✅ مدیا گروهی = یک آیتم در لیست رسانه‌ها، با یک کپشن برای کل گروه")
    print("  ✅ پست بدون مدیا و بدون کپشن ذخیره و حمل می‌شوند")
finally:
    os.chdir(str(BASE))
    shutil.rmtree(TMP, ignore_errors=True)
    print("\n🧹 فایل موقت پاک شد")
