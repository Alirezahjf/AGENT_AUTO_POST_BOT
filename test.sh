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
