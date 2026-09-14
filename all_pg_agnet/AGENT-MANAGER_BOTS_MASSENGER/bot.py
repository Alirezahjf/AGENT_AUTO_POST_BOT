# bot.py
import requests
import time
import re
from datetime import datetime
import jdatetime
import pytz
from logger import logger
from config import load_config, save_config, load_user_config, save_user_config, get_user_db
import woocommerce
import scheduler
from database import PostDatabase
from auth_manager import AuthManager
from auth_handlers import (
    handle_unauthenticated_user,
    handle_auth_callback,
    handle_token_input,
    send_message as auth_send_message,
)


# ========== متغیرهای سراسری ==========
TEHRAN_TZ = pytz.timezone("Asia/Tehran")
config = load_config()
user_states = {}
db = PostDatabase()
auth_manager = AuthManager()


# ========== زبان‌ها ==========

LANGUAGES = {
    "fa": {
        # ===== پیام‌های خوش‌آمدگویی =====
        "welcome": "👋 به ربات پست‌گذار خودکار ووکامرس خوش آمدید!\n\n🌐 لطفاً زبان خود را انتخاب کنید:",

        # ===== منوی اصلی =====
        "main_menu": "🏠 منوی اصلی",
        "settings": "⚙️ تنظیمات",
        "woocommerce_posts": "🛒 پست‌های ووکامرس",
        "posting_management": "📮 مدیریت پست‌ها",
        "contents": "📂 محتواها",
        "back": "🔙 بازگشت",
        "back_to_settings": "🔙 بازگشت به تنظیمات",
        "back_to_main": "🔙 بازگشت به منوی اصلی",
        "back_to_wc_posts": "🔙 بازگشت به پست‌های ووکامرس",
        "back_to_posting": "🔙 بازگشت به مدیریت پست‌ها",
        "back_to_contents": "🔙 بازگشت به محتواها",

        # ===== تنظیمات =====
        "messengers": "📱 پیام‌رسان‌ها",
        "woocommerce_api": "🛒 API ووکامرس",

        # ===== پست‌های ووکامرس =====
        "config_autopost": "⏰ تنظیم پست خودکار",
        "check_products": "📦 بررسی محصولات جدید",
        "test_product_posting": "🧪 تست ارسال محصولات",
        "toggle_autopost": "🔄 فعال/غیرفعال پست خودکار",
        "toggle_live_new": "⚡ پست زنده محصول جدید",
        "posts_per_day": "📊 تعداد پست در روز",
        "schedule_days": "📅 زمان‌بندی روزها",
        "category_filter": "📂 فیلتر دسته‌بندی",
        "category_all": "📂 همه دسته‌بندی‌ها",
        "category_selected": "✅ دسته‌بندی انتخاب شد: {cats}",
        "category_cleared": "✅ فیلتر دسته‌بندی پاک شد - همه دسته‌ها",
        "live_enabled": "⚡ پست زنده فعال شد - محصول جدید بلافاصله پست می‌شود",
        "live_disabled": "⚪ پست زنده غیرفعال شد",
        "enter_category": "📂 نام یا ID دسته‌بندی‌ها را ارسال کنید (با کاما جدا کنید):\nمثال: 15,20 یا shoes,clothing\nبرای پاک کردن فیلتر: all",
        "whatsapp_code_caption": "🔑 *کد اتصال واتساپ*\n\nکد زیر را در واتساپ وارد کنید:\n`{code}`\n\nمسیر: واتساپ -> تنظیمات -> دستگاه‌های متصل -> اتصال با شماره تلفن\n\nیا QR بالا را اسکن کنید",
        "whatsapp_qr_auto_refresh": "🔄 QR کد جدید (خودکار بروز شد - قبلی منقضی شد)",
        "whatsapp_connected_simple": "✅ *واتساپ متصل شد!* 🎉\n\n📱 شماره: {phone}\nمی‌توانید الان از واتساپ استفاده کنید",
        "whatsapp_qr_expired": "⏰ QR منقضی شد، QR جدید فرستاده شد",
        "messengers_help": "📚 راهنمای اتصال پیام‌رسان‌ها",
        "help_general": "📚 *راهنمای کلی اتصال پیام‌رسان‌ها*\n\nبرای اتصال هر پیام‌رسان، روی آن کلیک کنید و توکن/آیدی را وارد کنید. اگر بلد نیستید، روی دکمه راهنمای همان پیام‌رسان بزنید:\n\n🔵 Bale: ربات اصلی - حتما باید وصل باشد\n🟢 Rubika: پیام‌رسان ایرانی\n🟡 Eitaa: پیام‌رسان ایرانی\n✈️ Telegram: محبوب‌ترین\n💚 WhatsApp: با QR فوق ساده\n\nکدام پیام‌رسان را می‌خواهید یاد بگیرید؟",
        "help_bale": "🔵 *راهنمای اتصال Bale*\n\n1️⃣ به ربات @BotFather در Bale بروید\n2️⃣ دستور /newbot را بفرستید\n3️⃣ نام ربات را وارد کنید\n4️⃣ توکن را کپی کنید (مثل: 123456:ABC...)\n5️⃣ یک کانال بسازید و ربات را ادمین کنید\n6️⃣ آیدی کانال را بفرستید: @yourchannel\n\n⚠️ ربات باید ادمین کانال باشد!",
        "help_rubika": "🟢 *راهنمای اتصال Rubika*\n\n1️⃣ به ربات @BotFather روبیکا بروید\n2️⃣ ربات جدید بسازید\n3️⃣ توکن را کپی کنید\n4️⃣ یک کانال/گروه بسازید\n5️⃣ ربات را ادمین کنید\n6️⃣ آیدی چت را بفرستید\n\n💡 روبیکا پیام‌رسان ایرانی است",
        "help_eitaa": "🟡 *راهنمای اتصال Eitaa*\n\n1️⃣ به eitaayar.ir بروید\n2️⃣ ربات بسازید\n3️⃣ توکن را کپی کنید\n4️⃣ کانال بسازید و ربات را ادمین کنید\n5️⃣ آیدی را بفرستید\n\n💡 ایتا پیام‌رسان ایرانی است",
        "help_telegram": "✈️ *راهنمای اتصال Telegram*\n\n1️⃣ به @BotFather در تلگرام بروید\n2️⃣ /newbot را بفرستید\n3️⃣ نام ربات را وارد کنید (مثلا MyShopBot)\n4️⃣ یوزرنیم ربات را وارد کنید (باید با bot تمام شود)\n5️⃣ توکن را کپی کنید: 123456:ABC-DEF...\n6️⃣ یک کانال بسازید\n7️⃣ ربات را ادمین کانال کنید (Post Messages)\n8️⃣ آیدی کانال را بفرستید: @yourchannel یا -1001234567890\n\n⚠️ حتما ربات ادمین باشد!",
        "help_whatsapp": "💚 *راهنمای اتصال WhatsApp - فوق ساده*\n\n✨ حتی غیر برنامه‌نویس هم می‌تواند!\n\n1️⃣ شماره واتساپ مقصد را بفرستید: 989123456789\n2️⃣ ربات یک QR کد + یک کد 8 رقمی می‌فرستد\n3️⃣ دو روش برای اتصال:\n\n*روش 1 - اسکن QR (ساده):*\nواتساپ -> تنظیمات (سه نقطه) -> دستگاه‌های متصل -> اتصال دستگاه -> QR را اسکن کنید\n\n*روش 2 - کد 8 رقمی:*\nواتساپ -> تنظیمات -> دستگاه‌های متصل -> اتصال با شماره تلفن -> کد را وارد کنید: 123-45678\n\n4️⃣ بعد از اتصال، دکمه بررسی اتصال را بزنید\n\n⏰ QR هر 20 ثانیه عوض می‌شود (خودکار)\n🔑 کد هم با QR عوض می‌شود",
        "help_button": "📚 اگر بلد نیستید وصل کنید بگید تا یادتون بدم",
        "learn_how": "📚 یاد بده چطور وصل کنم",
        "back_to_messengers": "🔙 بازگشت به پیام‌رسان‌ها",



        # ===== مدیریت پست‌ها =====
        "new_post": "➕ پست جدید",
        "manual_posting": "✍️ پست دستی",
        "edit_scheduled": "📝 ویرایش پست‌های زمان‌بندی شده",
        "posting_history": "📊 تاریخچه پست‌ها",
        "drafts": "📋 پیش‌نویس‌ها",
        "archive": "🗂️ آرشیو",

        # ===== محتواها =====
        "new_content": "➕ محتوای جدید",
        "upload_media": "📸 آپلود رسانه",
        "upload_text": "📝 آپلود متن",
        "view_media": "📸 مشاهده رسانه‌ها",
        "view_text": "📝 مشاهده متن‌ها",
        "save": "💾 ذخیره",
        "delete": "🗑️ حذف",
        "all": "همه",
        "search": "🔍 جستجو",
        "media_title": "عنوان رسانه",
        "enter_media_title": "📝 عنوان رسانه را وارد کنید:",
        "title_exists": "❌ این عنوان قبلاً استفاده شده! لطفاً عنوان دیگری انتخاب کنید.",
        "enter_search_query": "🔍 عنوان مورد نظر را وارد کنید:",
        "no_results_found": "❌ نتیجه‌ای یافت نشد!",
        "delete_confirm": "✅ حذف شد!",

        # ===== انتخاب پیام‌رسان‌ها =====
        "select_messengers": "📱 پیام‌رسان‌های مقصد را انتخاب کنید:",
        "submit": "✅ ثبت نهایی",
        "no_messenger_selected": "❌ حداقل یک پیام‌رسان انتخاب کنید!",
        "post_scheduled": "✅ پست برای تاریخ {date} ساعت {time} زمان‌بندی شد!\n\n📱 پیام‌رسان‌های انتخابی:\n{messengers}",

        # ===== زمان‌بندی =====
        "enter_schedule_times": "⏰ ساعت‌های پست‌گذاری را وارد کنید:\n\nفرمت: HH:MM,HH:MM,HH:MM\nمثال: 09:30,14:00,18:45",
        "schedule_saved": "✅ زمان‌بندی ذخیره شد!\n\n📅 روز: {day}\n⏰ ساعت‌ها: {times}",
        "invalid_time_format": "❌ فرمت نامعتبر! لطفاً به صورت HH:MM,HH:MM وارد کنید.",
        "day_disabled": "⚪ {day} غیرفعال شد",
        "day_enabled": "✅ {day} فعال شد با {count} ساعت",

        # ===== منوی ادمین =====
        "admin_menu": "👮 منوی ادمین",
        "manage_users": "👥 مدیریت کاربران",
        "manage_admins": "👨‍💼 مدیریت ادمین‌ها",
        "view_access_requests": "📋 درخواست‌های دسترسی",
        "activity_logs": "📊 گزارش فعالیت",
        "add_admin": "➕ اضافه کردن ادمین جدید",
        "remove_admin": "❌ حذف کردن ادمین",
        "approve": "✅ تایید",
        "reject": "❌ رد",
        "back_to_admin_menu": "🔙 بازگشت به منوی ادمین",
        "enter_user_chat_id": "👤 شناسه کاربر را وارد کنید:",
        "user_not_found": "❌ کاربر یافت نشد",
        "user_already_admin": "❌ این کاربر قبلاً ادمین است",
        "admin_added_success": "✅ کاربر به عنوان ادمین اضافه شد",
        "admin_removed_success": "✅ ادمین حذف شد",
        "no_pending_requests": "📭 درخواست معلقی وجود ندارد",
        "reject_reason": "❌ دلیل رد کردن را بنویسید:",
        "access_granted": "✅ دسترسی تایید شد! توکن شما:",
        "access_denied": "❌ درخواست شما رد شد",
        "unauthorized_access": "❌ شما اجازه دسترسی ندارید",
        "invalid_token": "❌ توکن نامعتبر است",
        "pending_approval": "⏳ درخواست شما در انتظار تایید است",
        "awaiting_token": "🔑 لطفاً توکن خود را وارد کنید:",
        "enabled": "✅ فعال",
        "disabled": "⚪ غیرفعال",
    },
    "en": {
        # ===== پیام‌های خوش‌آمدگویی =====
        "welcome": "👋 Welcome to WooCommerce Auto-Poster Bot!\n\n🌐 Please select your language:",

        # ===== منوی اصلی =====
        "main_menu": "🏠 Main Menu",
        "settings": "⚙️ Settings",
        "woocommerce_posts": "🛒 WooCommerce Posts",
        "posting_management": "📮 Posting Management",
        "contents": "📂 Contents",
        "back": "🔙 Back",
        "back_to_settings": "🔙 Back to Settings",
        "back_to_main": "🔙 Back to Main Menu",
        "back_to_wc_posts": "🔙 Back to WooCommerce Posts",
        "back_to_posting": "🔙 Back to Posting Management",
        "back_to_contents": "🔙 Back to Contents",

        # ===== تنظیمات =====
        "messengers": "📱 Messengers",
        "woocommerce_api": "🛒 WooCommerce API",

        # ===== پست‌های ووکامرس =====
        "config_autopost": "⏰ Config Auto Post",
        "check_products": "📦 Check New Products",
        "test_product_posting": "🧪 Test Product Posting",
        "toggle_autopost": "🔄 Toggle Auto Post",
        "toggle_live_new": "⚡ Live New Product Post",
        "posts_per_day": "📊 Posts Per Day",
        "schedule_days": "📅 Schedule Days & Times",
        "category_filter": "📂 Category Filter",
        "category_all": "📂 All Categories",
        "category_selected": "✅ Category selected: {cats}",
        "category_cleared": "✅ Category filter cleared - all categories",
        "live_enabled": "⚡ Live post enabled - new products will be posted immediately",
        "live_disabled": "⚪ Live post disabled",
        "enter_category": "📂 Send category IDs or slugs separated by comma:\nExample: 15,20 or shoes,clothing\nTo clear filter: all",
        "whatsapp_code_caption": "🔑 *WhatsApp Pairing Code*\n\nEnter this code in WhatsApp:\n`{code}`\n\nPath: WhatsApp -> Settings -> Linked Devices -> Link with phone number\n\nOr scan QR above",
        "whatsapp_qr_auto_refresh": "🔄 New QR (auto-refreshed - old expired)",
        "whatsapp_connected_simple": "✅ *WhatsApp Connected!* 🎉\n\n📱 Number: {phone}",
        "whatsapp_qr_expired": "⏰ QR expired, new QR sent",
        "messengers_help": "📚 Messenger Connection Guide",
        "help_general": "📚 *Messenger Connection Guide*\n\nClick on any messenger to connect. If you dont know how, click its guide:\n\n🔵 Bale: Main bot - must be connected\n🟢 Rubika: Iranian messenger\n🟡 Eitaa: Iranian messenger\n✈️ Telegram: Most popular\n💚 WhatsApp: Super easy with QR\n\nWhich one do you want to learn?",
        "help_bale": "🔵 *Bale Guide*\n\n1️⃣ Go to @BotFather in Bale\n2️⃣ Send /newbot\n3️⃣ Enter bot name\n4️⃣ Copy token\n5️⃣ Create channel and make bot admin\n6️⃣ Send channel ID: @yourchannel",
        "help_rubika": "🟢 *Rubika Guide*\n\n1️⃣ Go to @BotFather in Rubika\n2️⃣ Create new bot\n3️⃣ Copy token\n4️⃣ Create channel\n5️⃣ Make bot admin\n6️⃣ Send chat ID",
        "help_eitaa": "🟡 *Eitaa Guide*\n\n1️⃣ Go to eitaayar.ir\n2️⃣ Create bot\n3️⃣ Copy token\n4️⃣ Create channel\n5️⃣ Send ID",
        "help_telegram": "✈️ *Telegram Guide*\n\n1️⃣ Go to @BotFather in Telegram\n2️⃣ Send /newbot\n3️⃣ Enter name\n4️⃣ Enter username ending with bot\n5️⃣ Copy token\n6️⃣ Create channel\n7️⃣ Make bot admin\n8️⃣ Send @yourchannel or -100...",
        "help_whatsapp": "💚 *WhatsApp Guide - Super Easy*\n\n1️⃣ Send number: 989123456789\n2️⃣ Bot sends QR + 8-digit code\n3️⃣ Two ways:\nQR: WhatsApp -> Settings -> Linked Devices -> Link Device -> Scan QR\nCode: WhatsApp -> Settings -> Linked Devices -> Link with phone number -> Enter code\n4️⃣ Click Check Connection",
        "help_button": "📚 If you dont know how to connect, let me teach you",
        "learn_how": "📚 Teach me how to connect",
        "back_to_messengers": "🔙 Back to Messengers",



        # ===== مدیریت پست‌ها =====
        "new_post": "➕ New Post",
        "manual_posting": "✍️ Manual Posting",
        "edit_scheduled": "📝 Edit Scheduled Posts",
        "posting_history": "📊 Posting History",
        "drafts": "📋 Drafts",
        "archive": "🗂️ Archive",

        # ===== محتواها =====
        "new_content": "➕ New Content",
        "upload_media": "📸 Upload Media",
        "upload_text": "📝 Upload Text",
        "view_media": "📸 View Media",
        "view_text": "📝 View Text",
        "save": "💾 Save",
        "delete": "🗑️ Delete",
        "all": "All",
        "search": "🔍 Search",
        "media_title": "Media Title",
        "enter_media_title": "📝 Enter media title:",
        "title_exists": "❌ This title already exists! Please choose another one.",
        "enter_search_query": "🔍 Enter search query:",
        "no_results_found": "❌ No results found!",
        "delete_confirm": "✅ Deleted!",

        # ===== انتخاب پیام‌رسان‌ها =====
        "select_messengers": "📱 Select destination messengers:",
        "submit": "✅ Submit",
        "no_messenger_selected": "❌ Please select at least one messenger!",
        "post_scheduled": "✅ Post scheduled for {date} at {time}!\n\n📱 Selected messengers:\n{messengers}",

        # ===== زمان‌بندی =====
        "enter_schedule_times": "⏰ Enter posting times:\n\nFormat: HH:MM,HH:MM,HH:MM\nExample: 09:30,14:00,18:45",
        "schedule_saved": "✅ Schedule saved!\n\n📅 Day: {day}\n⏰ Times: {times}",
        "invalid_time_format": "❌ Invalid format! Please enter as HH:MM,HH:MM",
        "day_disabled": "⚪ {day} disabled",
        "day_enabled": "✅ {day} enabled with {count} time(s)",

        # ===== منوی ادمین =====
        "admin_menu": "👮 Admin Menu",
        "manage_users": "👥 Manage Users",
        "manage_admins": "👨‍💼 Manage Admins",
        "view_access_requests": "📋 Access Requests",
        "activity_logs": "📊 Activity Logs",
        "add_admin": "➕ Add Admin",
        "remove_admin": "❌ Remove Admin",
        "approve": "✅ Approve",
        "reject": "❌ Reject",
        "back_to_admin_menu": "🔙 Back to Admin Menu",
        "enter_user_chat_id": "👤 Enter user chat ID:",
        "user_not_found": "❌ User not found",
        "user_already_admin": "❌ This user is already an admin",
        "admin_added_success": "✅ User added as admin",
        "admin_removed_success": "✅ Admin removed",
        "no_pending_requests": "📭 No pending requests",
        "reject_reason": "❌ Write rejection reason:",
        "access_granted": "✅ Access granted! Your token:",
        "access_denied": "❌ Your request has been denied",
        "unauthorized_access": "❌ You don't have access",
        "invalid_token": "❌ Invalid token",
        "pending_approval": "⏳ Your request is pending approval",
        "awaiting_token": "🔑 Please enter your token:",
        "enabled": "✅ Enabled",
        "disabled": "⚪ Disabled",
    }
}


# ========== توابع کمکی - ترجمه و زبان ==========

def get_user_lang(chat_id):
    """دریافت زبان کاربر"""
    return config.get("user_languages", {}).get(str(chat_id), "en")


def set_user_lang(chat_id, lang):
    """تنظیم زبان کاربر"""
    if "user_languages" not in config:
        config["user_languages"] = {}
    config["user_languages"][str(chat_id)] = lang
    save_config(config)


def t(chat_id, key):
    """ترجمه متن بر اساس زبان کاربر"""
    lang = get_user_lang(chat_id)
    return LANGUAGES.get(lang, LANGUAGES["en"]).get(key, key)

def tehran_now():
    """تاریخ و زمان فعلی به وقت تهران"""
    return datetime.now(TEHRAN_TZ)


def tehran_today():
    """تاریخ امروز به وقت تهران"""
    return tehran_now().date()


def tehran_jalali_today():
    """تاریخ شمسی امروز به وقت تهران"""
    today = tehran_today()
    return jdatetime.date.fromgregorian(date=today)


def gregorian_to_jalali(date_str):
    """تبدیل تاریخ میلادی YYYY-MM-DD به شمسی"""
    try:
        g_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        j_date = jdatetime.date.fromgregorian(date=g_date)
        return j_date.strftime("%Y/%m/%d")
    except Exception:
        return date_str


def gregorian_datetime_to_jalali(datetime_str):
    """تبدیل تاریخ و زمان میلادی به شمسی"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            g_dt = datetime.strptime(datetime_str, fmt)
            j_dt = jdatetime.datetime.fromgregorian(datetime=g_dt)
            return j_dt.strftime("%Y/%m/%d %H:%M")
        except Exception:
            continue
    return datetime_str


def format_date_for_user(chat_id, date_str):
    """اگر زبان کاربر فارسی باشد، تاریخ شمسی برمی‌گرداند"""
    if not date_str:
        return date_str
    if get_user_lang(chat_id) == "fa":
        return gregorian_to_jalali(date_str)
    return date_str


def format_datetime_for_user(chat_id, datetime_str=None):
    """
    اگر زبان کاربر فارسی باشد، تاریخ/زمان شمسی به وقت تهران برمی‌گرداند
    اگر datetime_str داده نشود، زمان فعلی تهران را برمی‌گرداند
    """
    if datetime_str is None:
        now = tehran_now()
        if get_user_lang(chat_id) == "fa":
            j_dt = jdatetime.datetime.fromgregorian(datetime=now)
            return j_dt.strftime("%Y/%m/%d %H:%M")
        return now.strftime("%Y-%m-%d %H:%M")

    if not datetime_str:
        return datetime_str
    if get_user_lang(chat_id) == "fa":
        return gregorian_datetime_to_jalali(datetime_str)
    return datetime_str


def get_calendar_year_month(chat_id, gregorian_date_str=None):
    """
    برای فارسی: سال/ماه شمسی به وقت تهران
    برای انگلیسی: سال/ماه میلادی به وقت تهران
    """
    if get_user_lang(chat_id) == "fa":
        if gregorian_date_str:
            try:
                g_date = datetime.strptime(gregorian_date_str, "%Y-%m-%d").date()
                j_date = jdatetime.date.fromgregorian(date=g_date)
                return j_date.year, j_date.month
            except Exception:
                pass

        today_j = tehran_jalali_today()
        return today_j.year, today_j.month

    if gregorian_date_str:
        try:
            g_date = datetime.strptime(gregorian_date_str, "%Y-%m-%d").date()
            return g_date.year, g_date.month
        except Exception:
            pass

    now = tehran_now()
    return now.year, now.month


def parse_jalali_input(text_input):
    """
    تبدیل تاریخ شمسی ورودی کاربر به میلادی
    فرمت‌های قابل قبول:
      1405/3/7
      405/3/7
      05/03/07
      05/3/7
      1405-3-7
      405-3-7
      05-03-07
      05-3-7

    خروجی:
      رشته میلادی به فرمت YYYY-MM-DD
      یا None اگر نامعتبر باشد
    """
    try:
        text_input = text_input.strip()
        text_input = text_input.replace("-", "/")

        parts = text_input.split("/")
        if len(parts) != 3:
            return None

        y_raw = parts[0].strip()
        m_raw = parts[1].strip()
        d_raw = parts[2].strip()

        y_int = int(y_raw)
        m_int = int(m_raw)
        d_int = int(d_raw)

        # نرمال‌سازی سال
        # 05 => 1405
        # 405 => 1405
        # 1405 => 1405
        current_j_year = tehran_jalali_today().year

        if y_int < 100:
            century = (current_j_year // 100) * 100   # مثلا 1400
            y_int += century
        elif y_int < 1000:
            y_int += 1000

        # اعتبارسنجی اولیه
        if y_int < 1300 or y_int > 1500:
            return None

        if not (1 <= m_int <= 12):
            return None

        if not (1 <= d_int <= 31):
            return None

        # تعداد روزهای ماه شمسی
        if 1 <= m_int <= 6:
            max_day = 31
        elif 7 <= m_int <= 11:
            max_day = 30
        else:
            max_day = 30 if jdatetime.date(y_int, 1, 1).isleap() else 29

        if d_int > max_day:
            return None

        # تبدیل شمسی به میلادی
        j_date = jdatetime.date(y_int, m_int, d_int)
        g_date = j_date.togregorian()

        return g_date.strftime("%Y-%m-%d")

    except Exception:
        return None


def parse_gregorian_input(text_input):
    """
    تبدیل تاریخ میلادی ورودی کاربر
    فرمت‌های قابل قبول:
      2026/5/28
      2026-05-28
      26/5/28

    خروجی:
      رشته میلادی به فرمت YYYY-MM-DD
      یا None اگر نامعتبر باشد
    """
    try:
        text_input = text_input.strip()
        text_input = text_input.replace("/", "-")

        parts = text_input.split("-")
        if len(parts) != 3:
            return None

        y_int = int(parts[0].strip())
        m_int = int(parts[1].strip())
        d_int = int(parts[2].strip())

        if y_int < 100:
            y_int += 2000

        if not (1 <= m_int <= 12):
            return None

        if not (1 <= d_int <= 31):
            return None

        from datetime import date
        g_date = date(y_int, m_int, d_int)

        return g_date.strftime("%Y-%m-%d")

    except Exception:
        return None


def parse_date_input(chat_id, text_input):
    """
    بر اساس زبان کاربر، تاریخ ورودی را به میلادی تبدیل می‌کند.
    خروجی:
      (gregorian_date_str, display_date_str)
      یا
      (None, None)
    """
    try:
        if get_user_lang(chat_id) == "fa":
            g_date_str = parse_jalali_input(text_input)
        else:
            g_date_str = parse_gregorian_input(text_input)

        if not g_date_str:
            return None, None

        g_date = datetime.strptime(g_date_str, "%Y-%m-%d").date()

        # تاریخ نباید از امروز تهران عقب‌تر باشد
        if g_date < tehran_today():
            return None, None

        display_date = format_date_for_user(chat_id, g_date_str)
        return g_date_str, display_date

    except Exception:
        return None, None


# ========== توابع کمکی - ارسال پیام ==========

def send_message(chat_id, text, keyboard=None):
    """ارسال پیام"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = keyboard

    try:
        requests.post(f"{api}/sendMessage", json=data, timeout=10)
    except Exception as e:
        logger.error(f"❌ خطا در ارسال پیام: {e}")


