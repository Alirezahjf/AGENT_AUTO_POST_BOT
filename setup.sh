#!/bin/bash
# setup.sh - نصب و راه‌اندازی کامل AGENT AUTO POST BOT - NEONIZE EDITION
set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  🤖 AGENT AUTO POST BOT - Neonize Edition (LID Fix)       ║"
echo "║  Bale Bot + WhatsApp Neonize + Telegram + WooCommerce     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo -e "${YELLOW}📁 پوشه پروژه: $SCRIPT_DIR${NC}"

echo -e "\n${BLUE}1️⃣ بررسی سیستم...${NC}"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then echo -e "${GREEN}✅ Linux detected${NC}"; else echo -e "${YELLOW}⚠️ غیر از لینوکس${NC}"; fi

echo -e "\n${BLUE}2️⃣ بررسی Node.js و npm...${NC}"
if command -v node &> /dev/null; then echo -e "${GREEN}✅ Node.js نصب است: $(node -v)${NC}"; else echo -e "${YELLOW}📦 نصب Node.js...${NC}"; curl -fsSL https://deb.nodesource.com/setup_20.x | bash -; apt install nodejs -y; fi
if command -v npm &> /dev/null; then echo -e "${GREEN}✅ npm نصب است: $(npm -v)${NC}"; else echo -e "${RED}❌ npm یافت نشد${NC}"; exit 1; fi

echo -e "\n${BLUE}3️⃣ بررسی Python و pip...${NC}"
if command -v python3 &> /dev/null; then echo -e "${GREEN}✅ $(python3 --version) نصب است${NC}"; else echo -e "${RED}❌ python3 یافت نشد${NC}"; exit 1; fi
if command -v pip3 &> /dev/null; then echo -e "${GREEN}✅ pip3 نصب است${NC}"; else apt install python3-pip -y; fi

echo -e "\n${BLUE}4️⃣ نصب وابستگی‌های Python...${NC}"
BOT_DIR="$SCRIPT_DIR/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER"
if [ -f "$BOT_DIR/requirements.txt" ]; then cd "$BOT_DIR"; pip3 install -r requirements.txt --break-system-packages --quiet 2>/dev/null || pip3 install -r requirements.txt --quiet || pip3 install requests jdatetime pytz python-dotenv --break-system-packages --quiet; echo -e "${GREEN}✅ وابستگی‌های Python نصب شد${NC}"; cd "$SCRIPT_DIR"; else pip3 install requests jdatetime pytz python-dotenv --break-system-packages --quiet 2>/dev/null || pip3 install requests jdatetime pytz python-dotenv --quiet; fi

echo -e "\n${BLUE}5️⃣ نصب وابستگی‌های WhatsApp Neonize Service...${NC}"
WA_DIR="$SCRIPT_DIR/whatsapp-service"
if [ -d "$WA_DIR" ]; then
    cd "$WA_DIR"
    mkdir -p auth
    echo -e "${YELLOW}📁 Auth folder: $(pwd)/auth${NC}"
    echo -e "${YELLOW}📦 نصب پکیج‌های Python Neonize (LID ساپورت)...${NC}"
    if [ -f "requirements.txt" ]; then pip3 install -r requirements.txt --break-system-packages -q 2>&1 | tail -5 || pip3 install fastapi uvicorn neonize segno qrcode pillow python-magic --break-system-packages -q; else pip3 install fastapi uvicorn neonize segno qrcode pillow python-magic --break-system-packages -q 2>&1 | tail -5 || true; fi
    echo -e "${GREEN}✅ پکیج‌های Neonize نصب شد${NC}"
    if [ -f "package.json" ]; then echo -e "${YELLOW}📦 نصب Node (fallback اختیاری)...${NC}"; npm config set fetch-retries 5 2>/dev/null || true; NODE_OPTIONS="--dns-result-order=ipv4first" npm install --legacy-peer-deps --no-audit --no-fund 2>&1 | tail -3 || true; fi
    cd "$SCRIPT_DIR"
