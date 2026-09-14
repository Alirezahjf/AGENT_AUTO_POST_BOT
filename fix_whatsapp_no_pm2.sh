#!/bin/bash
# fix_whatsapp_no_pm2.sh - فیکس ارور No sessions + SQLite بدون pm2
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 1. بستن سرویس‌های قدیمی..."
./stop.sh 2>/dev/null || true
pkill -f "node.*index.js" 2>/dev/null || true
pkill -f "python.*bot.py" 2>/dev/null || true
fuser -k 3001/tcp 2>/dev/null || true
sleep 2

echo "📂 2. چک کردن فایل‌های خراب..."
echo "   - auth folders: $(ls whatsapp-service/auth 2>/dev/null | wc -l) سشن"
ls -1 whatsapp-service/auth 2>/dev/null || echo "   (پوشه auth خالی)"

# اگر سشن 335570544 خراب است (پوشه خالی یا <3 فایل)، حذفش کن
for USER_DIR in whatsapp-service/auth/*; do
  if [ -d "$USER_DIR" ]; then
    COUNT=$(ls -1 "$USER_DIR" 2>/dev/null | wc -l)
    USER_ID=$(basename "$USER_DIR")
    if [ "$COUNT" -lt 3 ]; then
      echo "   🔥 حذف سشن خراب $USER_ID (فقط $COUNT فایل دارد) - No sessions fix"
      rm -rf "$USER_DIR"
    fi
  fi
done

# حذف از sessions_db.json هم
if [ -f "whatsapp-service/sessions_db.json" ]; then
  echo "   📄 sessions_db.json وجود دارد - سشن‌های خراب را پاک می‌کنیم..."
  # فقط سشن‌هایی که auth ندارند حذف
  python3 -c "
import json, os, pathlib
db_file='whatsapp-service/sessions_db.json'
auth_base='whatsapp-service/auth'
try:
    with open(db_file) as f: db=json.load(f)
    to_del=[]
    for uid in list(db.keys()):
        auth_path=os.path.join(auth_base, str(uid))
        if not os.path.exists(auth_path) or len(os.listdir(auth_path))<3:
            to_del.append(uid)
    for uid in to_del:
        print(f'   🗑️ حذف {uid} از DB (auth خراب)')
        del db[uid]
    with open(db_file,'w') as f: json.dump(db,f,indent=2,ensure_ascii=False)
    print(f'✅ DB تمیز شد، {len(db)} سشن باقی مانده')
except Exception as e:
    print(f'⚠️ خطا در تمیز کردن DB: {e}')
"
fi

echo "🚀 3. اجرای مجدد سرویس‌ها با کد فیکس شده..."
./start.sh

echo ""
echo "⏳ 4. صبر 6 ثانیه برای بالا آمدن..."
sleep 6

echo "🔍 5. تست سرویس..."
curl -s http://localhost:3001/ | head -c 500
echo ""

echo ""
echo "🔥 6. فیکس سشن خاص 335570544 (اگر داری):"
curl -s -X DELETE "http://localhost:3001/session?userId=335570544&force=true" || echo "⚠️ سشن 335570544 وجود نداشت یا قبلا پاک شده"

echo ""
echo "📱 7. درخواست QR جدید با force (نمونه - شماره خودت را بگذار):"
echo "   curl \"http://localhost:3001/qr?userId=335570544&force=true&phone=989123456789&ownPhone=989123456789\""
echo ""
echo "✅ تمام! حالا:"
echo "   - لاگ واتساپ: tail -f whatsapp-service/whatsapp.log"
echo "   - لاگ ربات: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log"
echo "   - در Bale بنویس: reset  (برای حذف سشن خراب و گرفتن QR جدید)"
echo "   - یا بنویس: 989123456789  (شماره خودت)"
