#!/bin/bash
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
echo "📊 وضعیت سرویس‌ها:"
echo -e "\n${YELLOW}📱 WhatsApp (3001):${NC}"
if curl -s http://localhost:3001/ | grep -q "ok"; then echo -e "${GREEN}✅ روشن${NC}"; curl -s http://localhost:3001/ | python3 -m json.tool 2>/dev/null | head -n 20; else echo -e "${RED}❌ خاموش${NC}"; fi
echo -e "\n${YELLOW}🤖 Bale Bot:${NC}"
if [ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid" ] && ps -p $(cat all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid 2>/dev/null) > /dev/null 2>&1; then echo -e "${GREEN}✅ روشن PID $(cat all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid)${NC}"; else echo -e "${RED}❌ خاموش${NC}"; fi
# فقط خواندنی: همهٔ پروسه‌های bot.py (دو پروسه روی یک توکن، آپدیت‌ها را بین خود تقسیم می‌کنند)
BOT_PROCS="$(ps -eo pid=,args= 2>/dev/null | grep -E '[p]ython[0-9.]* .*bot\.py')"
BOT_COUNT="$(printf '%s\n' "$BOT_PROCS" | grep -c '[0-9]')"
echo "   پروسه‌های bot.py در حال اجرا: $BOT_COUNT"
printf '%s\n' "$BOT_PROCS" | while read -r P_PID P_ARGS; do
    [ -n "$P_PID" ] || continue
    echo "     PID $P_PID | $P_ARGS | cwd: $(readlink "/proc/$P_PID/cwd" 2>/dev/null || echo '?')"
done
LOCK_PID=""
[ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.lock" ] && LOCK_PID="$(tr -dc '0-9' < all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.lock)"
if [ -n "$LOCK_PID" ] && [ -d "/proc/$LOCK_PID" ]; then echo "   🔒 قفل تک‌نمونه (bot.lock): PID $LOCK_PID"; fi
if [ "$BOT_COUNT" -gt 1 ]; then
    echo -e "${RED}⚠️ بیش از یک bot.py در حال اجراست؛ آپدیت‌ها بین آن‌ها تقسیم می‌شود.${NC}"
    echo -e "${RED}   فقط PID داخل bot.pid را نگه دار و بقیه را با  kill <PID>  ببند (نه pkill).${NC}"
fi
echo -e "\n${YELLOW}📝 لاگ‌ها:${NC}"
echo "  WhatsApp: tail -f whatsapp-service/whatsapp.log"
echo "  Bale: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log"
