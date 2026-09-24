# 📖 راهنمای آپدیت ایمن — سیستم مدیریت دسترسی و تعرفه‌ها

> **تاریخ:** ۲۰۲۶/۰۹/۲۴  
> **شاخه:** `arena/01a0d39d-agent-auto-post-bot`  
> **سطح ریسک:** 🟢 پایین — مهاجرت فقط **افزودنی** است، هیچ رکوردی حذف نمی‌شود

---

## ✅ چه چیزهایی اضافه شد؟

### ۱. پنل مدیریت حرفه‌ای‌تر
- **دکمه‌های اصلی** (مدیریت کاربران، تعرفه‌ها، درخواست‌ها، …) روی **کیبورد پایین** (solid/تحت‌کیبورد)
- **دکمه‌های فرعی** (لیست کاربران، پروفایل، انتخاب مدت، ویرایش پلن) به صورت **inline/شیشه‌ای**
- داشبورد ادمین با آمار زنده: تعداد کاربران، دائمی، محدود، منقضی

### ۲. مدیریت کاربران — روی هر کاربر کلیک کن
- لیست کاربران با **صفحه‌بندی** و نشان وضعیت (♾️ دائمی / 🟢 فعال / 🎁 تست / 🔴 منقضی)
- **پروفایل کاربر** با بخش‌های:
  - اطلاعات پایه (نام، آیدی، نقش، وضعیت، تاریخ ثبت‌نام)
  - **مدت دسترسی** (نوع، تا کی، باقی‌مانده)
  - یادداشت و آخرین هدیه
- دکمه‌های عملیاتی (inline):
  - 🎁 **هدیه دسترسی رایگان** — ۱/۳/۷/۱۴/۳۰ روز یا عدد دلخواه
  - ⏱️ **تمدید مدت دسترسی** — ۷/۳۰/۹۰/۱۸۰ روز یا دلخواه
  - ♾️ **دائمی کردن** (برای کاربران محدود)
  - ⏱️ **تغییر به دسترسی مدت‌دار** (ویژه کاربران دائمی — با تایید قبلی)
  - 🧾 پرداخت‌های کاربر / 📊 فعالیت اخیر
- **کاربران دائمی هم قابل تغییرند:** هر دو دکمه «هدیه» و «تمدید» برای کاربران ♾️ دائمی نمایش داده می‌شود؛ قبل از تبدیل دائمی→محدود، دیالوگ **تایید** ظاهر می‌شود تا اشتباهاً دسترسی دائمی کسی کم نشود.

### ۳. تعرفه‌ها و قیمت‌گذاری درون ربات
- منوی **🏷️ تعرفه‌ها و قیمت‌گذاری** برای ادمین
- افزودن پلن جدید (نام → مدت به روز یا `permanent` → قیمت به تومان)
- ویرایش قیمت / مدت / فعال‌سازی / حذف هر پلن
- **📣 اطلاع‌رسانی خودکار به همه کاربران** هنگام:
  - ساخت پلن جدید
  - تغییر قیمت
  - دکمه دستی «اطلاع‌رسانی به همه»

### ۴. خرید چندپلنی برای کاربران
- دکمه **🏷️ تعرفه‌ها** روی کیبورد اصلی همه کاربران
- لیست پلن‌ها با قیمت و مدت → انتخاب → فاکتور پرداخت با **همان قیمت**
- پس از پرداخت، مدت دسترسی بر اساس پلن اعمال می‌شود (مثلاً ۳۰ روز از انتهای اعتبار قبلی)
- پرداخت‌های قدیمی/بدون پلن → **دائمی** (رفتار قبلی حفظ شد)

### ۵. اطلاع‌رسانی تغییر دسترسی
- هر تغییری توسط ادمین (هدیه/تمدید/دائمی) → پیام خودکار به کاربر با دکمه **🏷️ تعرفه‌ها**

### ۶. تست پیش‌فرض قابل تنظیم
- دکمه **⏱️ تست پیش‌فرض کاربران جدید** در منوی ادمین
- پیش‌فرض: **۱ روز** (بدون تغییر رفتار فعلی) — قابل تغییر به ۳ روز، ۷ روز و …

