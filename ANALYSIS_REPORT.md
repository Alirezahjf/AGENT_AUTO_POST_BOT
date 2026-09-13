# گزارش بررسی دقیق پروژه AGENT_AUTO_POST_BOT

تاریخ بررسی: 2026-09-09

## 1. نمای کلی پروژه
این پروژه یک **ربات مدیریت و ارسال خودکار پست** است که:
- هسته کنترل آن روی **پیام‌رسان بله (Bale)** اجرا می‌شود (`tapi.bale.ai`)
- محصولات را از **WooCommerce** می‌گیرد
- پست‌ها را به صورت دستی (زمان‌بندی شده) یا خودکار (WooCommerce) به 3 پیام‌رسان **Bale, Rubika, Eitaa** ارسال می‌کند
- سیستم **احراز هویت چندکاربره** + **خرید اشتراک با کیف پول بله** دارد
- هر کاربر دیتابیس و کانفیگ اختصاصی خودش را در `users/<chat_id>/` دارد

```
AGENT_AUTO_POST_BOT/
└── all_pg_agnet/
    └── AGENT-MANAGER_BOTS_MASSENGER/
        ├── bot.py (4000+ خط - هسته اصلی)
        ├── config.py (مدیریت کانفیگ)
        ├── database.py (PostDatabase)
        ├── auth_manager.py (احراز هویت + پرداخت)
        ├── auth_handlers.py (هندلر ورود/خرید)
        ├── scheduler.py (زمان‌بند 30 ثانیه‌ای)
        ├── messenger_bale.py
        ├── messenger_rubika.py
        ├── messenger_eitaa.py
        ├── woocommerce.py
        ├── logger.py
        ├── config.json (کانفیگ سراسری)
        └── users/
            └── 261406913/
                └── config.json
```

---

## 2. تحلیل فایل به فایل

### 2.1 `config.py`
- `DEFAULT_CONFIG` شامل `woocommerce`, `messengers` (bale,rubika,eitaa), `auto_post`
- `load_config()` با `deep_merge` کار می‌کند - خوبه
- **مشکل:** به صورت hard-code فقط 3 پیام‌رسان را چک می‌کند:
```python
if "eitaa" not in config["messengers"]: ...
if "rubika" not in ...
if "bale" not in ...
```
برای اضافه کردن تلگرام باید اینجا هم اضافه شود.

- توابع `load_user_config` و `save_user_config` وابسته به `AuthManager` هستند - وابستگی دایره‌ای (circular import) ایجاد می‌کند.

### 2.2 `database.py` - `PostDatabase`
جداول:
- `scheduled_posts` - پست‌های زمان‌بندی شده
- `posting_history` - تاریخچه
- `content_media` - کتابخانه رسانه با `title` (قابلیت جستجو)
- `content_text` - کتابخانه متن
- `draft_posts` - پیش‌نویس
- `archived_posts` - آرشیو

**نکات مثبت:**
- Migration برای اضافه کردن ستون‌ها دارد
- Index روی title
- جستجوی case-insensitive

**باگ‌ها:**
- `cleanup_old_history` از `timedelta` استفاده می‌کند ولی import نشده!
```python
from datetime import datetime # فقط datetime هست
cutoff_date = datetime.now() - timedelta(...) # NameError
```
- مسیر DB به صورت نسبی `posts.db` است، اگر از پوشه دیگر اجرا شود می‌شکند.

### 2.3 `messenger_*.py` - الگوی مشترک
هر سه فایل ساختار یکسان دارند:
```python
def _clean_html(text)
def _shorten_url(url) # tinyurl + is.gd + decode
def _format_product(product, config, is_new)
def _send_with_retry(...)
def send_product(product, config, is_new)
def send_manual_post(caption, media_content, media_type, config)
```

**تفاوت‌ها:**
- **Bale**: `https://tapi.bale.ai/bot{token}/sendPhoto` - می‌تواند URL مستقیم عکس را بفرستد (مزیت)
- **Rubika**: دو مرحله‌ای `requestSendFile` -> `upload_url` -> `sendFile` (طبق مستندات رسمی)
- **Eitaa**: `https://eitaayar.ir/api/{token}/sendFile`

