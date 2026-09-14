# پرامپت برای سشن بعدی - AGENT AUTO POST BOT

> این فایل را کپی کن و به سشن بعدی بده. تمام وظایف و وضعیت فعلی پروژه در آن هست.

---

## 🎯 وظیفه اصلی سشن بعدی

تو یک سینیور پایتون دولوپر هستی که باید پروژه `AGENT_AUTO_POST_BOT` را ادامه بدهی.

**معماری کلی:**
- ربات اصلی فقط **Bale** است (`tapi.bale.ai`) - همه کاربران از طریق ربات Bale کنترل می‌کنند
- کاربران در بخش `تنظیمات -> پیام‌رسان‌ها` می‌توانند 5 پیام‌رسان مقصد را متصل کنند:
  - Bale (🔵) - bot_token + channel_id
  - Rubika (🟢) - bot_token + chat_id
  - Eitaa (🟡) - bot_token + chat_id
  - Telegram (✈️) - bot_token + chat_id (@channel یا -100...)
  - WhatsApp (💚) - chat_id + provider (baileys/cloud) + service_url

- پیام‌رسان‌ها فقط **مقصد** هستند (dest_only)، هیچ polling جداگانه ندارند
- `scheduler.py` هر 30 ثانیه پست‌های دستی و هر 2 دقیقه محصولات جدید ووکامرس را چک می‌کند
- ووکامرس به صورت **زنده** با ذخیره فقط ID کار می‌کند (نه کل محصول)

---

## ✅ چیزهایی که تا الان انجام شده (نباید دوباره بسازی)

1. **Telegram dest_only کامل:**
   - `messenger_telegram.py` با 3-tier fallback (URL عکس -> multipart -> متن) + retry روی 429
   - در `config.py` MESSENGER_LIST شامل telegram هست
   - در `scheduler.py` MESSENGER_LIST و post_to_all_messengers شامل telegram هست
   - در `bot.py` کیبوردها و هندلرهای telegram اضافه شد (waiting_telegram_token, waiting_telegram_chat)

2. **WhatsApp اسکلت کامل:**
   - `messenger_whatsapp.py` با دو provider: baileys (میکروسرویس Node.js) و cloud (رسمی)
   - `whatsapp-service/index.js` میکروسرویس Baileys با QR
   - در `config.py` و `scheduler.py` اضافه شده
   - در `bot.py` کیبوردها و هندلرهای whatsapp اضافه شد (waiting_whatsapp_chat, waiting_whatsapp_provider, waiting_whatsapp_token, waiting_whatsapp_phone_id)

3. **WooCommerce بازنویسی حرفه‌ای:**
   - `woocommerce.py` فقط ID ذخیره می‌کند: `known_product_ids.json` و `sent_product_ids.json`
   - `get_all_products()` با فیلتر دسته‌بندی و orderby=date desc
   - `check_new_products()` با تفاضل IDها
   - `get_next_product_to_post()` اولویت: محصول جدید > موجود (جدید به قدیم)
   - `mark_product_as_sent()` و `is_product_sent()` برای جلوگیری از تکراری
   - `get_categories()` برای نمایش دسته‌ها
   - در `bot.py`: toggle_live_new + category_filter + گزارش زنده check_products
   - در `config.py`: auto_post.live_new_product, categories, category_mode, resend_after_all
   - در `scheduler.py`: check_live_new_products_for_user هر 2 دقیقه + check_live_woocommerce_for_user

4. **معماری داینامیک:**
   - هر جا MESSENGER_LIST هست، اضافه کردن پیام‌رسان جدید فقط 3 قدم: اضافه به لیست + ساخت messenger_xxx.py + اضافه به ایموجی‌ها

5. **مستندات:**
   - README.md حرفه‌ای (550 خط)
   - TELEGRAM_INTEGRATION.md
   - WHATSAPP_EVALUATION.md (مقایسه API vs library)
   - UPGRADE_CHECKLIST.md (105 تسک در 4 فاز)
   - ANALYSIS_REPORT.md

6. **بکاپ:**
   - فایل زیپ `AGENT_AUTO_POST_BOT_FULL_BACKUP_*.zip` ساخته شده

---

## 🔍 چیزی که باید الان چک کنی (وظیفه فوری)

**وظیفه 1 تو الان اینه:**
وقتی کاربر می‌ره توی `تنظیمات -> پیام‌رسان‌ها`، باید بتونه **واتساپ و تلگرام** رو تنظیم و متصل کنه.

**چک کن:**

1. `bot.py` -> `create_messengers_keyboard()` آیا 5 پیام‌رسان را نشان می‌دهد؟ (Bale, Rubika, Eitaa, Telegram, WhatsApp) با وضعیت ✅/⚪
   - الان درست شد: باید 5 تا باشد

2. `bot.py` -> `create_messenger_selection_keyboard()` آیا برای پست دستی 5 پیام‌رسان را نشان می‌دهد؟
   - الان درست شد: باید بر اساس کانفیگ، همه را نشان دهد

3. `bot.py` -> هندلر `elif "Telegram" in text:` و `elif "WhatsApp" in text:` وجود دارد؟
   - الان اضافه شد: waiting_telegram_token, waiting_telegram_chat, waiting_whatsapp_chat, waiting_whatsapp_provider, waiting_whatsapp_token, waiting_whatsapp_phone_id

4. `bot.py` -> `toggle_all_messengers` آیا 5 پیام‌رسان را toggle می‌کند؟
   - الان درست شد

5. `bot.py` -> `test_product_posting` آیا telegram و whatsapp را هم چک می‌کند؟
   - الان درست شد

