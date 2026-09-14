#!/bin/bash
# fix_whatsapp_no_pm2.sh - v4 nobackuploop - فیکس 401 + 428 + بکاپ خراب
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

# حذف سشن‌های خراب <2 فایل
for USER_DIR in whatsapp-service/auth/*; do
  if [ -d "$USER_DIR" ]; then
    COUNT=$(ls -1 "$USER_DIR" 2>/dev/null | wc -l)
    USER_ID=$(basename "$USER_DIR")
    if [ "$COUNT" -lt 2 ]; then
      echo "   🔥 حذف سشن خراب $USER_ID (فقط $COUNT فایل)"
      rm -rf "$USER_DIR"
    else
      echo "   ✅ $USER_ID سالم ($COUNT فایل)"
    fi
  fi
done

# 🔥 v4 FIX: حذف بکاپ خراب که باعث لوپ 401 میشه
# مسیر: all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users/335570544/whatsapp_auth_backup/335570544
echo "   🧹 چک کردن بکاپ‌های خراب..."
for BACKUP_DIR in all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users/*/whatsapp_auth_backup/*; do
  if [ -d "$BACKUP_DIR" ]; then
    USER_ID=$(basename "$BACKUP_DIR")
    COUNT=$(ls -1 "$BACKUP_DIR" 2>/dev/null | wc -l)
    # اگر بکاپ وجود دارد و سشن 335570544 مشکل دارد، بکاپ را هم حذف کن
    if [ "$USER_ID" = "335570544" ]; then
      echo "   🔥 حذف بکاپ خراب $USER_ID ($COUNT فایل) - عامل لوپ 401"
      rm -rf "$BACKUP_DIR"
      # اگر پوشه والد خالی شد حذف
      PARENT=$(dirname "$BACKUP_DIR")
      if [ -d "$PARENT" ] && [ -z "$(ls -A "$PARENT" 2>/dev/null)" ]; then
        rmdir "$PARENT" 2>/dev/null || true
      fi
    fi
  fi
done

# حذف اجباری سشن مشکل‌دار 335570544 قبل از استارت (هم auth هم بکاپ)
if [ -d "whatsapp-service/auth/335570544" ]; then
  echo "   🔥 حذف اجباری سشن 335570544 قبل از استارت"
  rm -rf "whatsapp-service/auth/335570544"
fi
if [ -d "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users/335570544/whatsapp_auth_backup" ]; then
  echo "   🔥 حذف بکاپ 335570544 قبل از استارت"
  rm -rf "all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users/335570544/whatsapp_auth_backup"
fi

# تمیز کردن sessions_db.json
if [ -f "whatsapp-service/sessions_db.json" ]; then
  echo "   📄 sessions_db.json تمیز می‌شود..."
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
    if '335570544' in db and '335570544' not in to_del:
        to_del.append('335570544')
    for uid in to_del:
        print(f'   🗑️ حذف {uid} از DB')
        del db[uid]
    with open(db_file,'w') as f: json.dump(db,f,indent=2,ensure_ascii=False)
    print(f'✅ DB تمیز شد، {len(db)} سشن باقی مانده')
except Exception as e:
    print(f'⚠️ خطا: {e}')
    try:
        os.remove(db_file)
        print('🗑️ DB خراب حذف شد')
    except: pass
"
fi

echo "🚀 3. اجرای مجدد سرویس‌ها با کد v4 nobackuploop..."
./start.sh

echo ""
echo "⏳ 4. صبر 8 ثانیه..."
sleep 8

echo "🔍 5. تست سرویس..."
curl -s http://localhost:3001/ | head -c 1000
echo ""
if curl -s http://localhost:3001/ | grep -q "ok"; then
  echo "✅ WhatsApp روشن است"
else
  echo "❌ WhatsApp خاموش - لاگ:"
  tail -100 whatsapp-service/whatsapp.log
  echo ""
  echo "🔄 تلاش مجدد با پاکسازی کامل..."
  ./stop.sh 2>/dev/null || true
  rm -rf whatsapp-service/auth/*
  rm -rf all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER/users/*/whatsapp_auth_backup
  rm -f whatsapp-service/sessions_db.json
  echo "🗑️ همه auth و بکاپ‌ها پاک شد"
  ./start.sh
  sleep 6
  curl -s http://localhost:3001/ || echo "هنوز خاموش"
fi

echo ""
echo "🔥 6. حذف کامل سشن 335570544 با بکاپ:"
curl -s -X DELETE "http://localhost:3001/session?userId=335570544&force=true&deleteBackup=true" || echo "⚠️ قبلا پاک شده"

echo ""
echo "📱 7. QR جدید با force (شماره خودت):"
echo "   curl \"http://localhost:3001/qr?userId=335570544&force=true&deleteBackup=true&phone=989038013654&ownPhone=989038013654\""

echo ""
echo "✅ v4 نصب شد - بکاپ خراب دیگر ری‌استور نمی‌شود"
echo "   - لاگ: tail -f whatsapp-service/whatsapp.log"
echo "   - وضعیت: ./status.sh"
echo "   - در Bale: reset"
