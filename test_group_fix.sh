#!/bin/bash
# test_group_fix.sh v6 - تست و فیکس ارور No sessions برای گروه با participant sync + sender-key clean
USER_ID="335570544"
GROUP_ID="120363312386194255@g.us"
OWN_PHONE="989038013654"

echo "🔍 1. وضعیت سشن:"
curl -s "http://localhost:3001/status?userId=$USER_ID" | python3 -m json.tool

echo ""
echo "📋 2. سینک کردن گروه‌ها (مهم):"
curl -s "http://localhost:3001/chats?userId=$USER_ID" | python3 -m json.tool | head -150

echo ""
echo "⏳ صبر 5 ثانیه..."
sleep 5

echo ""
echo "📱 3. تست ارسال به شماره خودت (چک signal):"
curl -s -X POST http://localhost:3001/send -H "Content-Type: application/json" -d "{\"userId\":\"$USER_ID\",\"to\":\"${OWN_PHONE}@s.whatsapp.net\",\"text\":\"تست signal - $(date)\"}" | python3 -m json.tool

echo ""
echo "⏳ صبر 3 ثانیه..."
sleep 3

echo ""
echo "👥 4. تست ارسال به گروه $GROUP_ID (با retry خودکار):"
curl -s -X POST http://localhost:3001/send -H "Content-Type: application/json" -d "{\"userId\":\"$USER_ID\",\"to\":\"$GROUP_ID\",\"text\":\"تست گروه v6 - $(date) - ربات وصله ✅\"}" | python3 -m json.tool

echo ""
echo "🔍 5. اگر باز No sessions بود، تمیز کردن sender-key و تلاش مجدد:"
echo "   curl -X POST http://localhost:3001/clean-sessions?userId=$USER_ID"
curl -s -X POST "http://localhost:3001/clean-sessions?userId=$USER_ID" | python3 -m json.tool

echo ""
sleep 3
echo "👥 6. تلاش مجدد بعد از clean:"
curl -s -X POST http://localhost:3001/send -H "Content-Type: application/json" -d "{\"userId\":\"$USER_ID\",\"to\":\"$GROUP_ID\",\"text\":\"تست بعد از clean v6 - $(date)\"}" | python3 -m json.tool

echo ""
echo "💡 راه حل نهایی اگر باز نشد:"
echo "   1. از گوشی اصلی خودت یک پیام داخل گروه بفرست (تا sender key توزیع شود)"
echo "   2. از یک عضو دیگر بخواه یک پیام بفرستد"
echo "   3. 10 ثانیه صبر کن"
echo "   4. دوباره: curl -X POST http://localhost:3001/send -d '{\"userId\":\"$USER_ID\",\"to\":\"$GROUP_ID\",\"text\":\"hi\"}'"
echo "   - لاگ: tail -f whatsapp-service/whatsapp.log"
