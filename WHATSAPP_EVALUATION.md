# 📱 ارزیابی روش‌های افزودن واتساپ - WhatsApp Integration Evaluation

## سوال کاربر
> کدام بهتر است: WhatsApp Business API رسمی یا کتابخانه‌هایی مثل neon/baileys/whatsmeow؟

## خلاصه توصیه
### برای پروژه شما: **ترکیبی**
- **کوتاه‌مدت / تست / کانال شخصی**: کتابخانه **Baileys (Node.js)** یا **whatsmeow (Go)** یا **pywhatkit / neon** برای پروتوتایپ سریع
- **بلندمدت / بیزینس واقعی / مقیاس بالا**: **WhatsApp Business API رسمی (Cloud API)**

### توصیه نهایی برای AGENT_AUTO_POST_BOT:
**فعلا پیاده‌سازی WhatsApp با Baileys (از طریق یک میکروسرویس Node.js) + طراحی اینترفیس برای مهاجرت به Cloud API در آینده**

دلیل: پروژه شما پایتونی است اما اکوسیستم واتساپ در Node.js/Go بسیار قوی‌تر است. با یک سرویس واسط می‌توانید هر دو را ساپورت کنید.

---

## مقایسه دقیق

### 1️⃣ WhatsApp Business API رسمی (Cloud API)

#### ✅ مزایا
- **رسمی و پایدار**: توسط متا پشتیبانی می‌شود، بن نمی‌شوید
- **مقیاس‌پذیر**: برای هزاران پیام/روز طراحی شده
- **قابلیت‌ها**:
  - Template Messages (برای مارکتینگ)
  - Interactive Buttons, Lists
  - Webhook برای دریافت پیام
  - Verified Business Badge
  - پشتیبانی از شماره ثابت
- **امنیت**: رمزگذاری سرتاسری حفظ می‌شود
- **مستندات عالی**: https://developers.facebook.com/docs/whatsapp/cloud-api

#### ❌ معایب
- **هزینه**: 
  - بعد از 1000 مکالمه رایگان/ماه، هر مکالمه 0.02$ تا 0.15$ بسته به کشور
  - ایران در لیست تحریم؟ نیاز به شماره مجازی + کسب‌وکار خارج ایران
- **تایید سخت**: نیاز به Facebook Business Manager، تایید کسب‌وکار (ممکن است 1-2 هفته)
- **محدودیت 24 ساعته**: فقط در 24 ساعت بعد از پیام کاربر می‌توانید پیام عادی بفرستید، بعد از آن فقط Template
- **Template باید تایید شود**: هر پیام مارکتینگ باید توسط متا تایید شود (سخت‌گیری روی متن فارسی)
- **نیاز به سرور با دامنه و SSL**: برای Webhook
- **شماره شما نمی‌تواند همزمان روی گوشی باشد**: باید فقط روی API باشد

#### 📋 نیازمندی‌ها
```
- Facebook Developer Account
- Business Manager Verified
- شماره تلفن که قبلا روی واتساپ نبوده (یا حذف شده)
- سرور با HTTPS برای Webhook
- هزینه برای هر Conversation
```

#### 💻 نمونه کد پایتون (Cloud API)
```python
import requests

def send_whatsapp_cloud_api(to, text, token, phone_id):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,  # مثلا 989123456789
        "type": "text",
        "text": {"body": text}
    }
    resp = requests.post(url, headers=headers, json=data)
    return resp.json()

# برای عکس
def send_whatsapp_image(to, image_url, caption, token, phone_id):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption}
    }
    return requests.post(url, headers=headers, json=data).json()
```

---

### 2️⃣ کتابخانه‌های غیررسمی (Baileys / whatsmeow / neon)

#### گزینه‌های محبوب

| کتابخانه | زبان | وضعیت | مزایا | معایب |
|----------|------|-------|-------|-------|
| **Baileys** | Node.js | ⭐ فعال‌ترین (WhisKeys) | مستندات عالی، مالتی‌دیوایس، بدون نیاز به مرورگر | نیاز به Node.js، احتمال بن شدن کم اما وجود دارد |
| **whatsmeow** | Go | فعال | سرعت بالا، پایدار، مالتی‌دیوایس | نیاز به Go، کامیونیتی کوچک‌تر |
| **neon / whatsapp-api** | Python | نیمه‌فعال | پایتون، ساده | اغلب از selenium استفاده می‌کنند، ناپایدار، بن بالا |
| **pywhatkit** | Python | ساده | فقط ارسال پیام ساده | نیاز به باز کردن مرورگر، برای اتوماسیون مناسب نیست |
| **WPPConnect** | Node.js | فعال | امکانات زیاد | سنگین |

