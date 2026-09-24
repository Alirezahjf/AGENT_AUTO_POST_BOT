#!/usr/bin/env python3
"""
تست ایمنی ارتقای سیستم دسترسی
- شبیه‌سازی دیتابیس قدیمی با کاربران موجود
- بررسی اینکه هیچ رکوردی حذف/تغییر مخرب نمی‌شود
- بررسی مهاجرت افزودنی (ALTER ADD COLUMN)
- بررسی پلن‌ها، اعطای رایگان، دائمی کردن
"""
import os
import sys
import sqlite3
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# تنظیم مسیر
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

TMP = tempfile.mkdtemp(prefix="access_test_")
OLD_DB = Path(TMP) / "auth.db"

print("=" * 60)
print("1) ساخت دیتابیس قدیمی با کاربران نمونه")
print("=" * 60)

# ساخت اسکیمای قدیمی (قبل از تغییرات)
conn = sqlite3.connect(str(OLD_DB))
c = conn.cursor()
c.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        token TEXT UNIQUE NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TEXT NOT NULL,
        approved_at TEXT,
        approved_by INTEGER,
        is_admin INTEGER DEFAULT 0,
        is_trial INTEGER DEFAULT 0,
        trial_start TEXT,
        trial_end TEXT
    )
''')
c.execute('''
    CREATE TABLE purchase_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        token_hash TEXT UNIQUE NOT NULL,
        token_plain TEXT NOT NULL,
        payment_id TEXT,
        amount INTEGER DEFAULT 0,
        currency TEXT DEFAULT 'IRR',
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL,
        last_used_at TEXT
    )
''')
c.execute('''
    CREATE TABLE payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        payment_id TEXT UNIQUE,
        amount INTEGER NOT NULL,
        currency TEXT DEFAULT 'IRR',
        status TEXT DEFAULT 'pending',
        payload TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT
    )