**مشکلات فعلی:**
- کد تکراری زیاد (DRY نقض شده) - `_clean_html`, `_shorten_url` در هر 3 فایل کپی شده
- هیچ اینترفیس مشترکی ندارند
- اضافه کردن پیام‌رسان جدید = کپی کل فایل + تغییر دستی 10 جای دیگر

### 2.4 `bot.py` - غول 4000 خطی
این فایل همه چیز است: ترجمه، کیبوردها، هندلرها، state management.

**ساختار:**
- `LANGUAGES` = دیکشنری fa/en با 60+ کلید
- `get_user_lang`, `t(chat_id, key)` - سیستم ترجمه
- تاریخ شمسی با `jdatetime` + timezone تهران
- `send_message`, `edit_message`, `send_photo`, `send_video` - فقط برای Bale
- ده‌ها تابع `create_*_keyboard`
- `handle_message` - تابع 3000 خطی که همه callback ها را هندل می‌کند!

**State Management:**
```python
user_states = {} # در حافظه RAM
# ساختار: {chat_id: {"state": "...", "media_id": ..., "selected_messengers": []}}
def get_state, set_state, clear_state
```
- اگر ربات ریستارت شود همه state ها می‌پرند
- بدون persistence

**نقاط وابستگی به پیام‌رسان‌ها:**
```python
# در create_messengers_keyboard
bale_status = "✅" if user_config["messengers"]["bale"]["bot_token"] else "⚪"
rubika_status = ...
eitaa_status = ...

# در create_messenger_selection_keyboard
if user_config["messengers"]["bale"]["bot_token"] and ...
    available_messengers.append("bale")
# همین برای rubika, eitaa

# در toggle_all_messengers
available = []
if bale... append bale
if rubika... append rubika
if eitaa... append eitaa
```

برای تلگرام باید 4-5 جای دیگر هم دستی اضافه شود.

### 2.5 `scheduler.py`
- دو set برای جلوگیری از ارسال مضاعف: `_executed_posts`, `_executed_wc_jobs` با Lock
- `post_to_all_messengers` - به ترتیب bale -> rubika -> eitaa با sleep 2 ثانیه
- `_send_to_platforms` - ارسال پست دستی (کپی تقریباً مشابه post_to_all)
- `check_woocommerce_for_user` - چک زمان‌بندی auto_post هر کاربر
- `post_scheduled_posts_for_user` - چک پست‌های دستی
- `check_schedule` - حلقه اصلی هر 30 ثانیه برای همه کاربران تایید شده
- `start_scheduler` - thread دایمون

**مشکلات:**
- دوباره hard-code سه پیام‌رسان
- `download_bale_file` هم در bot.py هم در scheduler.py کپی شده
- اگر یک پیام‌رسان کند باشد کل حلقه بلوکه می‌شود (sync)

### 2.6 `auth_manager.py`
بسیار کامل - 1200 خط
- جداول: `users`, `access_requests`, `temp_tokens`, `activity_log`, `admins`, `purchase_tokens`, `payments`
- `generate_token` با `secrets.token_urlsafe(32)` - امن
- `hash_token` با SHA256
- `create_purchase_token` - توکن دائمی بدون انقضا (برای خرید)
- `verify_purchase_token(chat_id)` - چک مالکیت توکن (خیلی مهم امنیتی)
- `approve_user_by_purchase` - پس از پرداخت
- محیط کاربر `_create_user_environment` - ساخت پوشه و فایل‌های اولیه

**نکته امنیتی خوب:** توکن فقط برای صاحبش معتبر است.

### 2.7 `auth_handlers.py`
- `create_auth_keyboard_fa/en` - با دکمه خرید
- `send_invoice_to_user` - ارسال فاکتور از طریق کیف پول بله (`provider_token` = wallet_token)
- `handle_successful_payment` - پس از پرداخت موفق: ثبت پرداخت + ساخت توکن + تایید کاربر + اطلاع به ادمین
- `handle_pre_checkout` - تایید پیش از پرداخت

**وابستگی شدید به بله:** کل سیستم پرداخت فقط با بله کار می‌کند.

### 2.8 `woocommerce.py`
- `get_all_products` - pagination با 100 محصول در هر صفحه
- `check_new_products` - مقایسه با known_products.json
- `decode_permalink` - unquote برای لینک‌های فارسی

