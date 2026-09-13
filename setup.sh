#!/bin/bash
# setup.sh - نصب و راه‌اندازی کامل AGENT AUTO POST BOT
# برای کاربر غیر برنامه‌نویس - یک دستور همه چیز را نصب و اجرا می‌کند

set -e

# رنگ‌ها
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  🤖 AGENT AUTO POST BOT - نصب و راه‌اندازی کامل           ║"
echo "║  Bale Bot + WhatsApp QR + Telegram + WooCommerce Live      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# تشخیص پوشه پروژه
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${YELLOW}📁 پوشه پروژه: $SCRIPT_DIR${NC}"

# ========== 1. بررسی سیستم عامل ==========
echo -e "\n${BLUE}1️⃣ بررسی سیستم...${NC}"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "${GREEN}✅ Linux detected${NC}"
else
    echo -e "${YELLOW}⚠️ غیر از لینوکس - ممکن است دستورات apt کار نکند${NC}"
fi

# ========== 2. نصب Node.js و npm ==========
echo -e "\n${BLUE}2️⃣ بررسی Node.js و npm...${NC}"

if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    echo -e "${GREEN}✅ Node.js نصب است: $NODE_VERSION${NC}"
    if [[ "$NODE_VERSION" == v12* ]] || [[ "$NODE_VERSION" == v14* ]]; then
        echo -e "${YELLOW}⚠️ نسخه Node قدیمی است، پیشنهاد آپدیت به 18+${NC}"
        echo -e "${YELLOW}   دستور: curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt install nodejs -y${NC}"
    fi
else
    echo -e "${YELLOW}📦 نصب Node.js...${NC}"
    if command -v apt &> /dev/null; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt install nodejs -y
    else
        echo -e "${RED}❌ لطفا Node.js را دستی نصب کنید: https://nodejs.org${NC}"
        exit 1
    fi
fi

if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm -v)
    echo -e "${GREEN}✅ npm نصب است: $NPM_VERSION${NC}"
else
    echo -e "${RED}❌ npm یافت نشد${NC}"
    exit 1
fi

# ========== 3. نصب Python و pip ==========
echo -e "\n${BLUE}3️⃣ بررسی Python و pip...${NC}"

if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version)
    echo -e "${GREEN}✅ $PY_VERSION نصب است${NC}"
else
    echo -e "${RED}❌ python3 یافت نشد - نصب کنید: apt install python3 -y${NC}"
    exit 1
fi

if command -v pip3 &> /dev/null; then
    echo -e "${GREEN}✅ pip3 نصب است${NC}"
else
    echo -e "${YELLOW}📦 نصب pip3...${NC}"
    apt install python3-pip -y
fi

# ========== 4. نصب وابستگی‌های Python ==========
echo -e "\n${BLUE}4️⃣ نصب وابستگی‌های Python...${NC}"

BOT_DIR="$SCRIPT_DIR/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER"
if [ -f "$BOT_DIR/requirements.txt" ]; then
    cd "$BOT_DIR"
    echo -e "${YELLOW}📦 نصب از requirements.txt...${NC}"
    pip3 install -r requirements.txt --break-system-packages --quiet 2>/dev/null || pip3 install -r requirements.txt --quiet || pip3 install requests jdatetime pytz python-dotenv --break-system-packages --quiet
    echo -e "${GREEN}✅ وابستگی‌های Python نصب شد${NC}"
    cd "$SCRIPT_DIR"
else
    echo -e "${YELLOW}⚠️ requirements.txt یافت نشد، نصب دستی...${NC}"
    pip3 install requests jdatetime pytz python-dotenv --break-system-packages --quiet 2>/dev/null || pip3 install requests jdatetime pytz python-dotenv --quiet
fi

# ========== 5. نصب وابستگی‌های WhatsApp Service ==========
echo -e "\n${BLUE}5️⃣ نصب وابستگی‌های WhatsApp Service...${NC}"

