#!/bin/bash
# start.sh - اجرای همه سرویس‌ها در پس‌زمینه - بدون نیاز به چند سشن
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
echo -e "${BLUE}🚀 در حال اجرای سرویس‌ها...${NC}"

# پاک کردن لاگ‌های قدیمی و PID ها
rm -f whatsapp-service/whatsapp.pid all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid
# حفظ سشن‌های واتساپ - پاک نمی‌کنیم (کاربر خواست)
# rm -f whatsapp-service/auth/* 2>/dev/null; true
mkdir -p whatsapp-service/auth

# اجرای WhatsApp Service
echo -e "${BLUE}📱 WhatsApp Service روی پورت 3001...${NC}"
cd "$SCRIPT_DIR/whatsapp-service"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}📦 نصب وابستگی‌های WhatsApp...${NC}"
    NODE_OPTIONS="--dns-result-order=ipv4first" npm install --legacy-peer-deps --no-audit --no-fund
fi
# اطمینان از وجود پوشه auth با لاگ
mkdir -p auth
echo -e "${BLUE}📁 Auth: $(pwd)/auth - $(ls auth 2>/dev/null | wc -l) session(s)${NC}"
ls -1 auth 2>/dev/null | head -5
# بستن پروسه‌های قدیمی روی پورت 3001
fuser -k 3001/tcp 2>/dev/null || true
pkill -f "node.*index.js" 2>/dev/null || true
sleep 1
nohup node index.js > whatsapp.log 2>&1 &
echo $! > whatsapp.pid
echo -e "${GREEN}✅ WhatsApp اجرا شد PID: $(cat whatsapp.pid)${NC}"
cd "$SCRIPT_DIR"
sleep 4
# چک کردن با چند تلاش
for i in {1..5}; do
    if curl -s http://localhost:3001/ | grep -q "ok"; then
        echo -e "${GREEN}✅ WhatsApp روشن http://localhost:3001${NC}"
        break
    else
        if [ $i -eq 5 ]; then
            echo -e "${RED}❌ WhatsApp روشن نشد - لاگ:${NC}"
            tail -20 whatsapp-service/whatsapp.log
            echo -e "${YELLOW}⏳ تلاش مجدد...${NC}"
        else
            echo -e "${YELLOW}⏳ WhatsApp در حال بالا آمدن... تلاش $i${NC}"
            sleep 2
        fi
    fi
done

# اجرای Bale Bot
echo -e "\n${BLUE}🤖 Bale Bot...${NC}"
cd "$SCRIPT_DIR/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER"
# چک کردن auth.db - اگر خراب است فقط هشدار بده، پاک نکن مگر اینکه واقعا خراب باشد
if [ -f "auth.db" ]; then
    if ! python3 -c "import sqlite3; sqlite3.connect('auth.db', timeout=2).execute('SELECT 1')" 2>/dev/null; then
        echo -e "${RED}⚠️ auth.db خراب است، بکاپ و بازسازی...${NC}"
        cp auth.db auth.db.backup.$(date +%s) 2>/dev/null; true
        rm -f auth.db auth.db-journal
        echo -e "${YELLOW}⚠️ بکاپ گرفته شد، دیتابیس جدید ساخته می‌شود - کاربران باید دوباره تایید شوند${NC}"
    else
        echo -e "${GREEN}✅ auth.db سالم است - حفظ شد${NC}"
    fi
fi
# حفظ پوشه یوزرها - پاک نمی‌کنیم
mkdir -p users
if [ -d "users" ] && [ "$(ls -A users 2>/dev/null)" ]; then
    echo -e "${GREEN}✅ پوشه users حفظ شد ($(ls users | wc -l) کاربر)${NC}"
fi
if [ -f "bot.pid" ]; then rm -f bot.pid; fi
# بستن ربات‌های قدیمی
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
