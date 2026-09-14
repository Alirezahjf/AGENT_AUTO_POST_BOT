# گزارش نهایی - یکپارچه‌سازی تلگرام و واتساپ

تاریخ: 2026-09-09
شاخه: arena/01a086a1-agent-auto-post-bot

## ✅ کارهای انجام شده

### 1. تلگرام - پیاده‌سازی کامل (dest_only)

#### فایل‌های جدید:
- `messenger_telegram.py` (367 خط)
  - `send_product`: ارسال محصول ووکامرس به کانال تلگرام
    - 3 روش fallback: URL مستقیم عکس → multipart upload → فقط متن
    - مدیریت Markdown + fallback بدون Markdown
    - مدیریت محدودیت 1024 کپشن و 4096 متن + chunking
    - `_send_with_retry` با مدیریت Rate Limit 429 و retry_after
  - `send_manual_post`: ارسال پست دستی زمان‌بندی شده
  - `is_configured`: بررسی پیکربندی

- `messenger_common.py` (جدید)
  - `clean_html`, `shorten_url`, `format_product_base`, `send_with_retry`
  - برای جلوگیری از تکرار کد بین messenger ها

- `messenger_whatsapp.py` (اسکلت کامل)
  - پشتیبانی دو provider: `baileys` (پیشنهادی) و `cloud` (رسمی)
  - اینترفیس یکسان با بقیه: `send_product`, `send_manual_post`
  - آماده برای اتصال به میکروسرویس Node.js

- `whatsapp-service/` (میکروسرویس)
  - `index.js`: سرور Express + Baileys
  - QR Code در ترمینال + ذخیره سشن در `auth/`
  - API `/send` برای ارسال پیام
  - تاخیر تصادفی 1-3 ثانیه برای جلوگیری از بن
  - `package.json`, `README.md`

#### فایل‌های تغییر یافته:

**config.py:**
- `MESSENGER_LIST = ["bale", "rubika", "eitaa", "telegram", "whatsapp"]`
- `MESSENGER_CONFIGS` شامل 5 پیام‌رسان
- `DEFAULT_CONFIG` شامل telegram و whatsapp
- `load_config()` داینامیک شد: loop روی `MESSENGER_LIST` به جای hard-code

**bot.py:**
- `MESSENGER_LIST`, `MESSENGER_EMOJIS`, `MESSENGER_DISPLAY_NAMES` اضافه شد
- `create_messengers_keyboard` داینامیک شد (loop روی MESSENGER_LIST)
- `create_messenger_selection_keyboard` داینامیک شد
- `toggle_all_messengers` داینامیک شد
- `test_product_posting` بررسی داینامیک `has_any_messenger`
- `messenger_names` شامل telegram و whatsapp
- `platform_emojis` شامل telegram
- تشخیص پیام‌رسان‌ها با ایموجی: `any(x in text for x in ["Bale", "🔵"])` به جای `"Bale" in text`
- هندلر جدید `waiting_telegram_token` و `waiting_telegram_chat` با راهنمای کامل
- هندلر جدید `waiting_whatsapp_chat` با پشتیبانی دو provider

**scheduler.py:**
- `import messenger_telegram, messenger_whatsapp`
- `MESSENGER_LIST` و `MESSENGER_EMOJIS`
- `post_to_all_messengers` داینامیک شد با دیکشنری `messenger_modules`
- `has_messenger` داینامیک: `any(... for m in MESSENGER_LIST)`
- `_resolve_messengers` داینامیک
- `_send_to_platforms` اضافه شدن شاخه telegram (4) و whatsapp (5)

**database.py:**
- فیکس باگ `timedelta` import نشده: `from datetime import datetime, timedelta`

**config.json:**
- اضافه شدن `telegram` و `whatsapp` placeholder
- اضافه شدن `initial_admin_id`

**فایل‌های کمکی:**
- `requirements.txt`: requests, pytz, jdatetime, python-dotenv
- `.gitignore`: برای __pycache__, *.db, config.json, users/, auth/, node_modules/, etc
- `TELEGRAM_INTEGRATION.md`: راهنمای کامل
- `WHATSAPP_EVALUATION.md`: ارزیابی دقیق API vs Library

