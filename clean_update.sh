#!/bin/bash
# clean_update.sh - آپدیت تمیز بدون پاک کردن یوزرها و سشن واتساپ
# برای وقتی که می‌خوای کد جدید رو بگیری ولی کانفیگ یوزرها حفظ بشه

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${BLUE}🔄 آپدیت تمیز - حفظ یوزرها و سشن واتساپ...${NC}"

# بستن سرویس‌ها
echo -e "${BLUE}🛑 بستن سرویس‌های قدیمی...${NC}"
./stop.sh 2>/dev/null; true
pkill -9 -f "node.*index.js" 2>/dev/null; true
pkill -9 -f "python.*bot.py" 2>/dev/null; true
fuser -k 3001/tcp 2>/dev/null; true
sleep 2

# بکاپ یوزرها و سشن‌ها
echo -e "${BLUE}💾 بکاپ یوزرها و سشن‌ها...${NC}"
BACKUP_DIR="/tmp/bot_backup_$(date +%s)"
mkdir -p "$BACKUP_DIR"
if [ -d "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users" ]; then
    cp -r all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users "$BACKUP_DIR/" 2>/dev/null
    echo -e "${GREEN}✅ بکاپ users: $(ls all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users 2>/dev/null | wc -l) کاربر${NC}"
fi
if [ -d "whatsapp-service/auth" ]; then
    cp -r whatsapp-service/auth "$BACKUP_DIR/whatsapp_auth" 2>/dev/null
    echo -e "${GREEN}✅ بکاپ whatsapp auth: $(ls whatsapp-service/auth 2>/dev/null | wc -l) سشن${NC}"
fi
if [ -f "whatsapp-service/sessions_db.json" ]; then
    cp whatsapp-service/sessions_db.json "$BACKUP_DIR/sessions_db.json" 2>/dev/null
    echo -e "${GREEN}✅ بکاپ sessions_db.json${NC}"
fi
if [ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db" ]; then
    cp all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db "$BACKUP_DIR/" 2>/dev/null
    echo -e "${GREEN}✅ بکاپ auth.db${NC}"
fi
if [ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json" ]; then
    cp all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json "$BACKUP_DIR/" 2>/dev/null
    echo -e "${GREEN}✅ بکاپ config.json${NC}"
fi
# بکاپ اضافی whatsapp_auth_backup داخل users
if [ -d "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users" ]; then
    find all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users -type d -name "whatsapp_auth_backup" 2>/dev/null | while read dir; do
        echo -e "${GREEN}✅ بکاپ موجود: $dir${NC}"
    done
fi

echo -e "${BLUE}📥 دریافت کد جدید از برنچ...${NC}"
cd ~
rm -rf AGENT_AUTO_POST_BOT_NEW
git clone --branch arena/01a086a1-agent-auto-post-bot https://github.com/Alirezahjf/AGENT_AUTO_POST_BOT.git AGENT_AUTO_POST_BOT_NEW

echo -e "${BLUE}♻️ بازگردانی یوزرها و سشن‌ها...${NC}"
# بازگردانی users
if [ -d "$BACKUP_DIR/users" ]; then
    rm -rf ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users
    cp -r "$BACKUP_DIR/users" ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users
    echo -e "${GREEN}✅ بازگردانی users${NC}"
fi
# بازگردانی whatsapp auth
if [ -d "$BACKUP_DIR/whatsapp_auth" ]; then
    rm -rf ~/AGENT_AUTO_POST_BOT_NEW/whatsapp-service/auth
    cp -r "$BACKUP_DIR/whatsapp_auth" ~/AGENT_AUTO_POST_BOT_NEW/whatsapp-service/auth
    echo -e "${GREEN}✅ بازگردانی whatsapp auth: $(ls $BACKUP_DIR/whatsapp_auth 2>/dev/null | wc -l) سشن${NC}"
fi
# بازگردانی sessions_db.json
if [ -f "$BACKUP_DIR/sessions_db.json" ]; then
    cp "$BACKUP_DIR/sessions_db.json" ~/AGENT_AUTO_POST_BOT_NEW/whatsapp-service/sessions_db.json
    echo -e "${GREEN}✅ بازگردانی sessions_db.json${NC}"
fi
# بازگردانی auth.db
if [ -f "$BACKUP_DIR/auth.db" ]; then
    cp "$BACKUP_DIR/auth.db" ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db
    echo -e "${GREEN}✅ بازگردانی auth.db${NC}"
fi
# بازگردانی config.json (اگر توکن جدید نخوای، قدیمی حفظ می‌شه)
if [ -f "$BACKUP_DIR/config.json" ]; then
    # فقط اگر config جدید توکن ندارد، قدیمی را بگذار
    NEW_TOKEN=$(cat ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json | grep -o '"bot_token": *"[^"]*"' | head -1)
    if echo "$NEW_TOKEN" | grep -q '""\|YOUR_BOT'; then
        cp "$BACKUP_DIR/config.json" ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json
        echo -e "${GREEN}✅ بازگردانی config.json (توکن قدیمی حفظ شد)${NC}"
    else
        echo -e "${YELLOW}⚠️ config.json جدید توکن دارد، قدیمی بازگردانی نشد - دستی چک کن${NC}"
        echo -e "${YELLOW}   بکاپ قدیمی در: $BACKUP_DIR/config.json${NC}"
    fi
fi

# جایگزینی پوشه قدیمی با جدید
echo -e "${BLUE}🔄 جایگزینی...${NC}"
rm -rf ~/AGENT_AUTO_POST_BOT
mv ~/AGENT_AUTO_POST_BOT_NEW ~/AGENT_AUTO_POST_BOT
cd ~/AGENT_AUTO_POST_BOT

echo -e "${BLUE}🚀 اجرای سرویس‌ها...${NC}"
./start.sh &

sleep 8
./status.sh

echo ""
echo -e "${GREEN}✅ آپدیت تمیز انجام شد - یوزرها حفظ شدند!${NC}"
echo -e "${BLUE}📁 بکاپ در: $BACKUP_DIR${NC}"
echo -e "${BLUE}📝 لاگ: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log${NC}"
echo ""
echo -e "${YELLOW}⚠️ ترمینال شما هنوز در پوشه قدیمی (حذف شده) است!${NC}"
echo -e "${BLUE}👉 حتما اجرا کن: cd ~/AGENT_AUTO_POST_BOT && ./status.sh${NC}"
echo -e "${BLUE}👉 سپس: ls whatsapp-service/auth/ | head${NC}"