#### ✅ مزایا (کل کتابخانه‌های غیررسمی)
- **رایگان**: بدون هزینه هر پیام
- **راه‌اندازی فوری**: 5 دقیقه‌ای با QR Code
- **بدون نیاز به تایید کسب‌وکار**
- **شماره فعلی شما**: می‌توانید از شماره شخصی استفاده کنید
- **امکانات کامل**: ارسال عکس، ویدیو، دکمه، لیست، گروه، استوری
- **بدون محدودیت 24 ساعته**

#### ❌ معایب
- **ریسک بن شدن**: واتساپ رسما این روش را ممنوع کرده (اما با Baileys ریسک کم است اگر اسپم نکنید)
- **ناپایدار**: با هر آپدیت واتساپ ممکن است بشکند (Baileys سریع آپدیت می‌شود)
- **نیاز به نگهداری سشن**: باید QR را اسکن کنید و فایل auth را نگه دارید
- **یک شماره = یک اتصال**: نمی‌توانید همزمان روی گوشی و ربات باشید (مالتی‌دیوایس کمک می‌کند اما...)
- **مقیاس‌پذیری پایین**: برای 1000+ پیام/روز مناسب نیست
- **امنیت**: باید مراقب فایل سشن باشید

#### 💻 نمونه معماری پیشنهادی با Baileys (برای پروژه شما)

**ساختار:**
```
AGENT_AUTO_POST_BOT/
  all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/
    messenger_whatsapp.py  (کلاینت پایتون که به سرویس Node.js درخواست می‌دهد)
  whatsapp-service/  (میکروسرویس Node.js با Baileys)
    index.js
    auth/ (فایل‌های سشن)
```

**whatsapp-service/index.js:**
```javascript
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys')
const express = require('express')
const app = express()
app.use(express.json({limit: '50mb'}))

let sock;

async function start() {
    const { state, saveCreds } = await useMultiFileAuthState('auth')
    sock = makeWASocket({ auth: state, printQRInTerminal: true })
    sock.ev.on('creds.update', saveCreds)
    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect } = update
        if(connection === 'close') {
            const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut
            if(shouldReconnect) start()
        }
    })
}

app.post('/send', async (req, res) => {
    const { to, text, imageBase64 } = req.body
    // to = 989123456789@s.whatsapp.net یا گروه
    try {
        if(imageBase64) {
            const buffer = Buffer.from(imageBase64, 'base64')
            await sock.sendMessage(to, { image: buffer, caption: text })
        } else {
            await sock.sendMessage(to, { text })
        }
        res.json({ok: true})
    } catch(e) {
        res.status(500).json({ok: false, error: e.message})
    }
})

app.listen(3001, '0.0.0.0', () => console.log('WhatsApp service on 3001'))
start()
```

**messenger_whatsapp.py (در پروژه پایتون):**
```python
import requests, base64

WHATSAPP_SERVICE_URL = "http://localhost:3001"

def send_product(product, config, is_new=False):
    wa = config["messengers"].get("whatsapp", {})
    if not wa.get("chat_id"):
        return False
    # chat_id = 989123456789@s.whatsapp.net یا group id
    caption = _format_product(product, config, is_new)
    images = product.get("images", [])
    image_b64 = None
    if images:
        try:
            resp = requests.get(images[0]["src"], timeout=20)
            image_b64 = base64.b64encode(resp.content).decode()
        except:
            pass
    try:
        r = requests.post(f"{WHATSAPP_SERVICE_URL}/send", json={
            "to": wa["chat_id"],
            "text": caption,
            "imageBase64": image_b64
        }, timeout=30)
        return r.json().get("ok")
    except Exception as e:
        print(f"WA error {e}")
        return False
```

---

## 🎯 توصیه برای شما (AGENT_AUTO_POST_BOT)

