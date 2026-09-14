#!/bin/bash
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
echo "📊 وضعیت سرویس‌ها:"
echo -e "\n${YELLOW}📱 WhatsApp (3001):${NC}"
if curl -s http://localhost:3001/ | grep -q "ok"; then echo -e "${GREEN}✅ روشن${NC}"; curl -s http://localhost:3001/ | python3 -m json.tool 2>/dev/null | head -n 20; else echo -e "${RED}❌ خاموش${NC}"; fi
echo -e "\n${YELLOW}🤖 Bale Bot:${NC}"
if [ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid" ] && ps -p $(cat all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid 2>/dev/null) > /dev/null 2>&1; then echo -e "${GREEN}✅ روشن PID $(cat all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid)${NC}"; else echo -e "${RED}❌ خاموش${NC}"; fi
echo -e "\n${YELLOW}📝 لاگ‌ها:${NC}"
echo "  WhatsApp: tail -f whatsapp-service/whatsapp.log"
echo "  Bale: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log"
