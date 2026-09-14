#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo "🛑 بستن سرویس‌ها..."
if [ -f "whatsapp-service/whatsapp.pid" ]; then
    kill -9 $(cat whatsapp-service/whatsapp.pid) 2>/dev/null || true
    rm -f whatsapp-service/whatsapp.pid
fi
if [ -f "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid" ]; then
    kill -9 $(cat all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid) 2>/dev/null || true
    rm -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.pid
fi
# بستن با pkill هم
pkill -f "whatsapp-service/index.js" 2>/dev/null || true
pkill -f "neonize_service.py" 2>/dev/null || true
pkill -f "all_pg_agnet.*bot.py" 2>/dev/null || true
fuser -k 3001/tcp 2>/dev/null || true
echo "✅ بسته شد"
echo "پورت 3001: $(lsof -i :3001 2>&1 | head -n 1 || echo 'آزاد')"
