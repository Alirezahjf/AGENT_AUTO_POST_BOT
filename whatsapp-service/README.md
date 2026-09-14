# 💚 WhatsApp Service - Neonize (whatsmeow) Professional - LID Supported

> **Rebuilt with `neonize` (Python wrapper for whatsmeow Go) to solve @lid issue**
> Old Baileys 6.7.24 fails on LID groups: `No PN mapping found`, `No sessions`, `Timed Out generics.js`
> New Neonize handles LID natively: `278645381836862@lid` etc. work perfectly!

## 🚀 Why Neonize?

**Baileys Problem (old):**
- Group `120363312386194255@g.us` participants all `@lid` (new WhatsApp privacy IDs)
- `278645381836862@lid`, `29515686392037@lid`, `179005680525361@lid`...
- Baileys `signalRepository.lidMapping.getPNForLID(lid)` returns null
- `onWhatsApp: [{error: No PN mapping found, type: lid} x6]`
- `lidMappings: []`, `senderKeys 0`, `sessionFiles 0`, `authFiles 113`
- `POST /send` → `NO_SESSIONS_GROUP_NEEDS_MESSAGE` + `Timed Out generics.js:170:32`
- Even with 812 prekeys uploaded, Baileys cannot send to LID groups

**Neonize Solution (new):**
- Wraps `whatsmeow` Go client (official WhatsApp Web implementation)
- Handles `@lid` natively, no PN mapping needed
- User's working example proves it:
  ```python
  from neonize.client import NewClient
  client = NewClient("session.sqlite3")
  # ... ConnectedEv, get_joined_groups(), send_image
  # Logs: Successfully paired 989038013654:13@s.whatsapp.net
  # Uploading 812 new prekeys, Stored 33 secret keys
  # Listed group "شومبول بلا ها" 120363312386194255@g.us and sent image successfully
  ```

## 🚀 Quick Start

```bash
cd whatsapp-service
pip install -r requirements.txt --break-system-packages
python3 neonize_service.py
# Output: 🚀 WhatsApp Neonize Service listening on 0.0.0.0:3001
# Engine: whatsmeow via neonize - LID supported, no No sessions error
```

Or via start.sh (production):
```bash
./start.sh
# Runs neonize_service.py via nohup on port 3001
# Bale bot via nohup python3 bot.py
```

Service on `http://localhost:3001`

## 📱 User Flow (Bale Bot)

1. User in Bale bot: `Settings -> Messengers -> WhatsApp 💚`
2. Sends own number: `989123456789`
3. Bot calls: `GET /qr?userId=12345&ownPhone=989123456789`
4. Service creates `auth/12345/neonize.sqlite3`, starts NewClient thread
5. QR generated via `segno`, pairing code via `PairPhone(989..., True)`
6. Bot sends QR image + pairing code (copyable) to Bale
7. User scans: `WhatsApp -> Settings -> Linked Devices -> Link a Device -> Scan QR`
   Or enters code: `WhatsApp -> Settings -> Linked Devices -> Link with phone number -> Enter 1234-5678`
8. User clicks `✅ Check Connection`
9. Bot checks: `GET /status?userId=12345` → `connected: true`
10. Bot lists groups: `GET /chats?userId=12345` → finds `120363312386194255@g.us` "شومبول بلا ها"
11. User selects destination group
12. Bot sends test: `POST /send {to: "120363312386194255@g.us", text: "✅ Connected!"}`
13. **Works even though participants are @lid!**

## 🔌 API Endpoints (Compatible with old Baileys service)

### GET / - Service status
```json
{
  "status": "ok",
  "service": "whatsapp-neonize-v1",
  "engine": "whatsmeow via neonize - LID supported",
  "sessionsCount": 1,
  "sessions": [{"userId": "12345", "connected": true, "hasQR": false, "groups": 5}]
}
```

### GET /qr?userId=...&ownPhone=...&force=
Returns QR + pairing code
```json
{
  "ok": true,
  "hasQR": true,
  "qr": "2@...",
  "qrImage": "data:image/png;base64,iVBOR...",
  "pairingCode": "1234-5678",
  "pairingCodePlain": "12345678",
  "copyableCode": "1234-5678"
}
```

### GET /status?userId=
```json
{
  "ok": true,
  "connected": true,
  "exists": true,
  "phone": "989038013654",
  "me": "989038013654:13@s.whatsapp.net",
  "groups": 3
}
```

### GET /chats?userId=
Lists joined groups via `get_joined_groups()`
```json
{
  "ok": true,
  "chats": [
    {"id": "120363312386194255@g.us", "name": "شومبول بلا ها", "participants": 6, "isGroup": true}
  ],
  "count": 1
}
```

### POST /send
```json
{
  "userId": "12345",
  "to": "120363312386194255@g.us",
  "text": "Hello from Neonize!",
  "imageBase64": "optional base64 image",
  "mediaType": "image|video|document"
}
```
Response: `{"ok": true, "messageId": "...", "to": "120363312386194255@g.us", "engine": "neonize"}`

### DELETE /session?userId=&force=
Deletes `auth/<userId>/neonize.sqlite3`

### POST /reset {userId, phone}
Force delete + new QR

### GET /pairing-code?userId=&phone=
Gets pairing code via `PairPhone`

### GET /qr-check?userId=&lastQR=
Checks if QR changed (auto-refresh)