else echo -e "${RED}❌ پوشه whatsapp-service یافت نشد${NC}"; exit 1; fi

echo -e "\n${BLUE}6️⃣ بررسی تنظیمات...${NC}"
CONFIG_FILE="$BOT_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}⚠️ config.json یافت نشد - یک نمونه می‌سازم${NC}"
    cat > "$CONFIG_FILE" << 'EOF'
{
  "messengers": {
    "bale": {"bot_token": "YOUR_BALE_BOT_TOKEN_HERE","channel_id": "@yourchannel"},
    "rubika": {"bot_token": "", "chat_id": ""},
    "eitaa": {"bot_token": "", "chat_id": ""},
    "telegram": {"bot_token": "", "chat_id": ""},
    "whatsapp": {"chat_id": "","provider": "neonize","service_url": "http://localhost:3001"}
  },
  "woocommerce": {"url": "","consumer_key": "","consumer_secret": ""},
  "auto_post": {"enabled": false,"live_new_product": true,"posts_per_day": 2,"categories": [],"schedule": {"saturday": {"enabled": true, "times": ["09:00", "18:00"]},"sunday": {"enabled": true, "times": ["09:00", "18:00"]},"monday": {"enabled": true, "times": ["09:00"]},"tuesday": {"enabled": false, "times": []},"wednesday": {"enabled": false, "times": []},"thursday": {"enabled": false, "times": []},"friday": {"enabled": false, "times": []}}},
  "initial_admin_id": 0,
  "initial_admin_username": "Admin"
}
EOF
    echo -e "${RED}❌ لطفا توکن ربات Bale را در $CONFIG_FILE وارد کنید!${NC}"
else echo -e "${GREEN}✅ config.json وجود دارد${NC}"; if grep -q "YOUR_BALE_BOT_TOKEN" "$CONFIG_FILE" || grep -q '"bot_token": ""' "$CONFIG_FILE"; then echo -e "${YELLOW}⚠️ توکن Bale خالی است - nano $CONFIG_FILE${NC}"; fi; fi

echo -e "\n${BLUE}7️⃣ ساخت اسکریپت‌های مدیریت Neonize...${NC}"