---

## 🛡️ چرا دیتابیس و کاربران آسیب نمی‌بینند؟

| اقدام | نوع | توضیح |
|---|---|---|
| `ALTER TABLE users ADD COLUMN access_type` | ➕ افزودن | فقط ستون جدید، ردیف‌ها دست‌نخورده |
| `ALTER TABLE users ADD COLUMN access_until` | ➕ افزودن | همین‌طور |
| `CREATE TABLE plans` | ➕ جدول جدید | جدول کاملاً جدید |
| `CREATE TABLE access_changes` | ➕ جدول جدید | تاریخچه تغییرات |
| بک‌فیل `UPDATE ... WHERE access_type IS NULL` | 🔄 فقط ردیف‌های خالی | کاربران قدیمی: پولی→دائمی، تستی→ trial با همان تاریخ |
| پلن پیش‌فرض «دائمی ۲۰ میلیون» | ➕ فقط اگر `plans` خالی باشد | قیمت فعلی حفظ می‌شود |
| `DROP` / `DELETE` / `TRUNCATE` روی کاربران | ❌ **وجود ندارد** | — |

**رفتار کاربران موجود (قبل → بعد):**

| کاربر قبل از آپدیت | بعد از آپدیت |
|---|---|
| ادمین | ♾️ دائمی — بدون تغییر |
| پولی/دائمی (بدون تست) | ♾️ دائمی — بدون تغییر |
| تستی فعال | 🎁 تست — همان تاریخ پایان قبلی |
| تستی منقضی | 🔴 منقضی — همان پیام «خرید» قبلی |
| در انتظار/رد شده | بدون تغییر |
| توکن خرید قدیمی | همچنان معتبر و فعال |
| پرداخت موفق قدیمی | دسترسی دائمی (مثل قبل) |

---

## 🚀 نحوه آپدیت روی سرور (قدم به قدم)

### روش پیشنهادی: اسکریپت موجود (بکاپ خودکار)

```bash
# ۱) ورود به سرور و رفتن به پوشه پروژه
cd ~/AGENT_AUTO_POST_BOT

# ۲) آپدیت کد از گیت (کد جدید می‌گیرد، users/auth.db/config حفظ می‌شوند)
./clean_update.sh
```

> ⚠️ `clean_update.sh` قبل از هر چیز از `users/`، `auth.db`، `config.json` و سشن‌های واتساپ  
> بکاپ در `/tmp/bot_backup_*` می‌گیرد و بعد بازگردانی می‌کند.

### روش دستی (کنترل بیشتر)

```bash
cd ~/AGENT_AUTO_POST_BOT

# ۱) توقف سرویس‌ها
./stop.sh
pkill -9 -f "python.*bot.py" 2>/dev/null; true
pkill -9 -f "node.*index.js" 2>/dev/null; true
fuser -k 3001/tcp 2>/dev/null; true

# ۲) بکاپ کامل (اجباری)
BK=/tmp/bot_backup_$(date +%s)
mkdir -p "$BK"
cp -r all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users    "$BK/users"
cp    all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db    "$BK/"
cp    all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json "$BK/"
cp -r whatsapp-service/auth                                "$BK/whatsapp_auth" 2>/dev/null; true
cp    whatsapp-service/sessions_db.json                    "$BK/" 2>/dev/null; true
echo "بکاپ در: $BK"

# ۳) دریافت کد جدید (مثلاً merge کردن شاخه کاری)
git fetch origin
git merge origin/arena/01a0d39d-agent-auto-post-bot   # یا هر روش pull دلخواه

# ۴) اطمینان از بازگشت بکاپ (فقط اگر git آن‌ها را لمس کرده باشد)
#    معمولاً users/ و auth.db در .gitignore هستند و دست نمی‌خورند
ls all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users | wc -l   # باید تعداد کاربران قبلی باشد
ls -lh all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db

# ۵) اجرای مجدد
./start.sh
sleep 5
./status.sh
```

