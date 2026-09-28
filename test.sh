#!/bin/bash
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo -e "${BLUE}🧪 تست کامل سیستم...${NC}"
FAILED=0
echo -e "\n${YELLOW}1️⃣ Python compile...${NC}"
for file in all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/*.py; do
    if python3 -m py_compile "$file" 2>/dev/null; then echo -e "${GREEN}✅ $(basename $file)${NC}"; else echo -e "${RED}❌ $(basename $file)${NC}"; FAILED=1; fi
done
echo -e "\n${YELLOW}🧾 Ticket subsystem regression tests...${NC}"
if python3 "$SCRIPT_DIR/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/test_support_tickets.py"; then
    echo -e "${GREEN}✅ Support ticket tests${NC}"
else
    echo -e "${RED}❌ Support ticket tests${NC}"
    FAILED=1
fi
echo -e "\n${YELLOW}🧪 Migration / group media / single-instance / bot flow tests...${NC}"
for t in test_access_upgrade.py test_media_group_upgrade.py test_media_group_dispatch.py test_instance_lock.py test_bot_flows.py; do
    OUT="$(mktemp)"
    if python3 "$SCRIPT_DIR/all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/$t" > "$OUT" 2>&1; then
        echo -e "${GREEN}✅ $t${NC}"
    else
        echo -e "${RED}❌ $t${NC}"; tail -n 25 "$OUT"; FAILED=1
    fi
    rm -f "$OUT"
done
echo -e "\n${YELLOW}2️⃣ WhatsApp Service...${NC}"
if curl -s http://localhost:3001/ | grep -q "ok"; then echo -e "${GREEN}✅ WhatsApp روشن${NC}"; else echo -e "${YELLOW}⚪ WhatsApp خاموش (برای تست واتساپ باید روشن باشد)${NC}"; fi
echo -e "\n${YELLOW}3️⃣ Config...${NC}"
if [ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/config.json" ]; then echo -e "${GREEN}✅ config.json${NC}"; else echo -e "${RED}❌ config.json نیست${NC}"; FAILED=1; fi
echo -e "\n${YELLOW}4️⃣ Node & Python...${NC}"
command -v node &> /dev/null && echo -e "${GREEN}✅ Node $(node -v)${NC}" || FAILED=1
command -v python3 &> /dev/null && echo -e "${GREEN}✅ Python $(python3 --version)${NC}" || FAILED=1
echo -e "\n${YELLOW}5️⃣ فایل‌های کلیدی...${NC}"
for f in "whatsapp-service/index.js" "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.py" "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/woocommerce.py" "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/messenger_whatsapp.py" "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/messenger_telegram.py"; do
    [ -f "$f" ] && echo -e "${GREEN}✅ $f${NC}" || { echo -e "${RED}❌ $f${NC}"; FAILED=1; }
done
if [ $FAILED -eq 0 ]; then echo -e "\n${GREEN}✅ همه تست‌ها موفق!${NC}"; echo "برای اجرا: ./start.sh"; else echo -e "\n${RED}❌ بعضی تست‌ها ناموفق${NC}"; exit 1; fi