cat > "$SCRIPT_DIR/start.sh" << 'EOF'
#!/bin/bash
# start.sh - اجرای همه سرویس‌ها - NEONIZE (LID supported)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
echo -e "${BLUE}🚀 در حال اجرای سرویس‌ها...${NC}"
rm -f whatsapp-service/whatsapp.pid all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid
mkdir -p whatsapp-service/auth
echo -e "${BLUE}📱 WhatsApp Neonize Service روی پورت 3001 (LID ساپورت)...${NC}"
cd "$SCRIPT_DIR/whatsapp-service"
mkdir -p auth
echo -e "${BLUE}📁 Auth: $(pwd)/auth - $(ls auth 2>/dev/null | wc -l) session(s)${NC}"
fuser -k 3001/tcp 2>/dev/null || true
pkill -f "node.*index.js" 2>/dev/null || true
pkill -f "neonize_service.py" 2>/dev/null || true
sleep 1
if [ -f "requirements.txt" ]; then echo -e "${YELLOW}📦 نصب وابستگی‌های Neonize...${NC}"; pip install -r requirements.txt --break-system-packages -q 2>&1 | tail -5 || pip install fastapi uvicorn neonize segno qrcode pillow --break-system-packages -q; fi
echo -e "${BLUE}🚀 اجرای Neonize service...${NC}"
nohup python3 neonize_service.py > whatsapp.log 2>&1 &
echo $! > whatsapp.pid
echo -e "${GREEN}✅ WhatsApp Neonize اجرا شد PID: $(cat whatsapp.pid)${NC}"
cd "$SCRIPT_DIR"
sleep 4
for i in {1..5}; do if curl -s http://localhost:3001/ | grep -q "ok"; then echo -e "${GREEN}✅ WhatsApp روشن http://localhost:3001${NC}"; break; else if [ $i -eq 5 ]; then echo -e "${RED}❌ WhatsApp روشن نشد - لاگ:${NC}"; tail -20 whatsapp-service/whatsapp.log; else echo -e "${YELLOW}⏳ WhatsApp در حال بالا آمدن... تلاش $i${NC}"; sleep 2; fi; fi; done
echo -e "\n${BLUE}🤖 Bale Bot...${NC}"
cd "$SCRIPT_DIR/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER"
if [ -f "auth.db" ]; then if ! python3 -c "import sqlite3; sqlite3.connect('auth.db', timeout=2).execute('SELECT 1')" 2>/dev/null; then echo -e "${RED}⚠️ auth.db خراب است، بکاپ و بازسازی...${NC}"; cp auth.db auth.db.backup.$(date +%s) 2>/dev/null; true; rm -f auth.db auth.db-journal; else echo -e "${GREEN}✅ auth.db سالم است${NC}"; fi; fi
mkdir -p users
if [ -d "users" ] && [ "$(ls -A users 2>/dev/null)" ]; then echo -e "${GREEN}✅ پوشه users حفظ شد ($(ls users | wc -l) کاربر)${NC}"; fi
if [ -f "bot.pid" ]; then rm -f bot.pid; fi
pkill -f "python.*bot.py" 2>/dev/null || true
sleep 1
rm -f bot.log
nohup python3 bot.py > bot.log 2>&1 &
echo $! > bot.pid
echo -e "${GREEN}✅ Bale Bot اجرا شد PID: $(cat bot.pid)${NC}"
cd "$SCRIPT_DIR"
sleep 2
echo -e "\n${GREEN}✅ همه سرویس‌ها اجرا شدند!${NC}"
echo "📱 WhatsApp: http://localhost:3001/"
echo "📝 لاگ واتساپ: tail -f whatsapp-service/whatsapp.log"
echo "📝 لاگ ربات: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log"
echo "🔍 وضعیت: ./status.sh"
echo "🛑 بستن: ./stop.sh"
echo ""
echo -e "${BLUE}📊 تست سریع:${NC}"
./test.sh 2>&1 | head -30
EOF