def edit_message(chat_id, message_id, text, keyboard=None):
    """ویرایش پیام"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if keyboard:
        data["reply_markup"] = keyboard

    try:
        requests.post(f"{api}/editMessageText", json=data, timeout=10)
    except Exception as e:
        logger.error(f"❌ خطا در ویرایش پیام: {e}")


def send_photo(chat_id, photo_id, caption=None, keyboard=None):
    """ارسال عکس"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    data = {"chat_id": chat_id, "photo": photo_id}
    if caption:
        data["caption"] = caption
    if keyboard:
        data["reply_markup"] = keyboard

    try:
        requests.post(f"{api}/sendPhoto", json=data, timeout=10)
    except Exception as e:
        logger.error(f"❌ خطا در ارسال عکس: {e}")


def send_video(chat_id, video_id, caption=None, keyboard=None):
    """ارسال ویدیو"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    data = {"chat_id": chat_id, "video": video_id}
    if caption:
        data["caption"] = caption
    if keyboard:
        data["reply_markup"] = keyboard

    try:
        requests.post(f"{api}/sendVideo", json=data, timeout=10)
    except Exception as e:
        logger.error(f"❌ خطا در ارسال ویدیو: {e}")


def send_local_photo(chat_id, file_path, caption=None, keyboard=None):
    """ارسال عکس محلی (برای راهنما) - با multipart - نسخه بهینه برای سرعت"""
    global config
    try:
        api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
        
        import os
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ Guide image not found: {file_path}")
            send_message(chat_id, caption or "راهنما", keyboard)
            return False
        
        # بررسی سایز و انتخاب کوچکترین نسخه (JPG ترجیح داده می‌شود - 30-40KB)
        file_size = os.path.getsize(file_path)
        jpg_path = os.path.splitext(file_path)[0] + ".jpg"
        if os.path.exists(jpg_path):
            jpg_size = os.path.getsize(jpg_path)
            if jpg_size < file_size:
                logger.info(f"✅ Using smaller JPG: {jpg_path} ({jpg_size//1024}KB vs {file_size//1024}KB)")
                file_path = jpg_path
                file_size = jpg_size
        
        # اگر هنوز بزرگ است، فقط متن بفرست
        if file_size > 500 * 1024:
            logger.warning(f"⚠️ Guide image still large: {file_size//1024}KB - sending text only for speed")
            send_message(chat_id, caption or "راهنما", keyboard)
            return True
        
        with open(file_path, "rb") as f:
            files = {"photo": (os.path.basename(file_path), f, "image/jpeg" if file_path.endswith(".jpg") else "image/png")}
            data = {"chat_id": chat_id}
            if caption:
                # Bale caption limit 1024, truncate if needed
                if len(caption) > 1000:
                    caption = caption[:1000] + "..."
                data["caption"] = caption
            if keyboard:
                import json
                data["reply_markup"] = json.dumps(keyboard)
            
            # افزایش timeout به 60 ثانیه برای عکس‌های بزرگ
            resp = requests.post(f"{api}/sendPhoto", data=data, files=files, timeout=60)
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info(f"✅ Guide photo sent: {file_path} ({file_size//1024}KB)")
                return True
            else:
                logger.warning(f"⚠️ Failed to send guide photo: {resp.status_code} {resp.text[:300]}")
                # fallback: فقط متن
                send_message(chat_id, caption or "راهنما", keyboard)
                return False
    except Exception as e:
        logger.error(f"❌ send_local_photo error: {e}")
        # fallback به متن ساده بدون عکس
        try:
            send_message(chat_id, caption or "راهنما", keyboard)
        except:
            pass
        return False


def send_guide_with_image(chat_id, messenger_name):
    """ارسال راهنمای یک پیام‌رسان با عکس"""
    lang = get_user_lang(chat_id)
    
    # متن راهنما
    help_key = f"help_{messenger_name}"
    caption = t(chat_id, help_key)
    
    # مسیر عکس راهنما
    import os
    guide_path = os.path.join(os.path.dirname(__file__), "..", "..", "guides", f"{messenger_name}_guide.png")
    guide_path = os.path.abspath(guide_path)
    
    # اگر عکس راهنما وجود ندارد، از لوگو استفاده کن
    if not os.path.exists(guide_path):
        # تلاش برای پوشه image-search
        alt_path = os.path.join(os.path.dirname(__file__), "..", "..", f"image-search/{messenger_name}-logo-1.png")
        alt_path = os.path.abspath(alt_path)
        if os.path.exists(alt_path):
            guide_path = alt_path
        else:
            # اگر هیچ عکسی نیست، فقط متن بفرست
            keyboard = {
                "inline_keyboard": [
                    [{"text": t(chat_id, "back_to_messengers"), "callback_data": "messengers_help"}],
                    [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
                ]
            }
            send_message(chat_id, caption, keyboard)
            return
    
    # کیبورد بازگشت + دکمه اتصال
    keyboard = {
        "inline_keyboard": [
            [{"text": f"🔗 اتصال {messenger_name.capitalize()}" if lang == "fa" else f"🔗 Connect {messenger_name.capitalize()}", "callback_data": f"connect_{messenger_name}"}],
            [{"text": t(chat_id, "back_to_messengers"), "callback_data": "messengers_help"}],
            [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
        ]
    }
    
    send_local_photo(chat_id, guide_path, caption, keyboard)


def download_bale_file(file_id, bot_token):
    """دانلود فایل از بیل با file_id - استفاده در scheduler"""
    try:
        api = f"https://tapi.bale.ai/bot{bot_token}"

        response = requests.get(
            f"{api}/getFile",
            params={"file_id": file_id},
            timeout=15
        )

        if response.status_code != 200:
            logger.error(f"❌ getFile failed: {response.status_code}")
            return None

        result = response.json()
        if not result.get("ok"):
            logger.error(f"❌ getFile not ok: {result}")
            return None

        file_path = result["result"]["file_path"]
        download_url = f"https://tapi.bale.ai/file/bot{bot_token}/{file_path}"

        file_response = requests.get(download_url, timeout=60)
        if file_response.status_code == 200:
            logger.info(f"✅ File downloaded: {file_id[:20]}...")
            return file_response.content
        else:
            logger.error(f"❌ File download failed: {file_response.status_code}")
            return None

    except Exception as e:
        logger.error(f"❌ download_bale_file error: {e}")
        return None


def notify_post_success(admin_chat_id, post_tuple, platforms_sent):
    """اطلاع‌رسانی ادمین درباره ارسال موفق پست دستی - فراخوانی از scheduler"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"

    try:
        post_id = post_tuple[0]
        media_type = post_tuple[2] if len(post_tuple) > 2 else "unknown"
        caption = post_tuple[3] if len(post_tuple) > 3 else ""
        scheduled_date = post_tuple[5] if len(post_tuple) > 5 else ""
        display_scheduled_date = format_date_for_user(admin_chat_id, scheduled_date)
        actual_posted = format_datetime_for_user(
            admin_chat_id,
            datetime.now().strftime('%Y-%m-%d %H:%M')
        )
        scheduled_time = post_tuple[6] if len(post_tuple) > 6 else ""

        platform_emojis = {
            "bale": "🔵 Bale",
            "rubika": "🟢 Rubika",
            "eitaa": "🟡 Eitaa"
        }

        message = "✅ *Scheduled Post Published!*\n\n"
        message += f"🆔 Post ID: #{post_id}\n"
        message += f"📋 Type: {'📸 Photo' if media_type == 'photo' else '🎥 Video'}\n"
        message += f"📅 Scheduled: {display_scheduled_date} at {scheduled_time}\n"
        message += f"⏰ Actually posted: {format_datetime_for_user(admin_chat_id)}\n\n"

        if caption:
            preview = caption[:100] + "..." if len(caption) > 100 else caption
            message += f"📝 Caption preview:\n{preview}\n\n"

        message += "📱 *Published on:*\n"
        for platform in platforms_sent:
            message += f"  {platform_emojis.get(platform, platform)}\n"

        message += f"\n🎉 Total platforms: {len(platforms_sent)}"

        data = {"chat_id": admin_chat_id, "text": message}
        requests.post(f"{api}/sendMessage", json=data, timeout=10)

    except Exception as e:
        logger.error(f"❌ Failed to send post success notification: {e}")


# ========== صفحه‌کلیدها - انتخاب زبان ==========

def create_language_keyboard():
    """صفحه‌کلید انتخاب زبان"""
    return {
        "inline_keyboard": [
            [
                {"text": "🇮🇷 فارسی", "callback_data": "lang_fa"},
                {"text": "🇬🇧 English", "callback_data": "lang_en"}
            ]
        ]
    }


# ========== صفحه‌کلیدها - منوی اصلی ==========

def create_main_keyboard(chat_id):
    """صفحه‌کلید منوی اصلی"""
    keyboard_buttons = [
        [{"text": t(chat_id, "settings")}],
        [{"text": t(chat_id, "woocommerce_posts")}],
        [{"text": t(chat_id, "posting_management")}],
        [{"text": t(chat_id, "contents")}],
    ]

    if auth_manager.is_admin(chat_id):
        keyboard_buttons.append([{"text": t(chat_id, "admin_menu")}])

    return {
        "keyboard": keyboard_buttons,
        "resize_keyboard": True
    }


# ========== صفحه‌کلیدها - تنظیمات ==========

def create_settings_keyboard(chat_id):
    """صفحه‌کلید تنظیمات"""
    return {
        "keyboard": [
            [{"text": t(chat_id, "messengers")}],
            [{"text": t(chat_id, "woocommerce_api")}],
            [{"text": t(chat_id, "back_to_main")}]
        ],
        "resize_keyboard": True
    }


# ========== صفحه‌کلیدها - پست‌های ووکامرس ==========

def create_woocommerce_posts_keyboard(chat_id):
    """صفحه‌کلید پست‌های ووکامرس"""
    return {
        "keyboard": [
            [{"text": t(chat_id, "config_autopost")}],
            [{"text": t(chat_id, "check_products")}],
            [{"text": t(chat_id, "test_product_posting")}],
            [{"text": t(chat_id, "back_to_main")}]
        ],
        "resize_keyboard": True
    }


# ========== صفحه‌کلیدها - تنظیم پست خودکار ==========

def create_autopost_keyboard(chat_id, user_config):
    """صفحه‌کلید تنظیمات پست خودکار - نسخه حرفه‌ای"""
    auto_cfg = user_config.get("auto_post", {})
    enabled = auto_cfg.get("enabled", False)
    live_enabled = auto_cfg.get("live_new_product", True)
    
    status = t(chat_id, "enabled") if enabled else t(chat_id, "disabled")
    live_status = t(chat_id, "enabled") if live_enabled else t(chat_id, "disabled")
    
    categories = auto_cfg.get("categories", [])
    cat_text = f"({len(categories)} فیلتر)" if categories else "(همه)"
    if get_user_lang(chat_id) != "fa":
        cat_text = f"({len(categories)} filtered)" if categories else "(all)"
    
    return {
        "keyboard": [
            [{"text": f"{t(chat_id, 'toggle_autopost')} ({status})"}],
            [{"text": f"{t(chat_id, 'toggle_live_new')} ({live_status})"}],
            [{"text": t(chat_id, "posts_per_day")}],
            [{"text": t(chat_id, "schedule_days")}],
            [{"text": f"{t(chat_id, 'category_filter')} {cat_text}"}],
            [{"text": t(chat_id, "back_to_wc_posts")}]
        ],
        "resize_keyboard": True
    }


# ========== صفحه‌کلیدها - زمان‌بندی روزها ==========

def create_days_keyboard(chat_id, user_config):
    """صفحه‌کلید انتخاب روزها با نمایش ساعت‌ها - Inline"""
    schedule = user_config["auto_post"].get("schedule", {})

    days_fa = {
        "saturday": "شنبه",
        "sunday": "یکشنبه",
        "monday": "دوشنبه",
        "tuesday": "سه‌شنبه",
        "wednesday": "چهارشنبه",
        "thursday": "پنج‌شنبه",
        "friday": "جمعه"
    }

    days_en = {
        "saturday": "Saturday",
        "sunday": "Sunday",
        "monday": "Monday",
        "tuesday": "Tuesday",
        "wednesday": "Wednesday",
        "thursday": "Thursday",
        "friday": "Friday"
    }

    lang = get_user_lang(chat_id)
    days = days_fa if lang == "fa" else days_en

    keyboard = []
    for day_en, day_name in days.items():
        day_info = schedule.get(day_en, {"enabled": False, "times": []})
        times = day_info.get("times", [])

        if day_info.get("enabled") and times:
            status = f"✅ ({len(times)})"
            times_preview = ", ".join(times[:2])
            if len(times) > 2:
                times_preview += "..."
            button_text = f"{status} {day_name}: {times_preview}"
        elif day_info.get("enabled"):
            status = "⚠️"
            button_text = (
                f"{status} {day_name} (بدون ساعت)"
                if lang == "fa"
                else f"{status} {day_name} (no times)"
            )
        else:
            status = "⚪"
            button_text = f"{status} {day_name}"

        keyboard.append([{
            "text": button_text,
            "callback_data": f"day_schedule_{day_en}"
        }])

    keyboard.append([{
        "text": t(chat_id, "back_to_wc_posts"),
        "callback_data": "back_to_wc_posts"
    }])

    return {"inline_keyboard": keyboard}


# ========== صفحه‌کلیدها - منوی ادمین ==========

def create_admin_menu_keyboard(chat_id):
    """صفحه‌کلید منوی ادمین"""
    is_super = auth_manager.is_super_admin(chat_id)

    keyboard_buttons = [
        [{"text": t(chat_id, "manage_users")}],
        [{"text": t(chat_id, "view_access_requests")}],
    ]

    if is_super:
        keyboard_buttons.append([{"text": t(chat_id, "manage_admins")}])

    keyboard_buttons.extend([
        [{"text": t(chat_id, "activity_logs")}],
        [{"text": t(chat_id, "back_to_main")}]
    ])

    return {
        "keyboard": keyboard_buttons,
        "resize_keyboard": True
    }


# ========== صفحه‌کلیدها - مدیریت پست‌ها ==========