### سناریوی فعلی شما
- فروشگاه ووکامرس دارید
- می‌خواهید محصولات را به کانال‌ها بفرستید
- کاربران شما ایرانی هستند (واتساپ Business API برای ایران سخت است)
- Bale به عنوان کنترل باقی می‌ماند

### پیشنهاد مرحله‌ای

#### فاز 1: پروتوتایپ سریع (1-2 روز) - Baileys
```
1. یک پوشه whatsapp-service بسازید
2. Baileys + Express را نصب کنید
3. QR را اسکن کنید
4. messenger_whatsapp.py را بسازید که به سرویس Node.js درخواست می‌دهد
5. به MESSENGER_LIST اضافه کنید
```
**مزیت**: فردا می‌توانید واتساپ داشته باشید، بدون هزینه، بدون تایید.

#### فاز 2: پایدارسازی (1 هفته)
```
- اضافه کردن مدیریت سشن (ذخیره auth در فایل)
- اضافه کردن صف پیام (Queue) برای جلوگیری از بن شدن (فاصله 2-3 ثانیه بین پیام‌ها)
- لاگ و مانیتورینگ
- داکرایز کردن سرویس واتساپ
```

#### فاز 3: مهاجرت به Cloud API (وقتی کسب‌وکار بزرگ شد)
```
- وقتی به 1000+ پیام/روز رسیدید یا نیاز به Verified Badge داشتید
- یک شماره مجازی (مثلا از Twilio) بگیرید
- Business Manager را تایید کنید
- کد messenger_whatsapp.py را به دو حالت Cloud/Baileys تبدیل کنید:
  config["messengers"]["whatsapp"]["provider"] = "baileys" | "cloud"
```

### چرا نه neon (پایتون مستقیم)؟
- اکثر کتابخانه‌های پایتون واتساپ یا از selenium استفاده می‌کنند (کند، ناپایدار، نیاز به مرورگر)
- یا مدت‌هاست آپدیت نشده‌اند
- Baileys در Node.js استاندارد صنعت است و هر روز آپدیت می‌شود

### ریسک بن شدن واتساپ را چطور کم کنیم؟
1. **فاصله بین پیام‌ها**: حداقل 2-3 ثانیه
2. **اسپم نکنید**: روزی بیش از 100 پیام به افراد ناشناس نفرستید
3. **از شماره شخصی استفاده نکنید**: یک شماره جداگانه برای ربات بگیرید
4. **Warm-up**: اول با دوستان تست کنید، بعد گروه‌ها، بعد کانال
5. **از Template استفاده کنید**: پیام‌ها را شخصی‌سازی کنید، نه یک متن ثابت برای همه

---

## 📊 جدول تصمیم‌گیری نهایی

| معیار | Cloud API رسمی | Baileys |
|-------|----------------|---------|
| هزینه | 0.02$-0.15$ هر مکالمه | رایگان |
| زمان راه‌اندازی | 1-2 هفته (تایید) | 10 دقیقه |
| ریسک بن | 0% | 5-10% اگر اسپم کنید |
| مقیاس‌پذیری | نامحدود | تا ~500 پیام/روز |
| نیاز به سرور | بله (Webhook + HTTPS) | بله (Node.js) |
| ایران | سخت (تحریم) | آسان |
| مناسب برای شما | بلندمدت | **کوتاه‌مدت + میان‌مدت ✅** |

---

## ✅ جمع‌بندی و Action Plan

### توصیه من به شما:
1. **الان**: تلگرام را که اضافه کردیم نگه دارید (تموم شد ✅)
2. **هفته آینده**: واتساپ را با **Baileys** به صورت میکروسرویس اضافه کنید
3. **ساختار کد**: از همین الان `messenger_whatsapp.py` را با اینترفیس `send_product` و `send_manual_post` بسازید تا با بقیه پیام‌رسان‌ها یکسان باشد
4. **آینده**: وقتی خواستید مقیاس بدهید، یک `provider` به کانفیگ اضافه کنید و Cloud API را هم ساپورت کنید

اگر بخواهید، می‌توانم همین الان ساختار `whatsapp-service` + `messenger_whatsapp.py` را برایتان بسازم.

### سوالی دارید؟
- آیا شماره واتساپ جداگانه برای ربات دارید؟
- آیا می‌خواهید به گروه واتساپ بفرستید یا چت شخصی/کانال؟
- آیا سرور شما Node.js را ساپورت می‌کند؟
