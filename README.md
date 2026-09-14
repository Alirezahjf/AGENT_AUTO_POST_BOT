# 🤖 AGENT AUTO POST BOT - ربات هوشمند پست‌گذاری خودکار

> **ایجنت هوشمند پست‌گذاری** که با کنترل ربات **Bale** به شما اجازه می‌دهد فروشگاه ووکامرس خود را به صورت خودکار، زمان‌بندی شده و بدون تکراری به 5 پیام‌رسان مختلف متصل کنید.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Bale](https://img.shields.io/badge/Bale-Main_Controller-00A8E8?style=for-the-badge)
![Telegram](https://img.shields.io/badge/Telegram-Destination-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![WooCommerce](https://img.shields.io/badge/WooCommerce-Live_Detection-96588A?style=for-the-badge&logo=woocommerce&logoColor=white)

---

## 📋 فهرست مطالب
- [معرفی](#-معرفی)
- [معماری](#-معماری)
- [ویژگی‌ها](#-ویژگی‌ها)
- [پیام‌رسان‌های پشتیبانی شده](#-پیام‌رسان‌های-پشتیبانی-شده)
- [نصب و راه‌اندازی](#-نصب-و-راه‌اندازی)
- [پیکربندی](#-پیکربندی)
- [نحوه کار ووکامرس - تشخیص زنده](#-نحوه-کار-ووکامرس---تشخیص-زنده)
- [استفاده](#-استفاده)
- [ساختار پروژه](#-ساختار-پروژه)
- [API پیام‌رسان‌ها](#-api-پیام‌رسان‌ها)
- [توسعه پیام‌رسان جدید](#-توسعه-پیام‌رسان-جدید)
- [واتساپ](#-واتساپ)
- [عیب‌یابی](#-عیب‌یابی)
- [نقشه راه](#-نقشه-راه)

---

## 🌟 معرفی

**AGENT AUTO POST BOT** یک ربات چندکاربره و هوشمند است که:

1.  **کنترل‌گر اصلی آن Bale است** - همه کاربران از طریق ربات Bale ربات را کنترل می‌کنند
2.  هر کاربر می‌تواند پیام‌رسان‌های خودش (Bale, Rubika, Eitaa, Telegram, WhatsApp) را متصل کند
3.  محصولات ووکامرس به صورت **زنده** تشخیص داده می‌شوند و بلافاصله پست می‌شوند
4.  پست‌های دستی را می‌توان زمان‌بندی کرد (تقویم شمسی/میلادی با timezone تهران)
5.  سیستم احراز هویت + خرید اشتراک با کیف پول Bale دارد
6.  هر کاربر دیتابیس و کانفیگ اختصاصی خودش را دارد

### چرا Bale به عنوان کنترل‌گر؟
- پرداخت درون‌برنامه‌ای با کیف پول Bale (بدون نیاز به درگاه خارجی)
- کاربران ایرانی به Bale دسترسی راحت‌تری دارند
- API ساده و پایدار `tapi.bale.ai`
- پیام‌رسان‌های مقصد فقط وظیفه ارسال دارند، نه کنترل

---

## 🏗️ معماری

```
┌─────────────────────────────────────────────────────────────┐
│                    Bale Bot (Main Controller)               │
│  - getUpdates polling (تنها جایی که پیام دریافت می‌شود)     │
│  - مدیریت کاربران، احراز هویت، پرداخت، تنظیمات              │
│  - UI کامل به دو زبان فارسی/انگلیسی                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │  users/{chat_id}/config.json
                       │  {
                       │    "messengers": {
                       │      "bale": {"bot_token": "", "channel_id": "@xxx"},
                       │      "telegram": {"bot_token": "", "chat_id": "@yyy"},
                       │      "whatsapp": {"chat_id": "98912...@s.whatsapp.net"}
                       │    },
                       │    "woocommerce": {"url": "", "consumer_key": "", ...},
                       │    "auto_post": {
                       │      "enabled": true,
                       │      "live_new_product": true,  # تشخیص زنده
                       │      "categories": [],  # فیلتر دسته‌بندی
                       │      "schedule": {"saturday": {"enabled": true, "times": ["09:00"]}}
                       │    }
                       │  }
                       │
        ┌──────────────┼──────────────┬──────────────┐
        │              │              │              │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │  Bale   │    │ Rubika  │    │  Eitaa  │    │Telegram │  WhatsApp
   │  API    │    │   API   │    │   API   │    │   API   │  Baileys
   └─────────┘    └─────────┘    └─────────┘    └─────────┘
        Destination Only - فقط ارسال
```

### جریان پست‌گذاری ووکامرس (جدید - زنده)

```
WooCommerce Site
      │
      │  wp-json/wc/v3/products?orderby=date&order=desc&status=publish
      │  (هر 2 دقیقه برای محصول جدید، هر 30 ثانیه برای زمان‌بندی)
      ▼
┌─────────────────┐
│ woocommerce.py  │
│ - get_all_products() - لایو از API، مرتب جدید به قدیم
│ - _load_known_ids() - فقط ID ها (سبک)
│ - check_new_products() - تشخیص ID جدید
│ - get_next_product_to_post() - اولویت: جدید > موجود
│ - mark_product_as_sent() - جلوگیری از تکراری
└────────┬────────┘
         │
         ├─> محصول جدید؟  ──> فورا پست (اگر live_new_product=true)
         │                  هر 2 دقیقه چک می‌شود
         │
         └─> زمان‌بندی رسیده؟ ──> پست زمان‌بندی شده
                               (شنبه 09:00، یکشنبه 14:00، ...)
```

---

## ✨ ویژگی‌ها

### 🤖 کنترل هوشمند
- [x] ربات اصلی Bale با پشتیبانی کامل فارسی/انگلیسی
- [x] تقویم شمسی/میلادی با timezone تهران
- [x] سیستم state مدیریت شده با persistence
- [x] چندکاربره واقعی - هر کاربر DB و کانفیگ جدا

### 🛒 ووکامرس - تشخیص زنده (جدید)
- [x] **ذخیره فقط ID** - نه کل محصول (سبک و سریع)
- [x] **تشخیص زنده محصول جدید** - هر 2 دقیقه چک، بلافاصله پست
- [x] **اولویت‌بندی هوشمند**: محصول جدید > محصول موجود (جدید به قدیم)
- [x] **فیلتر دسته‌بندی**: کاربر می‌تواند انتخاب کند از چه دسته‌ای پست شود
- [x] **جلوگیری از تکراری**: `sent_product_ids.json` - هیچ محصولی دو بار پست نمی‌شود
- [x] **مرتب‌سازی**: همیشه از جدیدترین به قدیمی‌ترین
- [x] **لایو بودن**: بدون نیاز به ذخیره همه محصولات در فایل حجیم

### 📮 مدیریت پست
- [x] پست جدید با انتخاب از کتابخانه رسانه
- [x] انتخاب چند پیام‌رسان مقصد با تیک
- [x] زمان‌بندی با تقویم گرافیکی
- [x] ویرایش پست زمان‌بندی شده (رسانه، کپشن، زمان، همه)
- [x] پیش‌نویس، آرشیو، تاریخچه

### 📂 کتابخانه محتوا
- [x] آپلود رسانه با عنوان (جلوگیری از عنوان تکراری)
- [x] جستجو در رسانه‌ها بر اساس عنوان
- [x] آپلود متن/کپشن
- [x] مشاهده، حذف، آرشیو

### 👮 پنل ادمین
- [x] مدیریت کاربران، ادمین‌ها
- [x] درخواست‌های دسترسی (تایید/رد با دلیل)
- [x] گزارش فعالیت
- [x] خرید اشتراک با کیف پول Bale

---

## 📱 پیام‌رسان‌های پشتیبانی شده

| پیام‌رسان | وضعیت | نوع | ایموجی | نیازمندی |
|-----------|--------|-----|---------|----------|
| **Bale** | ✅ فعال - کنترل‌گر اصلی | کنترل + مقصد | 🔵 | bot_token + channel_id |
| **Rubika** | ✅ فعال | مقصد | 🟢 | bot_token + chat_id |
| **Eitaa** | ✅ فعال | مقصد | 🟡 | bot_token + chat_id |
| **Telegram** | ✅ فعال - جدید | مقصد | ✈️ | bot_token + chat_id (@channel یا -100...) |
| **WhatsApp** | 🚧 اسکلت + سرویس | مقصد | 💚 | chat_id + Baileys service یا Cloud API |

### افزودن پیام‌رسان جدید
با معماری داینامیک جدید، فقط 3 قدم:

1.  اضافه کردن به `MESSENGER_LIST` در `config.py`, `bot.py`, `scheduler.py`
2.  ساخت `messenger_xxx.py` با دو تابع:
    ```python
    def send_product(product, config, is_new=False) -> bool
    def send_manual_post(caption, media_content, media_type, config) -> bool
    ```
3.  اضافه کردن به `MESSENGER_EMOJIS` و `MESSENGER_DISPLAY_NAMES`

همه کیبوردها و چک‌ها خودکار داینامیک هستند.

---

## 🚀 نصب و راه‌اندازی

### پیش‌نیازها
- Python 3.10+
- pip
- یک ربات Bale از @BotFather Bale
- (اختیاری) Node.js 18+ برای واتساپ

### نصب

```bash
git clone https://github.com/Alirezahjf/AGENT_AUTO_POST_BOT.git
cd AGENT_AUTO_POST_BOT/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER

# نصب وابستگی‌ها
pip install -r requirements.txt

# کپی کانفیگ نمونه
cp config.json.example config.json
# یا اگر وجود ندارد، فایل config.json بسازید:
```

### پیکربندی اولیه `config.json`

```json
{
  "woocommerce": {
    "url": "",
    "consumer_key": "",
    "consumer_secret": ""
  },
  "messengers": {
    "bale": {
      "bot_token": "YOUR_BALE_BOT_TOKEN",
      "channel_id": "@yourchannel"
    },
    "rubika": {"bot_token": "", "chat_id": ""},
    "eitaa": {"bot_token": "", "chat_id": ""},
    "telegram": {"bot_token": "", "chat_id": ""},
    "whatsapp": {
      "chat_id": "",
      "provider": "baileys",
      "service_url": "http://localhost:3001"
    }
  },
  "auto_post": {
    "enabled": false,
    "live_new_product": true,
    "posts_per_day": 2,
    "categories": [],
    "schedule": {
      "saturday": {"enabled": true, "times": ["09:00", "18:00"]},
      "sunday": {"enabled": true, "times": ["09:00", "18:00"]},
      "monday": {"enabled": true, "times": ["09:00"]},
      "tuesday": {"enabled": false, "times": []},
      "wednesday": {"enabled": false, "times": []},
      "thursday": {"enabled": false, "times": []},
      "friday": {"enabled": false, "times": []}
    }
  },
  "initial_admin_id": 123456789,
  "initial_admin_username": "SuperAdmin",
  "wallet_token": "WALLET-TOKEN-FOR-PAYMENT"
}
```

### اجرا

```bash
python bot.py
# خروجی: 🤖 ربات در حال اجراست... برای توقف Ctrl+C را بزنید.
```

ربات هر 30 ثانیه زمان‌بندی را چک می‌کند و هر 2 دقیقه محصولات جدید را به صورت زنده.

---

## ⚙️ پیکربندی

### از داخل ربات Bale

1.  `/start` -> انتخاب زبان
2.  **تنظیمات**:
    - 📱 پیام‌رسان‌ها -> انتخاب Bale/Rubika/Eitaa/Telegram/WhatsApp -> وارد کردن توکن و آیدی
    - 🛒 API ووکامرس -> URL سایت + Consumer Key + Secret
3.  **پست‌های ووکامرس**:
    - ⏰ تنظیم پست خودکار:
      - 🔄 فعال/غیرفعال پست خودکار
      - ⚡ پست زنده محصول جدید (فعال = محصول جدید بلافاصله پست می‌شود)
      - 📊 تعداد پست در روز
      - 📅 زمان‌بندی روزها (مثلا شنبه 09:00,14:00)
      - 📂 فیلتر دسته‌بندی (مثلا `15,20` یا `shoes,clothing` یا `all` برای همه)
    - 📦 بررسی محصولات جدید - گزارش زنده
    - 🧪 تست ارسال محصولات

### فیلتر دسته‌بندی

در منوی `تنظیم پست خودکار -> 📂 فیلتر دسته‌بندی`:

- ابتدا لیست دسته‌بندی‌های موجود سایت نمایش داده می‌شود (ID, نام, slug, تعداد محصول)
- سپس می‌توانید وارد کنید:
  - `all` -> پاک کردن فیلتر، همه دسته‌ها
  - `15,20,25` -> فقط دسته‌های با ID 15,20,25
  - `shoes,clothing` -> فقط دسته‌های با slug shoes,clothing
  - `15,shoes` -> ترکیبی

ذخیره در `auto_post.categories`

---

## 🔍 نحوه کار ووکامرس - تشخیص زنده

### مشکل قدیم
- همه محصولات در `known_products.json` ذخیره می‌شد (فایل حجیم، کند)
- تشخیص محصول جدید فقط بر اساس تاریخ امروز
- اگر محصول دیروز اضافه شده و ارسال نشده بود، گم می‌شد

### راه‌حل جدید (حرفه‌ای)

#### 1. ذخیره فقط ID (سبک)
```python
# به جای ذخیره کل محصول:
# known_products.json (10MB)
# الان:
known_product_ids.json = [123, 124, 125, ...]  # فقط ID ها، چند KB
sent_product_ids.json = [123, 124]  # ارسال شده‌ها
```

#### 2. تشخیص زنده
```python
def check_new_products(config, user_chat_id):
    current = get_all_products(config)  # لایو از API
    known_ids = load_known_ids()
    new_ids = current_ids - known_ids  # تفاضل مجموعه‌ها
    
    if new_ids:
        new_products = [p for p in current if p.id in new_ids]
        save_known_ids(known_ids | new_ids)  # آپدیت
        return new_products  # مرتب جدید به قدیم
```

هر بار که تابع صدا زده می‌شود:
- ID های فعلی سایت را می‌گیرد
- با ID های شناخته شده قبلی مقایسه می‌کند
- اگر ID جدید بود -> محصول جدید

#### 3. اولویت‌بندی
```python
def get_next_product_to_post(config, user_chat_id):
    # اولویت 1: محصول جدید ارسال نشده
    new = check_new_products()
    unsent_new = [p for p in new if p.id not in sent_ids]
    if unsent_new:
        return unsent_new[0], True  # جدیدترین جدید
    
    # اولویت 2: محصول موجود ارسال نشده، از جدید به قدیم
    current = get_all_products()  # مرتب date desc از API
    unsent = [p for p in current if p.id not in sent_ids]
    if unsent:
        return unsent[0], False  # جدیدترین موجود
```

#### 4. جلوگیری از تکراری
```python
def mark_product_as_sent(product_id, user_chat_id):
    sent_ids.add(product_id)
    save_sent_ids(sent_ids)
```

قبل از هر ارسال چک می‌شود:
```python
if is_product_sent(product.id):
    skip
```

#### 5. لایو بودن
- **هر 2 دقیقه**: `check_live_woocommerce_for_user` - فقط محصولات جدید را چک و بلافاصله پست می‌کند (اگر `live_new_product=true`)
- **هر 30 ثانیه**: `check_woocommerce_for_user` - زمان‌بندی روزانه (مثلا شنبه 09:00)

#### 6. فیلتر دسته‌بندی
```python
get_all_products(config, category_filter=[15,20])
# API: /wp-json/wc/v3/products?category=15,20&orderby=date&order=desc
```

---

## 📖 استفاده

### پست خودکار ووکامرس

1.  ووکامرس را متصل کنید
2.  پیام‌رسان‌های مقصد را متصل کنید (حداقل یکی)
3.  پست خودکار را فعال کنید + پست زنده را فعال کنید
4.  زمان‌بندی را تنظیم کنید
5.  (اختیاری) فیلتر دسته‌بندی

حالا:
- اگر محصول جدیدی در سایت ثبت کنید، **ظرف 2 دقیقه** به صورت خودکار در همه پیام‌رسان‌ها پست می‌شود
- اگر محصول جدیدی نبود، در زمان‌های زمان‌بندی شده، محصولات موجود از جدید به قدیم پست می‌شوند
- هیچ محصولی دو بار پست نمی‌شود

### پست دستی زمان‌بندی شده

1.  محتواها -> آپلود رسانه (با عنوان) + آپلود متن
2.  مدیریت پست‌ها -> پست جدید -> انتخاب رسانه -> انتخاب کپشن -> انتخاب تاریخ (تقویم شمسی) -> انتخاب ساعت -> انتخاب پیام‌رسان‌ها (تیک) -> ثبت

---

## 📁 ساختار پروژه

```
AGENT_AUTO_POST_BOT/
├── README.md (این فایل)
├── TELEGRAM_INTEGRATION.md
├── WHATSAPP_EVALUATION.md
├── ANALYSIS_REPORT_UPDATED.md
├── .gitignore
├── whatsapp-service/  # میکروسرویس واتساپ
│   ├── index.js
│   ├── package.json
│   └── README.md
└── all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/
    ├── bot.py (4500+ خط - کنترل‌گر اصلی Bale)
    ├── config.py (مدیریت کانفیگ داینامیک)
    ├── woocommerce.py (تشخیص زنده محصول جدید - بازنویسی شده)
    ├── scheduler.py (زمان‌بند + لایو چک)
    ├── database.py (PostDatabase)
    ├── auth_manager.py (احراز هویت + پرداخت)
    ├── auth_handlers.py (خرید اشتراک)
    ├── messenger_common.py (توابع مشترک)
    ├── messenger_bale.py
    ├── messenger_rubika.py
    ├── messenger_eitaa.py
    ├── messenger_telegram.py (جدید)
    ├── messenger_whatsapp.py (جدید)
    ├── logger.py
    ├── requirements.txt
    ├── config.json
    └── users/
        └── {chat_id}/
            ├── config.json
            ├── posts.db
            ├── known_product_ids.json (جدید - سبک)
            └── sent_product_ids.json (جدید)
```

---

## 🔌 API پیام‌رسان‌ها

### Bale
```
https://tapi.bale.ai/bot{token}/sendPhoto
https://tapi.bale.ai/bot{token}/sendVideo
https://tapi.bale.ai/bot{token}/sendMessage
```

### Telegram
```
https://api.telegram.org/bot{token}/sendPhoto
  - chat_id: @channel یا -100...
  - photo: URL یا file_id یا multipart
  - caption: max 1024 chars
  - parse_mode: Markdown
```

### Rubika
```
https://messengerg2c{number}.iranlms.ir/
  - requestSendFile
  - upload به upload_url
  - sendFile
```

### Eitaa
```
https://eitaayar.ir/api/{token}/sendFile
```

### WhatsApp Neonize (whatsmeow - Professional, LID Supported)
```
POST http://localhost:3001/send
{
  "userId": "123456",
  "to": "120363312386194255@g.us",
  "text": "✅ LID group works!",
  "imageBase64": "optional"
}
# Handles @lid participants natively - no No sessions error
```

---

## 💚 واتساپ - Neonize Professional (جدید)

> **Baileys قدیمی با گروه‌های @lid مشکل داشت:**
> `No PN mapping found`, `No sessions`, `Timed Out generics.js`
> **Neonize با whatsmeow Go این مشکل را حل کرده**

### چرا Neonize؟ (حرفه‌ای)

**مشکل Baileys 6.7.24:**
- گروه `120363312386194255@g.us` همه اعضاش `@lid` هستند (شناسه جدید واتساپ)
- `278645381836862@lid`, `29515686392037@lid`...
- `signalRepository.lidMapping.getPNForLID(lid)` برمی‌گرداند null
- ارسال ناموفق: `NO_SESSIONS_GROUP_NEEDS_MESSAGE`

**راه‌حل Neonize (whatsmeow):**
- Python wrapper برای `whatsmeow` Go (پیاده‌سازی رسمی واتساپ وب)
- `@lid` را native ساپورت می‌کند
- تست کاربر: `NewClient("session.sqlite3")`, `get_joined_groups()` گروه "شومبول بلا ها" را لیست کرد و `send_image` موفق بود
- لاگ: `Successfully paired 989038013654:13@s.whatsapp.net`, `Uploading 812 prekeys`, `Stored 33 secret keys`

#### نصب و اجرا (پیشنهادی)
```bash
cd whatsapp-service
pip install -r requirements.txt --break-system-packages
python3 neonize_service.py
# یا
./start.sh  # اجرای neonize + Bale bot via nohup
```

در `config.json`:
```json
"whatsapp": {
  "chat_id": "120363312386194255@g.us",
  "provider": "neonize",
  "service_url": "http://localhost:3001",
  "connected": true,
  "destination_selected": true
}
```

**مزایا**: LID ساپورت native، بدون ارور No sessions، تک فایل SQLite، حرفه‌ای
**معایب**: نیاز به Python + Go binary (neonize خودش نصب می‌کند)

#### روش قدیمی Baileys (منسوخ - فقط برای مرجع)
```bash
cd whatsapp-service
npm install
npm start
```
`provider: baileys` - با گروه‌های LID کار نمی‌کند

#### روش Cloud API رسمی
```json
"whatsapp": {
  "chat_id": "989123456789",
  "provider": "cloud",
  "bot_token": "EAA...",
  "phone_id": "123456789"
}
```

مستندات کامل: `whatsapp-service/README.md` (نسخه Neonize)

---

## 🔧 عیب‌یابی

### محصول جدید پست نمی‌شود؟
1.  `live_new_product` فعال است؟ (تنظیم پست خودکار -> ⚡ پست زنده)
2.  `known_product_ids.json` را چک کنید - اگر محصول قبلا known شده، جدید حساب نمی‌شود. برای تست، فایل را پاک کنید.
3.  لاگ را چک کنید: `bot.log`
4.  آیا دسته‌بندی فیلتر شده؟ `check_products` گزارش می‌دهد.

### تلگرام ارسال نمی‌شود؟
1.  ربات ادمین کانال است؟ (Post Messages)
2.  chat_id درست است؟ `@channel` برای عمومی، `-100...` برای خصوصی
3.  توکن درست است؟ از @BotFather دوباره بگیرید

### واتساپ ارسال نمی‌شود؟
1.  `whatsapp-service` ران است؟ `http://localhost:3001/` را چک کنید
2.  QR اسکن شده؟ پوشه `auth/` وجود دارد؟
3.  فرمت `to` درست است؟ `98912...@s.whatsapp.net`

---

## 🗺️ نقشه راه

- [x] تلگرام dest_only
- [x] واتساپ اسکلت + ارزیابی
- [x] بازنویسی ووکامرس به تشخیص زنده
- [x] فیلتر دسته‌بندی
- [x] جلوگیری از تکراری با ID
- [ ] ریفکتور bot.py به فایل‌های کوچک‌تر
- [ ] تبدیل user_states RAM به SQLite
- [ ] صف (Queue) به جای sleep
- [ ] پنل تحت وب
- [ ] داکر

---

## 📄 مجوز

MIT

---

## 👨‍💻 توسعه‌دهنده

ساخته شده با ❤️ برای فروشگاه‌های ایرانی

> **نکته**: این ربات به عنوان ایجنت هوشمند پست‌گذاری عمل می‌کند - Bale کنترل‌گر اصلی است و همه کاربران می‌توانند از طریق آن به پیام‌رسان‌های خود متصل شوند و پست‌گذاری خودکار زمان‌بندی شده را شروع کنند.