def create_posting_keyboard(chat_id):
    """صفحه‌کلید مدیریت پست‌ها - Inline"""
    return {
        "inline_keyboard": [
            [
                {"text": t(chat_id, "new_post"), "callback_data": "posting_new"}
            ],
            [
                {"text": t(chat_id, "edit_scheduled"), "callback_data": "posting_edit"},
                {"text": t(chat_id, "posting_history"), "callback_data": "posting_history"}
            ],
            [
                {"text": t(chat_id, "drafts"), "callback_data": "posting_drafts"},
                {"text": t(chat_id, "archive"), "callback_data": "posting_archive"}
            ],
            [
                {"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}
            ]
        ]
    }


# ========== صفحه‌کلیدها - مدیریت محتوا ==========

def create_contents_keyboard(chat_id):
    """صفحه‌کلید مدیریت محتوا - Inline"""
    return {
        "inline_keyboard": [
            [
                {"text": t(chat_id, "upload_media"), "callback_data": "content_upload_media"},
                {"text": t(chat_id, "upload_text"), "callback_data": "content_upload_text"}
            ],
            [
                {"text": t(chat_id, "view_media"), "callback_data": "content_view_media"},
                {"text": t(chat_id, "view_text"), "callback_data": "content_view_text"}
            ],
            [
                {"text": t(chat_id, "archive"), "callback_data": "content_archive"}
            ],
            [
                {"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}
            ]
        ]
    }


# ========== صفحه‌کلیدها - پیام‌رسان‌ها ==========

def create_messengers_keyboard(chat_id, user_config):
    """صفحه‌کلید انتخاب پیام‌رسان‌ها - داینامیک 5 پیام‌رسان + راهنما - واتساپ فقط وقتی متصل+مقصد"""
    def status_icon(name):
        cfg = user_config["messengers"].get(name, {})
        if name == "whatsapp":
            # تیک سبز فقط وقتی متصل + مقصد انتخاب شده - نسخه پایدار
            has_chat = bool(cfg.get("chat_id"))
            connected = cfg.get("connected", False)
            dest_selected = cfg.get("destination_selected", False)
            has_connected_flag = "connected" in cfg
            has_dest_flag = "destination_selected" in cfg
            if has_connected_flag or has_dest_flag:
                if has_connected_flag and has_dest_flag:
                    return "✅" if (connected and dest_selected and has_chat) else "⚪"
                elif has_dest_flag:
                    return "✅" if (dest_selected and has_chat) else "⚪"
                elif has_connected_flag:
                    return "✅" if (connected and has_chat) else "⚪"
            # نسخه قدیمی بدون flag - فقط chat_id
            return "✅" if has_chat else "⚪"
        return "✅" if cfg.get("bot_token") else "⚪"

    return {
        "keyboard": [
            [{"text": f"{status_icon('bale')} Bale 🔵"}],
            [{"text": f"{status_icon('rubika')} Rubika 🟢"}],
            [{"text": f"{status_icon('eitaa')} Eitaa 🟡"}],
            [{"text": f"{status_icon('telegram')} Telegram ✈️"}],
            [{"text": f"{status_icon('whatsapp')} WhatsApp 💚"}],
            [{"text": t(chat_id, "messengers_help")}],
            [{"text": t(chat_id, "back_to_settings")}]
        ],
        "resize_keyboard": True
    }


def create_messengers_help_keyboard(chat_id):
    """صفحه‌کلید راهنمای پیام‌رسان‌ها - Inline"""
    lang = get_user_lang(chat_id)
    
    if lang == "fa":
        return {
            "inline_keyboard": [
                [{"text": "🔵 راهنمای Bale", "callback_data": "help_bale"}],
                [{"text": "🟢 راهنمای Rubika", "callback_data": "help_rubika"}],
                [{"text": "🟡 راهنمای Eitaa", "callback_data": "help_eitaa"}],
                [{"text": "✈️ راهنمای Telegram", "callback_data": "help_telegram"}],
                [{"text": "💚 راهنمای WhatsApp", "callback_data": "help_whatsapp"}],
                [{"text": "🔙 بازگشت به پیام‌رسان‌ها", "callback_data": "back_to_messengers_list"}],
                [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
            ]
        }
    else:
        return {
            "inline_keyboard": [
                [{"text": "🔵 Bale Guide", "callback_data": "help_bale"}],
                [{"text": "🟢 Rubika Guide", "callback_data": "help_rubika"}],
                [{"text": "🟡 Eitaa Guide", "callback_data": "help_eitaa"}],
                [{"text": "✈️ Telegram Guide", "callback_data": "help_telegram"}],
                [{"text": "💚 WhatsApp Guide", "callback_data": "help_whatsapp"}],
                [{"text": "🔙 Back to Messengers", "callback_data": "back_to_messengers_list"}],
                [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
            ]
        }


# ========== صفحه‌کلیدها - انتخاب پیام‌رسان برای پست ==========

def create_messenger_selection_keyboard(chat_id, user_config):
    """صفحه‌کلید انتخاب پیام‌رسان‌ها برای پست - Inline - داینامیک 5 پیام‌رسان"""
    current_state = user_states.get(chat_id, {})
    selected = current_state.get("selected_messengers", []) if isinstance(current_state, dict) else []

    available_messengers = []
    messenger_emojis = {
        "bale": "🔵 Bale",
        "rubika": "🟢 Rubika",
        "eitaa": "🟡 Eitaa",
        "telegram": "✈️ Telegram",
        "whatsapp": "💚 WhatsApp"
    }

    # Bale needs channel_id, others need chat_id, whatsapp only chat_id
    for m_name in ["bale", "rubika", "eitaa", "telegram", "whatsapp"]:
        cfg = user_config["messengers"].get(m_name, {})
        if m_name == "bale":
            if cfg.get("bot_token") and cfg.get("channel_id"):
                available_messengers.append(m_name)
        elif m_name == "whatsapp":
            if cfg.get("chat_id"):
                available_messengers.append(m_name)
        else:
            if cfg.get("bot_token") and cfg.get("chat_id"):
                available_messengers.append(m_name)

    keyboard = []

    for messenger in available_messengers:
        icon = "✅" if messenger in selected else "⚪"
        name = messenger_emojis.get(messenger, messenger.capitalize())
        keyboard.append([{
            "text": f"{icon} {name}",
            "callback_data": f"toggle_messenger_{messenger}"
        }])

    all_selected = (len(selected) == len(available_messengers)) if available_messengers else False
    all_icon = "✅" if all_selected else "⚪"
    keyboard.append([{
        "text": f"{all_icon} {t(chat_id, 'all')}",
        "callback_data": "toggle_all_messengers"
    }])

    keyboard.append([{"text": t(chat_id, "submit"), "callback_data": "submit_messenger_selection"}])
    keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

    return {"inline_keyboard": keyboard}


# ========== صفحه‌کلیدها - تقویم ==========

def create_calendar_keyboard(chat_id, year, month):
    """صفحه‌کلید تقویم - برای فارسی شمسی به وقت تهران، برای انگلیسی میلادی"""
    from calendar import monthrange
    import datetime as dt

    lang = get_user_lang(chat_id)
    today_tehran = tehran_today()

    # ===== نسخه انگلیسی / میلادی =====
    if lang != "fa":
        first_weekday, days_in_month = monthrange(year, month)

        month_names_en = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        keyboard = []

        keyboard.append([{
            "text": f"📅 {month_names_en[month]} {year}",
            "callback_data": "ignore"
        }])

        days_header = [{"text": d, "callback_data": "ignore"} for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]]
        keyboard.append(days_header)

        week = []
        for _ in range(first_weekday):
            week.append({"text": " ", "callback_data": "ignore"})

        for day in range(1, days_in_month + 1):
            current_date = dt.date(year, month, day)

            if current_date < today_tehran:
                week.append({"text": "·", "callback_data": "ignore"})
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                week.append({"text": str(day), "callback_data": f"date_{date_str}"})

            if len(week) == 7:
                keyboard.append(week)
                week = []

        if week:
            while len(week) < 7:
                week.append({"text": " ", "callback_data": "ignore"})
            keyboard.append(week)

        nav_buttons = []

        if year > today_tehran.year or (year == today_tehran.year and month > today_tehran.month):
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1
            prev_name = month_names_en[prev_month]
            nav_buttons.append({"text": f"◀️ {prev_name}", "callback_data": f"cal_{prev_year}_{prev_month}"})
        else:
            nav_buttons.append({"text": " ", "callback_data": "ignore"})

        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        max_future = dt.date(today_tehran.year + 1, today_tehran.month, 1)
        current_month_date = dt.date(year, month, 1)

        if current_month_date < max_future:
            next_name = month_names_en[next_month]
            nav_buttons.append({"text": f"{next_name} ▶️", "callback_data": f"cal_{next_year}_{next_month}"})
        else:
            nav_buttons.append({"text": " ", "callback_data": "ignore"})

        keyboard.append(nav_buttons)

        keyboard.append([{"text": "📝 Enter date manually", "callback_data": "manual_date_input"}])
        keyboard.append([{"text": "🔙 Cancel", "callback_data": "posting_menu"}])
        keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

        return {"inline_keyboard": keyboard}

    # ===== نسخه فارسی / شمسی به وقت تهران =====
    month_names_fa = [
        "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
        "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
    ]

    def jalali_month_days(jy, jm):
        if 1 <= jm <= 6:
            return 31
        if 7 <= jm <= 11:
            return 30
        return 30 if jdatetime.date(jy, 1, 1).isleap() else 29

    days_in_month = jalali_month_days(year, month)

    first_j = jdatetime.date(year, month, 1)
    first_g = first_j.togregorian()

    # شنبه=0 ، یکشنبه=1 ... جمعه=6
    first_weekday = (first_g.weekday() + 2) % 7

    today_j = tehran_jalali_today()

    keyboard = []

    # ✅ سرتیتر: ماه فارسی + سال شمسی (مثلاً خرداد ۱۴۰۵)
    keyboard.append([{
        "text": f"📅 {month_names_fa[month]} {year}",
        "callback_data": "ignore"
    }])

    days_header = [{"text": d, "callback_data": "ignore"} for d in ["ش", "ی", "د", "س", "چ", "پ", "ج"]]
    keyboard.append(days_header)

    week = []
    for _ in range(first_weekday):
        week.append({"text": " ", "callback_data": "ignore"})

    for day in range(1, days_in_month + 1):
        j_day = jdatetime.date(year, month, day)
        g_day = j_day.togregorian()

        if g_day < today_tehran:
            week.append({"text": "·", "callback_data": "ignore"})
        else:
            # ✅ ذخیره داخلی همچنان میلادی
            date_str = g_day.strftime("%Y-%m-%d")
            week.append({"text": str(day), "callback_data": f"date_{date_str}"})

        if len(week) == 7:
            keyboard.append(week)
            week = []

    if week:
        while len(week) < 7:
            week.append({"text": " ", "callback_data": "ignore"})
        keyboard.append(week)

    # ✅ ناوبری با نام ماه‌ها
    nav_buttons = []

    current_index = year * 12 + month
    today_index = today_j.year * 12 + today_j.month

    if current_index > today_index:
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        prev_name = month_names_fa[prev_month]
        nav_buttons.append({"text": f"◀️ {prev_name}", "callback_data": f"cal_{prev_year}_{prev_month}"})
    else:
        nav_buttons.append({"text": " ", "callback_data": "ignore"})

    if current_index < today_index + 12:
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        next_name = month_names_fa[next_month]
        nav_buttons.append({"text": f"{next_name} ▶️", "callback_data": f"cal_{next_year}_{next_month}"})
    else:
        nav_buttons.append({"text": " ", "callback_data": "ignore"})

    keyboard.append(nav_buttons)

    # ✅ دکمه ورود دستی تاریخ
    keyboard.append([{"text": "📝 وارد کردن تاریخ دستی", "callback_data": "manual_date_input"}])
    keyboard.append([{"text": "🔙 انصراف", "callback_data": "posting_menu"}])
    keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

    return {"inline_keyboard": keyboard}

# ========== صفحه‌کلیدها - انتخاب رسانه ==========

def create_media_content_keyboard(chat_id, user_db):
    """صفحه‌کلید انتخاب رسانه با جستجو - Inline"""
    media_contents = user_db.get_media_contents()

    keyboard = []
    keyboard.append([{"text": t(chat_id, "search"), "callback_data": "search_media"}])

    if not media_contents:
        upload_text = (
            "📤 بارگذاری رسانه جدید"
            if get_user_lang(chat_id) == "fa"
            else "📤 Upload New Media"
        )
        keyboard.append([{"text": upload_text, "callback_data": "upload_new_media_inline"}])
        keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])
        return {"inline_keyboard": keyboard}

    for content_id, media_type, file_id, title, created_at in media_contents:
        icon = "🖼️" if media_type == "photo" else "🎥"
        display_title = title if title else f"ID:{content_id}"
        button_text = f"{icon} {display_title}"
        keyboard.append([
            {"text": button_text, "callback_data": f"select_media_{content_id}"},
            {"text": "👁️", "callback_data": f"view_media_{content_id}"}
        ])

    upload_text = (
        "📤 بارگذاری جدید"
        if get_user_lang(chat_id) == "fa"
        else "📤 Upload New"
    )
    keyboard.append([{"text": upload_text, "callback_data": "upload_new_media_inline"}])
    keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

    return {"inline_keyboard": keyboard}


def create_text_content_keyboard(chat_id, user_db):
    """صفحه‌کلید انتخاب متن - Inline"""
    text_contents = user_db.get_text_contents()

    if not text_contents:
        write_text = (
            "✍️ نوشتن کپشن جدید"
            if get_user_lang(chat_id) == "fa"
            else "✍️ Write New Caption"
        )
        return {
            "inline_keyboard": [
                [{"text": write_text, "callback_data": "write_new_caption"}],
                [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
            ]
        }

    keyboard = []
    for content_id, text_preview, created_at in text_contents:
        preview = text_preview[:30] + "..." if len(text_preview) > 30 else text_preview
        button_text = f"📝 {preview}"
        keyboard.append([
            {"text": button_text, "callback_data": f"select_text_{content_id}"},
            {"text": "👁️", "callback_data": f"view_text_{content_id}"}
        ])

    write_text = (
        "✍️ نوشتن جدید"
        if get_user_lang(chat_id) == "fa"
        else "✍️ Write New"
    )
    keyboard.append([{"text": write_text, "callback_data": "write_new_caption"}])
    keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

    return {"inline_keyboard": keyboard}


# ========== صفحه‌کلیدها - مشاهده رسانه‌ها ==========

def create_media_list_keyboard(chat_id, user_db):
    """صفحه‌کلید لیست رسانه‌ها - Inline"""
    media_contents = user_db.get_media_contents()

    if not media_contents:
        upload_text = (
            "📤 بارگذاری رسانه"
            if get_user_lang(chat_id) == "fa"
            else "📤 Upload Media"
        )
        return {
            "inline_keyboard": [
                [{"text": upload_text, "callback_data": "content_upload_media"}],
                [{"text": t(chat_id, "back_to_contents"), "callback_data": "main_contents_menu"}],
                [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
            ]
        }

    keyboard = []
    for content_id, media_type, file_id, title, created_at in media_contents:
        icon = "🖼️" if media_type == "photo" else "🎥"
        display_title = title if title else f"ID:{content_id}"
        button_text = f"{icon} {display_title}"
        keyboard.append([
            {"text": button_text, "callback_data": "ignore"},
            {"text": "👁️", "callback_data": f"show_media_{content_id}"},
            {"text": "🗑️", "callback_data": f"del_media_{content_id}"}
        ])

    keyboard.append([{"text": t(chat_id, "back_to_contents"), "callback_data": "main_contents_menu"}])
    keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

    return {"inline_keyboard": keyboard}


def create_text_list_keyboard(chat_id, user_db):
    """صفحه‌کلید لیست متن‌ها - Inline"""
    text_contents = user_db.get_text_contents()

    if not text_contents:
        add_text = (
            "✍️ افزودن متن"
            if get_user_lang(chat_id) == "fa"
            else "✍️ Add Text"
        )
        return {
            "inline_keyboard": [
                [{"text": add_text, "callback_data": "content_upload_text"}],
                [{"text": t(chat_id, "back_to_contents"), "callback_data": "main_contents_menu"}],
                [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
            ]
        }

    keyboard = []
    for content_id, text_content, created_at in text_contents:
        preview = text_content[:25] + "..." if len(text_content) > 25 else text_content
        button_text = f"📝 {preview}"
        keyboard.append([
            {"text": button_text, "callback_data": "ignore"},
            {"text": "👁️", "callback_data": f"show_text_{content_id}"},
            {"text": "🗑️", "callback_data": f"del_text_{content_id}"}
        ])

    keyboard.append([{"text": t(chat_id, "back_to_contents"), "callback_data": "main_contents_menu"}])
    keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

    return {"inline_keyboard": keyboard}


def create_archive_content_keyboard(chat_id, user_db):
    """صفحه‌کلید آرشیو محتوا - Inline"""
    archived_media = user_db.get_archived_media_contents()
    archived_text = user_db.get_archived_text_contents()

    keyboard = []

    if archived_media:
        media_text = (
            "🖼️ رسانه‌های آرشیو شده"
            if get_user_lang(chat_id) == "fa"
            else "🖼️ Archived Media"
        )
        keyboard.append([{"text": media_text, "callback_data": "archive_media_list"}])

    if archived_text:
        text_text = (
            "📝 متن‌های آرشیو شده"
            if get_user_lang(chat_id) == "fa"
            else "📝 Archived Text"
        )
        keyboard.append([{"text": text_text, "callback_data": "archive_text_list"}])

    if not archived_media and not archived_text:
        empty_text = (
            "📭 آرشیو خالی است"
            if get_user_lang(chat_id) == "fa"
            else "📭 Archive is empty"
        )
        keyboard.append([{"text": empty_text, "callback_data": "ignore"}])

    keyboard.append([{"text": t(chat_id, "back_to_contents"), "callback_data": "main_contents_menu"}])
    keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

    return {"inline_keyboard": keyboard}


def create_drafts_keyboard(chat_id, user_db):
    """صفحه‌کلید پیش‌نویس‌ها - Inline"""
    drafts = user_db.get_draft_posts()

    if not drafts:
        no_drafts = (
            "📭 بدون پیش‌نویس"
            if get_user_lang(chat_id) == "fa"
            else "📭 No drafts"
        )
        return {
            "inline_keyboard": [
                [{"text": no_drafts, "callback_data": "ignore"}],
                [{"text": t(chat_id, "back_to_posting"), "callback_data": "posting_menu"}],
                [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
            ]
        }

    keyboard = []
    for draft in drafts:
        draft_id = draft[0]
        media_type = draft[2]
        scheduled_date = draft[5] if len(draft) > 5 else ""
        scheduled_time = draft[6] if len(draft) > 6 else ""

        icon = "📸" if media_type == "photo" else "🎥"
        time_info = (
            f"{scheduled_date} {scheduled_time}"
            if scheduled_date and scheduled_time
            else "No date"
        )

        lang = get_user_lang(chat_id)
        draft_text = f"پیش‌نویس #{draft_id}" if lang == "fa" else f"Draft #{draft_id}"
        button_text = f"{icon} {draft_text} - {time_info}"

        keyboard.append([
            {"text": button_text, "callback_data": f"view_draft_{draft_id}"},
            {"text": "📤", "callback_data": f"restore_draft_{draft_id}"},
            {"text": "🗑️", "callback_data": f"delete_draft_{draft_id}"}
        ])

    keyboard.append([{"text": t(chat_id, "back_to_posting"), "callback_data": "posting_menu"}])
    keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

    return {"inline_keyboard": keyboard}


def create_archive_posts_keyboard(chat_id, user_db):
    """صفحه‌کلید پست‌های آرشیو شده - Inline"""
    archived = user_db.get_archived_posts()

    if not archived:
        no_archived = (
            "📭 بدون پست آرشیو شده"
            if get_user_lang(chat_id) == "fa"
            else "📭 No archived posts"
        )
        return {
            "inline_keyboard": [
                [{"text": no_archived, "callback_data": "ignore"}],
                [{"text": t(chat_id, "back_to_posting"), "callback_data": "posting_menu"}],
                [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
            ]
        }

    keyboard = []
    for post in archived:
        post_id = post[0]
        media_type = post[2]
        scheduled_date = post[5] if len(post) > 5 else ""
        scheduled_time = post[6] if len(post) > 6 else ""

        icon = "📸" if media_type == "photo" else "🎥"
        time_info = (
            f"{scheduled_date} {scheduled_time}"
            if scheduled_date and scheduled_time
            else "N/A"
        )
        button_text = f"{icon} #{post_id} - {time_info}"

        keyboard.append([
            {"text": button_text, "callback_data": f"view_archived_{post_id}"},
            {"text": "🗑️", "callback_data": f"delete_archived_{post_id}"}
        ])

    keyboard.append([{"text": t(chat_id, "back_to_posting"), "callback_data": "posting_menu"}])
    keyboard.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

    return {"inline_keyboard": keyboard}


def create_edit_post_keyboard(chat_id, post_id):
    """صفحه‌کلید ویرایش پست - Inline"""
    lang = get_user_lang(chat_id)

    if lang == "fa":
        keyboard = [
            [
                {"text": "🖼️ تغییر رسانه", "callback_data": f"edit_media_{post_id}"},
                {"text": "📝 تغییر کپشن", "callback_data": f"edit_caption_{post_id}"}
            ],
            [
                {"text": "⏰ تغییر زمان", "callback_data": f"edit_time_{post_id}"},
                {"text": "🔄 تغییر همه", "callback_data": f"edit_all_{post_id}"}
            ],
            [
                {"text": "📋 ذخیره به پیش‌نویس", "callback_data": f"save_draft_{post_id}"},
                {"text": "🗑️ حذف", "callback_data": f"delete_post_{post_id}"}
            ],
            [{"text": t(chat_id, "back_to_posting"), "callback_data": "posting_edit"}],
            [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
        ]
    else:
        keyboard = [
            [
                {"text": "🖼️ Change Media", "callback_data": f"edit_media_{post_id}"},
                {"text": "📝 Change Caption", "callback_data": f"edit_caption_{post_id}"}
            ],
            [
                {"text": "⏰ Change Time", "callback_data": f"edit_time_{post_id}"},
                {"text": "🔄 Change All", "callback_data": f"edit_all_{post_id}"}
            ],
            [
                {"text": "📋 Save as Draft", "callback_data": f"save_draft_{post_id}"},
                {"text": "🗑️ Delete", "callback_data": f"delete_post_{post_id}"}
            ],
            [{"text": t(chat_id, "back_to_posting"), "callback_data": "posting_edit"}],
            [{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}]
        ]

    return {"inline_keyboard": keyboard}
# ========== هندلرهای مدیریت ادمین ==========

def handle_admin_menu(chat_id, message_id=None):
    """نمایش منوی ادمین"""
    if not auth_manager.is_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    keyboard = create_admin_menu_keyboard(chat_id)

    lang = get_user_lang(chat_id)
    if lang == "fa":
        msg = "👮 *منوی ادمین*\n\nیک گزینه را انتخاب کنید:"
    else:
        msg = "👮 *Admin Menu*\n\nChoose an option:"

    send_message(chat_id, msg, keyboard)


def handle_manage_users(chat_id):
    """مدیریت کاربران"""
    if not auth_manager.is_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    users = auth_manager.get_all_users()

    if not users:
        msg = (
            "👥 *کاربرانی وجود ندارد*"
            if get_user_lang(chat_id) == "fa"
            else "👥 *No users found*"
        )
        send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))
        return

    lang = get_user_lang(chat_id)
    msg = "👥 *لیست کاربران:*\n\n" if lang == "fa" else "👥 *User List:*\n\n"

    for user in users:
        user_chat_id = user['chat_id']
        username = user['username'] or "Unknown"
        status = user['status']

        if lang == "fa":
            role = "👨‍💼 ادمین" if user['is_admin'] else "👤 کاربر عادی"
        else:
            role = "👨‍💼 Admin" if user['is_admin'] else "👤 Regular User"

        msg += f"{role} | {username}\n"
        msg += f"  🆔 {user_chat_id}\n"
        msg += f"  📊 {status}\n"
        msg += f"  📅 {user['created_at']}\n\n"

    send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))


def handle_manage_admins(chat_id):
    """مدیریت ادمین‌ها"""
    if not auth_manager.is_super_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    admins = auth_manager.get_all_admins()
    lang = get_user_lang(chat_id)

    keyboard_buttons = [
        [{"text": t(chat_id, "add_admin")}],
        [{"text": t(chat_id, "remove_admin")}],
        [{"text": t(chat_id, "back_to_main")}]
    ]

    if not admins:
        msg = (
            "👨‍💼 *ادمینی وجود ندارد*"
            if lang == "fa"
            else "👨‍💼 *No admins found*"
        )
        send_message(chat_id, msg, {"keyboard": keyboard_buttons, "resize_keyboard": True})
        return

    msg = "👨‍💼 *لیست ادمین‌ها:*\n\n" if lang == "fa" else "👨‍💼 *Admin List:*\n\n"

    for admin in admins:
        if lang == "fa":
            admin_type = "⭐ سوپر ادمین" if admin['is_super_admin'] else "👨‍💼 ادمین"
        else:
            admin_type = "⭐ Super Admin" if admin['is_super_admin'] else "👨‍💼 Admin"

        msg += f"{admin_type} | {admin['username']}\n"
        msg += f"  🆔 {admin['chat_id']}\n"
        msg += f"  📅 {admin['created_at']}\n\n"

    send_message(chat_id, msg, {"keyboard": keyboard_buttons, "resize_keyboard": True})


def handle_add_admin(chat_id):
    """شروع فرایند اضافه کردن ادمین"""
    if not auth_manager.is_super_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    send_message(chat_id, t(chat_id, "enter_user_chat_id"))
    user_states[chat_id] = {"state": "awaiting_new_admin_id"}


def handle_remove_admin(chat_id):
    """شروع فرایند حذف ادمین"""
    if not auth_manager.is_super_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    admins = auth_manager.get_all_admins()

    if not admins:
        msg = (
            "📭 ادمینی برای حذف وجود ندارد"
            if get_user_lang(chat_id) == "fa"
            else "📭 No admins to remove"
        )
        send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))
        return

    send_message(chat_id, t(chat_id, "enter_user_chat_id"))
    user_states[chat_id] = {"state": "awaiting_remove_admin_id"}


def handle_view_access_requests(chat_id):
    """مشاهده درخواست‌های دسترسی"""
    if not auth_manager.is_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    requests_list = auth_manager.get_pending_requests()

    if not requests_list:
        msg = (
            "📭 درخواست‌های معلقی وجود ندارد"
            if get_user_lang(chat_id) == "fa"
            else "📭 No pending requests"
        )
        send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))
        return

    lang = get_user_lang(chat_id)

    for req in requests_list:
        request_id = req['request_id']
        user_id = req['chat_id']
        username = req['username']
        reason = req['reason']
        requested_at = req['requested_at']

        if lang == "fa":
            msg = "📋 *درخواست دسترسی*\n\n"
            msg += f"🆔 شناسه درخواست: {request_id}\n"
            msg += f"👤 کاربر: {username}\n"
            msg += f"💬 Chat ID: {user_id}\n"
            msg += f"📝 دلیل: {reason or 'ذکر نشده'}\n"
            msg += f"📅 زمان: {requested_at}\n"
        else:
            msg = "📋 *Access Request*\n\n"
            msg += f"🆔 Request ID: {request_id}\n"
            msg += f"👤 User: {username}\n"
            msg += f"💬 Chat ID: {user_id}\n"
            msg += f"📝 Reason: {reason or 'Not specified'}\n"
            msg += f"📅 Time: {requested_at}\n"

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": t(chat_id, "approve"), "callback_data": f"admin_approve_req_{request_id}"},
                    {"text": t(chat_id, "reject"), "callback_data": f"admin_reject_req_{request_id}"}
                ]
            ]
        }

        send_message(chat_id, msg, keyboard)

    final_msg = (
        f"✅ {len(requests_list)} درخواست نمایش داده شد"
        if lang == "fa"
        else f"✅ {len(requests_list)} request(s) displayed"
    )
    send_message(chat_id, final_msg, create_admin_menu_keyboard(chat_id))


def handle_activity_logs(chat_id):
    """مشاهده گزارش فعالیت"""
    if not auth_manager.is_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    logs = auth_manager.get_activity_log(limit=30)
    lang = get_user_lang(chat_id)

    if not logs:
        msg = (
            "📊 گزارشی وجود ندارد"
            if lang == "fa"
            else "📊 No activity logs"
        )
        send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))
        return

    msg = (
        "📊 *گزارش فعالیت (30 مورد اخیر):*\n\n"
        if lang == "fa"
        else "📊 *Activity Logs (Last 30):*\n\n"
    )

    for log in logs:
        log_chat_id = log['chat_id']
        action = log['action']
        details = log['details'] or ""
        timestamp = log['timestamp']

        msg += f"🆔 {log_chat_id} | {action}\n"
        if details:
            msg += f"   {details}\n"
        msg += f"   ⏰ {timestamp}\n\n"

    send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))


# ========== تابع کمکی - مدیریت یکپارچه state ==========

def get_state(chat_id):
    """
    دریافت یکپارچه state کاربر
    همیشه (state_name, state_data) برمی‌گرداند
    """
    state = user_states.get(chat_id)

    if state is None:
        return None, {}

    if isinstance(state, str):
        return state, {}

    if isinstance(state, dict):
        state_name = state.get('state') or state.get('step')
        return state_name, state

    return None, {}


def set_state(chat_id, state_name, **kwargs):
    """تنظیم state کاربر به صورت یکپارچه"""
    user_states[chat_id] = {"state": state_name, **kwargs}


def clear_state(chat_id):
    """پاک کردن state کاربر"""
    if chat_id in user_states:
        del user_states[chat_id]


# ========== هندلر اصلی ==========