### چک‌لیست بعد از آپدیت

```bash
# لاگ ربات — نباید خطای migration باشد
tail -50 all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log

# باید ببینید:
#   ✅ جداول پایگاه داده ایجاد شدند
#   🤖 ربات شروع به کار کرد!

# تعداد کاربران نباید تغییر کرده باشد
python3 -c "
import sqlite3
c = sqlite3.connect('all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db')
print('کاربران:', c.execute('SELECT COUNT(*) FROM users').fetchone()[0])
print('ستون‌ها:', [r[1] for r in c.execute('PRAGMA table_info(users)')])
"
```

### تست محلی قبل از آپدیت سرور (اختیاری)

```bash
cd all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER
python3 test_access_upgrade.py
# باید بنویسد: 🎉 همه تست‌های ایمنی موفق بود!
```

---

## 🔙 بازگردانی (Rollback) در صورت مشکل

```bash
cd ~/AGENT_AUTO_POST_BOT
./stop.sh

# بکاپ‌ها معمولاً اینجاست:
ls -dt /tmp/bot_backup_* | head -3

# بازگردانی auth.db و users از آخرین بکاپ
BK=$(ls -dt /tmp/bot_backup_* | head -1)
cp "$BK/auth.db"    all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db
rm -rf all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users
cp -r "$BK/users"   all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users

# کد قبلی را برگردانید (مثلاً checkout کامیت قبلی) و سپس:
./start.sh
```

> ستون‌های اضافه‌شده (`access_type` و …) حتی در نسخه قدیمی کد مشکلی ایجاد نمی‌کنند  
> چون کد قدیمی آن ستون‌ها را `SELECT` نمی‌کند.

---

## 🔌 فیلدهای API ووکامرس — اتصال و پست‌گذاری

### الف) فیلدهای اتصال (در `users/{chat_id}/config.json` → بخش `woocommerce`)

| فیلد | نقش | محل استفاده |
|---|---|---|
| `url` | آدرس پایه فروشگاه (مثلاً `https://mysite.com`) | ساخت مسیر API |
| `consumer_key` | کلید API ووکامرس (معمولاً شروع با `ck_`) | احراز هویت + شرط اجباری اتصال |
| `consumer_secret` | رمز API ووکامرس (معمولاً شروع با `cs_`) | احراز هویت |

**نحوه احراز هویت:** HTTP Basic روی همه درخواست‌ها:

```python
auth=(config["woocommerce"]["consumer_key"],
      config["woocommerce"]["consumer_secret"])
```

**شرط فعال بودن اتصال** (بدون این دو، API صدا زده نمی‌شود):

```python
if not wc.get("url") or not wc.get("consumer_key"):
    return None  # یا []
```

> `consumer_secret` در شرط چک نمی‌شود ولی در همه درخواست‌ها ارسال می‌گردد؛  
> اگر خالی باشد، API با خطای 401 پاسخ می‌دهد.

### ب) endpoint های استفاده شده

| endpoint | پارامترها | کاربرد |
|---|---|---|
| `GET {url}/wp-json/wc/v3/products` | `per_page`, `page`, `orderby=date`, `order=desc`, `status=publish`, `category` | دریافت محصولات (تشخیص جدید + پست‌گذاری + تست) |
| `GET {url}/wp-json/wc/v3/products/categories` | `per_page=100`, `hide_empty=true` | لیست دسته‌بندی‌ها (فیلتر دسته در پست خودکار) |

نکات:
- **فقط محصولات `status=publish`** دریافت می‌شوند.
- صفحه‌بندی با هدر پاسخ `X-WP-TotalPages` انجام می‌شود.
- بین درخواست‌ها `sleep(0.3)` برای احترام به محدودیت API.

### ج) فیلدهای خود محصول که در پست‌گذاری استفاده می‌شوند