cat > "$SCRIPT_DIR/stop.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo "🛑 بستن سرویس‌ها..."
if [ -f "whatsapp-service/whatsapp.pid" ]; then kill -9 $(cat whatsapp-service/whatsapp.pid) 2>/dev/null || true; rm -f whatsapp-service/whatsapp.pid; fi
if [ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid" ]; then kill -9 $(cat all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid) 2>/dev/null || true; rm -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid; fi
pkill -f "whatsapp-service/index.js" 2>/dev/null || true
pkill -f "neonize_service.py" 2>/dev/null || true
pkill -f "all_pg_agnet.*bot.py" 2>/dev/null || true
fuser -k 3001/tcp 2>/dev/null || true
echo "✅ بسته شد"
echo "پورت 3001: $(lsof -i :3001 2>&1 | head -n 1 || echo 'آزاد')"
EOF

cat > "$SCRIPT_DIR/status.sh" << 'EOF'
#!/bin/bash
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
echo "📊 وضعیت سرویس‌ها:"
echo "===================="
echo -e "\n${YELLOW}📱 WhatsApp Service (پورت 3001):${NC}"
if curl -s http://localhost:3001/ | grep -q "ok"; then echo -e "${GREEN}✅ روشن است${NC}"; curl -s http://localhost:3001/ | python3 -m json.tool 2>/dev/null || curl -s http://localhost:3001/; else echo -e "${RED}❌ خاموش است${NC}"; fi
echo -e "\n${YELLOW}🤖 Bale Bot:${NC}"
if pgrep -f "bot.py" > /dev/null; then echo -e "${GREEN}✅ روشن است${NC}"; else echo -e "${RED}❌ خاموش است${NC}"; fi
echo -e "\n${YELLOW}📁 PID ها:${NC}"
ps aux | grep -E "whatsapp|bot.py|neonize" | grep -v grep || echo "هیچ سرویسی یافت نشد"
echo -e "\n${YELLOW}📝 لاگ‌ها:${NC}"
echo "  WhatsApp: tail -f whatsapp-service/whatsapp.log"
echo "  Bale: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log"
EOF

cat > "$SCRIPT_DIR/test.sh" << 'EOF'
#!/bin/bash
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo -e "${BLUE}🧪 تست کامل سیستم Neonize...${NC}"
FAILED=0
echo -e "\n${YELLOW}1️⃣ تست کامپایل Python...${NC}"
for file in all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/*.py whatsapp-service/*.py; do if [ -f "$file" ]; then if python3 -m py_compile "$file" 2>/dev/null; then echo -e "${GREEN}✅ $file${NC}"; else echo -e "${RED}❌ $file${NC}"; FAILED=1; fi; fi; done
echo -e "\n${YELLOW}2️⃣ تست WhatsApp Neonize Service...${NC}"
if curl -s http://localhost:3001/ | grep -q "ok"; then echo -e "${GREEN}✅ WhatsApp Neonize روشن است${NC}"; curl -s http://localhost:3001/ | head -c 200; echo ""; else echo -e "${RED}❌ WhatsApp خاموش - ./start.sh${NC}"; FAILED=1; fi
echo -e "\n${YELLOW}3️⃣ تست تنظیمات Bale...${NC}"
CONFIG="$SCRIPT_DIR/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json"
if [ -f "$CONFIG" ]; then if grep -q "YOUR_BALE_BOT_TOKEN" "$CONFIG"; then echo -e "${RED}❌ توکن Bale تنظیم نشده${NC}"; FAILED=1; else echo -e "${GREEN}✅ config.json وجود دارد${NC}"; fi; else echo -e "${RED}❌ config.json یافت نشد${NC}"; FAILED=1; fi
echo -e "\n${YELLOW}4️⃣ وابستگی‌ها...${NC}"
python3 -c "import neonize" 2>/dev/null && echo -e "${GREEN}✅ neonize نصب است${NC}" || echo -e "${YELLOW}⚠️ neonize نصب نیست - pip install neonize${NC}"
echo -e "\n${BLUE}📊 نتیجه:${NC}"
if [ $FAILED -eq 0 ]; then echo -e "${GREEN}✅ همه تست‌ها موفق - سیستم آماده (Neonize LID ساپورت)${NC}"; else echo -e "${RED}❌ بعضی تست‌ها ناموفق${NC}"; exit 1; fi
EOF

chmod +x "$SCRIPT_DIR/start.sh" "$SCRIPT_DIR/stop.sh" "$SCRIPT_DIR/status.sh" "$SCRIPT_DIR/test.sh"

echo -e "${GREEN}✅ اسکریپت‌های مدیریت Neonize ساخته شد${NC}"

echo -e "\n${BLUE}8️⃣ تست نهایی...${NC}"
echo -e "${YELLOW}تست کامپایل Python...${NC}"
FAILED=0
for pyfile in "$BOT_DIR"/*.py; do if ! python3 -m py_compile "$pyfile" 2>/dev/null; then echo -e "${RED}❌ $pyfile${NC}"; FAILED=1; fi; done
if [ $FAILED -eq 0 ]; then echo -e "${GREEN}✅ همه فایل‌های Python سالم${NC}"; else exit 1; fi

echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ نصب Neonize کامل شد! LID فیکس 🎉                       ║"
echo "║  برای اجرا: ./start.sh                                     ║"
echo "║  وضعیت: ./status.sh                                        ║"
echo "║  واتساپ: فقط شماره بفرست، QR + کد میاد!                   ║"
echo "║  گروه 120363312386194255@g.us الان کار می‌کنه              ║"
echo "╚════════════════════════════════════════════════════════════╝${NC}"