6. `config.py` -> MESSENGER_LIST شامل 5 تا هست؟
   - بله: ["bale", "rubika", "eitaa", "telegram", "whatsapp"]

7. `scheduler.py` -> MESSENGER_LIST و MESSENGER_EMOJIS و post_to_all_messengers و _resolve_messengers و _send_to_platforms شامل telegram/whatsapp هست؟
   - بله، کامل است

8. `messenger_telegram.py` و `messenger_whatsapp.py` وجود دارند و compile می‌شوند؟
   - بله

**اگر هر کدام نیست، کامل درست کن و پوش کن.**

---

## 📋 چک‌لیست کامل برای سشن بعدی (از UPGRADE_CHECKLIST.md)

### فاز 1 بحرانی - پایداری (اولویت 1)
- [ ] شکستن bot.py (8100 خط) به ماژول‌ها:
  - handlers/start.py, handlers/messengers.py, handlers/woocommerce.py, handlers/posts.py, handlers/media.py, handlers/admin.py, handlers/auth.py
  - keyboards/, utils/i18n.py
- [ ] State از RAM به SQLite (جدول user_states)
- [ ] Scheduler پایدار با APScheduler + JobStore
- [ ] رمزنگاری توکن‌ها با Fernet + .env
- [ ] Queue و Retry با exponential backoff + Dead Letter Queue

### فاز 2 بالا - محصول حرفه‌ای
- [ ] WooCommerce Webhook به جای polling (/webhook/woocommerce/{user_id})
- [ ] فیلترهای پیشرفته: موجودی، قیمت min/max، نوع محصول، تگ، ویژگی
- [ ] ساپورت محصول متغیر (variable product + variations)
- [ ] Template Engine کپشن: {title} {price} {link} {category} ...
- [ ] مدیریت رسانه: فشرده‌سازی + Object Storage (S3) + Cache
- [ ] Anti-Ban: تاخیر رندوم، Rate Limit per messenger، پراکسی ساپورت، handle 429

### فاز 3 متوسط - مقیاس‌پذیری
- [ ] Async (aiohttp) یا Celery
- [ ] لاگ ساختاریافته + Sentry + داشبورد ادمین (پست موفق/ناموفق)
- [ ] UX جدید: Inline Keyboard برای انتخاب پیام‌رسان، تقویم گرافیکی، پیش‌نمایش پست
- [ ] i18n حرفه‌ای: locales/fa.json, locales/en.json
- [ ] DevOps: Dockerfile + docker-compose + systemd + بکاپ خودکار + Health Check + CI/CD
- [ ] تست: pytest + coverage >70%

### فاز 4 آینده - هوش مصنوعی
- [ ] کپشن با AI (OpenAI), هشتگ خودکار, ترجمه خودکار, حذف بک‌گراند
- [ ] آنالیتیکس: ویو، کلیک با UTM، داشبورد تحت وب
- [ ] بیزینس: چند فروشگاه per user, نقش‌ها, تعرفه بر اساس تعداد پست, ارجاع, کوپن
- [ ] امنیت: حذف داده GDPR, 2FA ادمین, Rate Limit ربات
- [ ] پیام‌رسان‌های جدید: اینستاگرام, توییتر, لینکدین

---

## 🚀 دستورات شروع

```bash
cd /home/user/AGENT_AUTO_POST_BOT
git status
git log --oneline -10
python -m py_compile all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/*.py
cat UPGRADE_CHECKLIST.md
cat README.md | head -n 100
```

---

## 📦 ساختار پروژه

```
AGENT_AUTO_POST_BOT/
├── README.md (حرفه‌ای)
├── UPGRADE_CHECKLIST.md (105 تسک)
├── NEXT_SESSION_PROMPT.md (این فایل)
├── TELEGRAM_INTEGRATION.md
├── WHATSAPP_EVALUATION.md
├── .gitignore
├── AGENT_AUTO_POST_BOT_FULL_BACKUP_*.zip
├── whatsapp-service/
│   ├── index.js (Baileys)
│   ├── package.json
│   └── README.md
└── all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/
    ├── bot.py (8100 خط - باید ماژولار شود)
    ├── config.py (MESSENGER_LIST 5 تایی)
    ├── woocommerce.py (ID-only live)
    ├── scheduler.py (داینامیک 5 پیام‌رسان + لایو چک)
    ├── messenger_bale.py
    ├── messenger_rubika.py
    ├── messenger_eitaa.py
    ├── messenger_telegram.py (جدید)
    ├── messenger_whatsapp.py (جدید)
    ├── messenger_common.py
    ├── database.py
    ├── auth_manager.py
    ├── logger.py
    ├── requirements.txt
    └── users/{chat_id}/ (هر کاربر جدا)
```

---

## ⚠️ نکات مهم

- زبان: فارسی
- کنترل‌گر اصلی فقط Bale - بقیه مقصد فقط
- هیچ وقت توکن‌ها را plain text لاگ نکن
- هر تغییر را جداگانه کامیت و پوش کن به شاخه `arena/01a086a1-agent-auto-post-bot`
- قبل از هر فاز بزرگ، یک زیپ بکاپ بگیر
- تست: `python -m py_compile` بعد از هر تغییر

---

## 🎯 خروجی مورد انتظار سشن بعدی

1. تایید کن که تنظیمات پیام‌رسان‌ها (تلگرام/واتساپ) کامل کار می‌کند
2. اگر نه، درست کن و پوش کن
3. سپس فاز 1 را شروع کن: شکستن bot.py به ماژول‌ها
4. هر قدم را در UPGRADE_CHECKLIST.md تیک بزن

> آخرین آپدیت: 2026-09-10 - نسخه شامل تلگرام/واتساپ کامل + ووکامرس لایو + README حرفه‌ای

