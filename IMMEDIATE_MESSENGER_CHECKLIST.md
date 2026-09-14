# ✅ چک‌لیست فوری - تنظیمات پیام‌رسان‌ها (تلگرام و واتساپ)

> وظیفه: وقتی کاربر می‌ره توی تنظیمات -> پیام‌رسان‌ها، بتونه واتساپ و تلگرام رو تنظیم و متصل کنه

---

## 🔍 بررسی‌های انجام شده - 2026-09-10

### 1. config.py
- [x] MESSENGER_LIST شامل 5 پیام‌رسان: bale, rubika, eitaa, telegram, whatsapp
- [x] MESSENGER_CONFIGS شامل telegram و whatsapp
- [x] DEFAULT_CONFIG شامل telegram و whatsapp
- [x] load_config() داینامیک همه پیام‌رسان‌ها را لود می‌کند

### 2. scheduler.py
- [x] MESSENGER_LIST شامل 5 پیام‌رسان
- [x] MESSENGER_EMOJIS شامل telegram و whatsapp
- [x] post_to_all_messengers() داینامیک 5 پیام‌رسان + whatsapp فقط chat_id
- [x] _resolve_messengers() داینامیک
- [x] _send_to_platforms() شامل بخش Telegram و WhatsApp
- [x] check_woocommerce_for_user() شامل همه پیام‌رسان‌ها
- [x] messenger_telegram و messenger_whatsapp ایمپورت شده

### 3. bot.py - کیبوردها
- [x] create_messengers_keyboard() - 5 پیام‌رسان با وضعیت ✅/⚪ و ایموجی
  - Bale 🔵
  - Rubika 🟢
  - Eitaa 🟡
  - Telegram ✈️
  - WhatsApp 💚
- [x] create_messenger_selection_keyboard() - داینامیک 5 پیام‌رسان برای انتخاب پست
  - فقط پیام‌رسان‌های کانفیگ شده را نشان می‌دهد
  - با ایموجی و تیک

### 4. bot.py - هندلرهای تنظیمات
- [x] elif "Bale" in text -> waiting_bale_token -> waiting_bale_channel
- [x] elif "Rubika" in text -> waiting_rubika_token -> waiting_rubika_chat
- [x] elif "Eitaa" in text -> waiting_eitaa_token -> waiting_eitaa_chat
- [x] elif "Telegram" in text -> waiting_telegram_token -> waiting_telegram_chat (جدید - اضافه شد)
  - توضیح از @BotFather
  - فرمت‌های chat_id: @channel, -100..., @username
  - هشدار: ربات باید ادمین باشد
  - تست اتصال
- [x] elif "WhatsApp" in text -> waiting_whatsapp_chat -> waiting_whatsapp_provider -> waiting_whatsapp_token -> waiting_whatsapp_phone_id (جدید - اضافه شد)
  - فرمت‌های شماره: 98912...@s.whatsapp.net, 120363...@g.us, 98912...
  - انتخاب provider: baileys (پیشنهادی) یا cloud
  - راهنمای راه‌اندازی whatsapp-service
  - برای cloud: توکن و phone_id

### 5. bot.py - سایر هندلرها
- [x] toggle_all_messengers - 5 پیام‌رسان را toggle می‌کند
- [x] test_product_posting - چک شامل telegram و whatsapp
- [x] submit_messenger_selection - messenger_names شامل telegram و whatsapp

### 6. messenger_telegram.py
- [x] وجود دارد (367 خط)
- [x] _format_product() با Markdown + دسته‌بندی + قیمت + تگ + لینک کوتاه
- [x] _send_with_retry() با handle 429 + retry
- [x] send_product() 3-tier: URL photo -> multipart -> text
- [x] send_manual_post() با split برای متن طولانی + caption limit 1024
- [x] is_configured()
- [x] compile می‌شود

### 7. messenger_whatsapp.py
- [x] وجود دارد (228 خط)
- [x] دو provider: baileys و cloud
- [x] _format_product() مناسب واتساپ
- [x] _send_via_baileys() با imageBase64
- [x] _send_via_cloud_api() با graph.facebook.com
- [x] send_product() با دانلود عکس
- [x] send_manual_post()
- [x] is_configured()
- [x] compile می‌شود

### 8. whatsapp-service/
- [x] index.js وجود دارد (Baileys microservice)
- [x] package.json
- [x] README.md
- [x] .gitignore

### 9. تست نهایی
- [x] python -m py_compile bot.py OK
- [x] python -m py_compile scheduler.py OK
- [x] python -m py_compile config.py OK
- [x] python -m py_compile woocommerce.py OK
- [x] python -m py_compile messenger_telegram.py OK
- [x] python -m py_compile messenger_whatsapp.py OK

---

## 🎯 جریان کاربر - تست دستی

1. کاربر در Bale ربات را /start می‌کند
2. منوی اصلی -> تنظیمات
3. تنظیمات -> پیام‌رسان‌ها
4. می‌بیند:
   ```
   ⚪ Bale 🔵
   ⚪ Rubika 🟢
   ⚪ Eitaa 🟡
   ⚪ Telegram ✈️
   ⚪ WhatsApp 💚
   ```
5. روی "⚪ Telegram ✈️" کلیک می‌کند
6. ربات می‌گوید: "توکن ربات Telegram خود را ارسال کنید: از @BotFather بگیرید"
7. کاربر توکن را می‌فرستد: "123456:ABC-..."
8. ربات می‌گوید: "شناسه کانال/گروه را ارسال کنید: @yourchannel یا -100..."
9. کاربر می‌فرستد: "@mychannel"
10. ربات تست می‌کند و می‌گوید: "✅ Telegram پیکربندی شد!"
11. برمی‌گردد به لیست، حالا "✅ Telegram ✈️"

12. روی "⚪ WhatsApp 💚" کلیک می‌کند
13. ربات می‌گوید: "شماره مقصد را ارسال کنید: 98912...@s.whatsapp.net"
14. کاربر می‌فرستد: "989123456789@s.whatsapp.net"
15. ربات می‌گوید: "نوع اتصال را انتخاب کنید: baileys یا cloud"
16. کاربر می‌فرستد: "baileys"
17. ربات می‌گوید: "✅ WhatsApp پیکربندی شد! برای Baileys: cd whatsapp-service && npm start"

18. حالا در پست دستی -> انتخاب پیام‌رسان‌ها، 5 پیام‌رسان را می‌بیند (اگر کانفیگ شده باشند)
19. در پست‌های ووکامرس -> تست ارسال، به همه پیام‌رسان‌های کانفیگ شده ارسال می‌شود

---

## ✅ نتیجه

**همه چیز کامل است و پوش شد.**

- کامیت: 6a5ccb9
- شاخه: arena/01a086a1-agent-auto-post-bot
- فایل‌های جدید: NEXT_SESSION_PROMPT.md + این چک‌لیست
- بکاپ زیپ هم پوش شد (برای اطمینان)

---

## 📋 برای سشن بعدی

این چک‌لیست را به عنوان Done علامت بزن و برو سراغ فاز 1 از UPGRADE_CHECKLIST.md:
- شکستن bot.py به ماژول‌ها