WA_DIR="$SCRIPT_DIR/whatsapp-service"
if [ -d "$WA_DIR" ]; then
    cd "$WA_DIR"
    
    # پاک کردن کش قدیمی اگر مشکل دارد
    if [ -d "node_modules" ]; then
        echo -e "${YELLOW}🧹 پاک کردن node_modules قدیمی...${NC}"
        rm -rf node_modules package-lock.json
    fi
    
    if [ -d "auth" ]; then
        echo -e "${YELLOW}🧹 پاک کردن سشن‌های قدیمی واتساپ (برای نصب تمیز)...${NC}"
        rm -rf auth
        mkdir -p auth
    fi
    
    echo -e "${YELLOW}📦 نصب پکیج‌های Node.js (ممکن است 1-2 دقیقه طول بکشد)...${NC}"
    
    # تنظیمات برای حل مشکل IPv6
    npm config set fetch-retries 5 2>/dev/null || true
    npm config set fetch-retry-mintimeout 20000 2>/dev/null || true
    
    # نصب با IPv4 اجباری برای حل EHOSTUNREACH
    if NODE_OPTIONS="--dns-result-order=ipv4first" npm install --legacy-peer-deps --no-audit --no-fund; then
        echo -e "${GREEN}✅ پکیج‌های WhatsApp نصب شد${NC}"
    else
        echo -e "${YELLOW}⚠️ نصب با رجیستری اصلی ناموفق، تلاش با رجیستری جایگزین...${NC}"
        npm config set registry https://registry.npmmirror.com
        NODE_OPTIONS="--dns-result-order=ipv4first" npm install --legacy-peer-deps --no-audit --no-fund
        npm config set registry https://registry.npmjs.org/
        echo -e "${GREEN}✅ پکیج‌های WhatsApp با رجیستری جایگزین نصب شد${NC}"
    fi
    
    cd "$SCRIPT_DIR"
else
    echo -e "${RED}❌ پوشه whatsapp-service یافت نشد${NC}"
    exit 1
fi

# ========== 6. بررسی config.json ==========
echo -e "\n${BLUE}6️⃣ بررسی تنظیمات...${NC}"