def handle_message(message, callback_data=None):
    """هندلر پیام‌های اصلی"""
    global config

    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    message_id = message.get("message_id")
    username = message.get("from", {}).get("username", "unknown")

    bot_token = config['messengers']['bale']['bot_token']

    # ========== بررسی احراز هویت - با هندل خطای دیتابیس ==========
    try:
        user_info = auth_manager.get_user_info(chat_id)
    except Exception as e:
        logger.error(f"❌ get_user_info failed for {chat_id}: {e}, assuming not approved")
        user_info = None
    try:
        is_admin = auth_manager.is_admin(chat_id)
    except Exception as e:
        logger.error(f"❌ is_admin check failed for {chat_id}: {e}")
        is_admin = False

    user_is_approved = user_info and user_info['status'] == 'approved'

    if not user_is_approved and not is_admin:
        if text == "/start":
            handle_unauthenticated_user(message, bot_token)

        elif callback_data and callback_data.startswith('auth_'):

            # ✅ خرید دسترسی
            if callback_data == "auth_buy_access":
                from auth_handlers import _handle_buy_access
                _handle_buy_access(chat_id, username, bot_token, user_states)

            # ✅ تایید خرید و ارسال فاکتور
            elif callback_data == "auth_confirm_purchase":
                from auth_handlers import handle_purchase_confirm
                handle_purchase_confirm(chat_id, username, bot_token)
                clear_state(chat_id)

            # ✅ بازگشت به منوی احراز
            elif callback_data == "auth_back_to_menu":
                clear_state(chat_id)
                handle_unauthenticated_user(message, bot_token)

            else:
                handle_auth_callback(callback_data, message, bot_token, user_states)

        # ✅ پرداخت موفق
        elif message.get("successful_payment"):
            payment_info = message["successful_payment"]
            from auth_handlers import handle_successful_payment
            handle_successful_payment(chat_id, username, payment_info, bot_token)
            clear_state(chat_id)

        # ✅ دلیل درخواست دسترسی
        elif user_states.get(chat_id, {}).get('state') == 'awaiting_access_reason':
            if text:
                from auth_handlers import handle_access_reason_input
                handle_access_reason_input(chat_id, username, text, bot_token)
                clear_state(chat_id)

        elif user_states.get(chat_id, {}).get('state') == 'awaiting_token':
            if handle_token_input(chat_id, text, bot_token):
                clear_state(chat_id)
                send_message(chat_id, t(chat_id, "main_menu"), create_main_keyboard(chat_id))

        else:
            handle_unauthenticated_user(message, bot_token)
        return

    # ✅ اگر ادمین است اما در دیتابیس ثبت نشده، ثبت کن
    if is_admin and not user_info:
        logger.warning(f"⚠️ ادمین {chat_id} در دیتابیس یافت نشد، ثبت می‌شود...")
        auth_manager.register_user(chat_id, username)

    # ========== بارگذاری کانفیگ و DB شخصی ==========
    user_config = load_user_config(chat_id)
    user_db = get_user_db(chat_id)

    # ثبت فعالیت
    if text and text != "/start":
        auth_manager.log_activity(chat_id, "action", text[:50])

    # ========== انتخاب زبان ==========
    if text == "/start":
        if str(chat_id) not in config.get("user_languages", {}):
            keyboard = create_language_keyboard()
            send_message(chat_id, LANGUAGES["en"]["welcome"], keyboard)
        else:
            send_message(chat_id, t(chat_id, "main_menu"), create_main_keyboard(chat_id))
        return

    elif callback_data and callback_data.startswith("lang_"):
        selected_lang = callback_data.replace("lang_", "")
        set_user_lang(chat_id, selected_lang)

        welcome_text = (
            "🎉 زبان شما به فارسی تنظیم شد!"
            if selected_lang == "fa"
            else "🎉 Your language has been set to English!"
        )
        send_message(chat_id, welcome_text)
        send_message(chat_id, t(chat_id, "main_menu"), create_main_keyboard(chat_id))
        return

    # ========== بازگشت به منوی اصلی ==========
    elif text == t(chat_id, "back_to_main") or callback_data == "main_menu":
        clear_state(chat_id)
        send_message(chat_id, t(chat_id, "main_menu"), create_main_keyboard(chat_id))
        return

    # ========== منوی ادمین ==========
    elif text == t(chat_id, "admin_menu"):
        if not auth_manager.is_admin(chat_id):
            send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
            return
        handle_admin_menu(chat_id, message_id)
        return

    elif text == t(chat_id, "manage_users"):
        handle_manage_users(chat_id)
        return

    elif text == t(chat_id, "manage_admins"):
        if not auth_manager.is_super_admin(chat_id):
            send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
            return
        handle_manage_admins(chat_id)
        return

    elif text == t(chat_id, "add_admin"):
        if not auth_manager.is_super_admin(chat_id):
            send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
            return
        handle_add_admin(chat_id)
        return

    elif text == t(chat_id, "remove_admin"):
        if not auth_manager.is_super_admin(chat_id):
            send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
            return
        handle_remove_admin(chat_id)
        return

    elif text == t(chat_id, "view_access_requests") or callback_data == "admin_view_requests":
        handle_view_access_requests(chat_id)
        return

    elif text == t(chat_id, "activity_logs"):
        handle_activity_logs(chat_id)
        return

    # ========== تایید/رد درخواست‌های ادمین ==========
    elif callback_data and callback_data.startswith("admin_approve_req_"):
        if not auth_manager.is_admin(chat_id):
            send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
            return

        request_id = int(callback_data.replace("admin_approve_req_", ""))
        result = auth_manager.approve_request(request_id, chat_id)

        if result['success']:
            msg = (
                "✅ درخواست تایید شد!"
                if get_user_lang(chat_id) == "fa"
                else "✅ Request approved!"
            )
            send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))

            user_chat_id = result['chat_id']
            token = result['token']

            user_lang = get_user_lang(user_chat_id)
            if user_lang == "fa":
                user_msg = (
                    f"✅ *درخواست شما تایید شد!*\n\n"
                    f"🔑 توکن شما:\n`{token}`\n\n"
                    f"این توکن را نگه‌دارید و آن را برای ورود استفاده کنید."
                )
            else:
                user_msg = (
                    f"✅ *Your request has been approved!*\n\n"
                    f"🔑 Your token:\n`{token}`\n\n"
                    f"Keep this token safe and use it to login."
                )

            send_message(user_chat_id, user_msg)
        else:
            send_message(chat_id, "❌ خطای تایید درخواست", create_admin_menu_keyboard(chat_id))
        return

    elif callback_data and callback_data.startswith("admin_reject_req_"):
        if not auth_manager.is_admin(chat_id):
            send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
            return

        request_id = int(callback_data.replace("admin_reject_req_", ""))
        set_state(chat_id, "awaiting_reject_reason", request_id=request_id)
        send_message(chat_id, t(chat_id, "reject_reason"))
        return

    # ========== منوی اصلی - تنظیمات ==========
    elif text == t(chat_id, "settings"):
        send_message(chat_id, t(chat_id, "settings"), create_settings_keyboard(chat_id))
        return

    elif text == t(chat_id, "back"):
        send_message(chat_id, t(chat_id, "main_menu"), create_main_keyboard(chat_id))
        return

    elif text == t(chat_id, "back_to_settings"):
        send_message(chat_id, t(chat_id, "settings"), create_settings_keyboard(chat_id))
        return

    elif text == t(chat_id, "messengers"):
        send_message(chat_id, t(chat_id, "messengers"), create_messengers_keyboard(chat_id, user_config))
        return

    elif text == t(chat_id, "messengers_help"):
        # راهنمای کلی
        keyboard = create_messengers_help_keyboard(chat_id)
        send_message(chat_id, t(chat_id, "help_general"), keyboard)
        return

    # ========== پست‌های ووکامرس ==========
    elif text == t(chat_id, "woocommerce_posts") or callback_data == "woocommerce_posts":
        lang = get_user_lang(chat_id)
        msg = (
            "🛒 *پست‌های ووکامرس*\n\nگزینه مورد نظر را انتخاب کنید:"
            if lang == "fa"
            else "🛒 *WooCommerce Posts*\n\nSelect an option:"
        )
        send_message(chat_id, msg, create_woocommerce_posts_keyboard(chat_id))
        return

    elif text == t(chat_id, "back_to_wc_posts") or callback_data == "back_to_wc_posts":
        lang = get_user_lang(chat_id)
        msg = (
            "🛒 *پست‌های ووکامرس*"
            if lang == "fa"
            else "🛒 *WooCommerce Posts*"
        )
        send_message(chat_id, msg, create_woocommerce_posts_keyboard(chat_id))
        return

    elif text == t(chat_id, "config_autopost"):
        send_message(chat_id, t(chat_id, "config_autopost"), create_autopost_keyboard(chat_id, user_config))
        return

    elif t(chat_id, "toggle_autopost") in text:
        user_config["auto_post"]["enabled"] = not user_config["auto_post"]["enabled"]
        save_user_config(chat_id, user_config)

        lang = get_user_lang(chat_id)
        if lang == "fa":
            status = "فعال ✅" if user_config["auto_post"]["enabled"] else "غیرفعال ⚪"
            msg = f"پست خودکار اکنون {status} است"
        else:
            status = "enabled ✅" if user_config["auto_post"]["enabled"] else "disabled ⚪"
            msg = f"Auto post is now {status}"

        send_message(chat_id, msg, create_autopost_keyboard(chat_id, user_config))
        return

    elif t(chat_id, "toggle_live_new") in text:
        current = user_config["auto_post"].get("live_new_product", True)
        user_config["auto_post"]["live_new_product"] = not current
        save_user_config(chat_id, user_config)

        lang = get_user_lang(chat_id)
        if user_config["auto_post"]["live_new_product"]:
            msg = t(chat_id, "live_enabled")
        else:
            msg = t(chat_id, "live_disabled")

        send_message(chat_id, msg, create_autopost_keyboard(chat_id, user_config))
        return

    elif t(chat_id, "category_filter") in text:
        lang = get_user_lang(chat_id)
        # نمایش دسته‌بندی‌های موجود
        try:
            cats = woocommerce.get_categories(user_config)
            if cats:
                msg = "📂 *دسته‌بندی‌های موجود:*\n\n" if lang == "fa" else "📂 *Available categories:*\n\n"
                for c in cats[:20]:
                    msg += f"• {c['id']}: {c['name']} ({c.get('slug','')}) - {c.get('count',0)} محصول\n"
                if len(cats) > 20:
                    msg += f"\n... و {len(cats)-20} دسته دیگر"
            else:
                msg = "📂 دسته‌بندی یافت نشد یا ووکامرس متصل نیست" if lang == "fa" else "📂 No categories found"
        except Exception as e:
            msg = f"❌ خطا: {e}"
        
        msg += "\n\n" + t(chat_id, "enter_category")
        send_message(chat_id, msg)
        set_state(chat_id, "waiting_category_filter")
        return

    elif text == t(chat_id, "posts_per_day"):
        prompt = (
            "📊 تعداد پست در روز را ارسال کنید (1-10):"
            if get_user_lang(chat_id) == "fa"
            else "📊 Send number of posts per day (1-10):"
        )
        send_message(chat_id, prompt)
        set_state(chat_id, "waiting_posts_per_day")
        return

    elif text == t(chat_id, "schedule_days"):
        lang = get_user_lang(chat_id)
        msg = (
            "📅 *زمان‌بندی روزها*\n\nروی هر روز کلیک کنید تا ساعت‌های آن روز را تنظیم کنید:"
            if lang == "fa"
            else "📅 *Schedule Days*\n\nClick on each day to set its posting times:"
        )
        keyboard = create_days_keyboard(chat_id, user_config)
        send_message(chat_id, msg, keyboard)
        return

    # ========== زمان‌بندی روزها - کلیک روی روز ==========
    elif callback_data and callback_data.startswith("day_schedule_"):
        day_name = callback_data.replace("day_schedule_", "")

        set_state(chat_id, "awaiting_day_times", day=day_name)

        current_times = user_config["auto_post"]["schedule"].get(day_name, {}).get("times", [])

        days_map_fa = {
            "saturday": "شنبه", "sunday": "یکشنبه", "monday": "دوشنبه",
            "tuesday": "سه‌شنبه", "wednesday": "چهارشنبه",
            "thursday": "پنج‌شنبه", "friday": "جمعه"
        }
        days_map_en = {
            "saturday": "Saturday", "sunday": "Sunday", "monday": "Monday",
            "tuesday": "Tuesday", "wednesday": "Wednesday",
            "thursday": "Thursday", "friday": "Friday"
        }

        lang = get_user_lang(chat_id)
        day_display = days_map_fa.get(day_name, day_name) if lang == "fa" else days_map_en.get(day_name, day_name)

        if current_times:
            times_str = ", ".join(current_times)
            msg = (
                f"📅 *{day_display}*\n\n⏰ ساعت‌های فعلی:\n{times_str}\n\n"
                if lang == "fa"
                else f"📅 *{day_display}*\n\n⏰ Current times:\n{times_str}\n\n"
            )
        else:
            msg = f"📅 *{day_display}*\n\n"

        msg += t(chat_id, "enter_schedule_times")

        disable_text = (
            "⚪ غیرفعال کردن این روز"
            if lang == "fa"
            else "⚪ Disable this day"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": disable_text, "callback_data": f"disable_day_{day_name}"}],
                [{"text": t(chat_id, "back_to_wc_posts"), "callback_data": "back_to_wc_posts"}]
            ]
        }

        send_message(chat_id, msg, keyboard)
        return

    # ========== غیرفعال کردن روز ==========
    elif callback_data and callback_data.startswith("disable_day_"):
        day_name = callback_data.replace("disable_day_", "")

        user_config["auto_post"]["schedule"][day_name]["enabled"] = False
        user_config["auto_post"]["schedule"][day_name]["times"] = []
        save_user_config(chat_id, user_config)

        days_map_fa = {
            "saturday": "شنبه", "sunday": "یکشنبه", "monday": "دوشنبه",
            "tuesday": "سه‌شنبه", "wednesday": "چهارشنبه",
            "thursday": "پنج‌شنبه", "friday": "جمعه"
        }
        days_map_en = {
            "saturday": "Saturday", "sunday": "Sunday", "monday": "Monday",
            "tuesday": "Tuesday", "wednesday": "Wednesday",
            "thursday": "Thursday", "friday": "Friday"
        }

        lang = get_user_lang(chat_id)
        day_display = days_map_fa.get(day_name, day_name) if lang == "fa" else days_map_en.get(day_name, day_name)

        msg = t(chat_id, "day_disabled").format(day=day_display)
        send_message(chat_id, msg)

        msg2 = "📅 *زمان‌بندی روزها*" if lang == "fa" else "📅 *Schedule Days*"
        keyboard = create_days_keyboard(chat_id, user_config)
        send_message(chat_id, msg2, keyboard)
        return

    elif text == t(chat_id, "check_products"):
        if not user_config["woocommerce"]["url"]:
            error_msg = (
                "❌ ابتدا WooCommerce را پیکربندی کنید!"
                if get_user_lang(chat_id) == "fa"
                else "❌ Configure WooCommerce first!"
            )
            send_message(chat_id, error_msg, create_woocommerce_posts_keyboard(chat_id))
            return

        checking_msg = (
            "🔍 در حال بررسی لایو محصولات..."
            if get_user_lang(chat_id) == "fa"
            else "🔍 Live checking products..."
        )
        send_message(chat_id, checking_msg)
        
        # استفاده از منطق جدید
        new = woocommerce.check_new_products(user_config, user_chat_id=chat_id)
        unsent = woocommerce.get_unsent_products_sorted(user_config, user_chat_id=chat_id, limit=5)

        lang = get_user_lang(chat_id)
        if lang == "fa":
            result_msg = f"📊 *گزارش ووکامرس:*\n\n"
            result_msg += f"🆕 محصولات جدید: {len(new)}\n"
            result_msg += f"📦 محصولات ارسال نشده: {len(unsent)}\n"
            if new:
                result_msg += f"\n🆕 جدیدترین: {new[0].get('name','')[:40]}\n"
            if unsent:
                result_msg += f"\n📦 بعدی برای ارسال: {unsent[0].get('name','')[:40]} (ID: {unsent[0]['id']})\n"
            # نمایش دسته‌بندی فیلتر
            cats = user_config.get("auto_post", {}).get("categories", [])
            if cats:
                result_msg += f"\n📂 فیلتر دسته: {', '.join([str(c) for c in cats])}\n"
            else:
                result_msg += f"\n📂 فیلتر: همه دسته‌ها\n"
        else:
            result_msg = f"📊 *WooCommerce Report:*\n\n"
            result_msg += f"🆕 New products: {len(new)}\n"
            result_msg += f"📦 Unsent products: {len(unsent)}\n"
            if new:
                result_msg += f"\n🆕 Latest new: {new[0].get('name','')[:40]}\n"
            if unsent:
                result_msg += f"\n📦 Next to post: {unsent[0].get('name','')[:40]} (ID: {unsent[0]['id']})\n"

        send_message(chat_id, result_msg, create_woocommerce_posts_keyboard(chat_id))
        return

    elif text == t(chat_id, "test_product_posting"):
        if not any([
            user_config["messengers"]["bale"]["channel_id"],
            user_config["messengers"]["rubika"]["chat_id"],
            user_config["messengers"]["eitaa"]["chat_id"],
            user_config["messengers"]["telegram"]["chat_id"],
            user_config["messengers"]["whatsapp"]["chat_id"]
        ]):
            error_msg = (
                "❌ ابتدا پیام‌رسان‌ها را پیکربندی کنید!"
                if get_user_lang(chat_id) == "fa"
                else "❌ Configure messengers first!"
            )
            send_message(chat_id, error_msg, create_woocommerce_posts_keyboard(chat_id))
            return

        posting_msg = (
            "🧪 در حال تست ارسال..."
            if get_user_lang(chat_id) == "fa"
            else "🧪 Testing posting..."
        )
        send_message(chat_id, posting_msg)
        
        # ✅ اصلاح: ارسال chat_id کاربر
        scheduler.daily_job(user_config, user_chat_id=chat_id)

        done_msg = (
            "✅ تست انجام شد!"
            if get_user_lang(chat_id) == "fa"
            else "✅ Test completed!"
        )
        send_message(chat_id, done_msg, create_woocommerce_posts_keyboard(chat_id))
        return

    # ========== راهنمای پیام‌رسان‌ها - Callback ها ==========
    elif callback_data == "messengers_help":
        keyboard = create_messengers_help_keyboard(chat_id)
        if message_id:
            edit_message(chat_id, message_id, t(chat_id, "help_general"), keyboard)
        else:
            send_message(chat_id, t(chat_id, "help_general"), keyboard)
        return

    elif callback_data == "back_to_messengers_list":
        send_message(chat_id, t(chat_id, "messengers"), create_messengers_keyboard(chat_id, user_config))
        return

    elif callback_data and callback_data.startswith("help_"):
        messenger_name = callback_data.replace("help_", "")
        if messenger_name in ["bale", "rubika", "eitaa", "telegram", "whatsapp"]:
            # ارسال راهنما با عکس
            if message_id:
                # برای اینکه عکس جدید بفرستیم، نمی‌توانیم edit کنیم - باید پیام جدید بفرستیم
                pass
            send_guide_with_image(chat_id, messenger_name)
            
            # پیام کوتاه اضافی: اگر بلد نیستید...
            lang = get_user_lang(chat_id)
            short_msg = (
                f"💡 *نکته برای {messenger_name.capitalize()}*\n\n"
                f"اگر هنوز بلد نیستید، روی دکمه اتصال بزنید و من قدم به قدم راهنمایی‌تان می‌کنم!"
                if lang == "fa"
                else f"💡 Tip for {messenger_name.capitalize()}\nClick connect and I will guide you step by step!"
            )
            # این پیام کوتاه را با تاخیر بفرست تا بعد از عکس بیاید
            # send_message(chat_id, short_msg)
        return

    elif callback_data and callback_data.startswith("connect_"):
        messenger_name = callback_data.replace("connect_", "")
        if messenger_name in ["bale", "rubika", "eitaa", "telegram", "whatsapp"]:
            lang = get_user_lang(chat_id)
            # هدایت به تنظیم همان پیام‌رسان
            if messenger_name == "bale":
                prompt = "🤖 توکن ربات Bale خود را ارسال کنید:" if lang == "fa" else "🤖 Send your Bale bot token:"
                send_message(chat_id, prompt)
                set_state(chat_id, "waiting_bale_token")
            elif messenger_name == "rubika":
                prompt = "🤖 توکن ربات Rubika خود را ارسال کنید:" if lang == "fa" else "🤖 Send your Rubika bot token:"
                send_message(chat_id, prompt)
                set_state(chat_id, "waiting_rubika_token")
            elif messenger_name == "eitaa":
                prompt = "🤖 توکن ربات Eitaa خود را ارسال کنید:" if lang == "fa" else "🤖 Send your Eitaa bot token:"
                send_message(chat_id, prompt)
                set_state(chat_id, "waiting_eitaa_token")
            elif messenger_name == "telegram":
                prompt = (
                    "✈️ توکن ربات Telegram خود را ارسال کنید:\n"
                    "از @BotFather بگیرید"
                    if lang == "fa"
                    else "✈️ Send your Telegram bot token from @BotFather"
                )
                send_message(chat_id, prompt)
                set_state(chat_id, "waiting_telegram_token")
            elif messenger_name == "whatsapp":
                prompt = (
                    "💚 شماره واتساپ مقصد را ارسال کنید:\n"
                    "مثال: 989123456789\n\n"
                    "بعد QR + کد برای شما می‌آید!"
                    if lang == "fa"
                    else "💚 Send WhatsApp number: 989123456789"
                )
                send_message(chat_id, prompt)
                set_state(chat_id, "waiting_whatsapp_chat")
        return

    # ========== مدیریت پست‌ها ==========
    elif text == t(chat_id, "posting_management"):
        keyboard = create_posting_keyboard(chat_id)
        lang = get_user_lang(chat_id)
        msg = (
            "📮 *مدیریت پست‌ها*\n\nیک گزینه را انتخاب کنید:"
            if lang == "fa"
            else "📮 *Posting Management*\n\nChoose an option:"
        )
        send_message(chat_id, msg, keyboard)
        return

    # ========== پست جدید ==========
    elif callback_data == "posting_new":
        keyboard = create_media_content_keyboard(chat_id, user_db)
        lang = get_user_lang(chat_id)
        msg = (
            "📸 *پست جدید*\n\n🖼️ رسانه مورد نظر را انتخاب کنید:"
            if lang == "fa"
            else "📸 *New Post*\n\n🖼️ Select media:"
        )

        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    # ========== جستجو در رسانه‌ها ==========
    elif callback_data == "search_media":
        set_state(chat_id, "awaiting_search_query")
        prompt = t(chat_id, "enter_search_query")
        send_message(chat_id, prompt)
        return

    # ========== محتواها ==========
    elif text == t(chat_id, "contents"):
        keyboard = create_contents_keyboard(chat_id)
        lang = get_user_lang(chat_id)
        msg = (
            "📂 *مدیریت محتوا*\n\nرسانه‌ها و متن‌های خود را مدیریت کنید:"
            if lang == "fa"
            else "📂 *Contents Management*\n\nManage your media and text contents:"
        )
        send_message(chat_id, msg, keyboard)
        return

    elif callback_data == "main_contents_menu":
        keyboard = create_contents_keyboard(chat_id)
        lang = get_user_lang(chat_id)
        msg = (
            "📂 *مدیریت محتوا*\n\nیک گزینه را انتخاب کنید:"
            if lang == "fa"
            else "📂 *Contents Management*\n\nChoose an option:"
        )
        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    elif callback_data == "back_to_contents":
        keyboard = create_contents_keyboard(chat_id)
        lang = get_user_lang(chat_id)
        msg = (
            "📂 *مدیریت محتوا*"
            if lang == "fa"
            else "📂 *Contents Management*"
        )
        send_message(chat_id, msg, keyboard)
        return

    # ========== آپلود رسانه ==========
    elif callback_data == "content_upload_media":
        set_state(chat_id, "awaiting_media_title", content_upload_media=True)
        lang = get_user_lang(chat_id)
        msg = "📝 *آپلود رسانه*\n\n" + t(chat_id, "enter_media_title")
        if message_id:
            edit_message(chat_id, message_id, msg)
        else:
            send_message(chat_id, msg)
        return

    # ========== آپلود متن ==========
    elif callback_data == "content_upload_text":
        set_state(chat_id, "awaiting_text_content", content_upload_text=True)
        lang = get_user_lang(chat_id)
        msg = (
            "📝 *آپلود متن*\n\nمتن/کپشن خود را ارسال کنید:"
            if lang == "fa"
            else "📝 *Upload Text*\n\nSend your text/caption:"
        )
        if message_id:
            edit_message(chat_id, message_id, msg)
        else:
            send_message(chat_id, msg)
        return

    # ========== مشاهده رسانه‌ها ==========
    elif callback_data == "content_view_media":
        keyboard = create_media_list_keyboard(chat_id, user_db)
        lang = get_user_lang(chat_id)
        msg = (
            "📸 *مشاهده رسانه‌ها*\n\nلیست رسانه‌های شما:"
            if lang == "fa"
            else "📸 *View Media*\n\nYour media list:"
        )
        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    # ========== نمایش رسانه ==========
    elif callback_data and callback_data.startswith("show_media_"):
        content_id = int(callback_data.replace("show_media_", ""))
        media_content = user_db.get_content_by_id(content_id)

        if media_content:
            content_id_val, file_id, media_type, title, created_at = media_content
            caption = f"🖼️ {title}\n📅 {created_at}" if title else f"📅 {created_at}"

            if media_type == "photo":
                send_photo(chat_id, file_id, caption)
            elif media_type == "video":
                send_video(chat_id, file_id, caption)
        return

    # ========== حذف رسانه ==========
    elif callback_data and callback_data.startswith("del_media_"):
        content_id = int(callback_data.replace("del_media_", ""))
        user_db.delete_media_content(content_id)

        send_message(chat_id, t(chat_id, "delete_confirm"))

        keyboard = create_media_list_keyboard(chat_id, user_db)
        lang = get_user_lang(chat_id)
        msg = (
            "📸 *مشاهده رسانه‌ها*\n\nلیست رسانه‌های شما:"
            if lang == "fa"
            else "📸 *View Media*\n\nYour media list:"
        )
        send_message(chat_id, msg, keyboard)
        return

    # ========== مشاهده متن‌ها ==========
    elif callback_data == "content_view_text":
        keyboard = create_text_list_keyboard(chat_id, user_db)
        lang = get_user_lang(chat_id)
        msg = (
            "📝 *مشاهده متن‌ها*\n\nلیست متن‌های شما:"
            if lang == "fa"
            else "📝 *View Texts*\n\nYour text list:"
        )
        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    # ========== نمایش متن ==========
    elif callback_data and callback_data.startswith("show_text_"):
        content_id = int(callback_data.replace("show_text_", ""))
        text_content = user_db.get_text_content_by_id(content_id)

        if text_content:
            content_id_val, text_val, created_at = text_content
            lang = get_user_lang(chat_id)
            msg = (
                f"📝 *محتوای متنی*\n\n{text_val}\n\n📅 {created_at}"
                if lang == "fa"
                else f"📝 *Text Content*\n\n{text_val}\n\n📅 {created_at}"
            )
            send_message(chat_id, msg)
        return

    # ========== حذف متن ==========
    elif callback_data and callback_data.startswith("del_text_"):
        content_id = int(callback_data.replace("del_text_", ""))
        user_db.delete_text_content(content_id)

        send_message(chat_id, t(chat_id, "delete_confirm"))

        keyboard = create_text_list_keyboard(chat_id, user_db)
        lang = get_user_lang(chat_id)
        msg = (
            "📝 *مشاهده متن‌ها*\n\nلیست متن‌های شما:"
            if lang == "fa"
            else "📝 *View Texts*\n\nYour text list:"
        )
        send_message(chat_id, msg, keyboard)
        return

    elif callback_data == "content_archive":
        keyboard = create_archive_content_keyboard(chat_id, user_db)
        lang = get_user_lang(chat_id)
        msg = (
            "📦 *محتوای آرشیو شده*\n\nموارد حذف شده:"
            if lang == "fa"
            else "📦 *Archived Contents*\n\nDeleted items:"
        )
        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    # ========== پست‌های زمان‌بندی شده ==========
    elif callback_data == "posting_edit":
        posts = user_db.get_scheduled_posts()
        lang = get_user_lang(chat_id)

        if not posts:
            keyboard = create_posting_keyboard(chat_id)
            msg = (
                "📝 پست زمان‌بندی شده‌ای یافت نشد."
                if lang == "fa"
                else "📝 No scheduled posts found."
            )
            if message_id:
                edit_message(chat_id, message_id, msg, keyboard)
            else:
                send_message(chat_id, msg, keyboard)
        else:
            msg = (
                "📝 *پست‌های زمان‌بندی شده:*\n\n"
                if lang == "fa"
                else "📝 *Scheduled Posts:*\n\n"
            )
            keyboard_buttons = []

            for post in posts:
                post_id = post[0]
                media_type = post[2]
                caption = post[3]
                scheduled_date = post[5]
                scheduled_time = post[6]

                post_type_icon = "📸 عکس" if media_type == 'photo' else "🎥 ویدیو"
                display_date = format_date_for_user(chat_id, scheduled_date)
                msg += f"🆔 ID: {post_id}\n{post_type_icon}\n📅 {display_date} ساعت {scheduled_time}\n"
                if caption:
                    msg += f"📝 {caption[:50]}...\n"
                msg += "\n"

                edit_text = (
                    f"ویرایش پست #{post_id}"
                    if lang == "fa"
                    else f"Edit Post #{post_id}"
                )
                keyboard_buttons.append([{
                    "text": edit_text,
                    "callback_data": f"edit_post_{post_id}"
                }])

            keyboard_buttons.append([{
                "text": t(chat_id, "back_to_posting"),
                "callback_data": "posting_menu"
            }])
            keyboard_buttons.append([{
                "text": t(chat_id, "back_to_main"),
                "callback_data": "main_menu"
            }])

            if message_id:
                edit_message(chat_id, message_id, msg, {"inline_keyboard": keyboard_buttons})
            else:
                send_message(chat_id, msg, {"inline_keyboard": keyboard_buttons})
        return

    elif callback_data and callback_data.startswith("edit_post_"):
        post_id = int(callback_data.replace("edit_post_", ""))
        keyboard = create_edit_post_keyboard(chat_id, post_id)
        lang = get_user_lang(chat_id)
        msg = (
            f"✏️ *ویرایش پست #{post_id}*\n\nچه چیزی را می‌خواهید ویرایش کنید:"
            if lang == "fa"
            else f"✏️ *Edit Post #{post_id}*\n\nChoose what to edit:"
        )
        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    elif callback_data == "posting_drafts":
        keyboard = create_drafts_keyboard(chat_id, user_db)
        lang = get_user_lang(chat_id)
        msg = (
            "📋 *پیش‌نویس‌های شما*"
            if lang == "fa"
            else "📋 *Your Draft Posts*"
        )
        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    elif callback_data == "posting_archive":
        keyboard = create_archive_posts_keyboard(chat_id, user_db)
        lang = get_user_lang(chat_id)
        msg = (
            "🗂️ *پست‌های آرشیو شده*"
            if lang == "fa"
            else "🗂️ *Archived Posts*"
        )
        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    elif callback_data == "posting_history":
        history = user_db.get_posting_history(limit=20)
        lang = get_user_lang(chat_id)

        if not history:
            keyboard = create_posting_keyboard(chat_id)
            msg = (
                "📊 تاریخچه پست‌ای یافت نشد."
                if lang == "fa"
                else "📊 No posting history found."
            )
            if message_id:
                edit_message(chat_id, message_id, msg, keyboard)
            else:
                send_message(chat_id, msg, keyboard)
        else:
            msg = (
                "📊 *تاریخچه پست‌ها (20 تای اخیر):*\n\n"
                if lang == "fa"
                else "📊 *Posting History (Last 20):*\n\n"
            )
            for record in history:
                post_type_icon = "📸 عکس" if record[2] == 'photo' else "🎥 ویدیو"
                msg += f"{post_type_icon} | 📅 {record[5]}\n"
                if record[3]:
                    msg += f"📝 {record[3][:40]}...\n"
                msg += "\n"

            keyboard = create_posting_keyboard(chat_id)
            if message_id:
                edit_message(chat_id, message_id, msg, keyboard)
            else:
                send_message(chat_id, msg, keyboard)
        return

    elif callback_data == "posting_menu":
        keyboard = create_posting_keyboard(chat_id)
        lang = get_user_lang(chat_id)
        msg = (
            "📮 *مدیریت پست‌ها*\n\nیک گزینه را انتخاب کنید:"
            if lang == "fa"
            else "📮 *Posting Management*\n\nChoose an option:"
        )
        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    # ========== انتخاب پیام‌رسان‌ها ==========
    elif callback_data and callback_data.startswith("toggle_messenger_"):
        messenger = callback_data.replace("toggle_messenger_", "")

        current_state_name, current_state_data = get_state(chat_id)
        if not isinstance(user_states.get(chat_id), dict):
            user_states[chat_id] = {"selected_messengers": []}

        if "selected_messengers" not in user_states[chat_id]:
            user_states[chat_id]["selected_messengers"] = []

        if messenger in user_states[chat_id]["selected_messengers"]:
            user_states[chat_id]["selected_messengers"].remove(messenger)
        else:
            user_states[chat_id]["selected_messengers"].append(messenger)

        keyboard = create_messenger_selection_keyboard(chat_id, user_config)
        if message_id:
            edit_message(chat_id, message_id, t(chat_id, "select_messengers"), keyboard)
        return

    elif callback_data == "toggle_all_messengers":
        available = []
        for m_name in ["bale", "rubika", "eitaa", "telegram", "whatsapp"]:
            cfg = user_config["messengers"].get(m_name, {})
            if m_name == "bale":
                if cfg.get("bot_token") and cfg.get("channel_id"):
                    available.append(m_name)
            elif m_name == "whatsapp":
                if cfg.get("chat_id"):
                    available.append(m_name)
            else:
                if cfg.get("bot_token") and cfg.get("chat_id"):
                    available.append(m_name)

        if not isinstance(user_states.get(chat_id), dict):
            user_states[chat_id] = {"selected_messengers": []}

        if len(user_states[chat_id].get("selected_messengers", [])) == len(available):
            user_states[chat_id]["selected_messengers"] = []
        else:
            user_states[chat_id]["selected_messengers"] = available.copy()

        keyboard = create_messenger_selection_keyboard(chat_id, user_config)
        if message_id:
            edit_message(chat_id, message_id, t(chat_id, "select_messengers"), keyboard)
        return

    elif callback_data == "check_whatsapp_status":
        # بررسی اتصال واتساپ بعد از اسکن QR - با لیست گروه‌ها
        lang = get_user_lang(chat_id)
        try:
            import messenger_whatsapp
            wa_cfg = user_config["messengers"].get("whatsapp", {})
            service_url = wa_cfg.get("service_url", "http://localhost:3001")
            
            # چک وضعیت
            status = messenger_whatsapp.check_connection_status(chat_id, service_url)
            
            if status.get("connected"):
                # متصل شد! حالا گروه‌ها را لیست کن
                user_config["messengers"]["whatsapp"]["connected"] = True
                save_user_config(chat_id, user_config)
                
                # سعی کن گروه‌ها را بگیری
                chats_result = messenger_whatsapp.get_chats_for_user(chat_id, service_url)
                
                if chats_result.get("ok") and chats_result.get("chats"):
                    chats = chats_result["chats"]
                    # نمایش لیست گروه‌ها برای انتخاب مقصد
                    msg = (
                        f"✅ *واتساپ با موفقیت متصل شد!* 🎉\n\n"
                        f"📱 شماره: {wa_cfg.get('chat_id','')}\n"
                        f"🔗 وضعیت: متصل ✅\n\n"
                        f"📋 {len(chats)} گروه پیدا شد:\n\n"
                        "لطفا مقصد ارسال را انتخاب کنید:\n"
                        "(کدام گروه/کانال پست‌ها به آن ارسال شود)"
                        if lang == "fa"
                        else f"✅ WhatsApp connected! Found {len(chats)} groups, select destination:"
                    )
                    send_message(chat_id, msg)
                    
                    # کیبورد گروه‌ها
                    keyboard = []
                    for chat in chats[:10]:  # فقط 10 تای اول برای جلوگیری از شلوغی
                        name = chat.get("name", "Unknown")[:30]
                        chat_id_val = chat.get("id", "")
                        participants = chat.get("participants", 0)
                        btn_text = f"👥 {name} ({participants})" if participants else f"👥 {name}"
                        keyboard.append([{"text": btn_text, "callback_data": f"wa_select_dest_{chat_id_val}"}])
                    
                    # گزینه ارسال به شماره شخصی هم
                    keyboard.append([{"text": "📱 ارسال به شماره شخصی" if lang == "fa" else "📱 Send to personal number", "callback_data": "wa_select_personal"}])
                    keyboard.append([{"text": "⏭️ رد کردن - بعدا انتخاب می‌کنم" if lang == "fa" else "⏭️ Skip", "callback_data": "wa_skip_dest"}])
                    
                    send_message(chat_id, "👇 گروه مقصد را انتخاب کنید:", {"inline_keyboard": keyboard})
                    set_state(chat_id, "waiting_whatsapp_destination", chats=chats)
                    return
                else:
                    # گروهی پیدا نشد، ولی متصل است - مقصد را شماره شخصی بگذار و بپرس
                    msg = (
                        f"✅ *واتساپ متصل شد!* 🎉\n\n"
                        f"📱 شماره: {wa_cfg.get('chat_id','')}\n\n"
                        "⚠️ گروهی پیدا نشد (یا هنوز لود نشده)\n\n"
                        "می‌توانید:\n"
                        "1️⃣ شماره مقصد را دستی وارد کنید: 98912...\n"
                        "2️⃣ یا همین شماره فعلی به عنوان مقصد استفاده شود\n\n"
                        "شماره مقصد را ارسال کنید یا بنویسید `ok` برای تایید همین شماره"
                        if lang == "fa"
                        else f"✅ WhatsApp connected! No groups found, send destination number or type ok"
                    )
                    send_message(chat_id, msg)
                    set_state(chat_id, "waiting_whatsapp_destination", chats=[])
                    return
                
                success_msg = (
                    f"✅ *واتساپ با موفقیت متصل شد!* 🎉\n\n"
                    f"📱 شماره مقصد: {wa_cfg.get('chat_id','')}\n"
                    f"🔗 وضعیت: متصل ✅\n\n"
                    "حالا می‌توانید:\n"
                    "• پست‌های ووکامرس -> تست ارسال محصولات\n"
                    "• مدیریت پست‌ها -> پست جدید\n\n"
                    "پیام‌های شما به واتساپ ارسال خواهد شد!"
                    if lang == "fa"
                    else f"✅ WhatsApp connected! To: {wa_cfg.get('chat_id','')}"
                )
                send_message(chat_id, success_msg, create_messengers_keyboard(chat_id, user_config))
                clear_state(chat_id)
                return
            
            # اگر هنوز متصل نشده، چک کن آیا QR عوض شده (برای بروزرسانی خودکار)
            current_state_name, current_state_data = get_state(chat_id)
            last_qr = current_state_data.get("last_qr", "") if isinstance(current_state_data, dict) else ""
            
            # از endpoint qr-check برای تشخیص تغییر QR استفاده کن
            try:
                import requests as req_lib
                qr_check_resp = req_lib.get(
                    f"{service_url}/qr-check",
                    params={"userId": str(chat_id), "lastQR": last_qr},
                    timeout=10
                )
                if qr_check_resp.status_code == 200:
                    qr_check_data = qr_check_resp.json()
                    if qr_check_data.get("changed") and qr_check_data.get("qrImage"):
                        # QR عوض شده - خودکار QR جدید بفرست
                        logger.info(f"🔄 Auto-refresh QR for user {chat_id} - QR changed")
                        import base64, tempfile, os
                        base64_part = qr_check_data["qrImage"].split(",")[1] if "," in qr_check_data["qrImage"] else qr_check_data["qrImage"]
                        qr_bytes = base64.b64decode(base64_part)
                        bale_token = config["messengers"]["bale"]["bot_token"]
                        api = f"https://tapi.bale.ai/bot{bale_token}"
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            tmp.write(qr_bytes)
                            tmp_path = tmp.name
                        with open(tmp_path, "rb") as f:
                            files = {"photo": ("qr.png", f, "image/png")}
                            pairing_code = qr_check_data.get("pairingCode")
                            if pairing_code:
                                caption = f"🔄 QR جدید (خودکار) + کد: `{pairing_code}`\n⏰ سریع اسکن کنید!" if lang == "fa" else f"🔄 New QR (auto) + Code: `{pairing_code}`"
                            else:
                                caption = "🔄 QR جدید (خودکار بروز شد)" if lang == "fa" else "🔄 New QR (auto-refreshed)"
                            data = {"chat_id": chat_id, "caption": caption}
                            req_lib.post(f"{api}/sendPhoto", data=data, files=files, timeout=20)
                            os.unlink(tmp_path)
                        
                        # آپدیت last_qr
                        if isinstance(user_states.get(chat_id), dict):
                            user_states[chat_id]["last_qr"] = qr_check_data.get("qr", "")
                            if pairing_code:
                                user_states[chat_id]["pairing_code"] = pairing_code
                        
                        # پیام راهنما با کد اگر دارد
                        if qr_check_data.get("pairingCode"):
                            code_msg = f"🔑 کد جدید: `{qr_check_data['pairingCode']}`" if lang == "fa" else f"🔑 New code: `{qr_check_data['pairingCode']}`"
                            send_message(chat_id, code_msg)
                        
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "✅ بررسی اتصال" if lang == "fa" else "✅ Check", "callback_data": "check_whatsapp_status"}]
                            ]
                        }
                        send_message(chat_id, "QR جدید فرستاده شد (خودکار)" if lang == "fa" else "New QR auto-sent", keyboard)
                        return
            except Exception as e:
                logger.error(f"QR auto-check error: {e}")
            
            # هنوز متصل نشده و QR هم عوض نشده - نسخه کپی شدنی + شماره خودت
            has_qr = status.get("hasQR", False)
            pairing_code = status.get("pairingCode") or status.get("copyableCode")
            own_phone_check = wa_cfg.get("phone_number","") or wa_cfg.get("own_phone","") or wa_cfg.get("chat_id","")
            
            if has_qr:
                if pairing_code:
                    plain_check = pairing_code.replace("-", "").replace(" ", "")
                    msg = (
                        f"⏳ هنوز متصل نشده...\n\n"
                        f"🔑 *کد قابل کپی:* `{pairing_code}`\n"
                        f"📋 کپی راحت: `{plain_check}`\n\n"
                        f"برای شماره خودت {own_phone_check} - روی همین شماره وارد کن\n\n"
                        "یا QR را اسکن کنید:\n"
                        "واتساپ -> تنظیمات -> دستگاه‌های متصل -> اتصال دستگاه\n\n"
                        "بعد از اسکن دوباره بررسی بزنید\n"
                        "کد بالا به صورت جدا هم فرستاده می‌شود برای کپی"
                        if lang == "fa"
                        else f"Not connected yet\nCopyable Code: {pairing_code} plain {plain_check}\nFor {own_phone_check}\nScan QR and check again"
                    )
                    # پیام‌های جدا برای کپی آسان
                    try:
                        send_message(chat_id, f"{pairing_code}\n\n👆 کپی کن - برای {own_phone_check}")
                        send_message(chat_id, f"{plain_check}\n\n👆 بدون خط تیره")
                    except:
                        pass
                else:
                    msg = (
                        "⏳ هنوز متصل نشده...\n\n"
                        "لطفا QR را اسکن کنید:\n"
                        "واتساپ -> تنظیمات -> دستگاه‌های متصل -> اتصال دستگاه\n\n"
                        "بعد از اسکن دوباره دکمه بررسی را بزنید\n"
                        "یا بنویسید qr برای کد جدید"
                        if lang == "fa"
                        else "Not connected yet, please scan QR and check again or type qr"
                    )
            else:
                msg = (
                    "⏳ QR منقضی شده\n"
                    "در حال دریافت QR جدید..."
                    if lang == "fa"
                    else "QR expired, getting new..."
                )
                # خودکار QR جدید بگیر - با شماره خودت
                try:
                    import messenger_whatsapp
                    qr_result = messenger_whatsapp.get_qr_for_user(chat_id, own_phone_check or wa_cfg.get("chat_id",""), service_url)
                    if qr_result.get("qrImage"):
                        import base64, tempfile, os
                        base64_part = qr_result["qrImage"].split(",")[1] if "," in qr_result["qrImage"] else qr_result["qrImage"]
                        qr_bytes = base64.b64decode(base64_part)
                        bale_token = config["messengers"]["bale"]["bot_token"]
                        api = f"https://tapi.bale.ai/bot{bale_token}"
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            tmp.write(qr_bytes)
                            tmp_path = tmp.name
                        with open(tmp_path, "rb") as f:
                            files = {"photo": ("qr.png", f, "image/png")}
                            pc_tmp = qr_result.get("pairingCode") or ""
                            caption_tmp = f"🔄 QR جدید + کد {pc_tmp}" if pc_tmp else "🔄 QR جدید"
                            data = {"chat_id": chat_id, "caption": caption_tmp}
                            req_lib.post(f"{api}/sendPhoto", data=data, files=files, timeout=20)
                            os.unlink(tmp_path)
                        if isinstance(user_states.get(chat_id), dict):
                            user_states[chat_id]["last_qr"] = qr_result.get("qr","")
                        # کد جدا
                        if qr_result.get("pairingCode"):
                            pc = qr_result.get("pairingCode")
                            send_message(chat_id, f"{pc}\n\n👆 کپی کن")
                            send_message(chat_id, f"{pc.replace('-','')}\n\n👆 بدون خط تیره")
                        msg = "✅ QR جدید فرستاده شد، اسکن کنید و بررسی بزنید - کد بالا قابل کپی" if lang == "fa" else "New QR sent, code copyable above"
                except Exception as e:
                    logger.error(f"QR auto new error: {e}")
            
            keyboard = {
                "inline_keyboard": [
                    [{"text": "✅ بررسی مجدد" if lang == "fa" else "✅ Check Again", "callback_data": "check_whatsapp_status"}],
                    [{"text": "🔄 QR جدید" if lang == "fa" else "🔄 New QR", "callback_data": "whatsapp_new_qr"}]
                ]
            }
            if message_id:
                edit_message(chat_id, message_id, msg, keyboard)
            else:
                send_message(chat_id, msg, keyboard)
        except Exception as e:
            logger.error(f"❌ WhatsApp check status error for {chat_id}: {e}")
            # برای کاربر پیام ساده بدون جزئیات سرور
            simple_msg = "⏳ در حال بررسی... لطفا دوباره تلاش کنید" if get_user_lang(chat_id) == "fa" else "⏳ Checking... try again"
            send_message(chat_id, simple_msg)
        return

    elif callback_data and callback_data.startswith("wa_select_dest_"):
        # انتخاب گروه واتساپ به عنوان مقصد
        lang = get_user_lang(chat_id)
        dest_id = callback_data.replace("wa_select_dest_", "")
        
        # ذخیره به عنوان مقصد
        user_config["messengers"]["whatsapp"]["chat_id"] = dest_id
        user_config["messengers"]["whatsapp"]["destination_selected"] = True
        user_config["messengers"]["whatsapp"]["connected"] = True
        save_user_config(chat_id, user_config)
        
        # پیدا کردن نام گروه
        current_state_name, current_state_data = get_state(chat_id)
        chats = current_state_data.get("chats", []) if isinstance(current_state_data, dict) else []
        dest_name = dest_id
        for chat in chats:
            if chat.get("id") == dest_id:
                dest_name = chat.get("name", dest_id)
                break
        
        success_msg = (
            f"✅ *مقصد واتساپ انتخاب شد!* 🎉\n\n"
            f"👥 گروه: {dest_name}\n"
            f"🆔 آیدی: {dest_id}\n\n"
            f"🔗 وضعیت: متصل + مقصد انتخاب شده ✅\n\n"
            "حالا پست‌ها به این گروه ارسال می‌شود:\n"
            "• مدیریت پست‌ها -> پست جدید\n"
            "• ووکامرس -> تست ارسال\n\n"
            "⏳ در حال ارسال پیام تست به گروه..."
            if lang == "fa"
            else f"✅ WhatsApp destination selected: {dest_name} - sending test..."
        )
        send_message(chat_id, success_msg)
        
        # ارسال پیام تست به گروه مقصد برای اطمینان
        try:
            import messenger_whatsapp
            wa_cfg = user_config["messengers"].get("whatsapp", {})
            service_url = wa_cfg.get("service_url", "http://localhost:3001")
            test_text = (
                f"✅ ربات متصل شد! اوکی وصله 🎉\n\n"
                f"👥 گروه: {dest_name}\n"
                f"🤖 این گروه به عنوان مقصد انتخاب شد\n\n"
                f"از این به بعد پست‌ها اینجا ارسال می‌شود"
                if lang == "fa"
                else f"✅ Bot connected! Test OK 🎉 Group: {dest_name}"
            )
            # ارسال تست
            result = messenger_whatsapp._send_via_baileys(dest_id, test_text, None, service_url, str(chat_id))
            if result:
                send_message(chat_id, "✅ پیام تست به گروه ارسال شد! اوکی وصله 🎉" if lang == "fa" else "✅ Test message sent to group!", create_messengers_keyboard(chat_id, user_config))
            else:
                send_message(chat_id, "⚠️ اتصال برقرار است ولی پیام تست ارسال نشد - ممکن است گروه پرمیشن نداشته باشد، ولی پست‌ها سعی می‌شود ارسال شود" if lang == "fa" else "⚠️ Connected but test failed", create_messengers_keyboard(chat_id, user_config))
        except Exception as e:
            logger.error(f"❌ Test message error: {e}")
            send_message(chat_id, create_messengers_keyboard(chat_id, user_config))
        
        clear_state(chat_id)
        return
    
    elif callback_data == "wa_select_personal":
        lang = get_user_lang(chat_id)
        msg = (
            "📱 *ارسال به شماره شخصی*\n\n"
            "شماره مقصد را وارد کنید:\n"
            "مثال: 989123456789\n\n"
            "یا آیدی گروه: 120363...@g.us"
            if lang == "fa"
            else "📱 Send personal number or group ID"
        )
        send_message(chat_id, msg)
        set_state(chat_id, "waiting_whatsapp_destination", chats=[])
        return
    
    elif callback_data == "wa_skip_dest":
        lang = get_user_lang(chat_id)
        # رد کردن انتخاب مقصد - فقط connected ولی بدون destination_selected
        user_config["messengers"]["whatsapp"]["connected"] = True
        user_config["messengers"]["whatsapp"]["destination_selected"] = False
        save_user_config(chat_id, user_config)
        
        msg = (
            "⏭️ *رد شد*\n\n"
            "واتساپ متصل است ولی مقصد انتخاب نشده\n"
            "⚪ تیک سبز نمی‌خورد تا مقصد انتخاب شود\n\n"
            "برای انتخاب مقصد بعدا:\n"
            "تنظیمات -> پیام‌رسان‌ها -> WhatsApp\n"
            "سپس لیست گروه‌ها را ببینید"
            if lang == "fa"
            else "⏭️ Skipped - WhatsApp connected but no destination, no green tick until destination selected"
        )
        send_message(chat_id, msg, create_messengers_keyboard(chat_id, user_config))
        clear_state(chat_id)
        return
    
    elif callback_data == "whatsapp_new_qr":
        # درخواست QR جدید با کد - نسخه قابل کپی + شماره خودت
        lang = get_user_lang(chat_id)
        try:
            import messenger_whatsapp, base64, tempfile, os, requests as req_lib
            wa_cfg = user_config["messengers"].get("whatsapp", {})
            service_url = wa_cfg.get("service_url", "http://localhost:3001")
            # مهم: شماره خود کاربر برای pairing، نه مقصد
            phone = wa_cfg.get("phone_number", "") or wa_cfg.get("own_phone", "") or wa_cfg.get("chat_id", "")
            
            sending_msg = f"⏳ دریافت QR جدید برای شماره خودت {phone}..." if lang == "fa" else f"⏳ Getting new QR for {phone}..."
            if message_id:
                edit_message(chat_id, message_id, sending_msg)
            else:
                send_message(chat_id, sending_msg)
            
            qr_result = messenger_whatsapp.get_qr_for_user(chat_id, phone, service_url)
            
            if qr_result.get("connected"):
                success_msg = "✅ قبلا متصل است!" if lang == "fa" else "✅ Already connected!"
                send_message(chat_id, success_msg, create_messengers_keyboard(chat_id, user_config))
                clear_state(chat_id)
                return
            
            if qr_result.get("qrImage"):
                base64_part = qr_result["qrImage"].split(",")[1] if "," in qr_result["qrImage"] else qr_result["qrImage"]
                qr_bytes = base64.b64decode(base64_part)
                bale_token = config["messengers"]["bale"]["bot_token"]
                api = f"https://tapi.bale.ai/bot{bale_token}"
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(qr_bytes)
                    tmp_path = tmp.name
                with open(tmp_path, "rb") as f:
                    files = {"photo": ("qr.png", f, "image/png")}
                    caption = "📱 QR جدید - 20 ثانیه اعتبار دارد! اسکن کن" if lang == "fa" else "📱 New QR - 20s valid!"
                    data = {"chat_id": chat_id, "caption": caption}
                    req_lib.post(f"{api}/sendPhoto", data=data, files=files, timeout=20)
                    os.unlink(tmp_path)
                
                # کد قابل کپی - جداگانه
                pairing_code = qr_result.get("pairingCode") or qr_result.get("copyableCode")
                if pairing_code:
                    plain_code = pairing_code.replace("-", "").replace(" ", "")
                    send_message(chat_id, f"🔑 *کد جدید - قابل کپی:*\n\n`{pairing_code}`\n\n📋 کپی: `{plain_code}`\n\nبرای شماره خودت {phone} - روی همین شماره وارد کن" if lang == "fa" else f"🔑 New code: {pairing_code} plain {plain_code} for {phone}")
                    send_message(chat_id, f"{pairing_code}\n\n👆 کپی کن")
                    send_message(chat_id, f"{plain_code}\n\n👆 بدون خط تیره")
                else:
                    # سعی کن جدا بگیری
                    try:
                        pc_resp = req_lib.get(f"{service_url}/pairing-code", params={"userId": str(chat_id), "phone": phone}, timeout=15)
                        if pc_resp.status_code == 200:
                            pc_data = pc_resp.json()
                            pc = pc_data.get("pairingCode")
                            if pc:
                                send_message(chat_id, f"🔑 کد: `{pc}`\n📋 `{pc.replace('-','')}`\nبرای {phone}" if lang == "fa" else f"Code {pc}")
                                send_message(chat_id, f"{pc}\n\n👆 کپی")
                                pairing_code = pc
                    except:
                        pass
                
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✅ بررسی اتصال" if lang == "fa" else "✅ Check", "callback_data": "check_whatsapp_status"}]
                    ]
                }
                send_message(chat_id, "QR جدید فرستاده شد! کد بالا قابل کپی است" if lang == "fa" else "New QR sent! Code copyable above", keyboard)
                set_state(chat_id, "waiting_whatsapp_qr_check", phone=phone, own_phone=phone, last_qr=qr_result.get("qr",""), pairing_code=pairing_code)
            else:
                msg = "⏳ QR در حال آماده شدن است، لطفا چند ثانیه صبر کنید" if lang == "fa" else "⏳ QR preparing, wait"
                send_message(chat_id, msg)
        except Exception as e:
            logger.error(f"❌ whatsapp_new_qr error: {e}", exc_info=True)
            send_message(chat_id, "⏳ خطا در دریافت QR، دوباره تلاش کن - شماره خودت رو درست بفرست: 98912..." if lang == "fa" else "Error getting QR")
        return

    elif callback_data == "wa_list_groups":
        lang = get_user_lang(chat_id)
        try:
            import messenger_whatsapp
            wa_cfg = user_config["messengers"].get("whatsapp", {})
            service_url = wa_cfg.get("service_url", "http://localhost:3001")
            
            sending_msg = "⏳ در حال دریافت لیست گروه‌ها..." if lang == "fa" else "⏳ Getting groups..."
            send_message(chat_id, sending_msg)
            
            chats_result = messenger_whatsapp.get_chats_for_user(chat_id, service_url)
            
            if chats_result.get("ok") and chats_result.get("chats"):
                chats = chats_result["chats"]
                msg = (
                    f"📋 *{len(chats)} گروه پیدا شد*\n\n"
                    "مقصد ارسال را انتخاب کنید:"
                    if lang == "fa"
                    else f"📋 Found {len(chats)} groups, select dest:"
                )
                send_message(chat_id, msg)
                
                keyboard = []
                for chat in chats[:15]:
                    name = chat.get("name", "Unknown")[:30]
                    chat_id_val = chat.get("id", "")
                    participants = chat.get("participants", 0)
                    btn_text = f"👥 {name} ({participants})" if participants else f"👥 {name}"
                    keyboard.append([{"text": btn_text, "callback_data": f"wa_select_dest_{chat_id_val}"}])
                
                keyboard.append([{"text": "📱 شماره شخصی", "callback_data": "wa_select_personal"}])
                keyboard.append([{"text": t(chat_id, "back_to_settings"), "callback_data": "back_to_messengers_list"}])
                
                send_message(chat_id, "👇 انتخاب کنید:", {"inline_keyboard": keyboard})
                set_state(chat_id, "waiting_whatsapp_destination", chats=chats)
            else:
                error = chats_result.get("error", "Unknown")
                msg = (
                    f"❌ خطا در دریافت گروه‌ها: {error}\n\n"
                    "ممکن است واتساپ هنوز گروه‌ها را لود نکرده\n"
                    "چند ثانیه صبر کنید و دوباره تلاش کنید\n\n"
                    "یا شماره مقصد را دستی وارد کنید: 98912..."
                    if lang == "fa"
                    else f"❌ Error getting groups: {error}"
                )
                send_message(chat_id, msg)
                set_state(chat_id, "waiting_whatsapp_destination", chats=[])
        except Exception as e:
            logger.error(f"❌ wa_list_groups error: {e}")
            send_message(chat_id, f"❌ خطا: {e}")
        return
    
    elif callback_data == "submit_messenger_selection":
        current_state_name, current_state_data = get_state(chat_id)
        selected = current_state_data.get("selected_messengers", [])

        if not selected:
            send_message(chat_id, t(chat_id, "no_messenger_selected"))
            return

        # ذخیره پست
        post_id = user_db.add_scheduled_post(
            current_state_data["media_id"],
            current_state_data["media_type"],
            current_state_data.get("caption", ""),
            "",
            current_state_data["selected_date"],
            current_state_data["selected_time"],
            "manual",
            messengers=",".join(selected)
        )

        messenger_names = {
            "bale": "🔵 Bale",
            "rubika": "🟢 Rubika",
            "eitaa": "🟡 Eitaa",
            "telegram": "✈️ Telegram",
            "whatsapp": "💚 WhatsApp"
        }
        messenger_list = "\n".join([f"  {messenger_names[m]}" for m in selected])

        display_date = format_date_for_user(chat_id, current_state_data["selected_date"])

        success_msg = t(chat_id, "post_scheduled").format(
            date=display_date,
            time=current_state_data["selected_time"],
            messengers=messenger_list
        )
        success_msg += f"\n🆔 ID: {post_id}"

        send_message(chat_id, success_msg, create_main_keyboard(chat_id))
        clear_state(chat_id)
        return
        # ========== پیش‌نویس‌ها ==========
    elif callback_data and callback_data.startswith("view_draft_"):
        draft_id = int(callback_data.replace("view_draft_", ""))
        draft = user_db.get_draft_by_id(draft_id)
        lang = get_user_lang(chat_id)

        if draft:
            draft_id_val = draft[0]
            media_type = draft[2]
            caption = draft[3]
            scheduled_date = draft[5] if len(draft) > 5 else ""
            scheduled_time = draft[6] if len(draft) > 6 else ""

            if lang == "fa":
                msg = f"📋 *پیش‌نویس #{draft_id_val}*\n\n"
                msg += f"📅 زمان‌بندی شده: {scheduled_date} ساعت {scheduled_time}\n"
                if caption:
                    preview = caption[:100] + ("..." if len(caption) > 100 else "")
                    msg += f"📝 کپشن: {preview}\n"
                else:
                    msg += "📝 کپشن: ندارد\n"
            else:
                msg = f"📋 *Draft #{draft_id_val}*\n\n"
                msg += f"📅 Scheduled: {scheduled_date} at {scheduled_time}\n"
                if caption:
                    preview = caption[:100] + ("..." if len(caption) > 100 else "")
                    msg += f"📝 Caption: {preview}\n"
                else:
                    msg += "📝 Caption: N/A\n"

            send_message(chat_id, msg)
        else:
            error_msg = (
                "❌ پیش‌نویس یافت نشد!"
                if lang == "fa"
                else "❌ Draft not found!"
            )
            send_message(chat_id, error_msg)
        return

    elif callback_data and callback_data.startswith("restore_draft_"):
        draft_id = int(callback_data.replace("restore_draft_", ""))
        user_db.restore_draft_to_scheduled(draft_id)
        lang = get_user_lang(chat_id)

        success_msg = (
            "✅ پیش‌نویس به پست‌های زمان‌بندی شده منتقل شد!"
            if lang == "fa"
            else "✅ Draft restored to scheduled posts!"
        )
        send_message(chat_id, success_msg, create_main_keyboard(chat_id))
        return

    elif callback_data and callback_data.startswith("delete_draft_"):
        draft_id = int(callback_data.replace("delete_draft_", ""))
        user_db.delete_draft_post(draft_id)
        lang = get_user_lang(chat_id)

        success_msg = (
            "🗑️ پیش‌نویس حذف شد!"
            if lang == "fa"
            else "🗑️ Draft deleted!"
        )
        send_message(chat_id, success_msg, create_main_keyboard(chat_id))
        return

    # ========== آرشیو پست‌ها ==========
    elif callback_data and callback_data.startswith("view_archived_"):
        archived_id = int(callback_data.replace("view_archived_", ""))
        lang = get_user_lang(chat_id)

        # ✅ جستجوی مستقیم به جای loop روی همه پست‌ها
        archived_posts = user_db.get_archived_posts()
        found_post = None
        for post in archived_posts:
            if post[0] == archived_id:
                found_post = post
                break

        if found_post:
            post_id = found_post[0]
            media_type = found_post[2]
            caption = found_post[3]
            scheduled_date = found_post[5] if len(found_post) > 5 else ""
            scheduled_time = found_post[6] if len(found_post) > 6 else ""
            archived_at = found_post[7] if len(found_post) > 7 else ""

            display_scheduled_date = format_date_for_user(chat_id, scheduled_date)
            display_archived_at = format_datetime_for_user(chat_id, archived_at) if archived_at else ""

            if lang == "fa":
                msg = f"🗂️ *پست آرشیو شده #{post_id}*\n\n"
                msg += f"📅 زمان‌بندی شده بود برای: {display_scheduled_date} ساعت {scheduled_time}\n"
                if caption:
                    preview = caption[:100] + ("..." if len(caption) > 100 else "")
                    msg += f"📝 کپشن: {preview}\n"
                else:
                    msg += "📝 کپشن: ندارد\n"
                msg += f"🗑️ آرشیو شده در: {display_archived_at}\n"
            else:
                msg = f"🗂️ *Archived Post #{post_id}*\n\n"
                msg += f"📅 Was scheduled for: {display_scheduled_date} at {scheduled_time}\n"
                if caption:
                    preview = caption[:100] + ("..." if len(caption) > 100 else "")
                    msg += f"📝 Caption: {preview}\n"
                else:
                    msg += "📝 Caption: N/A\n"
                msg += f"🗑️ Archived at: {display_archived_at}\n"

            send_message(chat_id, msg)
        else:
            error_msg = (
                "❌ پست یافت نشد!"
                if lang == "fa"
                else "❌ Post not found!"
            )
            send_message(chat_id, error_msg)
        return

    elif callback_data and callback_data.startswith("delete_archived_"):
        archived_id = int(callback_data.replace("delete_archived_", ""))
        user_db.delete_archived_post(archived_id)
        lang = get_user_lang(chat_id)

        success_msg = (
            "🗑️ پست آرشیو شده به طور دائم حذف شد!"
            if lang == "fa"
            else "🗑️ Archived post permanently deleted!"
        )
        send_message(chat_id, success_msg, create_main_keyboard(chat_id))
        return

    # ========== آرشیو محتوا ==========
    elif callback_data == "archive_media_list":
        archived = user_db.get_archived_media_contents()
        lang = get_user_lang(chat_id)

        if not archived:
            msg = (
                "📭 رسانه آرشیو شده‌ای وجود ندارد"
                if lang == "fa"
                else "📭 No archived media"
            )
            send_message(chat_id, msg, create_main_keyboard(chat_id))
            return

        msg = (
            "🖼️ *رسانه‌های آرشیو شده*\n\n"
            if lang == "fa"
            else "🖼️ *Archived Media*\n\n"
        )
        for content_id, media_type, file_id, title, created_at in archived:
            icon = "🖼️" if media_type == "photo" else "🎥"
            display_title = title if title else f"ID:{content_id}"
            msg += f"{icon} {display_title} - {created_at}\n"

        send_message(chat_id, msg, create_main_keyboard(chat_id))
        return

    elif callback_data == "archive_text_list":
        archived = user_db.get_archived_text_contents()
        lang = get_user_lang(chat_id)

        if not archived:
            msg = (
                "📭 متن آرشیو شده‌ای وجود ندارد"
                if lang == "fa"
                else "📭 No archived text"
            )
            send_message(chat_id, msg, create_main_keyboard(chat_id))
            return

        msg = (
            "📝 *متن‌های آرشیو شده*\n\n"
            if lang == "fa"
            else "📝 *Archived Text*\n\n"
        )
        for content_id, text_content, created_at in archived:
            preview = text_content[:30] + "..." if len(text_content) > 30 else text_content
            msg += f"ID:{content_id} - {preview}\n"

        send_message(chat_id, msg, create_main_keyboard(chat_id))
        return

    # ========== انتخاب رسانه برای پست جدید ==========
    elif callback_data == "upload_new_media_inline":
        set_state(chat_id, "awaiting_media_title_for_post", new_post=True)
        lang = get_user_lang(chat_id)
        prompt = (
            "📝 عنوان رسانه را وارد کنید:"
            if lang == "fa"
            else "📝 Enter media title:"
        )
        send_message(chat_id, prompt)
        return

    elif callback_data and callback_data.startswith("select_media_"):
        content_id = int(callback_data.replace("select_media_", ""))
        media_content = user_db.get_content_by_id(content_id)
        lang = get_user_lang(chat_id)

        if media_content:
            file_id = media_content[1]
            media_type = media_content[2]

            # ✅ حفظ state موجود و اضافه کردن اطلاعات رسانه
            current_state_name, current_state_data = get_state(chat_id)
            user_states[chat_id] = {
                **current_state_data,
                "state": "select_caption",
                "new_post": True,
                "media_id": file_id,
                "media_type": media_type,
                "content_id": content_id
            }

            keyboard = create_text_content_keyboard(chat_id, user_db)
            msg = (
                "📝 *انتخاب کپشن*\n\nاز کپشن‌های آپلود شده انتخاب کنید یا جدید بنویسید:"
                if lang == "fa"
                else "📝 *Select Caption*\n\nChoose from your uploaded captions or write new:"
            )

            if message_id:
                edit_message(chat_id, message_id, msg, keyboard)
            else:
                send_message(chat_id, msg, keyboard)
        else:
            error_msg = (
                "❌ محتوا یافت نشد!"
                if lang == "fa"
                else "❌ Content not found!"
            )
            send_message(chat_id, error_msg)
        return

    elif callback_data and callback_data.startswith("view_media_"):
        content_id = int(callback_data.replace("view_media_", ""))
        media_content = user_db.get_content_by_id(content_id)

        if media_content:
            content_id_val, file_id, media_type, title, created_at = media_content
            caption = f"🖼️ {title}\n📅 {created_at}" if title else f"📅 {created_at}"

            if media_type == "photo":
                send_photo(chat_id, file_id, caption)
            elif media_type == "video":
                send_video(chat_id, file_id, caption)
        return

    # ========== انتخاب متن برای پست جدید ==========
    elif callback_data == "write_new_caption":
        current_state_name, current_state_data = get_state(chat_id)
        lang = get_user_lang(chat_id)

        if current_state_name == "select_caption":
            user_states[chat_id]["state"] = "awaiting_manual_caption"
        else:
            user_states[chat_id] = {
                **current_state_data,
                "state": "awaiting_manual_caption",
                "new_post": True,
                "new_caption": True
            }

        prompt = (
            "✍️ کپشن خود را بنویسید:"
            if lang == "fa"
            else "✍️ Write your caption:"
        )
        send_message(chat_id, prompt)
        return

    elif callback_data and callback_data.startswith("select_text_"):
        content_id = int(callback_data.replace("select_text_", ""))
        text_content_row = user_db.get_text_content_by_id(content_id)
        lang = get_user_lang(chat_id)

        if text_content_row:
            caption_text = text_content_row[1]

            # ✅ بررسی و حفظ state موجود
            if not isinstance(user_states.get(chat_id), dict):
                user_states[chat_id] = {}

            user_states[chat_id]['caption'] = caption_text
            user_states[chat_id]['state'] = 'awaiting_date'

            year, month = get_calendar_year_month(chat_id)
            keyboard = create_calendar_keyboard(chat_id, year, month)

            if lang == "fa":
                msg = (
                    f"✅ کپشن انتخاب شد!\n\n📅 *تاریخ ارسال را انتخاب کنید*\n\n"
                    f"پیش‌نمایش کپشن:\n{caption_text[:100]}"
                    + ("..." if len(caption_text) > 100 else "")
                )
            else:
                msg = (
                    f"✅ Caption selected!\n\n📅 *Select Date for Posting*\n\n"
                    f"Caption preview:\n{caption_text[:100]}"
                    + ("..." if len(caption_text) > 100 else "")
                )

            if message_id:
                edit_message(chat_id, message_id, msg, keyboard)
            else:
                send_message(chat_id, msg, keyboard)
        else:
            error_msg = (
                "❌ محتوا یافت نشد!"
                if lang == "fa"
                else "❌ Content not found!"
            )
            send_message(chat_id, error_msg)
        return

    elif callback_data and callback_data.startswith("view_text_"):
        content_id = int(callback_data.replace("view_text_", ""))
        text_content_row = user_db.get_text_content_by_id(content_id)
        lang = get_user_lang(chat_id)

        if text_content_row:
            caption_text = text_content_row[1]
            preview_msg = (
                f"📝 *پیش‌نمایش کپشن:*\n\n{caption_text}"
                if lang == "fa"
                else f"📝 *Caption Preview:*\n\n{caption_text}"
            )
            send_message(chat_id, preview_msg)
        return

    # ========== ناوبری تقویم ==========
    elif callback_data and callback_data.startswith("cal_"):
        parts = callback_data.split("_")
        year, month = int(parts[1]), int(parts[2])
        keyboard = create_calendar_keyboard(chat_id, year, month)

        current_state_name, current_state_data = get_state(chat_id)
        lang = get_user_lang(chat_id)

        if current_state_name == "editing_time_date":
            msg = (
                "📅 *ویرایش زمان‌بندی*\n\nتاریخ جدید را انتخاب کنید:"
                if lang == "fa"
                else "📅 *Edit Schedule*\n\nSelect the new date:"
            )
        else:
            msg = (
                "✍️ *پست جدید*\n\nتاریخ ارسال را انتخاب کنید:"
                if lang == "fa"
                else "✍️ *New Post*\n\nSelect the date for posting:"
            )

        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    # ========== انتخاب تاریخ ==========
    elif callback_data and callback_data.startswith("date_"):
        selected_date = callback_data.replace("date_", "")
        current_state_name, current_state_data = get_state(chat_id)
        lang = get_user_lang(chat_id)

        if current_state_name == "editing_time_date":
            user_states[chat_id]["selected_date"] = selected_date
            user_states[chat_id]["state"] = "editing_time_time"

            display_date = format_date_for_user(chat_id, selected_date)

            msg = (
                f"📅 تاریخ: {display_date}\n\n⏰ اکنون ساعت را ارسال کنید (فرمت HH:MM):\nمثال: 14:30"
                if lang == "fa"
                else f"📅 Date: {display_date}\n\n⏰ Now send the time (HH:MM format):\nExample: 14:30"
            )
            send_message(chat_id, msg)

        elif current_state_name == "awaiting_date":
            user_states[chat_id]["selected_date"] = selected_date
            user_states[chat_id]["state"] = "awaiting_manual_time"

            msg = (
                f"⏰ زمان ارسال را بفرستید (فرمت HH:MM)\nمثال: 14:30"
                if lang == "fa"
                else f"⏰ Send posting time (HH:MM format)\nExample: 14:30"
            )
            send_message(chat_id, msg)
        return
    

    # ========== ورود دستی تاریخ ==========
    elif callback_data == "manual_date_input":
        current_state_name, current_state_data = get_state(chat_id)
        lang = get_user_lang(chat_id)

        # حفظ state موجود و تغییر مرحله
        if isinstance(user_states.get(chat_id), dict):
            user_states[chat_id]["state"] = "awaiting_manual_date_text"
        else:
            user_states[chat_id] = {"state": "awaiting_manual_date_text"}

        if lang == "fa":
            msg = (
                "📝 *ورود دستی تاریخ شمسی*\n\n"
                "تاریخ را به یکی از فرمت‌های زیر ارسال کنید:\n\n"
                "• `1404/5/17`\n"
                "• `404/5/17`\n"
                "• `04/05/17`\n"
                "• `04/5/17`\n\n"
                "⚠️ تاریخ نباید در گذشته باشد."
            )
        else:
            msg = (
                "📝 *Manual Date Entry*\n\n"
                "Send the date in one of these formats:\n\n"
                "• `2025/7/15`\n"
                "• `2025-07-15`\n"
                "• `25/7/15`\n\n"
                "⚠️ Date must not be in the past."
            )

        send_message(chat_id, msg)
        return

    elif callback_data == "ignore":
        return

    # ========== ویرایش پست ==========
    elif callback_data and callback_data.startswith("edit_media_"):
        post_id = int(callback_data.replace("edit_media_", ""))
        set_state(chat_id, "editing_media", post_id=post_id)
        lang = get_user_lang(chat_id)
        prompt = (
            "📸 عکس یا ویدیوی جدید را ارسال کنید:"
            if lang == "fa"
            else "📸 Send new photo or video:"
        )
        send_message(chat_id, prompt)
        return

    elif callback_data and callback_data.startswith("edit_caption_"):
        post_id = int(callback_data.replace("edit_caption_", ""))
        set_state(chat_id, "editing_caption", post_id=post_id)
        lang = get_user_lang(chat_id)
        prompt = (
            "✍️ کپشن جدید را ارسال کنید:"
            if lang == "fa"
            else "✍️ Send new caption:"
        )
        send_message(chat_id, prompt)
        return

    elif callback_data and callback_data.startswith("edit_time_"):
        post_id = int(callback_data.replace("edit_time_", ""))
        lang = get_user_lang(chat_id)

        post = user_db.get_post_by_id(post_id)
        if post:
            current_date = post[5] if len(post) > 5 else ""
            year, month = get_calendar_year_month(chat_id, current_date)
        else:
            year, month = get_calendar_year_month(chat_id)

        set_state(chat_id, "editing_time_date", post_id=post_id, state_before_date="editing_time_date")
        keyboard = create_calendar_keyboard(chat_id, year, month)

        msg = (
            "📅 *ویرایش زمان‌بندی*\n\nابتدا تاریخ جدید را انتخاب کنید:"
            if lang == "fa"
            else "📅 *Edit Schedule*\n\nFirst, select the new date:"
        )

        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return
    
    elif callback_data and callback_data.startswith("edit_all_"):
        post_id = int(callback_data.replace("edit_all_", ""))
        lang = get_user_lang(chat_id)

        # ✅ ذخیره post_id و شروع از مرحله انتخاب رسانه
        set_state(chat_id, "edit_all_select_media", post_id=post_id)

        keyboard = create_media_content_keyboard(chat_id, user_db)
        msg = (
            f"🔄 *ویرایش کامل پست #{post_id}*\n\n"
            f"🖼️ مرحله 1/4: رسانه مورد نظر را انتخاب کنید:"
            if lang == "fa"
            else f"🔄 *Edit All - Post #{post_id}*\n\n"
                f"🖼️ Step 1/4: Select media:"
        )

        if message_id:
            edit_message(chat_id, message_id, msg, keyboard)
        else:
            send_message(chat_id, msg, keyboard)
        return

    elif callback_data and callback_data.startswith("delete_post_"):
        post_id = int(callback_data.replace("delete_post_", ""))
        user_db.delete_scheduled_post(post_id)
        lang = get_user_lang(chat_id)

        success_msg = (
            "📋 پست به آرشیو منتقل شد!"
            if lang == "fa"
            else "📋 Post moved to archive!"
        )
        send_message(chat_id, success_msg, create_main_keyboard(chat_id))
        return

    elif callback_data and callback_data.startswith("save_draft_"):
        post_id = int(callback_data.replace("save_draft_", ""))
        post = user_db.get_post_by_id(post_id)
        lang = get_user_lang(chat_id)

        if post:
            p_id = post[0]
            media_path = post[1]
            media_type = post[2]
            caption = post[3]
            hashtags = post[4]
            scheduled_date = post[5]
            scheduled_time = post[6]
            messengers_val = post[8] if len(post) > 8 else 'all'

            user_db.add_draft_post(
                media_path, media_type, caption, hashtags,
                scheduled_date, scheduled_time, messengers_val
            )
            user_db.delete_scheduled_post(p_id)

            success_msg = (
                "📋 پست به عنوان پیش‌نویس ذخیره شد!"
                if lang == "fa"
                else "📋 Post saved as draft!"
            )
            send_message(chat_id, success_msg, create_main_keyboard(chat_id))
        return

    # ========== پیکربندی پیام‌رسان‌ها ==========
    elif "Bale" in text:
        lang = get_user_lang(chat_id)
        prompt = (
            "🤖 توکن ربات Bale خود را ارسال کنید:"
            if lang == "fa"
            else "🤖 Send your Bale bot token:"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": t(chat_id, "learn_how"), "callback_data": "help_bale"}]
            ]
        }
        send_message(chat_id, prompt, keyboard)
        set_state(chat_id, "waiting_bale_token")
        return

    elif "Rubika" in text:
        lang = get_user_lang(chat_id)
        prompt = (
            "🤖 توکن ربات Rubika خود را ارسال کنید:"
            if lang == "fa"
            else "🤖 Send your Rubika bot token:"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": t(chat_id, "learn_how"), "callback_data": "help_rubika"}]
            ]
        }
        send_message(chat_id, prompt, keyboard)
        set_state(chat_id, "waiting_rubika_token")
        return

    elif "Eitaa" in text:
        lang = get_user_lang(chat_id)
        prompt = (
            "🤖 توکن ربات Eitaa خود را ارسال کنید:"
            if lang == "fa"
            else "🤖 Send your Eitaa bot token:"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": t(chat_id, "learn_how"), "callback_data": "help_eitaa"}]
            ]
        }
        send_message(chat_id, prompt, keyboard)
        set_state(chat_id, "waiting_eitaa_token")
        return

    elif "Telegram" in text:
        lang = get_user_lang(chat_id)
        prompt = (
            "✈️ توکن ربات Telegram خود را ارسال کنید:\n"
            "از @BotFather بگیرید\n"
            "مثال: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
            if lang == "fa"
            else "✈️ Send your Telegram bot token:\n"
            "Get from @BotFather\n"
            "Example: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": t(chat_id, "learn_how"), "callback_data": "help_telegram"}]
            ]
        }
        send_message(chat_id, prompt, keyboard)
        set_state(chat_id, "waiting_telegram_token")
        return

    elif "WhatsApp" in text:
        lang = get_user_lang(chat_id)
        wa_cfg = user_config["messengers"].get("whatsapp", {})
        current = wa_cfg.get("chat_id", "")
        is_connected = False
        dest_selected = wa_cfg.get("destination_selected", False)
        
        try:
            import messenger_whatsapp
            status = messenger_whatsapp.check_connection_status(chat_id, wa_cfg.get("service_url", "http://localhost:3001"))
            is_connected = status.get("connected", False)
        except:
            pass
        
        if lang == "fa":
            if current and is_connected and dest_selected:
                # کاملا ستاپ شده: متصل + مقصد انتخاب شده -> ✅
                prompt = (
                    f"💚 *WhatsApp کاملا متصل است* ✅\n\n"
                    f"📱 مقصد: {current}\n"
                    f"🔗 وضعیت: متصل + مقصد ✅\n\n"
                    "همه چیز آماده است!\n"
                    "برای تغییر مقصد، گروه‌ها را لیست کن:\n"
                    "بنویسید `groups` یا `لیست`\n\n"
                    "برای تغییر شماره: شماره جدید\n"
                    "برای قطع: `logout`"
                )
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📋 لیست گروه‌ها", "callback_data": "wa_list_groups"}],
                        [{"text": t(chat_id, "learn_how"), "callback_data": "help_whatsapp"}]
                    ]
                }
            elif current and is_connected and not dest_selected:
                # متصل ولی مقصد انتخاب نشده -> ⚪
                prompt = (
                    f"💚 *WhatsApp متصل ولی مقصد انتخاب نشده* ⚪\n\n"
                    f"📱 شماره: {current}\n"
                    f"🔗 وضعیت: متصل ولی مقصد ⚪\n\n"
                    "⚠️ تا مقصد انتخاب نشود تیک سبز نمی‌خورد\n\n"
                    "برای انتخاب مقصد:\n"
                    "بنویسید `groups` تا گروه‌ها لیست شود\n"
                    "یا شماره مقصد را ارسال کنید: 98912..."
                )
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📋 لیست گروه‌ها", "callback_data": "wa_list_groups"}],
                        [{"text": t(chat_id, "learn_how"), "callback_data": "help_whatsapp"}]
                    ]
                }
            elif current and not is_connected:
                prompt = (
                    f"💚 *WhatsApp*\n\n"
                    f"📱 شماره فعلی: {current}\n"
                    f"🔗 وضعیت: قطع ⚪ (تیک سبز ندارد)\n\n"
                    "برای اتصال مجدد، شماره را ارسال کنید:\n"
                    "مثال: 989123456789\n\n"
                    "یا بنویسید `qr` برای دریافت QR جدید"
                )
                keyboard = {
                    "inline_keyboard": [
                        [{"text": t(chat_id, "learn_how"), "callback_data": "help_whatsapp"}]
                    ]
                }
            else:
                prompt = (
                    "💚 *اتصال WhatsApp - فوق ساده*\n\n"
                    "فقط شماره واتساپ خود را ارسال کنید:\n\n"
                    "📱 مثال: 989123456789\n"
                    "یا 989123456789@s.whatsapp.net\n\n"
                    "بعد از ارسال شماره، یک QR کد + کد 8 رقمی برای شما ارسال می‌شود\n"
                    "آن را با واتساپ اسکن کنید یا کد را وارد کنید\n\n"
                    "✨ حتی یک غیر برنامه‌نویس هم می‌تواند وصل کند!\n\n"
                    "⚠️ تیک سبز فقط وقتی می‌خورد که متصل + مقصد انتخاب شده باشد"
                )
                keyboard = {
                    "inline_keyboard": [
                        [{"text": t(chat_id, "learn_how"), "callback_data": "help_whatsapp"}]
                    ]
                }
        else:
            if current and is_connected and dest_selected:
                prompt = f"💚 *WhatsApp Fully Connected* ✅\n\n📱 Dest: {current}\nStatus: Connected + Dest ✅\n\nReady!"
                keyboard = {"inline_keyboard": [[{"text": "📋 List Groups", "callback_data": "wa_list_groups"}]]}
            elif current and is_connected:
                prompt = f"💚 *WhatsApp Connected but no dest* ⚪\n\n📱 {current}\nStatus: Connected but no dest - no green tick\n\nType groups to list"
                keyboard = {"inline_keyboard": [[{"text": "📋 List Groups", "callback_data": "wa_list_groups"}]]}
            elif current:
                prompt = f"💚 *WhatsApp*\n\n📱 Current: {current}\nStatus: Disconnected ⚪\n\nSend number or qr"
                keyboard = {"inline_keyboard": [[{"text": t(chat_id, "learn_how"), "callback_data": "help_whatsapp"}]]}
            else:
                prompt = "💚 *WhatsApp Setup*\n\nSend number: 989123456789\n\nGreen tick only when connected + dest selected"
                keyboard = {"inline_keyboard": [[{"text": t(chat_id, "learn_how"), "callback_data": "help_whatsapp"}]]}
        
        send_message(chat_id, prompt, keyboard)
        set_state(chat_id, "waiting_whatsapp_chat")
        return

    elif text == t(chat_id, "woocommerce_api"):
        lang = get_user_lang(chat_id)
        prompt = (
            "🛒 آدرس WooCommerce خود را ارسال کنید:\nمثال: https://yoursite.com"
            if lang == "fa"
            else "🛒 Send your WooCommerce URL:\nExample: https://yoursite.com"
        )
        send_message(chat_id, prompt)
        set_state(chat_id, "waiting_wc_url")
        return

    # ========== مدیریت state های کاربر ==========
    elif chat_id in user_states:
        current_state_name, current_state_data = get_state(chat_id)
        lang = get_user_lang(chat_id)

        # ===== اضافه کردن ادمین جدید =====
        if current_state_name == "awaiting_new_admin_id":
            try:
                new_admin_id = int(text)

                user_info_check = auth_manager.get_user_info(new_admin_id)
                if not user_info_check:
                    send_message(chat_id, t(chat_id, "user_not_found"), create_admin_menu_keyboard(chat_id))
                    clear_state(chat_id)
                    return

                if auth_manager.is_admin(new_admin_id):
                    send_message(chat_id, t(chat_id, "user_already_admin"), create_admin_menu_keyboard(chat_id))
                    clear_state(chat_id)
                    return

                result = auth_manager.add_admin(
                    new_admin_id,
                    user_info_check['username'] or f"User{new_admin_id}",
                    chat_id,
                    is_super_admin=False
                )

                if result['success']:
                    send_message(chat_id, t(chat_id, "admin_added_success"), create_admin_menu_keyboard(chat_id))

                    admin_lang = get_user_lang(new_admin_id)
                    if admin_lang == "fa":
                        admin_msg = "👮 شما به عنوان ادمین اضافه شدید! می‌توانید اکنون درخواست‌های دسترسی را مدیریت کنید."
                    else:
                        admin_msg = "👮 You have been added as an admin! You can now manage access requests."

                    send_message(new_admin_id, admin_msg, create_main_keyboard(new_admin_id))
                else:
                    error_msg = result.get('error', "خطای نامشخص")
                    send_message(chat_id, f"❌ {error_msg}", create_admin_menu_keyboard(chat_id))

                clear_state(chat_id)

            except ValueError:
                error_msg = (
                    "❌ لطفاً یک شناسه معتبر وارد کنید"
                    if lang == "fa"
                    else "❌ Please enter a valid ID"
                )
                send_message(chat_id, error_msg)
            return

        # ===== حذف ادمین =====
        elif current_state_name == "awaiting_remove_admin_id":
            try:
                admin_id = int(text)

                admin_info_check = auth_manager.get_admin_info(admin_id)
                if not admin_info_check:
                    send_message(chat_id, t(chat_id, "user_not_found"), create_admin_menu_keyboard(chat_id))
                    clear_state(chat_id)
                    return

                result = auth_manager.remove_admin(admin_id, chat_id)

                if result['success']:
                    send_message(chat_id, t(chat_id, "admin_removed_success"), create_admin_menu_keyboard(chat_id))

                    removed_lang = get_user_lang(admin_id)
                    removed_msg = (
                        "❌ شما دیگر ادمین نیستید."
                        if removed_lang == "fa"
                        else "❌ You are no longer an admin."
                    )
                    send_message(admin_id, removed_msg, create_main_keyboard(admin_id))
                else:
                    error_msg = result.get('error', "خطای نامشخص")
                    send_message(chat_id, f"❌ {error_msg}", create_admin_menu_keyboard(chat_id))

                clear_state(chat_id)

            except ValueError:
                error_msg = (
                    "❌ لطفاً یک شناسه معتبر وارد کنید"
                    if lang == "fa"
                    else "❌ Please enter a valid ID"
                )
                send_message(chat_id, error_msg)
            return

        # ===== دلیل رد کردن درخواست =====
        elif current_state_name == "awaiting_reject_reason":
            request_id = current_state_data.get('request_id')
            result = auth_manager.reject_request(request_id, chat_id, text)

            if result['success']:
                # ✅ پیام موفقیت به ادمین
                msg = (
                    "✅ درخواست رد شد!"
                    if lang == "fa"
                    else "✅ Request rejected!"
                )
                send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))

                # ✅ ارسال پیام رد شدن به کاربر با دلیل
                rejected_chat_id = result.get('user_chat_id')
                if rejected_chat_id:
                    user_lang = get_user_lang(rejected_chat_id)
                    if user_lang == "fa":
                        user_msg = (
                            f"❌ *درخواست دسترسی شما رد شد*\n\n"
                            f"📝 دلیل:\n{text}\n\n"
                            f"می‌توانید از طریق خرید دسترسی، اشتراک تهیه کنید:"
                        )
                    else:
                        user_msg = (
                            f"❌ *Your access request was rejected*\n\n"
                            f"📝 Reason:\n{text}\n\n"
                            f"You can purchase access to use the bot:"
                        )

                    buy_keyboard = {
                        "inline_keyboard": [
                            [{"text": "💳 خرید دسترسی" if user_lang == "fa" else "💳 Buy Access",
                            "callback_data": "auth_buy_access"}]
                        ]
                    }
                    send_message(rejected_chat_id, user_msg, buy_keyboard)
            else:
                error_msg = result.get('error', "خطای نامشخص")
                send_message(chat_id, f"❌ {error_msg}", create_admin_menu_keyboard(chat_id))

            clear_state(chat_id)
            return
        # ===== جستجو در رسانه‌ها =====
        elif current_state_name == "awaiting_search_query":
            search_query = text.strip().lower() if text else ""
            results = user_db.search_media_by_title(search_query)

            if not results:
                send_message(chat_id, t(chat_id, "no_results_found"))
                keyboard = create_media_content_keyboard(chat_id, user_db)
                msg = (
                    "📸 *انتخاب رسانه*"
                    if lang == "fa"
                    else "📸 *Select Media*"
                )
                send_message(chat_id, msg, keyboard)
                clear_state(chat_id)
                return

            keyboard_rows = []
            for content_id, media_type, file_id, title, created_at in results:
                icon = "🖼️" if media_type == "photo" else "🎥"
                display_title = title if title else f"ID:{content_id}"
                button_text = f"{icon} {display_title}"
                keyboard_rows.append([
                    {"text": button_text, "callback_data": f"select_media_{content_id}"},
                    {"text": "👁️", "callback_data": f"view_media_{content_id}"}
                ])

            keyboard_rows.append([{"text": t(chat_id, "back_to_main"), "callback_data": "main_menu"}])

            msg = (
                f"🔍 *نتایج جستجو برای: {text}*\n\n{len(results)} نتیجه یافت شد:"
                if lang == "fa"
                else f"🔍 *Search Results for: {text}*\n\n{len(results)} result(s) found:"
            )
            send_message(chat_id, msg, {"inline_keyboard": keyboard_rows})
            clear_state(chat_id)
            return

        # ===== آپلود رسانه - عنوان =====
        elif current_state_name == "awaiting_media_title":
            title = text.strip() if text else ""

            if user_db.check_title_exists(title):
                send_message(chat_id, t(chat_id, "title_exists"))
                return

            user_states[chat_id]['title'] = title
            user_states[chat_id]['state'] = 'awaiting_media_file'

            prompt = (
                "📤 اکنون رسانه (عکس یا ویدیو) را ارسال کنید:"
                if lang == "fa"
                else "📤 Now send the media (photo or video):"
            )
            send_message(chat_id, prompt)
            return

        # ===== آپلود رسانه - فایل =====
        elif current_state_name == "awaiting_media_file":
            if message.get("photo"):
                file_id = message["photo"][-1]["file_id"]
                media_type = "photo"
            elif message.get("video"):
                file_id = message["video"]["file_id"]
                media_type = "video"
            else:
                error_msg = (
                    "❌ لطفاً یک عکس یا ویدیو ارسال کنید."
                    if lang == "fa"
                    else "❌ Please send a photo or video."
                )
                send_message(chat_id, error_msg)
                return

            title = current_state_data.get('title')
            content_id = user_db.add_media_content(file_id, media_type, title)

            success_msg = (
                f"✅ رسانه با عنوان '{title}' ذخیره شد!\n🆔 ID: {content_id}"
                if lang == "fa"
                else f"✅ Media saved with title '{title}'!\n🆔 ID: {content_id}"
            )
            send_message(chat_id, success_msg)

            keyboard = create_contents_keyboard(chat_id)
            msg = (
                "📂 *مدیریت محتوا*"
                if lang == "fa"
                else "📂 *Contents Management*"
            )
            send_message(chat_id, msg, keyboard)
            clear_state(chat_id)
            return

        # ===== آپلود متن =====
        elif current_state_name == "awaiting_text_content":
            if text and text.strip():
                content_id = user_db.add_text_content(text.strip())

                success_msg = (
                    f"✅ متن ذخیره شد!\n🆔 ID: {content_id}"
                    if lang == "fa"
                    else f"✅ Text saved!\n🆔 ID: {content_id}"
                )
                send_message(chat_id, success_msg)

                keyboard = create_contents_keyboard(chat_id)
                msg = (
                    "📂 *مدیریت محتوا*"
                    if lang == "fa"
                    else "📂 *Contents Management*"
                )
                send_message(chat_id, msg, keyboard)
                clear_state(chat_id)
            else:
                error_msg = (
                    "❌ لطفاً یک پیام متنی معتبر ارسال کنید."
                    if lang == "fa"
                    else "❌ Please send a valid text message."
                )
                send_message(chat_id, error_msg)
            return

                # ===== ورود دستی تاریخ =====
        elif current_state_name == "awaiting_manual_date_text":
            text_input = text.strip() if text else ""

            g_date_str, display_date = parse_date_input(chat_id, text_input)

            if not g_date_str:
                if lang == "fa":
                    error_msg = (
                        "❌ تاریخ نامعتبر!\n\n"
                        "لطفاً به فرمت صحیح ارسال کنید:\n"
                        "• `1404/5/17`\n"
                        "• `404/5/17`\n"
                        "• `04/05/17`\n\n"
                        "⚠️ تاریخ نباید در گذشته باشد."
                    )
                else:
                    error_msg = (
                        "❌ Invalid date!\n\n"
                        "Please send in correct format:\n"
                        "• `2025/7/15`\n"
                        "• `2025-07-15`\n\n"
                        "⚠️ Date must not be in the past."
                    )
                send_message(chat_id, error_msg)
                return

            # ✅ تاریخ معتبر - ذخیره و رفتن به مرحله بعد
            user_states[chat_id]["selected_date"] = g_date_str

            # بررسی اینکه از کجا آمده
            if current_state_data.get("state_before_date") == "editing_time_date" or \
               current_state_data.get("post_id") and not current_state_data.get("new_post"):
                # ویرایش زمان پست
                user_states[chat_id]["state"] = "editing_time_time"

                msg = (
                    f"📅 تاریخ: {display_date}\n\n⏰ اکنون ساعت را ارسال کنید (فرمت HH:MM):\nمثال: 14:30"
                    if lang == "fa"
                    else f"📅 Date: {display_date}\n\n⏰ Now send the time (HH:MM format):\nExample: 14:30"
                )
            else:
                # پست جدید
                user_states[chat_id]["state"] = "awaiting_manual_time"

                msg = (
                    f"✅ تاریخ: {display_date}\n\n⏰ زمان ارسال را بفرستید (فرمت HH:MM)\nمثال: 14:30"
                    if lang == "fa"
                    else f"✅ Date: {display_date}\n\n⏰ Send posting time (HH:MM format)\nExample: 14:30"
                )

            send_message(chat_id, msg)
            return

        # ===== پست جدید - عنوان رسانه =====
        elif current_state_name == "awaiting_media_title_for_post":
            title = text.strip() if text else ""

            if user_db.check_title_exists(title):
                send_message(chat_id, t(chat_id, "title_exists"))
                return

            user_states[chat_id]['title'] = title
            user_states[chat_id]['state'] = 'awaiting_media_file_for_post'

            prompt = (
                "📤 اکنون رسانه (عکس یا ویدیو) را ارسال کنید:"
                if lang == "fa"
                else "📤 Now send the media (photo or video):"
            )
            send_message(chat_id, prompt)
            return

        # ===== پست جدید - فایل رسانه =====
        elif current_state_name == "awaiting_media_file_for_post":
            if message.get("photo"):
                file_id = message["photo"][-1]["file_id"]
                media_type = "photo"
            elif message.get("video"):
                file_id = message["video"]["file_id"]
                media_type = "video"
            else:
                error_msg = (
                    "❌ لطفاً یک عکس یا ویدیو ارسال کنید."
                    if lang == "fa"
                    else "❌ Please send a photo or video."
                )
                send_message(chat_id, error_msg)
                return

            title = current_state_data.get('title')
            content_id = user_db.add_media_content(file_id, media_type, title)

            user_states[chat_id]["media_id"] = file_id
            user_states[chat_id]["media_type"] = media_type
            user_states[chat_id]["content_id"] = content_id
            user_states[chat_id]["state"] = "select_caption"

            keyboard = create_text_content_keyboard(chat_id, user_db)

            if lang == "fa":
                msg = (
                    f"✅ رسانه با عنوان '{title}' ذخیره شد!\n\n"
                    f"📝 *انتخاب کپشن*\n\nاز کپشن‌های آپلود شده انتخاب کنید یا جدید بنویسید:"
                )
            else:
                msg = (
                    f"✅ Media saved with title '{title}'!\n\n"
                    f"📝 *Select Caption*\n\nChoose from your uploaded captions or write new:"
                )

            send_message(chat_id, msg, keyboard)
            return

        # ===== پست جدید - کپشن دستی =====
        elif current_state_name == "awaiting_manual_caption":
            user_states[chat_id]["caption"] = text

            if current_state_data.get("new_caption"):
                caption_id = user_db.add_text_content(text)
                user_states[chat_id]["caption_id"] = caption_id

            user_states[chat_id]["state"] = "awaiting_date"

            year, month = get_calendar_year_month(chat_id)
            keyboard = create_calendar_keyboard(chat_id, year, month)

            msg = (
                "✅ کپشن ذخیره شد!\n\n📅 *تاریخ ارسال را انتخاب کنید*"
                if lang == "fa"
                else "✅ Caption saved!\n\n📅 *Select Date for Posting*"
            )
            send_message(chat_id, msg, keyboard)
            return

        # ===== پست جدید - زمان =====
        elif current_state_name == "awaiting_manual_time":
            text_clean = text.strip() if text else ""

            if re.match(r"^\d{1,2}:\d{2}$", text_clean):
                try:
                    parts = text_clean.split(":")
                    h, m = int(parts[0]), int(parts[1])

                    if 0 <= h <= 23 and 0 <= m <= 59:
                        formatted_time = f"{h:02d}:{m:02d}"
                        user_states[chat_id]["selected_time"] = formatted_time
                        user_states[chat_id]["state"] = "select_messengers"

                        keyboard = create_messenger_selection_keyboard(chat_id, user_config)
                        send_message(chat_id, t(chat_id, "select_messengers"), keyboard)
                        return
                    else:
                        error_msg = (
                            "❌ زمان نامعتبر. ساعت باید 0-23 و دقیقه 0-59 باشد."
                            if lang == "fa"
                            else "❌ Invalid time. Hour must be 0-23, minute 0-59."
                        )
                        send_message(chat_id, error_msg)
                        return
                except Exception as e:
                    send_message(chat_id, f"❌ خطا: {str(e)}")
                    return
            else:
                error_msg = (
                    "❌ فرمت نامعتبر. لطفاً زمان را به صورت HH:MM ارسال کنید (مثال: 09:30 یا 14:00)"
                    if lang == "fa"
                    else "❌ Invalid format. Please send time as HH:MM (e.g., 09:30 or 14:00)"
                )
                send_message(chat_id, error_msg)
                return

        # ===== زمان‌بندی روزها - ورودی ساعت‌ها =====
        elif current_state_name == "awaiting_day_times":
            day_name = current_state_data.get("day")
            times_input = text.strip() if text else ""

            # ✅ پردازش ساعت‌ها - بدون تداخل با تابع t()
            time_parts = [time_str.strip() for time_str in times_input.split(",")]

            valid_times = []
            has_error = False

            for time_str in time_parts:
                if re.match(r"^\d{1,2}:\d{2}$", time_str):
                    try:
                        h_str, m_str = time_str.split(":")
                        h, m = int(h_str), int(m_str)
                        if 0 <= h <= 23 and 0 <= m <= 59:
                            valid_times.append(f"{h:02d}:{m:02d}")
                        else:
                            has_error = True
                            break
                    except Exception:
                        has_error = True
                        break
                else:
                    has_error = True
                    break

            if has_error or not valid_times:
                send_message(chat_id, t(chat_id, "invalid_time_format"))
                return

            days_map_fa = {
                "saturday": "شنبه", "sunday": "یکشنبه", "monday": "دوشنبه",
                "tuesday": "سه‌شنبه", "wednesday": "چهارشنبه",
                "thursday": "پنج‌شنبه", "friday": "جمعه"
            }
            days_map_en = {
                "saturday": "Saturday", "sunday": "Sunday", "monday": "Monday",
                "tuesday": "Tuesday", "wednesday": "Wednesday",
                "thursday": "Thursday", "friday": "Friday"
            }

            day_display = (
                days_map_fa.get(day_name, day_name)
                if lang == "fa"
                else days_map_en.get(day_name, day_name)
            )

            user_config["auto_post"]["schedule"][day_name]["enabled"] = True
            user_config["auto_post"]["schedule"][day_name]["times"] = valid_times
            save_user_config(chat_id, user_config)

            times_str = ", ".join(valid_times)
            msg = t(chat_id, "schedule_saved").format(day=day_display, times=times_str)
            send_message(chat_id, msg)

            msg2 = (
                "📅 *زمان‌بندی روزها*"
                if lang == "fa"
                else "📅 *Schedule Days*"
            )
            keyboard = create_days_keyboard(chat_id, user_config)
            send_message(chat_id, msg2, keyboard)
            clear_state(chat_id)
            return

        # ===== ویرایش رسانه =====
        elif current_state_name == "editing_media":
            if message.get("photo"):
                file_id = message["photo"][-1]["file_id"]
                media_type = "photo"
            elif message.get("video"):
                file_id = message["video"]["file_id"]
                media_type = "video"
            else:
                error_msg = (
                    "❌ لطفاً یک عکس یا ویدیو ارسال کنید."
                    if lang == "fa"
                    else "❌ Please send a photo or video."
                )
                send_message(chat_id, error_msg)
                return

            user_db.update_post_media(current_state_data["post_id"], file_id, media_type)

            success_msg = (
                "✅ رسانه با موفقیت به‌روزرسانی شد!"
                if lang == "fa"
                else "✅ Media updated successfully!"
            )
            send_message(chat_id, success_msg, create_main_keyboard(chat_id))
            clear_state(chat_id)
            return

        # ===== ویرایش کپشن =====
        elif current_state_name == "editing_caption":
            user_db.update_post_caption(current_state_data["post_id"], text, "")

            success_msg = (
                "✅ کپشن با موفقیت به‌روزرسانی شد!"
                if lang == "fa"
                else "✅ Caption updated successfully!"
            )
            send_message(chat_id, success_msg, create_main_keyboard(chat_id))
            clear_state(chat_id)
            return

        # ===== ویرایش زمان - ورودی زمان =====
        elif current_state_name == "editing_time_time":
            text_clean = text.strip() if text else ""

            if not text_clean:
                error_msg = (
                    "❌ لطفاً یک زمان معتبر ارسال کنید."
                    if lang == "fa"
                    else "❌ Please send a valid time."
                )
                send_message(chat_id, error_msg)
                return

            if re.match(r"^\d{1,2}:\d{2}$", text_clean):
                try:
                    parts = text_clean.split(":")
                    h, m = int(parts[0]), int(parts[1])

                    if 0 <= h <= 23 and 0 <= m <= 59:
                        formatted_time = f"{h:02d}:{m:02d}"
                        selected_date = current_state_data["selected_date"]

                        user_db.update_post_datetime(
                            current_state_data["post_id"],
                            selected_date,
                            formatted_time
                        )

                        display_date = format_date_for_user(chat_id, selected_date)

                        if lang == "fa":
                            msg = f"✅ زمان‌بندی به‌روزرسانی شد!\n📅 {display_date} ساعت {formatted_time}"
                        else:
                            msg = f"✅ Schedule updated!\n📅 {display_date} at {formatted_time}"

                        send_message(chat_id, msg, create_main_keyboard(chat_id))
                        clear_state(chat_id)
                        return
                    else:
                        error_msg = (
                            "❌ زمان نامعتبر. ساعت باید 0-23 و دقیقه 0-59 باشد."
                            if lang == "fa"
                            else "❌ Invalid time. Hour must be 0-23, minute 0-59."
                        )
                        send_message(chat_id, error_msg)
                        return
                except Exception as e:
                    send_message(chat_id, f"❌ خطا: {str(e)}")
                    return
            else:
                error_msg = (
                    "❌ فرمت نامعتبر. لطفاً زمان را به صورت HH:MM ارسال کنید (مثال: 09:30 یا 14:00)"
                    if lang == "fa"
                    else "❌ Invalid format. Please send time as HH:MM (e.g., 09:30 or 14:00)"
                )
                send_message(chat_id, error_msg)
                return

        # ===== فیلتر دسته‌بندی =====
        elif current_state_name == "waiting_category_filter":
            input_text = text.strip() if text else ""
            lang = get_user_lang(chat_id)
            
            if input_text.lower() in ["all", "همه", "همه دسته‌ها", "clear", "پاک"]:
                user_config["auto_post"]["categories"] = []
                save_user_config(chat_id, user_config)
                send_message(chat_id, t(chat_id, "category_cleared"), create_autopost_keyboard(chat_id, user_config))
                clear_state(chat_id)
                return
            
            # پردازش ورودی: می‌تواند ID عددی یا slug باشد
            parts = [p.strip() for p in input_text.split(",") if p.strip()]
            categories = []
            for p in parts:
                # اگر عدد است
                if p.isdigit():
                    categories.append(int(p))
                else:
                    categories.append(p)
            
            user_config["auto_post"]["categories"] = categories
            save_user_config(chat_id, user_config)
            
            cats_str = ", ".join([str(c) for c in categories])
            msg = t(chat_id, "category_selected").format(cats=cats_str)
            send_message(chat_id, msg, create_autopost_keyboard(chat_id, user_config))
            clear_state(chat_id)
            return

        # ===== تعداد پست در روز =====
        elif current_state_name == "waiting_posts_per_day":
            try:
                num = int(text)
                if 1 <= num <= 10:
                    user_config["auto_post"]["posts_per_day"] = num
                    save_user_config(chat_id, user_config)

                    msg = (
                        f"✅ به {num} پست در روز تنظیم شد"
                        if lang == "fa"
                        else f"✅ Set to {num} posts per day"
                    )
                    send_message(chat_id, msg, create_autopost_keyboard(chat_id, user_config))
                    clear_state(chat_id)
                else:
                    error_msg = (
                        "❌ لطفاً عددی بین 1-10 ارسال کنید"
                        if lang == "fa"
                        else "❌ Please send a number between 1-10"
                    )
                    send_message(chat_id, error_msg)
            except Exception:
                error_msg = (
                    "❌ عدد نامعتبر"
                    if lang == "fa"
                    else "❌ Invalid number"
                )
                send_message(chat_id, error_msg)
            return

        # ===== پیکربندی Bale =====
        elif current_state_name == "waiting_bale_token":
            user_config["messengers"]["bale"]["bot_token"] = text
            save_user_config(chat_id, user_config)

            prompt = (
                "✅ ذخیره شد! اکنون شناسه کانال را ارسال کنید:\nمثال: @yourchannel"
                if lang == "fa"
                else "✅ Saved! Now send channel ID:\nExample: @yourchannel"
            )
            send_message(chat_id, prompt)
            set_state(chat_id, "waiting_bale_channel")
            return

        elif current_state_name == "waiting_bale_channel":
            user_config["messengers"]["bale"]["channel_id"] = text
            save_user_config(chat_id, user_config)

            success_msg = (
                "✅ Bale پیکربندی شد!"
                if lang == "fa"
                else "✅ Bale configured!"
            )
            send_message(chat_id, success_msg, create_messengers_keyboard(chat_id, user_config))
            clear_state(chat_id)
            return

        # ===== پیکربندی Rubika =====
        elif current_state_name == "waiting_rubika_token":
            user_config["messengers"]["rubika"]["bot_token"] = text
            save_user_config(chat_id, user_config)

            prompt = (
                "✅ ذخیره شد! اکنون شناسه چت را ارسال کنید:"
                if lang == "fa"
                else "✅ Saved! Now send chat ID:"
            )
            send_message(chat_id, prompt)
            set_state(chat_id, "waiting_rubika_chat")
            return

        elif current_state_name == "waiting_rubika_chat":
            user_config["messengers"]["rubika"]["chat_id"] = text
            save_user_config(chat_id, user_config)

            success_msg = (
                "✅ Rubika پیکربندی شد!"
                if lang == "fa"
                else "✅ Rubika configured!"
            )
            send_message(chat_id, success_msg, create_messengers_keyboard(chat_id, user_config))
            clear_state(chat_id)
            return

        # ===== پیکربندی Eitaa =====
        elif current_state_name == "waiting_eitaa_token":
            user_config["messengers"]["eitaa"]["bot_token"] = text
            save_user_config(chat_id, user_config)

            prompt = (
                "✅ ذخیره شد! اکنون شناسه چت را ارسال کنید:"
                if lang == "fa"
                else "✅ Saved! Now send chat ID:"
            )
            send_message(chat_id, prompt)
            set_state(chat_id, "waiting_eitaa_chat")
            return

        elif current_state_name == "waiting_eitaa_chat":
            user_config["messengers"]["eitaa"]["chat_id"] = text
            save_user_config(chat_id, user_config)

            success_msg = (
                "✅ Eitaa پیکربندی شد!"
                if lang == "fa"
                else "✅ Eitaa configured!"
            )
            send_message(chat_id, success_msg, create_messengers_keyboard(chat_id, user_config))
            clear_state(chat_id)
            return

        # ===== پیکربندی Telegram =====
        elif current_state_name == "waiting_telegram_token":
            user_config["messengers"]["telegram"]["bot_token"] = text.strip()
            save_user_config(chat_id, user_config)

            prompt = (
                "✅ توکن ذخیره شد! اکنون شناسه کانال/گروه را ارسال کنید:\n"
                "فرمت‌ها:\n"
                "• @yourchannel (کانال عمومی)\n"
                "• -1001234567890 (کانال خصوصی با -100)\n"
                "• @username یا chat_id عددی\n\n"
                "⚠️ ربات باید ادمین کانال باشد!"
                if lang == "fa"
                else "✅ Token saved! Now send channel/group ID:\n"
                "Formats:\n"
                "• @yourchannel (public)\n"
                "• -1001234567890 (private)\n\n"
                "⚠️ Bot must be admin!"
            )
            send_message(chat_id, prompt)
            set_state(chat_id, "waiting_telegram_chat")
            return

        elif current_state_name == "waiting_telegram_chat":
            user_config["messengers"]["telegram"]["chat_id"] = text.strip()
            save_user_config(chat_id, user_config)

            # تست سریع
            testing_msg = "⏳ در حال تست اتصال تلگرام..." if lang == "fa" else "⏳ Testing Telegram connection..."
            send_message(chat_id, testing_msg)

            try:
                import messenger_telegram
                if messenger_telegram.is_configured(user_config):
                    success_msg = (
                        "✅ Telegram پیکربندی شد!\n"
                        f"کانال: {text}\n\n"
                        "برای تست: پست‌های ووکامرس -> تست ارسال"
                        if lang == "fa"
                        else f"✅ Telegram configured!\nChannel: {text}"
                    )
                else:
                    success_msg = "✅ Telegram ذخیره شد!" if lang == "fa" else "✅ Telegram saved!"
            except:
                success_msg = "✅ Telegram پیکربندی شد!" if lang == "fa" else "✅ Telegram configured!"

            send_message(chat_id, success_msg, create_messengers_keyboard(chat_id, user_config))
            clear_state(chat_id)
            return

        # ===== پیکربندی WhatsApp - نسخه نهایی پایدار - ذخیره سشن در فایل+DB =====
        elif current_state_name == "waiting_whatsapp_chat":
            # دستورات خاص اول
            wa_input_raw = text.strip()
            lang = get_user_lang(chat_id)
            
            if wa_input_raw.lower() in ["groups", "گروه", "گروه‌ها", "لیست", "list", "group"]:
                try:
                    import messenger_whatsapp
                    wa_cfg = user_config["messengers"].get("whatsapp", {})
                    service_url = wa_cfg.get("service_url", "http://localhost:3001")
                    status = messenger_whatsapp.check_connection_status(chat_id, service_url)
                    if not status.get("connected"):
                        send_message(chat_id, "❌ واتساپ متصل نیست، اول شماره خودت رو بفرست تا وصل بشی" if lang == "fa" else "❌ Not connected")
                        return
                    chats_result = messenger_whatsapp.get_chats_for_user(chat_id, service_url)
                    if chats_result.get("ok") and chats_result.get("chats"):
                        chats = chats_result["chats"]
                        keyboard = []
                        for chat in chats[:15]:
                            name = chat.get("name", "Unknown")[:30]
                            chat_id_val = chat.get("id", "")
                            participants = chat.get("participants", 0)
                            btn_text = f"👥 {name} ({participants})" if participants else f"👥 {name}"
                            keyboard.append([{"text": btn_text, "callback_data": f"wa_select_dest_{chat_id_val}"}])
                        keyboard.append([{"text": "📱 شماره شخصی", "callback_data": "wa_select_personal"}])
                        send_message(chat_id, f"📋 {len(chats)} گروه پیدا شد، انتخاب کنید:", {"inline_keyboard": keyboard})
                        set_state(chat_id, "waiting_whatsapp_destination", chats=chats)
                    else:
                        send_message(chat_id, f"❌ خطا: {chats_result.get('error','')}")
                except Exception as e:
                    send_message(chat_id, f"❌ خطا: {e}")
                return
            
            if wa_input_raw.lower() in ["logout", "خروج", "قطع"]:
                try:
                    import messenger_whatsapp
                    wa_cfg = user_config["messengers"].get("whatsapp", {})
                    messenger_whatsapp.disconnect_user(chat_id, wa_cfg.get("service_url", "http://localhost:3001"))
                    user_config["messengers"]["whatsapp"]["chat_id"] = ""
                    user_config["messengers"]["whatsapp"]["phone_number"] = ""
                    user_config["messengers"]["whatsapp"]["connected"] = False
                    user_config["messengers"]["whatsapp"]["destination_selected"] = False
                    save_user_config(chat_id, user_config)
                    send_message(chat_id, "✅ اتصال WhatsApp قطع شد!" if lang == "fa" else "✅ Disconnected!", create_messengers_keyboard(chat_id, user_config))
                except Exception as e:
                    send_message(chat_id, f"❌ خطا: {e}")
                clear_state(chat_id)
                return
            
            if wa_input_raw.lower() in ["qr", "کیوآر", "اتصال"]:
                wa_input_raw = user_config["messengers"].get("whatsapp", {}).get("phone_number", "") or user_config["messengers"].get("whatsapp", {}).get("chat_id", "")
                if not wa_input_raw:
                    send_message(chat_id, "❌ ابتدا شماره خودت رو بفرست!" if lang == "fa" else "❌ Enter your OWN number first!")
                    return
            
            # ===== مرحله 1: شماره خود کاربر برای لینک کردن (نه مقصد) =====
            # این شماره باید شماره واتساپ خود کاربر باشد که روی گوشیش نصبه
            own_phone_raw = wa_input_raw.strip().replace(" ", "").replace("+", "")
            # نرمال‌سازی
            if own_phone_raw.startswith("0"):
                own_phone_raw = "98" + own_phone_raw[1:]
            if own_phone_raw.isdigit() and len(own_phone_raw) == 10 and own_phone_raw.startswith("9"):
                own_phone_raw = "98" + own_phone_raw
            
            # اعتبارسنجی
            if not own_phone_raw.isdigit() or len(own_phone_raw) < 10:
                send_message(chat_id, "❌ شماره نامعتبر! مثال: 989123456789 (با 98 شروع، بدون + و فاصله)" if lang == "fa" else "❌ Invalid number! Example: 989123456789")
                return
            
            # ذخیره شماره خود کاربر - برای pairing code
            user_config["messengers"]["whatsapp"]["phone_number"] = own_phone_raw
            user_config["messengers"]["whatsapp"]["own_phone"] = own_phone_raw
            user_config["messengers"]["whatsapp"]["provider"] = "baileys"
            user_config["messengers"]["whatsapp"]["session_persistent"] = True
            if "service_url" not in user_config["messengers"]["whatsapp"]:
                user_config["messengers"]["whatsapp"]["service_url"] = "http://localhost:3001"
            save_user_config(chat_id, user_config)
            logger.info(f"💾 Saved own phone {own_phone_raw} for user {chat_id} - persistent in file+DB")

            # حالا QR + Pairing Code بگیر
            try:
                import messenger_whatsapp
                wa_cfg = user_config["messengers"]["whatsapp"]
                service_url = wa_cfg.get("service_url", "http://localhost:3001")
                
                send_message(chat_id, "⏳ در حال دریافت QR کد و کد اتصال...\nشماره خودت: " + own_phone_raw if lang == "fa" else f"⏳ Getting QR for {own_phone_raw}...")
                
                qr_result = messenger_whatsapp.get_qr_for_user(chat_id, own_phone_raw, service_url)
                
                if qr_result.get("connected"):
                    success_msg = (
                        f"✅ *WhatsApp قبلا متصل است!* ✅\n\n"
                        f"📱 شماره خودت: {own_phone_raw}\n"
                        f"🔗 وضعیت: متصل ✅\n\n"
                        "حالا مقصد ارسال را انتخاب کن:\n"
                        "بنویس groups تا لیست گروه‌ها بیاد"
                        if lang == "fa"
                        else f"✅ Already connected! Own: {own_phone_raw}"
                    )
                    send_message(chat_id, success_msg, create_messengers_keyboard(chat_id, user_config))
                    # بعد از اتصال، لیست گروه‌ها
                    try:
                        chats_result = messenger_whatsapp.get_chats_for_user(chat_id, service_url)
                        if chats_result.get("ok") and chats_result.get("chats"):
                            chats = chats_result["chats"]
                            keyboard = []
                            for chat in chats[:10]:
                                name = chat.get("name", "Unknown")[:30]
                                cid = chat.get("id", "")
                                participants = chat.get("participants", 0)
                                btn_text = f"👥 {name} ({participants})" if participants else f"👥 {name}"
                                keyboard.append([{"text": btn_text, "callback_data": f"wa_select_dest_{cid}"}])
                            keyboard.append([{"text": "📱 شماره شخصی", "callback_data": "wa_select_personal"}])
                            send_message(chat_id, f"📋 {len(chats)} گروه پیدا شد:", {"inline_keyboard": keyboard})
                            set_state(chat_id, "waiting_whatsapp_destination", chats=chats)
                            return
                    except:
                        pass
                    clear_state(chat_id)
                    return
                
                if qr_result.get("ok") and qr_result.get("qrImage"):
                    try:
                        base64_part = qr_result["qrImage"].split(",")[1] if "," in qr_result["qrImage"] else qr_result["qrImage"]
                        import base64
                        qr_bytes = base64.b64decode(base64_part)
                        pairing_code = qr_result.get("pairingCode") or qr_result.get("copyableCode")
                        
                        # اگر کد نیست، جدا بگیر
                        if not pairing_code:
                            try:
                                import requests as req_tmp
                                pc_resp = req_tmp.get(
                                    f"{service_url}/pairing-code",
                                    params={"userId": str(chat_id), "phone": own_phone_raw},
                                    timeout=15
                                )
                                if pc_resp.status_code == 200:
                                    pc_data = pc_resp.json()
                                    pairing_code = pc_data.get("pairingCode") or pc_data.get("copyableCode")
                                    logger.info(f"🔑 Got pairing code fallback for {chat_id}: {pairing_code}")
                            except Exception as e:
                                logger.error(f"Pairing fallback error: {e}")
                        
                        # ارسال QR عکس
                        try:
                            bale_token = config["messengers"]["bale"]["bot_token"]
                            api = f"https://tapi.bale.ai/bot{bale_token}"
                            import tempfile, os
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                                tmp.write(qr_bytes)
                                tmp_path = tmp.name
                            with open(tmp_path, "rb") as f:
                                files = {"photo": ("qr.png", f, "image/png")}
                                caption_text = (
                                    f"📱 *QR کد واتساپ*\n\n"
                                    f"این QR را اسکن کن:\n"
                                    f"واتساپ -> تنظیمات -> دستگاه‌های متصل -> اتصال دستگاه\n\n"
                                    f"⏰ 20 ثانیه اعتبار - خودکار عوض می‌شود"
                                    if lang == "fa"
                                    else f"📱 Scan QR: WhatsApp -> Settings -> Linked Devices"
                                )
                                data = {"chat_id": chat_id, "caption": caption_text}
                                resp = requests.post(f"{api}/sendPhoto", data=data, files=files, timeout=20)
                                os.unlink(tmp_path)
                        except Exception as e:
                            logger.error(f"QR photo send error: {e}")
                        
                        # ===== ارسال کد به صورت قابل کپی - جداگانه =====
                        if pairing_code:
                            # کد با خط تیره مثلا 1234-5678
                            # بدون خط تیره برای کپی راحت‌تر
                            plain_code = pairing_code.replace("-", "").replace(" ", "")
                            formatted_code = pairing_code
                            
                            # پیام 1: کد با توضیح کامل - قابل کپی
                            code_msg_1 = (
                                f"🔑 *کد اتصال واتساپ - قابل کپی:*\n\n"
                                f"`{formatted_code}`\n\n"
                                f"📋 *کپی کنید:* `{plain_code}`\n\n"
                                f"⚠️ *مهم:* این کد برای شماره {own_phone_raw} است\n"
                                f"باید روی گوشی که همین شماره روش نصبه وارد کنی\n\n"
                                f"📍 مسیر:\n"
                                f"واتساپ -> تنظیمات (سه نقطه) -> دستگاه‌های متصل\n"
                                f"-> اتصال با شماره تلفن\n"
                                f"-> کد بالا را وارد کن\n\n"
                                f"اگر میگه 'مطمئن باش برای شماره خودت هست' یعنی شماره‌ای که وارد کردی ({own_phone_raw}) با شماره گوشی‌ت فرق داره!\n"
                                f"شماره خودت رو درست بفرست"
                                if lang == "fa"
                                else f"🔑 Pairing Code (copyable):\n{formatted_code}\nPlain: {plain_code}\nFor number {own_phone_raw}"
                            )
                            send_message(chat_id, code_msg_1)
                            
                            # پیام 2: فقط کد ساده برای کپی فوق آسان
                            send_message(chat_id, f"{formatted_code}\n\n👆 این کد را کپی کن")
                            send_message(chat_id, f"{plain_code}\n\n👆 بدون خط تیره - کپی راحت")
                        else:
                            send_message(chat_id, "⚠️ کد اتصال هنوز آماده نشده، فقط QR را اسکن کن - یا چند ثانیه بعد بنویس qr" if lang == "fa" else "⚠️ Code not ready, scan QR")
                        
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "✅ بررسی اتصال" if lang == "fa" else "✅ Check", "callback_data": "check_whatsapp_status"}],
                                [{"text": "🔄 QR + کد جدید" if lang == "fa" else "🔄 New QR+Code", "callback_data": "whatsapp_new_qr"}]
                            ]
                        }
                        send_message(chat_id, "✅ QR و کد بالا را استفاده کن، بعد بررسی بزن\n💡 QR خودکار عوض می‌شود" if lang == "fa" else "Use QR/code above, then check", keyboard)
                        set_state(chat_id, "waiting_whatsapp_qr_check", phone=own_phone_raw, own_phone=own_phone_raw, last_qr=qr_result.get("qr",""), pairing_code=pairing_code)
                        return
                    
                    except Exception as e:
                        logger.error(f"QR processing error: {e}", exc_info=True)
                        send_message(chat_id, f"❌ خطا در پردازش QR: {e}")
                        clear_state(chat_id)
                        return
                
                elif qr_result.get("ok") and qr_result.get("qr"):
                    send_message(chat_id, f"📱 QR دریافت شد\n{service_url}/qr-image?userId={chat_id}")
                    set_state(chat_id, "waiting_whatsapp_qr_check", phone=own_phone_raw)
                    return
                else:
                    error = qr_result.get("error", "Unknown")
                    logger.error(f"QR error for {chat_id}: {error} result={qr_result}")
                    msg = (
                        "⏳ در حال اتصال...\n"
                        "چند ثانیه صبر کن و بنویس qr"
                        if lang == "fa"
                        else "Connecting, try qr again"
                    )
                    send_message(chat_id, msg, {"inline_keyboard": [[{"text": "🔄 تلاش مجدد", "callback_data": "whatsapp_new_qr"}]]})
                    return
            
            except Exception as e:
                logger.error(f"WhatsApp QR flow error: {e}", exc_info=True)
                send_message(chat_id, f"❌ خطا: {e}\nسرویس چک: cd whatsapp-service && cat whatsapp.log", create_messengers_keyboard(chat_id, user_config))
                clear_state(chat_id)
                return

        elif current_state_name == "waiting_whatsapp_qr_check":
            # کاربر بعد از اسکن QR، چیزی فرستاده یا دکمه بررسی زده - با شماره خودت
            if text.lower() in ["qr", "کیوآر", "جدید", "کد"]:
                # QR جدید - با شماره خودت
                try:
                    import messenger_whatsapp
                    wa_cfg = user_config["messengers"].get("whatsapp", {})
                    service_url = wa_cfg.get("service_url", "http://localhost:3001")
                    phone = current_state_data.get("own_phone", "") or current_state_data.get("phone", "") or wa_cfg.get("phone_number", "") or wa_cfg.get("own_phone", "") or wa_cfg.get("chat_id", "")
                    
                    qr_result = messenger_whatsapp.get_qr_for_user(chat_id, phone, service_url, own_phone=phone)
                    if qr_result.get("qrImage"):
                        import base64, tempfile, os
                        base64_part = qr_result["qrImage"].split(",")[1] if "," in qr_result["qrImage"] else qr_result["qrImage"]
                        qr_bytes = base64.b64decode(base64_part)
                        bale_token = config["messengers"]["bale"]["bot_token"]
                        api = f"https://tapi.bale.ai/bot{bale_token}"
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            tmp.write(qr_bytes)
                            tmp_path = tmp.name
                        with open(tmp_path, "rb") as f:
                            files = {"photo": ("qr.png", f, "image/png")}
                            pc = qr_result.get("pairingCode") or ""
                            caption = f"📱 QR جدید - کد: {pc} برای {phone}" if pc else f"📱 QR جدید - برای {phone}"
                            data = {"chat_id": chat_id, "caption": caption}
                            requests.post(f"{api}/sendPhoto", data=data, files=files, timeout=20)
                            os.unlink(tmp_path)
                        # کد قابل کپی
                        if qr_result.get("pairingCode"):
                            pc = qr_result.get("pairingCode")
                            send_message(chat_id, f"{pc}\n\n👆 کپی کن - برای {phone}")
                            send_message(chat_id, f"{pc.replace('-','')}\n\n👆 بدون خط تیره")
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "✅ بررسی اتصال", "callback_data": "check_whatsapp_status"}]
                            ]
                        }
                        send_message(chat_id, f"QR جدید فرستاده شد برای شماره خودت {phone} - کد بالا قابل کپی", keyboard)
                        # آپدیت state
                        if isinstance(user_states.get(chat_id), dict):
                            user_states[chat_id]["last_qr"] = qr_result.get("qr","")
                            user_states[chat_id]["pairing_code"] = qr_result.get("pairingCode")
                        return
                except Exception as e:
                    logger.error(f"waiting_whatsapp_qr_check qr error: {e}")
                    send_message(chat_id, f"❌ خطا: {e}")
                    return
            
            # برای هر متن دیگری، راهنما
            msg = (
                "📱 QR را اسکن کردید؟\n"
                "دکمه ✅ بررسی اتصال را بزنید\n"
                "یا بنویسید `qr` برای QR جدید"
                if lang == "fa"
                else "Scanned? Click Check Connection or type qr for new QR"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "✅ بررسی اتصال" if lang == "fa" else "✅ Check", "callback_data": "check_whatsapp_status"}],
                    [{"text": "🔄 QR جدید" if lang == "fa" else "🔄 New QR", "callback_data": "whatsapp_new_qr"}]
                ]
            }
            send_message(chat_id, msg, keyboard)
            return

        elif current_state_name == "waiting_whatsapp_destination":
            # کاربر مقصد واتساپ را وارد می‌کند (شماره یا آیدی گروه)
            dest_input = text.strip()
            lang = get_user_lang(chat_id)
            
            if dest_input.lower() in ["ok", "تایید", "همین"]:
                # تایید شماره فعلی به عنوان مقصد
                current_dest = user_config["messengers"]["whatsapp"].get("chat_id", "")
                if current_dest:
                    user_config["messengers"]["whatsapp"]["destination_selected"] = True
                    user_config["messengers"]["whatsapp"]["connected"] = True
                    save_user_config(chat_id, user_config)
                    msg = (
                        f"✅ مقصد تایید شد: {current_dest}\n"
                        f"🔗 وضعیت: متصل + مقصد ✅"
                        if lang == "fa"
                        else f"✅ Destination confirmed: {current_dest}"
                    )
                    send_message(chat_id, msg, create_messengers_keyboard(chat_id, user_config))
                    clear_state(chat_id)
                    return
                else:
                    send_message(chat_id, "❌ مقصدی وجود ندارد، شماره وارد کنید" if lang == "fa" else "❌ No destination")
                    return
            
            # نرمال‌سازی ورودی
            normalized = dest_input.replace(" ", "").replace("+", "")
            if normalized.startswith("0"):
                normalized = "98" + normalized[1:]
            
            # ذخیره به عنوان مقصد
            user_config["messengers"]["whatsapp"]["chat_id"] = normalized
            user_config["messengers"]["whatsapp"]["destination_selected"] = True
            user_config["messengers"]["whatsapp"]["connected"] = True
            save_user_config(chat_id, user_config)
            
            success_msg = (
                f"✅ *مقصد واتساپ انتخاب شد!* 🎉\n\n"
                f"📱 مقصد: {normalized}\n"
                f"🔗 وضعیت: متصل + مقصد ✅\n\n"
                "⏳ در حال ارسال پیام تست..."
                if lang == "fa"
                else f"✅ WhatsApp destination: {normalized} - sending test..."
            )
            send_message(chat_id, success_msg)
            
            # پیام تست
            try:
                import messenger_whatsapp
                wa_cfg = user_config["messengers"].get("whatsapp", {})
                service_url = wa_cfg.get("service_url", "http://localhost:3001")
                test_text = "✅ ربات متصل شد! اوکی وصله 🎉\n\nاین مقصد به عنوان مقصد انتخاب شد"
                result = messenger_whatsapp._send_via_baileys(normalized, test_text, None, service_url, str(chat_id))
                if result:
                    send_message(chat_id, "✅ پیام تست ارسال شد! اوکی وصله 🎉" if lang == "fa" else "✅ Test sent!", create_messengers_keyboard(chat_id, user_config))
                else:
                    send_message(chat_id, "⚠️ پیام تست ارسال نشد ولی تنظیمات ذخیره شد" if lang == "fa" else "⚠️ Test failed but saved", create_messengers_keyboard(chat_id, user_config))
            except Exception as e:
                logger.error(f"Test message error: {e}")
                send_message(chat_id, create_messengers_keyboard(chat_id, user_config))
            
            clear_state(chat_id)
            return

        # ===== پیکربندی WooCommerce =====
        elif current_state_name == "waiting_wc_url":
            user_config["woocommerce"]["url"] = text.rstrip("/")
            save_user_config(chat_id, user_config)

            prompt = (
                "✅ ذخیره شد! اکنون Consumer Key را ارسال کنید:"
                if lang == "fa"
                else "✅ Saved! Now send Consumer Key:"
            )
            send_message(chat_id, prompt)
            set_state(chat_id, "waiting_wc_key")
            return

        elif current_state_name == "waiting_wc_key":
            user_config["woocommerce"]["consumer_key"] = text
            save_user_config(chat_id, user_config)

            prompt = (
                "✅ ذخیره شد! اکنون Consumer Secret را ارسال کنید:"
                if lang == "fa"
                else "✅ Saved! Now send Consumer Secret:"
            )
            send_message(chat_id, prompt)
            set_state(chat_id, "waiting_wc_secret")
            return

        elif current_state_name == "waiting_wc_secret":
            user_config["woocommerce"]["consumer_secret"] = text
            save_user_config(chat_id, user_config)

            testing_msg = (
                "⏳ در حال تست..."
                if lang == "fa"
                else "⏳ Testing..."
            )
            send_message(chat_id, testing_msg)

            products = woocommerce.get_all_products(user_config)
            if products:
                from config import save_json, PRODUCTS_FILE
                save_json(PRODUCTS_FILE, products)

                msg = (
                    f"✅ پیکربندی شد! {len(products)} محصول بارگذاری شد"
                    if lang == "fa"
                    else f"✅ Configured! Loaded {len(products)} products"
                )
                send_message(chat_id, msg, create_settings_keyboard(chat_id))
            else:
                error_msg = (
                    "❌ اتصال ناموفق بود!"
                    if lang == "fa"
                    else "❌ Connection failed!"
                )
                send_message(chat_id, error_msg, create_settings_keyboard(chat_id))

            clear_state(chat_id)
            return

    else:
        # ========== پیام ناشناخته ==========
        if not callback_data:
            lang = get_user_lang(chat_id)
            unknown_msg = (
                "❓ دستور ناشناخته. لطفاً از منو استفاده کنید."
                if lang == "fa"
                else "❓ Unknown command. Please use the menu."
            )
            send_message(chat_id, unknown_msg, create_main_keyboard(chat_id))


