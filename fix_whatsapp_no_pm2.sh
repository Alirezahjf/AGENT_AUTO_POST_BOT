#!/bin/bash
# fix_whatsapp_no_pm2.sh - فیکس ارور 428 Connection Closed + No sessions بدون pm2 - v3 crashproof
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 1. بستن سرویس‌های قدیمی..."
./stop.sh 2>/dev/null || true
pkill -9 -f "node.*index.js" 2>/dev/null || true
pkill -9 -f "python.*bot.py" 2>/dev/null || true
fuser -k 3001/tcp 2>/dev/null || true
sleep 2

echo "📂 2. چک کردن فایل‌های خراب..."
echo "   - auth folders: $(ls whatsapp-service/auth 2>/dev/null | wc -l) سشن"
ls -1 whatsapp-service/auth 2>/dev/null || echo "   (پوشه auth خالی)"

# حذف سشن‌های خراب <2 فایل (آپدیت از 3 به 2 برای crashproof)
for USER_DIR in whatsapp-service/auth/*; do
  if [ -d "$USER_DIR" ]; then
    COUNT=$(ls -1 "$USER_DIR" 2>/dev/null | wc -l)
    USER_ID=$(basename "$USER_DIR")
    if [ "$COUNT" -lt 2 ]; then
      echo "   🔥 حذف سشن خراب $USER_ID (فقط $COUNT فایل دارد) - No sessions fix"
      rm -rf "$USER_DIR"
    else
      echo "   ✅ $USER_ID سالم ($COUNT فایل)"
    fi
  fi
done

# سشن مشکل‌دار 335570544 را اگر کانکت نیست و کرش کرده، حذف کن تا تازه ساخته شود
# کاربر گفته بعد از فیکس قبلی کرش کرد با 428 - پس این سشن را کامل پاک می‌کنیم
if [ -d "whatsapp-service/auth/335570544" ]; then
  echo "   🔥 حذف اجباری سشن 335570544 برای فیکس 428 Connection Closed (قبل از استارت)"
  rm -rf "whatsapp-service/auth/335570544"
fi

# حذف از sessions_db.json هم
if [ -f "whatsapp-service/sessions_db.json" ]; then
  echo "   📄 sessions_db.json وجود دارد - سشن‌های خراب را پاک می‌کنیم..."
  python3 -c "
import json, os
db_file='whatsapp-service/sessions_db.json'
auth_base='whatsapp-service/auth'
try:
    with open(db_file) as f: db=json.load(f)
    to_del=[]
    for uid in list(db.keys()):
        auth_path=os.path.join(auth_base, str(uid))
        if not os.path.exists(auth_path) or len(os.listdir(auth_path))<2:
            to_del.append(uid)
    # همچنین 335570544 را حتما حذف کن
    if '335570544' in db and '335570544' not in to_del:
        to_del.append('335570544')
    for uid in to_del:
        print(f'   🗑️ حذف {uid} از DB (auth خراب یا 428)')
        del db[uid]
    with open(db_file,'w') as f: json.dump(db,f,indent=2,ensure_ascii=False)
    print(f'✅ DB تمیز شد، {len(db)} سشن باقی مانده')
except Exception as e:
    print(f'⚠️ خطا در تمیز کردن DB: {e}')
    # اگر DB خراب است، پاک کن
    try:
        os.remove(db_file)
        print('🗑️ DB خراب حذف شد')
    except: pass
"
fi

echo "🚀 3. اجرای مجدد سرویس‌ها با کد فیکس شده v3 crashproof..."
./start.sh

echo ""
echo "⏳ 4. صبر 8 ثانیه برای بالا آمدن..."
sleep 8

echo "🔍 5. تست سرویس..."
curl -s http://localhost:3001/ | head -c 1000
echo ""
# چک آیا روشن است؟
if curl -s http://localhost:3001/ | grep -q "ok"; then
  echo "✅ WhatsApp روشن است"
else
  echo "❌ WhatsApp هنوز خاموش است - لاگ:"
  tail -100 whatsapp-service/whatsapp.log
  echo ""
  echo "🔄 تلاش مجدد با auth کاملا تمیز..."
  ./stop.sh 2>/dev/null || true
  rm -rf whatsapp-service/auth/*
  rm -f whatsapp-service/sessions_db.json
  echo "🗑️ همه auth ها پاک شد - شروع مجدد"
  ./start.sh
  sleep 6
  curl -s http://localhost:3001/ || echo "هنوز خاموش"
fi

echo ""
echo "🔥 6. فیکس سشن خاص 335570544 (حذف کامل):"
curl -s -X DELETE "http://localhost:3001/session?userId=335570544&force=true" || echo "⚠️ سشن 335570544 وجود نداشت یا قبلا پاک شده"

echo ""
echo "📱 7. درخواست QR جدید با force (شماره خودت را بگذار):"
echo "   curl \"http://localhost:3001/qr?userId=335570544&force=true&phone=989123456789&ownPhone=989123456789\""

echo ""
echo "✅ تمام! نسخه v3 crashproof نصب شد"
echo "   - لاگ واتساپ: tail -f whatsapp-service/whatsapp.log"
echo "   - لاگ ربات: tail -f all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/bot.log"
echo "   - وضعیت: ./status.sh"
echo "   - در Bale بنویس: reset  (برای حذف سشن خراب و گرفتن QR جدید)"
echo "   - یا بنویس: 989123456789  (شماره خودت با 98)"
echo ""
echo "💡 اگر باز 428 دیدی: این یعنی سشن قدیمی از طرف واتساپ بسته شده"
echo "   راه حل: curl -X DELETE http://localhost:3001/session?userId=335570544&force=true"
echo "   سپس: curl \"http://localhost:3001/qr?userId=335570544&force=true&phone=989...\""