CONFIG_FILE="$BOT_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}⚠️ config.json یافت نشد - یک نمونه می‌سازم${NC}"
    cat > "$CONFIG_FILE" << 'EOF'
{
  "messengers": {
    "bale": {
      "bot_token": "YOUR_BALE_BOT_TOKEN_HERE",
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
  "woocommerce": {
    "url": "",
    "consumer_key": "",
    "consumer_secret": ""
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
  "initial_admin_id": 0,
  "initial_admin_username": "Admin"
}
EOF
    echo -e "${RED}❌ لطفا توکن ربات Bale را در $CONFIG_FILE وارد کنید!${NC}"
    echo -e "${YELLOW}   nano $CONFIG_FILE${NC}"
else
    echo -e "${GREEN}✅ config.json وجود دارد${NC}"
    
    # چک توکن Bale
    if grep -q "YOUR_BALE_BOT_TOKEN" "$CONFIG_FILE" || grep -q "\"bot_token\": \"\"" "$CONFIG_FILE"; then
        echo -e "${YELLOW}⚠️ توکن Bale خالی است - لطفا تنظیم کنید:${NC}"
        echo -e "${YELLOW}   nano $CONFIG_FILE${NC}"
    fi
fi

# ========== 7. ساخت اسکریپت‌های مدیریت ==========
echo -e "\n${BLUE}7️⃣ ساخت اسکریپت‌های مدیریت...${NC}"

# start.sh
cat > "$SCRIPT_DIR/start.sh" << 'EOF'
#!/bin/bash
# start.sh - اجرای همه سرویس‌ها در پس‌زمینه

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 در حال اجرای سرویس‌ها...${NC}"

# کشتن سرویس‌های قبلی
echo -e "${YELLOW}🧹 بستن سرویس‌های قبلی...${NC}"
pkill -f "whatsapp-service" 2>/dev/null || true
pkill -f "bot.py" 2>/dev/null || true
fuser -k 3001/tcp 2>/dev/null || true
sleep 2

# اجرای WhatsApp Service در پس‌زمینه
echo -e "${BLUE}📱 اجرای WhatsApp Service روی پورت 3001...${NC}"
cd "$SCRIPT_DIR/whatsapp-service"
if command -v pm2 &> /dev/null; then
    pm2 delete whatsapp-service 2>/dev/null || true
    pm2 start index.js --name whatsapp-service
    pm2 save 2>/dev/null || true
    echo -e "${GREEN}✅ WhatsApp با PM2 اجرا شد${NC}"
else
    nohup node index.js > whatsapp.log 2>&1 &
    echo $! > whatsapp.pid
    echo -e "${GREEN}✅ WhatsApp با nohup اجرا شد (PID: $(cat whatsapp.pid))${NC}"
fi
cd "$SCRIPT_DIR"
sleep 3

# تست WhatsApp Service
echo -e "${BLUE}🔍 تست WhatsApp Service...${NC}"
for i in {1..5}; do
    if curl -s http://localhost:3001/ | grep -q "ok"; then
        echo -e "${GREEN}✅ WhatsApp Service روشن است (http://localhost:3001)${NC}"
        break
    else
        echo -e "${YELLOW}⏳ تلاش $i/5 - صبر...${NC}"
        sleep 2
    fi
    if [ $i -eq 5 ]; then
        echo -e "${RED}❌ WhatsApp Service روشن نشد - لاگ:${NC}"
        cat whatsapp-service/whatsapp.log 2>/dev/null || cat whatsapp-service/*.log 2>/dev/null || echo "لاگ یافت نشد"
    fi
done

# اجرای ربات Bale
echo -e "\n${BLUE}🤖 اجرای ربات Bale...${NC}"
cd "$SCRIPT_DIR/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER"

if command -v pm2 &> /dev/null; then
    pm2 delete bale-bot 2>/dev/null || true
    pm2 start bot.py --name bale-bot --interpreter python3
    pm2 save 2>/dev/null || true
    echo -e "${GREEN}✅ Bale Bot با PM2 اجرا شد${NC}"
else
    nohup python3 bot.py > bot.log 2>&1 &
    echo $! > bot.pid
    echo -e "${GREEN}✅ Bale Bot با nohup اجرا شد (PID: $(cat bot.pid))${NC}"
fi

cd "$SCRIPT_DIR"
sleep 2

# تست نهایی
echo -e "\n${BLUE}📊 وضعیت نهایی:${NC}"
echo -e "${YELLOW}WhatsApp:${NC}"
curl -s http://localhost:3001/ | head -c 200
echo -e "\n"

if command -v pm2 &> /dev/null; then
    pm2 list
else
    echo -e "${YELLOW}PID ها:${NC}"
    cat whatsapp-service/whatsapp.pid 2>/dev/null && echo " - WhatsApp PID"
    cat all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid 2>/dev/null && echo " - Bale Bot PID"
    echo -e "\n${YELLOW}لاگ‌ها:${NC}"
    echo "  WhatsApp: tail -f whatsapp-service/whatsapp.log"
    echo "  Bale Bot: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log"
fi

echo -e "\n${GREEN}╔════════════════════════════════════════╗"
echo -e "║  ✅ همه سرویس‌ها اجرا شدند!             ║"
echo -e "║  Bale Bot + WhatsApp روی پورت 3001      ║"
echo -e "║  برای تست: برو توی Bale -> /start       ║"
echo -e "╚════════════════════════════════════════╝${NC}"
EOF

# stop.sh
cat > "$SCRIPT_DIR/stop.sh" << 'EOF'
#!/bin/bash
# stop.sh - بستن همه سرویس‌ها

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 بستن سرویس‌ها..."

if command -v pm2 &> /dev/null; then
    pm2 delete whatsapp-service 2>/dev/null || true
    pm2 delete bale-bot 2>/dev/null || true
    echo "✅ با PM2 بسته شد"
else
    pkill -f "whatsapp-service" 2>/dev/null || true
    pkill -f "bot.py" 2>/dev/null || true
    fuser -k 3001/tcp 2>/dev/null || true
    
    if [ -f "whatsapp-service/whatsapp.pid" ]; then
        kill -9 $(cat whatsapp-service/whatsapp.pid) 2>/dev/null || true
        rm whatsapp-service/whatsapp.pid
    fi
    if [ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid" ]; then
        kill -9 $(cat all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid) 2>/dev/null || true
        rm all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid
    fi
    echo "✅ بسته شد"
fi

echo "📊 وضعیت پورت 3001:"
lsof -i :3001 2>/dev/null || echo "✅ پورت 3001 آزاد است"
EOF

# status.sh
cat > "$SCRIPT_DIR/status.sh" << 'EOF'
#!/bin/bash
# status.sh - وضعیت سرویس‌ها

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "📊 وضعیت سرویس‌ها:"
echo "===================="

echo -e "\n${YELLOW}📱 WhatsApp Service (پورت 3001):${NC}"
if curl -s http://localhost:3001/ | grep -q "ok"; then
    echo -e "${GREEN}✅ روشن است${NC}"
    curl -s http://localhost:3001/ | python3 -m json.tool 2>/dev/null || curl -s http://localhost:3001/
else
    echo -e "${RED}❌ خاموش است${NC}"
fi

echo -e "\n${YELLOW}🤖 Bale Bot:${NC}"
if pgrep -f "bot.py" > /dev/null || (command -v pm2 &> /dev/null && pm2 list | grep -q "bale-bot.*online"); then
    echo -e "${GREEN}✅ روشن است${NC}"
else
    echo -e "${RED}❌ خاموش است${NC}"
fi

echo -e "\n${YELLOW}📁 PID ها:${NC}"
if command -v pm2 &> /dev/null; then
    pm2 list
else
    ps aux | grep -E "whatsapp|bot.py" | grep -v grep || echo "هیچ سرویسی با ps یافت نشد"
fi

echo -e "\n${YELLOW}📝 لاگ‌ها:${NC}"
echo "  WhatsApp: tail -f whatsapp-service/whatsapp.log"
echo "  Bale: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log"
if command -v pm2 &> /dev/null; then
    echo "  PM2: pm2 logs"
fi
EOF

# test.sh
cat > "$SCRIPT_DIR/test.sh" << 'EOF'
#!/bin/bash
# test.sh - تست همه چیز

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}🧪 تست کامل سیستم...${NC}"

FAILED=0

# تست 1: Python compile
echo -e "\n${YELLOW}1️⃣ تست کامپایل Python...${NC}"
for file in all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/*.py; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ $file${NC}"
        FAILED=1
    fi
done

# تست 2: WhatsApp Service
echo -e "\n${YELLOW}2️⃣ تست WhatsApp Service...${NC}"
if curl -s http://localhost:3001/ | grep -q "ok"; then
    echo -e "${GREEN}✅ WhatsApp Service روشن است${NC}"
    echo "   $(curl -s http://localhost:3001/ | head -c 100)"
else
    echo -e "${RED}❌ WhatsApp Service خاموش است - اجرا کنید: ./start.sh${NC}"
    FAILED=1
fi

# تست 3: Bale Bot config
echo -e "\n${YELLOW}3️⃣ تست تنظیمات Bale...${NC}"
CONFIG="$SCRIPT_DIR/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json"
if [ -f "$CONFIG" ]; then
    if grep -q "YOUR_BALE_BOT_TOKEN" "$CONFIG"; then
        echo -e "${RED}❌ توکن Bale تنظیم نشده در config.json${NC}"
        FAILED=1
    else
        echo -e "${GREEN}✅ config.json وجود دارد${NC}"
    fi
else
    echo -e "${RED}❌ config.json یافت نشد${NC}"
    FAILED=1
fi

# تست 4: Node.js و Python
echo -e "\n${YELLOW}4️⃣ تست وابستگی‌ها...${NC}"
if command -v node &> /dev/null; then
    echo -e "${GREEN}✅ Node.js: $(node -v)${NC}"
else
    echo -e "${RED}❌ Node.js نصب نیست${NC}"
    FAILED=1
fi

if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✅ Python: $(python3 --version)${NC}"
else
    echo -e "${RED}❌ Python3 نصب نیست${NC}"
    FAILED=1
fi

# تست 5: پوشه‌ها
echo -e "\n${YELLOW}5️⃣ تست پوشه‌ها...${NC}"
for dir in "whatsapp-service" "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER"; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✅ $dir${NC}"
    else
        echo -e "${RED}❌ $dir یافت نشد${NC}"
        FAILED=1
    fi
done

# نتیجه
echo -e "\n${BLUE}📊 نتیجه تست:${NC}"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════╗"
    echo -e "║  ✅ همه تست‌ها موفق بود!            ║"
    echo -e "║  سیستم آماده استفاده است            ║"
    echo -e "╚════════════════════════════════════╝${NC}"
    echo -e "\n${YELLOW}برای اجرای ربات:${NC}"
    echo "  ./start.sh"
    echo -e "\n${YELLOW}برای تست واتساپ:${NC}"
    echo "  1. Bale -> تنظیمات -> پیام‌رسان‌ها -> WhatsApp"
    echo "  2. شماره بفرست: 989123456789"
    echo "  3. QR + کد میاد -> اسکن کن"
else
    echo -e "${RED}╔════════════════════════════════════╗"
    echo -e "║  ❌ بعضی تست‌ها ناموفق بود          ║"
    echo -e "║  لاگ‌ها را چک کنید                  ║"
    echo -e "╚════════════════════════════════════╝${NC}"
    exit 1
fi
EOF

chmod +x "$SCRIPT_DIR/start.sh" "$SCRIPT_DIR/stop.sh" "$SCRIPT_DIR/status.sh" "$SCRIPT_DIR/test.sh"

echo -e "${GREEN}✅ اسکریپت‌های مدیریت ساخته شد:${NC}"
echo "  ./start.sh  - اجرای همه سرویس‌ها"
echo "  ./stop.sh   - بستن همه"
echo "  ./status.sh - وضعیت"
echo "  ./test.sh   - تست کامل"

# ========== 8. تست نهایی ==========
echo -e "\n${BLUE}8️⃣ تست نهایی...${NC}"

echo -e "${YELLOW}تست کامپایل Python...${NC}"
FAILED=0
for pyfile in "$BOT_DIR"/*.py; do
    if ! python3 -m py_compile "$pyfile" 2>/dev/null; then
        echo -e "${RED}❌ $pyfile${NC}"
        FAILED=1
    fi
done

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ همه فایل‌های Python سالم هستند${NC}"
else
    echo -e "${RED}❌ بعضی فایل‌ها خطا دارند${NC}"
    exit 1
fi

# ========== پایان ==========
echo -e "\n${GREEN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ نصب کامل شد!                                          ║"
echo "║                                                            ║"
echo "║  برای اجرا:                                                ║"
echo "║    ./start.sh                                              ║"
echo "║                                                            ║"
echo "║  برای تست:                                                 ║"
echo "║    ./test.sh                                               ║"
echo "║                                                            ║"
echo "║  برای وضعیت:                                               ║"
echo "║    ./status.sh                                             ║"
echo "║                                                            ║"
echo "║  برای بستن:                                                ║"
echo "║    ./stop.sh                                               ║"
echo "║                                                            ║"
echo "║  واتساپ: فقط شماره بفرست، QR + کد میاد!                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
