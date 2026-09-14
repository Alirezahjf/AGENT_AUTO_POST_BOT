# 📘 راهنمای یکپارچه‌سازی تلگرام - Telegram Integration Guide

## ✅ وضعیت فعلی
تلگرام به عنوان **مقصد ارسال** (dest_only) به پروژه اضافه شد. ربات کنترل همچنان Bale است.

### فایل‌های تغییر یافته:
- `config.py`: اضافه شدن `telegram` به `MESSENGER_LIST` و `DEFAULT_CONFIG` + لود داینامیک
- `bot.py`: 
  - `MESSENGER_LIST`, `MESSENGER_EMOJIS`, `MESSENGER_DISPLAY_NAMES`
  - `create_messengers_keyboard` داینامیک
  - `create_messenger_selection_keyboard` داینامیک
  - `toggle_all_messengers` داینامیک
  - `test_product_posting` بررسی داینامیک
  - هندلرهای `waiting_telegram_token` و `waiting_telegram_chat`
  - تشخیص متن با ایموجی `✈️`
- `scheduler.py`:
  - `post_to_all_messengers` داینامیک با `messenger_telegram`
  - `_resolve_messengers` داینامیک
  - `_send_to_platforms` اضافه شدن شاخه تلگرام
  - `has_messenger` داینامیک
- `messenger_telegram.py`: پیاده‌سازی کامل (جدید)
- `messenger_common.py`: توابع مشترک (جدید)
- `config.json`: اضافه شدن placeholder تلگرام
- `database.py`: فیکس باگ `timedelta` import

## 🚀 نحوه پیکربندی تلگرام

### 1. ساخت ربات در @BotFather
```
1. به @BotFather در تلگرام بروید
2. /newbot را بفرستید
3. نام ربات (مثلا MyShop Bot) را وارد کنید
4. یوزرنیم ربات (باید به bot ختم شود، مثلا myshop_post_bot)
5. توکن دریافتی را کپی کنید: 1234567890:AAHxxxx
```

### 2. اضافه کردن ربات به کانال
```
1. کانال تلگرام بسازید (مثلا @yourshop)
2. ربات را به عنوان ادمین کانال اضافه کنید
   - دسترسی Post Messages حتما فعال باشد
3. برای کانال خصوصی، آیدی عددی را بگیرید:
   - یک پیام از کانال به @userinfobot فوروارد کنید
   - آیدی مثل -1001234567890 را کپی کنید
```

### 3. تنظیم در ربات Bale
```
1. در ربات Bale: تنظیمات -> پیام‌رسان‌ها
2. ✈️ Telegram را انتخاب کنید
3. توکن را ارسال کنید
4. شناسه کانال را ارسال کنید:
   - @yourchannel یا -1001234567890
```

### 4. تست
```
پست‌های ووکامرس -> تست ارسال محصولات
باید در همه پیام‌رسان‌های فعال از جمله تلگرام ارسال شود
```

## 📝 فرمت‌های قابل قبول chat_id
- `@yourchannel` - یوزرنیم کانال عمومی
- `-1001234567890` - آیدی عددی کانال (خصوصی/عمومی)
- `@username` - یوزرنیم کاربر برای چت خصوصی
- `123456789` - آیدی عددی کاربر

## 🔧 جزئیات فنی پیاده‌سازی

### messenger_telegram.py
- `send_product`: ارسال محصول ووکامرس
  - تلاش 1: ارسال URL عکس مستقیم (تلگرام خودش دانلود می‌کند)
  - تلاش 2: دانلود عکس و آپلود multipart
  - تلاش 3: فقط متن
  - پشتیبانی Markdown + fallback بدون Markdown
  - مدیریت محدودیت 1024 کاراکتر کپشن و 4096 متن
- `send_manual_post`: ارسال پست دستی زمان‌بندی شده
  - پشتیبانی photo/video + متن طولانی (chunking)
- `_send_with_retry`: مدیریت Rate Limit (429) + retry_after
- `is_configured`: بررسی پیکربندی

### محدودیت‌های تلگرام
- کپشن عکس/ویدیو: 1024 کاراکتر
- متن: 4096 کاراکتر
- Rate Limit: 30 پیام/ثانیه برای یک چت، 20 پیام/دقیقه در گروه
- فایل: حداکثر 50MB برای Bot API

## 🛡️ امنیت
- توکن تلگرام را هرگز در گیت کامیت نکنید (در .gitignore هست)
- از `users/{chat_id}/config.json` برای هر کاربر جداگانه ذخیره می‌شود
- ربات باید فقط ادمین کانال باشد، نه با دسترسی کامل

## 🔄 توسعه آینده (داینامیک)
با معماری جدید، افزودن پیام‌رسان جدید فقط نیاز به:
1. اضافه کردن به `MESSENGER_LIST` در `config.py` و `bot.py` و `scheduler.py`
2. ساخت `messenger_xxx.py` با دو تابع `send_product` و `send_manual_post`
3. اضافه کردن به `MESSENGER_EMOJIS` و `MESSENGER_DISPLAY_NAMES`

همه کیبوردها و چک‌ها به صورت خودکار داینامیک هستند.