---

## 3. نقاط قوت
1.  **چندکاربره واقعی:** هر کاربر DB و کانفیگ جدا
2.  **سیستم احراز + خرید:** کامل و امن
3.  **تقویم شمسی/میلادی:** با timezone تهران
4.  **جلوگیری از ارسال تکراری:** با set + lock
5.  **کتابخانه محتوا:** رسانه با title و جستجو
6.  **مدیریت پست:** زمان‌بندی، پیش‌نویس، آرشیو، تاریخچه
7.  **لاگینگ:** logger مرکزی

## 4. نقاط ضعف و باگ‌های فنی

### 4.1 معماری
- **Monolith bot.py:** 4000 خط در یک فایل - نگهداری سخت
- **کپی کد:** 3 messenger فایل 70% مشترک هستند
- **Hard-code پیام‌رسان‌ها:** در 10+ نقطه نام پیام‌رسان‌ها به صورت رشته نوشته شده
- **وابستگی دایره‌ای:** config.py -> auth_manager.py -> config.py
- **بدون requirements.txt:** مشخص نیست چه پکیج‌هایی لازم است (requests, jdatetime, pytz)
- **بدون .gitignore:** احتمال کامیت شدن bot.log, *.db, auth.db
- **بدون تست:** هیچ unit test ندارد

### 4.2 باگ‌های مشخص
- `database.py: cleanup_old_history` -> `timedelta` import نشده
- `user_states` در RAM - با ریستارت می‌پرد
- `config` به صورت global در bot.py و scheduler.py - race condition احتمالی
- `requests` بدون Session - هر درخواست یک TCP connection جدید
- `time.sleep(2)` بین ارسال به هر پیام‌رسان - اگر 10 پیام‌رسان شود 20 ثانیه تاخیر

### 4.3 امنیت
- توکن‌ها در config.json به صورت plain text
- `bot_token` در لاگ‌ها ممکن است لو برود (logger.debug response کامل)
- هیچ rate limiting برای درخواست‌های دسترسی

---

## 5. پلن اضافه کردن تلگرام و سایر پیام‌رسان‌ها

### 5.1 هدف
دو سناریو ممکن:

**سناریو A (پیشنهادی فعلی):** تلگرام فقط به عنوان **مقصد ارسال پست** اضافه شود (مثل Bale/Rubika/Eitaa)
- کنترل ربات همچنان روی Bale بماند
- کاربر می‌تواند کانال تلگرامش را هم اضافه کند و پست‌ها همزمان به تلگرام هم برود

**سناریو B (پیشرفته):** ربات کنترل هم روی تلگرام بیاید
- یعنی bot.py هم Bale را poll کند هم Telegram را
- کاربر بتواند از تلگرام هم ربات را کنترل کند
- پیچیده‌تر است - نیاز به refactor اساسی

**برای شروع سناریو A را پیاده می‌کنیم** - سریع، کم ریسک، و نیاز فعلی را حل می‌کند.

### 5.2 طراحی جدید - Messenger Abstraction Layer

#### قدم 1: ساخت `messenger_interface.py`
```python
from abc import ABC, abstractmethod

class BaseMessenger(ABC):
    name: str # "telegram"
    display_name: str # "Telegram"
    emoji: str # "✈️"
    
    @abstractmethod
    def send_product(self, product, config, is_new=False) -> bool: ...
    
    @abstractmethod
    def send_manual_post(self, caption, media_content, media_type, config) -> bool: ...
    
    @abstractmethod
    def is_configured(self, user_config) -> bool: ...
```

#### قدم 2: ساخت `messenger_telegram.py`
الگو دقیقاً مثل بقیه:

```python
# messenger_telegram.py
import requests
import time
import re
from urllib.parse import unquote
from logger import logger

MAX_RETRY = 3
RETRY_DELAY = 2

def _clean_html(text): ...
def _shorten_url(url): ...
def _format_product(product, config, is_new=False): ...
def _send_with_retry(api, method, data=None, files=None, retry=0): ...

def send_product(product, config, is_new=False):
    telegram = config["messengers"]["telegram"]
    if not telegram.get("bot_token") or not telegram.get("chat_id"):
        return False
    api = f"https://api.telegram.org/bot{telegram['bot_token']}"
    caption = _format_product(product, config, is_new)
    images = product.get("images", [])
    # سعی 1: ارسال با URL عکس
    # سعی 2: دانلود و آپلود multipart
    # سعی 3: فقط متن

def send_manual_post(caption, media_content, media_type, config):
    # مشابه bale ولی با api.telegram.org
    # photo -> sendPhoto, video -> sendVideo
```

**جزئیات API تلگرام:**
- `sendPhoto`: `chat_id`, `photo` (file_id یا URL یا multipart), `caption`, `parse_mode`
- `sendVideo`: مشابه
- `sendMessage`: `chat_id`, `text`
- محدودیت کپشن 1024 کاراکتر (باید truncate کرد)
- chat_id می‌تواند `@channelusername` یا عدد منفی مثل `-1001234567890`

#### قدم 3: `config.py` - اضافه کردن تلگرام
```python
DEFAULT_CONFIG = {
    "messengers": {
        "bale": {...},
        "rubika": {...},
        "eitaa": {...},
        "telegram": {
            "bot_token": "",
            "chat_id": "" # @channel یا -100...
        }
    }
}

# در load_config:
for messenger in ["bale", "rubika", "eitaa", "telegram"]:
    if messenger not in config["messengers"]:
        config["messengers"][messenger] = DEFAULT_CONFIG["messengers"][messenger].copy()
```

#### قدم 4: `bot.py` - داینامیک کردن کیبوردها

**قبل (hard-code):**
```python
bale_status = "✅" if ... else "⚪"
rubika_status = ...
eitaa_status = ...
```

**بعد (dynamic):**
```python
MESSENGER_LIST = ["bale", "rubika", "eitaa", "telegram"]
MESSENGER_EMOJIS = {
    "bale": "🔵",
    "rubika": "🟢",
    "eitaa": "🟡",
    "telegram": "✈️"
}

def create_messengers_keyboard(chat_id, user_config):
    keyboard = []
    for name in MESSENGER_LIST:
        token = user_config["messengers"].get(name, {}).get("bot_token")
        status = "✅" if token else "⚪"
        keyboard.append([{"text": f"{status} {name.capitalize()}"}])
    keyboard.append([{"text": t(chat_id, "back_to_settings")}])
    return {"keyboard": keyboard, "resize_keyboard": True}

def create_messenger_selection_keyboard(...):
    available = []
    for m in MESSENGER_LIST:
        cfg = user_config["messengers"].get(m, {})
        # bale: channel_id, بقیه: chat_id
        chat_key = "channel_id" if m == "bale" else "chat_id"
        if cfg.get("bot_token") and cfg.get(chat_key):
            available.append(m)
    # بقیه منطق مثل قبل ولی با loop
```

همچنین در `handle_message` برای `"Bale" in text`, `"Rubika" in text` باید `"Telegram" in text` هم اضافه شود.

#### قدم 5: `scheduler.py`

**post_to_all_messengers:**
```python
import messenger_telegram

def post_to_all_messengers(product, config, is_new=False):
    platforms_sent = []
    messenger_modules = {
        "bale": messenger_bale,
        "rubika": messenger_rubika,
        "eitaa": messenger_eitaa,
        "telegram": messenger_telegram
    }
    for name, module in messenger_modules.items():
        if config["messengers"].get(name, {}).get("bot_token"):
            try:
                if module.send_product(product, config, is_new):
                    platforms_sent.append(name)
            except Exception as e:
                logger.error(f"❌ {name} error: {e}")
            time.sleep(1) # یا 0.5 برای سرعت بیشتر
    return platforms_sent
```

**_resolve_messengers:**
```python
def _resolve_messengers(messengers_str, user_config):
    configured = []
    for name in ["bale", "rubika", "eitaa", "telegram"]:
        cfg = user_config["messengers"].get(name, {})
        chat_key = "channel_id" if name == "bale" else "chat_id"
        if cfg.get("bot_token") and cfg.get(chat_key):
            configured.append(name)
    if not messengers_str or messengers_str.strip().lower() == 'all':
        return configured
    requested = [m.strip().lower() for m in messengers_str.split(',')]
    return [m for m in requested if m in configured]
```