''')

now = datetime.now()
# کاربر 1: ادمین دائمی قدیمی
c.execute('''INSERT INTO users (chat_id, username, token, status, created_at, approved_at, is_admin)
             VALUES (111, 'admin_user', 'hash_admin', 'approved', ?, ?, 1)''',
          (now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S')))
# کاربر 2: پولی دائمی قدیمی (بدون تست)
c.execute('''INSERT INTO users (chat_id, username, token, status, created_at, approved_at, is_admin, is_trial)
             VALUES (222, 'paid_user', 'hash_paid', 'approved', ?, ?, 0, 0)''',
          (now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S')))
# کاربر 3: تستی فعال
trial_end = (now + timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')
c.execute('''INSERT INTO users (chat_id, username, token, status, created_at, approved_at, is_admin, is_trial, trial_start, trial_end)
             VALUES (333, 'trial_user', 'hash_trial', 'approved', ?, ?, 0, 1, ?, ?)''',
          (now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S'),
           now.strftime('%Y-%m-%d %H:%M:%S'), trial_end))
# کاربر 4: تستی منقضی شده
old_trial_end = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
c.execute('''INSERT INTO users (chat_id, username, token, status, created_at, approved_at, is_admin, is_trial, trial_start, trial_end)
             VALUES (444, 'expired_user', 'hash_expired', 'approved', ?, ?, 0, 1, ?, ?)''',
          ((now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
           (now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
           (now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'), old_trial_end))
# کاربر 5: در انتظار
c.execute('''INSERT INTO users (chat_id, username, token, status, created_at, is_admin, is_trial)
             VALUES (555, 'pending_user', 'hash_pending', 'pending', ?, 0, 0)''',
          (now.strftime('%Y-%m-%d %H:%M:%S'),))
# توکن خرید قدیمی برای کاربر 2
c.execute('''INSERT INTO purchase_tokens (chat_id, token_hash, token_plain, payment_id, amount, currency, status, created_at)
             VALUES (222, 'old_tok_hash', 'old_tok_plain', 'pay_old_1', 200000000, 'IRR', 'active', ?)''',
          (now.strftime('%Y-%m-%d %H:%M:%S'),))
conn.commit()
conn.close()

# شمارش قبل از مهاجرت
conn = sqlite3.connect(str(OLD_DB))
before_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
before_tokens = conn.execute('SELECT COUNT(*) FROM purchase_tokens').fetchone()[0]
before_rows = conn.execute('SELECT chat_id, username, status, is_trial FROM users ORDER BY chat_id').fetchall()
conn.close()
print(f"  کاربران قبل: {before_users}")
print(f"  توکن‌ها قبل: {before_tokens}")
for r in before_rows:
    print(f"    {r}")

print()
print("=" * 60)
print("2) اجرای AuthManager جدید روی دیتابیس قدیمی (مهاجرت)")
print("=" * 60)

# اجرای مهاجرت - AuthManager باید همان مسیر را پیدا کند
os.environ['TEST_AUTH_DB'] = str(OLD_DB)

# شبیه‌سازی: AuthManager با مسیر دلخواه
import auth_manager as am_mod

class TestAuthManager(am_mod.AuthManager):
    def __init__(self, db_path):
        # فراخوانی بدون init خودکار مسیر
        from pathlib import Path as P
        self.auth_db_path = str(db_path)
        self.users_dir = P(TMP) / 'users'
        self.users_dir.mkdir(exist_ok=True)
        self.init_auth_database()

ta = TestAuthManager(OLD_DB)
print("  ✅ مهاجرت انجام شد")

print()
print("=" * 60)
print("3) بررسی حفظ رکوردها")
print("=" * 60)

conn = sqlite3.connect(str(OLD_DB))
after_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
after_tokens = conn.execute('SELECT COUNT(*) FROM purchase_tokens').fetchone()[0]
after_rows = conn.execute(
    'SELECT chat_id, username, status, is_trial, access_type, access_until FROM users ORDER BY chat_id'
).fetchall()
conn.close()

assert after_users == before_users, f"❌ تعداد کاربران تغییر کرد: {before_users} -> {after_users}"
assert after_tokens == before_tokens, f"❌ تعداد توکن‌ها تغییر کرد: {before_tokens} -> {after_tokens}"
print(f"  ✅ تعداد کاربران حفظ شد: {after_users}")
print(f"  ✅ تعداد توکن‌ها حفظ شد: {after_tokens}")

for r in after_rows:
    print(f"    chat={r[0]} user={r[1]} status={r[2]} trial={r[3]} access_type={r[4]} until={r[5]}")

# بررسی بک‌فیل
rows = {r[0]: r for r in after_rows}
# ادمین و پولی باید permanent شده باشند
assert rows[111][4] == 'permanent', f"ادمین permanent نشد: {rows[111]}"
assert rows[222][4] == 'permanent', f"پولی permanent نشد: {rows[222]}"
assert rows[222][5] is None, f"پولی نباید access_until داشته باشد"
# تستی باید trial با همان تاریخ end باشد
assert rows[333][4] == 'trial', f"تستی trial نشد: {rows[333]}"
assert rows[333][5] == trial_end, f"تاریخ تست تغییر کرد: {rows[333][5]} != {trial_end}"
print("  ✅ بک‌فیل دائمی/تست درست انجام شد")

# وضعیت‌ها نباید تغییر کرده باشند
assert rows[111][2] == 'approved'
assert rows[222][2] == 'approved'
assert rows[333][2] == 'approved'
assert rows[444][2] == 'approved'
assert rows[555][2] == 'pending', "کاربر pending نباید approved شود!"
print("  ✅ وضعیت‌ها (status) دست نخورده")

print()
print("=" * 60)
print("4) بررسی پلن‌های خرید")
print("=" * 60)

plans = ta.get_plans()
assert len(plans) >= 1, "پلن پیش‌فرض ایجاد نشد"
print(f"  تعداد پلن‌ها: {len(plans)}")
for p in plans:
    print(f"    [{p['id']}] {p['name']} | days={p['duration_days']} | {p['price_rial']} ریال | enabled={p['enabled']}")

# پلن پیش‌فرض باید دائمی 200 میلیون ریال باشد (سازگاری با قبل)
permanent_plans = [p for p in plans if p['duration_days'] is None]
assert any(p['price_rial'] == 200000000 for p in permanent_plans), "پلن پیش‌فرض دائمی 20M نیست"
print("  ✅ پلن پیش‌فرض دائمی ۲۰ میلیون ریال (سازگار با قبل)")

# ایجاد پلن جدید
r = ta.create_plan('یک‌ماهه', 30, 50000000)  # 5 میلیون تومان
assert r['success'], f"ایجاد پلن ناموفق: {r}"
plan30 = ta.get_plan(r['plan_id'])
assert plan30['duration_days'] == 30
assert plan30['price_rial'] == 50000000
print(f"  ✅ پلن ۳۰ روزه ایجاد شد: {plan30['name']}")

# ویرایش قیمت
r = ta.update_plan(plan30['id'], price_rial=60000000)
assert r['success']
assert ta.get_plan(plan30['id'])['price_rial'] == 60000000
print("  ✅ ویرایش قیمت")

# غیرفعال/فعال
r = ta.update_plan(plan30['id'], enabled=0)
assert r['success']
assert ta.get_plan(plan30['id'])['enabled'] == False
r = ta.update_plan(plan30['id'], enabled=1)
assert ta.get_plan(plan30['id'])['enabled'] == True
print("  ✅ فعال/غیرفعال")

print()
print("=" * 60)
print("5) بررسی اعطای دسترسی رایگان و تمدید")
print("=" * 60)

# هدیه ۳ روزه به کاربر تستی (333) - باید از انتهای اعتبار فعلی ادامه یابد
r = ta.grant_free_access(333, 3, granted_by=111, note='تست هدیه')
assert r['success'], f"هدیه ناموفق: {r}"
info = ta.get_user_info(333)
assert info['access_type'] == 'timed'
base = datetime.strptime(trial_end, '%Y-%m-%d %H:%M:%S')
expected = (base + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
assert info['access_until'] == expected, f"محاسبه غلط: {info['access_until']} != {expected}"
print(f"  ✅ هدیه ۳ روزه از انتهای اعتبار قبلی: {info['access_until']}")

# دائمی کردن کاربر منقضی (444)
r = ta.set_user_access(444, 'permanent', granted_by=111, note='دائمی شد')
assert r['success']
info444 = ta.get_user_info(444)
assert info444['access_type'] == 'permanent'
assert info444['access_until'] is None
assert not info444.get('access_expired')
assert info444['status'] == 'approved'
print("  ✅ دائمی کردن کاربر منقضی شده")

# خلاصه دسترسی
s = ta.get_access_summary(111)
assert s['access_type'] == 'permanent' and not s['expired']
s = ta.get_access_summary(333)
assert s['access_type'] == 'timed' and not s['expired']
s = ta.get_access_summary(444)
assert s['access_type'] == 'permanent' and not s['expired']
print("  ✅ خلاصه دسترسی درست است")

# آمار
stats = ta.get_users_stats()
print(f"  📊 آمار: {stats}")
assert stats['total'] == 5
assert stats['permanent'] >= 3  # 111, 222, 444

# تاریخچه تغییرات
changes = ta.get_access_change_log()
assert len(changes) >= 2, "تاریخچه تغییرات ثبت نشد"
print(f"  ✅ تاریخچه تغییرات: {len(changes)} مورد")

# توکن خرید قدیمی هنوز معتبر است
conn = sqlite3.connect(str(OLD_DB))
tok = conn.execute("SELECT status FROM purchase_tokens WHERE token_plain='old_tok_plain'").fetchone()
conn.close()
assert tok and tok[0] == 'active', "توکن خرید قدیمی خراب شد!"
print("  ✅ توکن خرید قدیمی دست‌نخورده")

print()
print("=" * 60)
print("6) بررسی مدت تست پیش‌فرض")
print("=" * 60)
# تست set/get بدون نوشتن در config.json اصلی
days = ta.get_default_trial_days()
print(f"  مدت تست فعلی: {days} روز (پیش‌فرض ۱)")
assert days == 1  # چون config اصلی default_trial_days ندارد

print()
print("=" * 60)
print("🎉 همه تست‌های ایمنی موفق بود!")
print("=" * 60)
print()
print("نتیجه:")
print("  ✅ هیچ کاربری حذف نشد")
print("  ✅ هیچ توکنی حذف نشد")
print("  ✅ وضعیت‌ها تغییر مخرب نکرد")
print("  ✅ مهاجرت فقط ستون افزود")
print("  ✅ کاربران قدیمی دائمی/تست درست دسته‌بندی شدند")
print("  ✅ پلن‌ها، هدیه، تمدید، دائمی‌سازی کار می‌کنند")

shutil.rmtree(TMP, ignore_errors=True)
print("\n🧹 فایل موقت پاک شد")
