#!/bin/bash
# test_group_fix.sh - تست و فیکس ارور No sessions برای گروه
USER_ID="335570544"
GROUP_ID="120363312386194255@g.us"
OWN_PHONE="989038013654"

echo "🔍 1. وضعیت سشن:"
curl -s "http://localhost:3001/status?userId=$USER_ID" | python3 -m json.tool

echo ""
echo "📋 2. سینک کردن گروه‌ها (مهم - 15 ثانیه صبر کن):"
curl -s "http://localhost:3001/chats?userId=$USER_ID" | python3 -m json.tool | head -100

echo ""
echo "⏳ صبر 5 ثانیه برای تکمیل سینک..."
sleep 5

echo ""
echo "📱 3. تست ارسال به شماره خودت (برای چک signal):"
curl -s -X POST http://localhost:3001/send -H "Content-Type: application/json" -d "{\"userId\":\"$USER_ID\",\"to\":\"${OWN_PHONE}@s.whatsapp.net\",\"text\":\"تست signal - $(date)\"}" | python3 -m json.tool

echo ""
echo "⏳ صبر 3 ثانیه..."
sleep 3

echo ""
echo "👥 4. تست ارسال به گروه $GROUP_ID:"
curl -s -X POST http://localhost:3001/send -H "Content-Type: application/json" -d "{\"userId\":\"$USER_ID\",\"to\":\"$GROUP_ID\",\"text\":\"تست گروه - $(date) - ربات وصله ✅\"}" | python3 -m json.tool

echo ""
echo "💡 اگر باز No sessions دیدی:"
echo "   - مطمئن شو داخل گروه هستی"
echo "   - گروه ID درست است؟ در Bale بنویس groups و چک کن"
echo "   - 15 ثانیه بعد از CONNECTED صبر کن، واتساپ باید گروه‌ها رو سینک کنه"
echo "   - یک پیام دستی داخل گروه بفرست (از گوشی)، بعد دوباره تست کن"
echo "   - لاگ: tail -f whatsapp-service/whatsapp.log"
