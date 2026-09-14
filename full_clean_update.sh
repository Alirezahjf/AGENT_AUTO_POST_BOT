#!/bin/bash
# full_clean_update.sh - آپدیت کامل از صفر - حذف همه دیتابیس یوزرها برای پایداری
# برای وقتی که می‌خوای همه چیز از اول بیاد

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${RED}⚠️ آپدیت کامل از صفر - همه دیتابیس یوزرها حذف می‌شود!${NC}"
echo -e "${YELLOW}این برای پایداری و اطمینان از درستی آپدیت است${NC}"
echo ""

# بستن سرویس‌ها
echo -e "${BLUE}🛑 بستن سرویس‌های قدیمی...${NC}"
./stop.sh 2>/dev/null; true
pkill -9 -f "node.*index.js" 2>/dev/null; true
pkill -9 -f "python.*bot.py" 2>/dev/null; true
fuser -k 3001/tcp 2>/dev/null; true
sleep 3

# حذف کامل
echo -e "${RED}🗑️ حذف پوشه قدیمی...${NC}"
cd ~
rm -rf AGENT_AUTO_POST_BOT
echo -e "${GREEN}✅ حذف شد${NC}"

# کلون جدید
echo -e "${BLUE}📥 کلون کد جدید از برنچ arena/01a086a1-agent-auto-post-bot...${NC}"
git clone --branch arena/01a086a1-agent-auto-post-bot https://github.com/Alirezahjf/AGENT_AUTO_POST_BOT.git AGENT_AUTO_POST_BOT
cd AGENT_AUTO_POST_BOT

# نصب
echo -e "${BLUE}📦 نصب وابستگی‌ها...${NC}"
chmod +x *.sh
./setup.sh

echo ""
echo -e "${GREEN}✅ آپدیت کامل از صفر انجام شد!${NC}"
echo -e "${BLUE}📝 لاگ: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log${NC}"
echo -e "${BLUE}📊 وضعیت: ./status.sh${NC}"
echo ""
echo -e "${YELLOW}🎁 کاربران جدید 1 روز تست رایگان دارند - بدون پرداخت${NC}"
echo -e "${YELLOW}💰 قیمت جدید: 20 میلیون تومان (200,000,000 ریال)${NC}"