| فیلد محصول (JSON پاسخ WC) | کجا و چطور استفاده می‌شود |
|---|---|
| `id` | شناسه یکتا — تشخیص محصول جدید (`known_ids`) و جلوگیری از تکرار (`sent_ids`) |
| `name` | عنوان پست (`📦 {name}`) |
| `short_description` | توضیحات پست — پاک‌سازی HTML، حداکثر ۲۵۰ کاراکتر |
| `price` | قیمت فعلی (`💰 قیمت: …`) |
| `regular_price` | قیمت قبلی — فقط وقتی حراج فعال است |
| `sale_price` | قیمت حراج (`🔥 قیمت حراج`) — اگر با `regular_price` فرق کند |
| `permalink` | لینک خرید — ابتدا کوتاه‌ساز (TinyURL → is.gd → decode) |
| `tags` | حداکثر ۵ تگ اول → هشتگ (`#تگ_اول …`) |
| `categories` | نمایش ۲ دسته اول در پست + **فیلتر دسته‌بندی** (در API با `category=id,id`) |
| `images[0].src` | تصویر اول محصول برای `sendPhoto` (URL مستقیم، سپس fallback دانلود multipart، سپس فقط متن) |
| `images` (بقیه) | در برخی پیام‌رسان‌ها گالری/تصاویر بعدی — اولین تصویر اصلی است |
| `date_created` | مرتب‌سازی «جدید به قدیم» (هم در API با `orderby=date` هم در کلاینت) |
| `stock_status` / موجودی | ❌ استفاده نمی‌شود (فقط محصولات publish بدون فیلتر موجودی) |
| `description` (بلند) | ❌ استفاده نمی‌شود — فقط `short_description` |

### د) جریان کامل

```
تنظیم توسط کاربر در ربات:
  URL → consumer_key → consumer_secret
        │
        ▼
users/{chat_id}/config.json  →  {"woocommerce": {"url", "consumer_key", "consumer_secret"}}
        │
        ▼
woocommerce.get_all_products()  ──Basic Auth──►  /wp-json/wc/v3/products
        │
        ├─► تشخیص جدید: مقایسه مجموعه id ها با known_product_ids.json
        ├─► فیلتر ارسال‌نشده: sent_product_ids.json
        ├─► فیلتر دسته (اختیاری): auto_post.categories
        │
        ▼
messenger_*.send_product(product)
        │
        ├─► کپشن: name + short_description + price/regular/sale + tags + categories + permalink
        └─► رسانه: images[0].src یا fallback متنی
```

**فایل‌های مرتبط در کد:**
- `woocommerce.py` — دریافت محصول/دسته، تشخیص جدید، صف ارسال
- `messenger_common.py` → `format_product_base()` — فرمت مشترک کپشن
- `messenger_bale.py` / `_telegram` / `_rubika` / `_eitaa` / `_whatsapp` → `_format_product()` + `send_product()`
- `scheduler.py` → `check_woocommerce_for_user()` / `check_live_new_products_for_user()`

**جمع‌آوری فیلدها در ربات:** از `bot.py` (states `waiting_wc_url`، سپس `consumer_key`، سپس `consumer_secret` در `user_config["woocommerce"]`) ذخیره می‌شود.

---

## 📝 نکات مهم

1. **قیمت پیش‌فرض:** پلن «دسترسی دائمی — ۲۰٬۰۰۰٬۰۰۰ تومان» عیناً مثل قبل از پرداخت‌ها حفظ شده؛ بعداً از منوی تعرفه‌ها قابل تغییر است.
2. **کیف پول:** مثل قبل `wallet_token` در `config.json` خوانده می‌شود — دست نخورده.
3. **بدون تغییر اجباری کاربران:** هیچ کاربری مجبور به خرید مجدد یا ورود مجدد نمی‌شود.
4. **تست رایگان:** تا وقتی `default_trial_days` را عوض نکنید، **۱ روز** مثل قبل باقی می‌ماند.
5. **فایل‌های حساس در git نیستند:** `auth.db`، `users/`، `config.json` همگی در `.gitignore` — آپدیت کد آن‌ها را پاک نمی‌کند.