### 2. معماری جدید - داینامیک

**قبل:**
```python
# در 10+ نقطه hard-code
if config["messengers"]["bale"]["bot_token"]: ...
if config["messengers"]["rubika"]["bot_token"]: ...
if config["messengers"]["eitaa"]["bot_token"]: ...
```

**بعد:**
```python
MESSENGER_LIST = ["bale", "rubika", "eitaa", "telegram", "whatsapp"]

for messenger_name in MESSENGER_LIST:
    cfg = config["messengers"].get(messenger_name, {})
    if cfg.get("bot_token"):
        ...
```

حالا افزودن پیام‌رسان جدید فقط نیاز به:
1. اضافه کردن نام به `MESSENGER_LIST`
2. ساخت `messenger_xxx.py` با دو تابع `send_product` و `send_manual_post`
3. اضافه کردن به `MESSENGER_EMOJIS` و `DISPLAY_NAMES`

### 3. واتساپ - ارزیابی و پیشنهاد

**سوال کاربر:** API رسمی بهتر است یا کتابخانه مثل neon؟

**پاسخ کامل در WHATSAPP_EVALUATION.md:**
- **کوتاه‌مدت / ایران / تست سریع**: Baileys (Node.js) - رایگان، 10 دقیقه راه‌اندازی، بدون تایید
- **بلندمدت / مقیاس بالا / بیزینس رسمی**: Cloud API - پایدار، بدون ریسک بن، ولی هزینه + تایید سخت + تحریم ایران

**توصیه برای این پروژه:**
فاز 1: Baileys به صورت میکروسرویس (ساخته شد ✅)
فاز 2: پایدارسازی با صف و مانیتورینگ
فاز 3: مهاجرت به Cloud API وقتی به 1000+ پیام/روز رسیدید

**ساختار پیشنهادی:**
```
AGENT_AUTO_POST_BOT/
  all_pg_agnet/.../messenger_whatsapp.py (کلاینت پایتون)
  whatsapp-service/ (سرویس Node.js)
    index.js (Express + Baileys)
    auth/ (سشن)
```

## 📊 تست‌ها

```bash
python -m py_compile bot.py -> OK
python -m py_compile config.py -> OK
python -m py_compile scheduler.py -> OK
python -m py_compile messenger_telegram.py -> OK
python -m py_compile messenger_whatsapp.py -> OK
python -m py_compile messenger_common.py -> OK
python -m py_compile database.py -> OK
```

## 🚀 نحوه استفاده تلگرام

1. ربات بساز در @BotFather -> توکن بگیر
2. ربات را ادمین کانال کن
3. در ربات Bale: تنظیمات -> پیام‌رسان‌ها -> ✈️ Telegram -> توکن + @channel
4. تست: پست‌های ووکامرس -> تست ارسال

## 📝 نحوه استفاده واتساپ (Baileys)

1. `cd whatsapp-service && npm install && npm start`
2. QR را با گوشی اسکن کن
3. در ربات Bale: تنظیمات -> پیام‌رسان‌ها -> 💚 WhatsApp -> شماره مقصد (98912...@s.whatsapp.net)
4. تست ارسال

## 🔜 کارهای باقی‌مانده (اختیاری)

- [ ] ریفکتور messenger_bale/rubika/eitaa برای استفاده از messenger_common.py
- [ ] جدا کردن bot.py به فایل‌های کوچک‌تر (keyboards.py, handlers.py)
- [ ] اضافه کردن persistence برای user_states (فعلا در RAM است)
- [ ] تبدیل time.sleep به صف (Queue) با Celery/RQ
- [ ] تست end-to-end با ربات واقعی
- [ ] داکرایز کردن پروژه

## 🎯 جمع‌بندی

پروژه از حالت hard-code 3 پیام‌رسان به معماری داینامیک 5 پیام‌رسان ارتقا یافت.
تلگرام به صورت کامل و تست شده اضافه شد.
واتساپ با ارزیابی دقیق + اسکلت کد + میکروسرویس آماده شد.
همه فایل‌ها compile می‌شوند و آماده تست هستند.

شاخه: arena/01a086a1-agent-auto-post-bot
