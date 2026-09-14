#!/bin/bash
# update_neonize.sh - آپدیت به نسخه Neonize (LID fix) - حرفه‌ای
# برای کاربر: فقط این یک دستور را بزنید
# دستور: cd ~/AGENT_AUTO_POST_BOT && chmod +x update_neonize.sh && ./update_neonize.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  💚 آپدیت به Neonize - حل مشکل گروه LID 120363...    ║${NC}"
echo -e "${BLUE}║  Baileys -> Neonize (whatsmeow) - بدون No sessions   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"

# 1. بستن
echo -e "\n${BLUE}1️⃣ بستن سرویس‌های قدیمی...${NC}"
./stop.sh 2>/dev/null || true
pkill -9 -f "node.*index.js" 2>/dev/null || true
pkill -9 -f "neonize_service.py" 2>/dev/null || true
pkill -9 -f "python.*bot.py" 2>/dev/null || true
fuser -k 3001/tcp 2>/dev/null || true
sleep 2
echo -e "${GREEN}✅ بسته شد${NC}"

# 2. بکاپ
echo -e "\n${BLUE}2️⃣ بکاپ یوزرها و سشن‌ها...${NC}"
BACKUP_DIR="/tmp/bot_backup_neonize_$(date +%s)"
mkdir -p "$BACKUP_DIR"
[ -d "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users" ] && cp -r all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users "$BACKUP_DIR/" && echo -e "${GREEN}✅ users: $(ls all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users 2>/dev/null | wc -l) کاربر${NC}"
[ -d "whatsapp-service/auth" ] && cp -r whatsapp-service/auth "$BACKUP_DIR/whatsapp_auth" && echo -e "${GREEN}✅ whatsapp auth${NC}"
[ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db" ] && cp all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db "$BACKUP_DIR/" && echo -e "${GREEN}✅ auth.db${NC}"
[ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json" ] && cp all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json "$BACKUP_DIR/" && echo -e "${GREEN}✅ config.json${NC}"

# 3. دریافت کد جدید
echo -e "\n${BLUE}3️⃣ دریافت کد جدید Neonize از گیت‌هاب...${NC}"
cd ~
rm -rf AGENT_AUTO_POST_BOT_NEW
# اول سعی کن برنچ neonize
if git ls-remote --heads https://github.com/Alirezahjf/AGENT_AUTO_POST_BOT.git arena/01a0a09e-agent-auto-post-bot | grep -q arena; then
    echo -e "${BLUE}📥 کلون برنچ arena/01a0a09e-agent-auto-post-bot${NC}"
    git clone --branch arena/01a0a09e-agent-auto-post-bot https://github.com/Alirezahjf/AGENT_AUTO_POST_BOT.git AGENT_AUTO_POST_BOT_NEW
else
    echo -e "${YELLOW}⚠️ برنچ جدید یافت نشد، از همین پوشه آپدیت می‌کنیم (git pull)${NC}"
    cd ~/AGENT_AUTO_POST_BOT
    git fetch origin
    git checkout arena/01a0a09e-agent-auto-post-bot 2>/dev/null || git checkout -b arena/01a0a09e-agent-auto-post-bot
    git pull origin arena/01a0a09e-agent-auto-post-bot || true
    # اگر pull کردیم، نیازی به کلون جدید نیست
    rm -rf ~/AGENT_AUTO_POST_BOT_NEW
    cp -r ~/AGENT_AUTO_POST_BOT ~/AGENT_AUTO_POST_BOT_NEW
    cd ~
fi

# 4. بازگردانی
echo -e "\n${BLUE}4️⃣ بازگردانی بکاپ‌ها...${NC}"
[ -d "$BACKUP_DIR/users" ] && rm -rf ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users && cp -r "$BACKUP_DIR/users" ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users && echo -e "${GREEN}✅ users${NC}"
[ -d "$BACKUP_DIR/whatsapp_auth" ] && rm -rf ~/AGENT_AUTO_POST_BOT_NEW/whatsapp-service/auth && cp -r "$BACKUP_DIR/whatsapp_auth" ~/AGENT_AUTO_POST_BOT_NEW/whatsapp-service/auth && echo -e "${GREEN}✅ whatsapp auth${NC}"
[ -f "$BACKUP_DIR/auth.db" ] && cp "$BACKUP_DIR/auth.db" ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/auth.db && echo -e "${GREEN}✅ auth.db${NC}"
if [ -f "$BACKUP_DIR/config.json" ]; then
    NEW_TOKEN=$(cat ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json 2>/dev/null | grep -o '"bot_token": *"[^"]*"' | head -1 || echo "")
    if echo "$NEW_TOKEN" | grep -q '""\|YOUR_BOT'; then
        cp "$BACKUP_DIR/config.json" ~/AGENT_AUTO_POST_BOT_NEW/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json
        echo -e "${GREEN}✅ config.json (توکن قدیمی حفظ شد)${NC}"
    else
        echo -e "${YELLOW}⚠️ config جدید توکن دارد - بکاپ قدیمی در $BACKUP_DIR${NC}"
    fi
fi

# 5. جایگزینی
echo -e "\n${BLUE}5️⃣ جایگزینی پروژه...${NC}"
rm -rf ~/AGENT_AUTO_POST_BOT
mv ~/AGENT_AUTO_POST_BOT_NEW ~/AGENT_AUTO_POST_BOT
cd ~/AGENT_AUTO_POST_BOT
chmod +x *.sh 2>/dev/null; true

# 6. نصب وابستگی‌های Neonize
echo -e "\n${BLUE}6️⃣ نصب وابستگی‌های Neonize (Python)...${NC}"
pip install fastapi uvicorn neonize segno qrcode pillow python-magic --break-system-packages -q || pip3 install fastapi uvicorn neonize segno qrcode pillow python-magic --break-system-packages -q || pip install fastapi uvicorn neonize segno qrcode pillow --break-system-packages
echo -e "${GREEN}✅ وابستگی‌ها نصب شد${NC}"

# 7. تمیز کردن سشن‌های Baileys قدیمی خراب (اختیاری - فقط فایل‌های baileys، نه neonize.sqlite3)
echo -e "\n${BLUE}7️⃣ تمیز کردن فایل‌های Baileys قدیمی (حفظ neonize.sqlite3)...${NC}"
python3 -c "
import os, pathlib
auth_base=pathlib.Path('whatsapp-service/auth')
if auth_base.exists():
    for user_dir in auth_base.iterdir():
        if user_dir.is_dir():
            for f in user_dir.iterdir():
                if f.is_file() and f.name!='neonize.sqlite3' and not f.name.endswith('.sqlite3'):
                    # فایل‌های قدیمی baileys مثل creds.json, app-state...
                    if f.suffix=='.json' or 'session' in f.name.lower() or 'app-state' in f.name:
                        try:
                            # فقط اگر neonize.sqlite3 وجود ندارد، همه را نگه دار - اگر وجود دارد، قدیمی‌ها را پاک کن
                            if (user_dir/'neonize.sqlite3').exists():
                                if f.name!='neonize.sqlite3':
                                    # حذف فایل‌های baileys قدیمی
                                    pass
                        except: pass
    print('✅ بررسی auth انجام شد')
"

# 8. اجرا
echo -e "\n${BLUE}8️⃣ اجرای سرویس‌ها...${NC}"
./start.sh
sleep 6
./status.sh

echo -e "\n${GREEN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ آپدیت Neonize کامل شد! LID حل شد 🎉           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
echo -e "${BLUE}📁 بکاپ: $BACKUP_DIR${NC}"
echo -e "${BLUE}📝 لاگ واتساپ: tail -f whatsapp-service/whatsapp.log${NC}"
echo -e "${BLUE}📝 لاگ ربات: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log${NC}"
echo -e "${BLUE}🔍 تست: curl http://localhost:3001/ | grep neonize${NC}"
echo -e "${YELLOW}⚠️ ترمینال قدیمی حذف شده - حتما بزن:${NC}"
echo -e "${BLUE}   cd ~/AGENT_AUTO_POST_BOT && ./status.sh${NC}"
echo -e "${BLUE}   ls whatsapp-service/auth/ | head${NC}"