### GET /qr-image?userId=
Returns PNG

### POST /connect, GET /restore, POST /clean-sessions, etc.
For compatibility - clean endpoints return "not needed for neonize"

## 🗂️ File Structure

```
whatsapp-service/
├── neonize_service.py          # NEW - Professional FastAPI + Neonize
├── test_neonize_example.py     # Working example (user's success case)
├── requirements.txt            # fastapi, uvicorn, neonize, segno, qrcode
├── auth/                       # Per-user SQLite sessions
│   ├── 123456789/
│   │   └── neonize.sqlite3     # Single file, no 113 files, no sender-key issues
│   └── 987654321/
│       └── neonize.sqlite3
├── index.js                    # OLD - Baileys (kept for reference, not used)
├── package.json                # OLD
└── README.md                   # This file
```

## 🔧 Bale Bot Integration

In `config.py`:
```python
"whatsapp": {
  "provider": "neonize",  # was baileys
  "service_url": "http://localhost:3001",
  "chat_id": "120363312386194255@g.us",  # destination group
  "connected": True,
  "destination_selected": True
}
```

In `bot.py` - uses `messenger_whatsapp.py` which now uses neonize service:
```python
import messenger_whatsapp  # now neonize under the hood

# QR
qr_result = messenger_whatsapp.get_qr_for_user(bale_chat_id, phone_number, service_url)
# qr_result["qrImage"] -> data URL
# qr_result["pairingCode"] -> 1234-5678

# Status
status = messenger_whatsapp.check_connection_status(bale_chat_id, service_url)

# Chats
chats = messenger_whatsapp.get_chats_for_user(bale_chat_id, service_url)
# chats["chats"] -> list with id, name, participants

# Send
messenger_whatsapp._send_via_neonize(dest, caption, image_bytes, service_url, bale_chat_id)
```

## 🧪 Testing LID Group

Target group: `120363312386194255@g.us` "شومبول بلا ها"
- Participants: all `@lid` (new WhatsApp privacy)
- Baileys: fails with `No sessions`
- Neonize: works!

Test manually:
```bash
# 1. Start service
python3 neonize_service.py

# 2. Get QR
curl "http://localhost:3001/qr?userId=test&ownPhone=989038013654" | jq

# 3. Scan QR, then check status
curl "http://localhost:3001/status?userId=test" | jq

# 4. List groups
curl "http://localhost:3001/chats?userId=test" | jq
# Should list 120363312386194255@g.us

# 5. Send to LID group
curl -X POST http://localhost:3001/send \
  -H "Content-Type: application/json" \
  -d '{"userId":"test","to":"120363312386194255@g.us","text":"✅ Neonize LID test 🎉"}' | jq
# Should succeed!
```

## 🐛 Troubleshooting

**QR not coming?**
- Check service: `curl http://localhost:3001/`
- Logs: `tail -f whatsapp.log`
- Port 3001 free? `fuser -k 3001/tcp`

**Not connected after scan?**
- `GET /status?userId=...` - check `connected`
- If `hasQR: true`, QR expired, get new via `GET /qr?userId=...&force=true`

**Groups not listing?**
- WhatsApp needs 30-60s after connect to sync groups
- Retry `GET /chats?userId=...` after 30s
- Or send group ID manually: `120363312386194255@g.us`

**Send fails?**
- Check `connected` true
- Check `to` format: `120363312386194255@g.us` for groups, `989...@s.whatsapp.net` for contacts
- Neonize should NOT give `No sessions` error for LID groups (unlike Baileys)

**Old Baileys auth files?**
- Delete old auth: `rm -rf auth/<userId>/*` except `neonize.sqlite3`
- Or force reset: `POST /reset {"userId": "..."}` or `GET /qr?userId=...&force=true`

## 📦 Production Deploy

```bash
# Via start.sh (no pm2 needed, uses nohup + pid files)
./start.sh
# - Kills old on 3001 via fuser
# - Runs neonize_service.py -> whatsapp.pid
# - Runs bot.py -> bot.pid
# - Checks health via curl

./stop.sh
# - Kills via pid files + pkill + fuser

./status.sh
# - Shows both services

# Manual
nohup python3 whatsapp-service/neonize_service.py > whatsapp-service/whatsapp.log 2>&1 &
echo $! > whatsapp-service/whatsapp.pid

# Systemd (optional)
# Create /etc/systemd/system/whatsapp-neonize.service
```

## 🎯 Differences from Baileys

| Feature | Baileys 6.7.24 | Neonize (whatsmeow) |
|---------|----------------|---------------------|
| LID support | ❌ No PN mapping, fails | ✅ Native |
| Auth files | 113 files, fragile | 1 SQLite file |
| No sessions error | ❌ Frequent for groups | ✅ No |
| Group send | ❌ Needs sender-key, fails | ✅ Works |
| Pairing code | Custom impl | ✅ PairPhone native |
| Engine | JS | Go (whatsmeow) |
| Multi-user | auth/<userId>/ many files | auth/<userId>/neonize.sqlite3 |

## 📚 References

- Neonize: https://github.com/Kenzo02/neonize
- whatsmeow: https://github.com/tulir/whatsmeow (Go)
- User's successful log: 812 prekeys, 33 secret keys, group "شومبول بلا ها" listed, image sent

---

**Built for AGENT_AUTO_POST_BOT - Professional, error-free, LID supported**
