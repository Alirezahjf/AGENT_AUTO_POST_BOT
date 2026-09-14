
# نصب تمیز با حفظ یوزرها

## روش 1: اسکریپت خودکار (پیشنهادی)
```bash
cd ~/AGENT_AUTO_POST_BOT
./clean_update.sh &
```

این اسکریپت:
- سرویس‌ها را می‌بندد
- از users/ و whatsapp-service/auth/ و auth.db و config.json بکاپ می‌گیرد به /tmp/
- پروژه جدید را کلون می‌کند
- بکاپ‌ها را برمی‌گرداند
- سرویس‌ها را اجرا می‌کند
- یوزرها حفظ می‌شوند!

## روش 2: دستی
```bash
cd ~
# بکاپ
mkdir -p /tmp/bot_backup
cp -r AGENT_AUTO_POST_BOT/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users /tmp/bot_backup/ 2>/dev/null; true
cp -r AGENT_AUTO_POST_BOT/whatsapp-service/auth /tmp/bot_backup/whatsapp_auth 2>/dev/null; true
cp AGENT_AUTO_POST_BOT/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db /tmp/bot_backup/ 2>/dev/null; true
cp AGENT_AUTO_POST_BOT/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json /tmp/bot_backup/ 2>/dev/null; true

# بستن
cd AGENT_AUTO_POST_BOT
./stop.sh; pkill -9 -f "node.*index.js"; pkill -9 -f "python.*bot.py"; fuser -k 3001/tcp 2>/dev/null; true
cd ~
rm -rf AGENT_AUTO_POST_BOT

# کلون جدید
git clone --branch arena/01a086a1-agent-auto-post-bot https://github.com/Alirezahjf/AGENT_AUTO_POST_BOT.git
cd AGENT_AUTO_POST_BOT

# بازگردانی
rm -rf all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users
cp -r /tmp/bot_backup/users all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users 2>/dev/null; true
rm -rf whatsapp-service/auth
cp -r /tmp/bot_backup/whatsapp_auth whatsapp-service/auth 2>/dev/null; true
cp /tmp/bot_backup/auth.db all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db 2>/dev/null; true
# config.json را فقط اگر توکن جدید نداری برگردان
# cp /tmp/bot_backup/config.json all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json

./start.sh &
sleep 5
./status.sh
```

## چک کردن حفظ شدن
```bash
ls -lh all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users/ | head -20
ls -lh whatsapp-service/auth/ | head -20
ls -lh all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db
```
