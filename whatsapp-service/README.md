# 💚 WhatsApp Service - نسخه فوق ساده برای غیر برنامه‌نویس

> هر کاربر Bale یک سشن جدا دارد. فقط شماره بگیر، QR بفرست، اسکن کن، متصل شد!

## 🚀 راه‌اندازی (یک بار)

```bash
cd whatsapp-service
npm install
npm start
# خروجی: 🚀 WhatsApp multi-user service listening on 0.0.0.0:3001
```

سرویس روی `http://localhost:3001` بالا می‌آید.

## 📱 جریان کاربر عادی (بدون کدنویسی)

1. کاربر در ربات Bale می‌رود: `تنظیمات -> پیام‌رسان‌ها -> WhatsApp 💚`
2. شماره مقصد را می‌فرستد: `989123456789`
3. ربات از سرویس QR می‌گیرد: `GET /qr?userId=12345`
4. ربات QR را به صورت عکس برای کاربر در Bale می‌فرستد
5. کاربر با گوشی اسکن می‌کند: `واتساپ -> تنظیمات -> دستگاه‌های متصل -> اتصال دستگاه`
6. کاربر دکمه `✅ بررسی اتصال` را می‌زند
7. ربات چک می‌کند: `GET /status?userId=12345` -> `connected: true`
8. پیام موفقیت: `✅ واتساپ با موفقیت متصل شد!`

**حتی یک غیر برنامه‌نویس هم می‌تواند وصل کند!**

## 🔌 API Endpoints

### گرفتن QR برای یک کاربر
```
GET /qr?userId=123456789&phone=989123456789
```
پاسخ:
```json
{
  "ok": true,
  "connected": false,
  "hasQR": true,
  "qr": "2@... (رشته QR)",
  "qrImage": "data:image/png;base64,iVBOR...",
  "userId": "123456789",
  "instructions": "این QR را با واتساپ اسکن کنید..."
}
```

### عکس QR مستقیم (PNG)
```
GET /qr-image?userId=123456789
```
برمی‌گرداند: `image/png`

### وضعیت اتصال
```
GET /status?userId=123456789
```
پاسخ:
```json
{
  "ok": true,
  "connected": true,
  "exists": true,
  "phoneNumber": "989123456789",
  "userId": "123456789"
}
```

### اتصال جدید (POST)
```
POST /connect
Body: { userId: "123456789", phoneNumber: "989123456789" }
```

### ارسال پیام (چندکاربره)
```
POST /send
Body: {
  "userId": "123456789",  // Bale chat_id - کدام سشن
  "to": "989123456789@s.whatsapp.net",  // مقصد
  "text": "سلام!",
  "imageBase64": "...."  // اختیاری
}
```

### حذف سشن (Logout)
```
DELETE /session?userId=123456789
```

### لیست همه سشن‌ها
```
GET /sessions
GET /
```

## 🗂️ ساختار فایل‌ها

```
whatsapp-service/
├── index.js          # سرور چندکاربره
├── package.json
├── auth/             # پوشه سشن‌ها (هر کاربر جدا)
│   ├── 123456789/    # Bale chat_id 123456789
│   │   ├── creds.json
│   │   └── ...
│   └── 987654321/    # کاربر دیگر
└── README.md
```

## 🔧 تنظیمات

در `config.json` هر کاربر:
```json
"whatsapp": {
  "chat_id": "989123456789@s.whatsapp.net",  // شماره مقصد
  "provider": "baileys",
  "service_url": "http://localhost:3001"
}
```

برای چندکاربره، نیازی به تنظیم دستی `service_url` نیست - پیش‌فرض `localhost:3001` است.

## 🐛 عیب‌یابی

**QR نمی‌آید؟**
- آیا سرویس روشن است؟ `http://localhost:3001/` را باز کنید
- لاگ را ببینید: `npm start`
- پورت 3001 آزاد است؟ `lsof -i :3001`

**بعد از اسکن متصل نمی‌شود؟**
- `GET /status?userId=YOUR_ID` را چک کنید
- اگر `connected: false` و `hasQR: false`، دوباره `GET /qr?userId=YOUR_ID` بزنید (QR هر 20 ثانیه منقضی می‌شود)

**پیام ارسال نمی‌شود؟**
- آیا سشن متصل است؟ `GET /status`
- آیا `to` درست است؟ باید `98912...@s.whatsapp.net` یا `1203...@g.us` باشد
- لاگ سرویس را ببینید

**چند کاربر همزمان؟**
- هر Bale chat_id یک پوشه جدا در `auth/` دارد
- هیچ تداخلی ندارند
- می‌توانید 100 کاربر همزمان داشته باشید

## 🔒 امنیت

- هر سشن فقط با `creds.json` خودش کار می‌کند
- QR هر 20 ثانیه عوض می‌شود
- اگر کاربر logout کند، پوشه `auth/{userId}` پاک می‌شود
- برای تولید، `auth/` را بکاپ بگیرید

## 📦 دیپلوی

```bash
# با PM2
npm install -g pm2
pm2 start index.js --name whatsapp-service
pm2 save
pm2 startup

# با Docker
docker build -t whatsapp-service .
docker run -d -p 3001:3001 -v $(pwd)/auth:/app/auth whatsapp-service
```

## 🎯 برای برنامه‌نویس ربات Bale

در `bot.py`:
```python
import messenger_whatsapp

# گرفتن QR
qr_result = messenger_whatsapp.get_qr_for_user(bale_chat_id, phone_number, service_url)
# qr_result["qrImage"] -> data:image/png;base64,...

# بررسی اتصال
status = messenger_whatsapp.check_connection_status(bale_chat_id, service_url)
# status["connected"] -> True/False
```

در `messenger_whatsapp.py` ارسال:
```python
# user_id از config خوانده می‌شود (bale chat_id)
config["messengers"]["whatsapp"]["_bale_user_id"] = str(bale_chat_id)
messenger_whatsapp.send_product(product, config)
```

---

**ساخته شده برای AGENT_AUTO_POST_BOT - نسخه فوق ساده**