**_send_to_platforms:** مشابه، یک if برای telegram اضافه شود:
```python
if "telegram" in selected_messengers:
    try:
        telegram_cfg = user_config["messengers"]["telegram"]
        if telegram_cfg.get("bot_token") and telegram_cfg.get("chat_id"):
            content_to_send = media_content
            if not content_to_send and media_path:
                bot_token = global_config["messengers"]["bale"]["bot_token"]
                content_to_send = download_bale_file(media_path, bot_token)
            if content_to_send or True: # تلگرام می‌تواند URL هم بگیرد
                if messenger_telegram.send_manual_post(...):
                    platforms_sent.append("telegram")
    except Exception as e:
        logger.error(...)
```

### 5.3 فایل‌های جدید پیشنهادی
```
messenger_interface.py   # Base class (اختیاری ولی خوب)
messenger_telegram.py    # پیاده‌سازی تلگرام
messenger_bale.py        # refactor برای ارث‌بری (اختیاری)
messengers/
    __init__.py          # registry
    base.py
    bale.py
    rubika.py
    eitaa.py
    telegram.py
```

### 5.4 تغییرات در UI
- در منوی پیام‌رسان‌ها: دکمه جدید `✈️ Telegram`
- در انتخاب مقصد پست: `✈️ Telegram` با تیک
- در تنظیمات: `telegram` مثل بقیه دو مرحله‌ای: اول توکن، بعد chat_id
- پیام موفقیت: `✈️ Telegram` اضافه شود

### 5.5 تست
1. یک ربات تلگرام از @BotFather بساز
2. ربات را ادمین کانال کن
3. chat_id کانال را بگیر (`@username` یا با forward کردن پیام به @userinfobot)
4. در ربات Bale: تنظیمات -> پیام‌رسان‌ها -> Telegram -> توکن و chat_id را وارد کن
5. تست محصول: پست‌های ووکامرس -> تست ارسال محصولات
6. تست دستی: پست جدید -> انتخاب رسانه -> کپشن -> تاریخ -> انتخاب Telegram

---

## 6. نقشه راه آینده (پس از تلگرام)

### فاز 1: تلگرام (همین الان)
- [x] تحلیل پروژه
- [ ] ساخت messenger_telegram.py
- [ ] آپدیت config.py
- [ ] آپدیت bot.py (کیبوردها + هندلر)
- [ ] آپدیت scheduler.py
- [ ] تست

### فاز 2: ریفکتور
- [ ] ساخت messenger_interface.py و انتقال کد مشترک (_clean_html, _shorten_url)
- [ ] ساخت requirements.txt
- [ ] ساخت .gitignore
- [ ] فیکس باگ timedelta
- [ ] تبدیل user_states به SQLite یا فایل JSON برای persistence
- [ ] جدا کردن bot.py به چند فایل: keyboards.py, handlers.py, translations.py

### فاز 3: پیام‌رسان‌های بیشتر
- واتساپ (از طریق API مثل Ultramsg یا WhatsApp Business)
- دیسکورد (webhook)
- اینستاگرام (Graph API)
- توییتر/X

### فاز 4: بهبودهای بزرگ
- وب‌هوک به جای polling
- پنل تحت وب برای مدیریت
- صف (Queue) با Celery یا RQ به جای time.sleep
- داکرایز کردن پروژه

---

## 7. جمع‌بندی
پروژه از نظر منطق کسب‌وکار کامل و هوشمندانه نوشته شده (چندکاربره، خرید، زمان‌بندی، آرشیو). ضعف اصلی **معماری** است: کد تکراری و hard-code بودن نام پیام‌رسان‌ها. با یک **لایه انتزاعی ساده** می‌توان به راحتی تلگرام و هر پیام‌رسان دیگری را اضافه کرد بدون دست زدن به 10 نقطه مختلف.

**پیشنهاد نهایی:** همین الان فاز 1 را شروع کنیم - من می‌توانم `messenger_telegram.py` را بسازم و تغییرات لازم در 3 فایل اصلی را اعمال کنم. بعدش تست می‌کنیم.

اگر موافقی بگو تا پیاده‌سازی را شروع کنم.
