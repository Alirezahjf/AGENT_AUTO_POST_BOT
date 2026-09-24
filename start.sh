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

# اجرای WhatsApp Service - NEONIZE (Python whatsmeow) - حرفه‌ای بدون No sessions
echo -e "${BLUE}📱 WhatsApp Neonize Service روی پورت 3001 (LID ساپورت)...${NC}"
cd "$SCRIPT_DIR/whatsapp-service"
# اطمینان از وجود پوشه auth با لاگ
mkdir -p auth
echo -e "${BLUE}📁 Auth: $(pwd)/auth - $(ls auth 2>/dev/null | wc -l) session(s)${NC}"
ls -1 auth 2>/dev/null | head -5
# بستن پروسه‌های قدیمی روی پورت 3001
fuser -k 3001/tcp 2>/dev/null || true
pkill -f "node.*index.js" 2>/dev/null || true
pkill -f "neonize_service.py" 2>/dev/null || true
sleep 1
# نصب وابستگی‌های پایتون برای neonize
if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}📦 نصب وابستگی‌های Neonize...${NC}"
    pip install -r requirements.txt --break-system-packages -q 2>&1 | tail -5 || pip install fastapi uvicorn neonize segno qrcode pillow --break-system-packages -q
fi
# اجرای سرویس Neonize
echo -e "${BLUE}🚀 اجرای Neonize service...${NC}"
nohup python3 neonize_service.py > whatsapp.log 2>&1 &
echo $! > whatsapp.pid
echo -e "${GREEN}✅ WhatsApp Neonize اجرا شد PID: $(cat whatsapp.pid)${NC}"
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
# چک کردن auth.db - امن: هرگز خودکار پاک نمی‌کند، فقط در صورت سلامت ادامه می‌دهد
if [ -f "auth.db" ]; then
    # چند تلاش با فاصله: ممکن است پروسه قبلی هنوز قفل داشته باشد (سرور شلوغ)
    DB_OK=0
    for i in 1 2 3 4 5; do
        if python3 -c "import sqlite3; c=sqlite3.connect('auth.db', timeout=10); c.execute('SELECT count(*) FROM users').fetchone(); c.close()" 2>/dev/null; then DB_OK=1; break; fi
        echo -e "${YELLOW}⏳ auth.db قفل/مشغول است، تلاش مجدد ($i/5)...${NC}"
        sleep 2
    done
    if [ "$DB_OK" = "1" ]; then
        echo -e "${GREEN}✅ auth.db سالم است - حفظ شد${NC}"
    else
        echo -e "${RED}❌ auth.db قابل خواندن نیست! استارت متوقف شد تا دیتابیس آسیب نبیند.${NC}"
        cp auth.db "auth.db.backup.$(date +%s)" 2>/dev/null; true
        echo -e "${YELLOW}📁 از auth.db بکاپ گرفته شد (auth.db.backup.*)${NC}"
        echo -e "${YELLOW}🔍 اول بررسی کن: پروسه قدیمی bot.py هنوز روشن است؟ (ps aux | grep bot.py)${NC}"
        echo -e "${YELLOW}   اگر پروسه‌ای ماند: ./stop.sh و چند ثانیه صبر، بعد دوباره ./start.sh${NC}"
        echo -e "${RED}⛔ ربات اجرا نشد - auth.db دست‌نخورده باقی ماند.${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}ℹ️ auth.db وجود ندارد (نصب تازه) - هنگام اجرا ساخته می‌شود${NC}"
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