# ========== دریافت آپدیت‌ها ==========

def get_updates(offset=None):
    """دریافت update‌های جدید"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset

    try:
        response = requests.get(f"{api}/getUpdates", params=params, timeout=35)
        return response.json()
    except Exception:
        return {"ok": False}


# ========== تابع اصلی ==========

def run():
    """تابع اصلی اجرای ربات"""
    global config
    config = load_config()

    if not config["messengers"]["bale"]["bot_token"]:
        print("❌ لطفاً ابتدا توکن ربات Bale را در config.json تنظیم کنید!")
        return

    logger.info("🤖 ربات شروع به کار کرد!")

    # ✅ تعریف bot_token در اینجا - در دسترس کل تابع
    bot_token = config["messengers"]["bale"]["bot_token"]

    if "admin_chat_id" not in config:
        config["admin_chat_id"] = None

    initial_admin_id = (
        config.get("initial_admin_id")
        or config.get("admin_chat_id")
    )
    initial_admin_username = config.get("initial_admin_username", "SuperAdmin")

    if initial_admin_id:
        try:
            initial_admin_id = int(initial_admin_id)
            existing_admin = auth_manager.get_admin_info(initial_admin_id)

            if not existing_admin:
                result = auth_manager.setup_initial_admin(
                    initial_admin_id,
                    initial_admin_username
                )
                if result['success']:
                    logger.info(f"✅ سوپر ادمین اولیه تنظیم شد: {initial_admin_id}")
                else:
                    logger.error(f"❌ خطا در تنظیم ادمین: {result.get('error', 'unknown')}")
            else:
                logger.info(f"ℹ️ ادمین اولیه قبلاً ثبت شده: {initial_admin_id}")

        except (ValueError, TypeError) as e:
            logger.error(f"❌ initial_admin_id نامعتبر: {e}")
    else:
        logger.warning(
            "⚠️ initial_admin_id یافت نشد. "
            "لطفاً 'initial_admin_id' را در config.json تنظیم کنید."
        )

    scheduler.start_scheduler(config)
    print("🤖 ربات در حال اجراست... برای توقف Ctrl+C را بزنید.")

    last_update_id = 0

    while True:
        try:
            updates = get_updates(last_update_id)

            if updates.get("ok") and updates.get("result"):
                for update in updates["result"]:
                    last_update_id = update["update_id"] + 1

                    # ========== پیام معمولی ==========
                    if "message" in update:
                        msg = update["message"]

                        # ✅ پرداخت موفق - قبل از handle_message بررسی کن
                        if msg.get("successful_payment"):
                            payment_chat_id = msg["chat"]["id"]
                            payment_username = msg.get("from", {}).get("username", "unknown")
                            payment_info = msg["successful_payment"]

                            from auth_handlers import handle_successful_payment
                            handle_successful_payment(
                                payment_chat_id,
                                payment_username,
                                payment_info,
                                bot_token
                            )
                            continue  # ✅ از handle_message رد کن

                        # ✅ تنظیم admin_chat_id اگر هنوز ست نشده
                        if config.get("admin_chat_id") is None:
                            first_chat_id = msg["chat"]["id"]
                            if auth_manager.is_admin(first_chat_id):
                                config["admin_chat_id"] = first_chat_id
                                save_config(config)
                                logger.info(f"✅ admin_chat_id تنظیم شد: {first_chat_id}")

                        handle_message(msg)

                    # ========== callback query ==========
                    elif "callback_query" in update:
                        callback = update["callback_query"]
                        message_with_user = callback["message"].copy()
                        message_with_user["from"] = callback["from"]

                        handle_message(
                            message_with_user,
                            callback_data=callback.get("data")
                        )

                    # ========== pre checkout query ==========
                    elif "pre_checkout_query" in update:
                        pcq = update["pre_checkout_query"]
                        from auth_handlers import handle_pre_checkout
                        handle_pre_checkout(
                            pcq["id"],
                            pcq["from"]["id"],
                            bot_token  # ✅ حالا در دسترسه
                        )

            time.sleep(1)

        except KeyboardInterrupt:
            logger.info("👋 ربات متوقف شد")
            break
        except Exception as e:
            logger.error(f"❌ خطا در حلقه اصلی: {e}", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    run()