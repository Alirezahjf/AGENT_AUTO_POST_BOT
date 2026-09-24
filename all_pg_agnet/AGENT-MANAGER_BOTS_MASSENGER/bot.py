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

        # ===== تعرفه‌ها (برای همه کاربران) =====
        "tariffs": "🏷️ تعرفه‌ها",
        "tariffs_title": "🏷️ *تعرفه‌های دسترسی*\n\nیکی از پلن‌های زیر را انتخاب کنید:",
        "buy_this_plan": "💳 خرید این پلن",

        # ===== مدیریت حرفه‌ای کاربران =====
        "users_list_title": "👥 *مدیریت کاربران*\n\nروی هر کاربر برای مشاهده جزئیات بزنید:",
        "user_detail_title": "👤 *پروفایل کاربر*",
        "user_access_section": "═══ *مدت دسترسی* ═══",
        "access_permanent": "♾️ دائمی",
        "access_timed": "⏱️ محدود",
        "access_trial": "🎁 تست رایگان",
        "access_expired": "🔴 منقضی شده",
        "access_active": "🟢 فعال",
        "access_until": "📅 معتبر تا",
        "access_remaining": "⏳ باقی‌مانده",
        "grant_free_access": "🎁 هدیه دسترسی رایگان",
        "extend_access": "⏱️ تمدید مدت دسترسی",
        "make_permanent": "♾️ دائمی کردن",
        "view_payments": "🧾 پرداخت‌های کاربر",
        "view_user_logs": "📊 فعالیت اخیر",
        "choose_free_duration": "🎁 مدت دسترسی رایگان را انتخاب کنید:",
        "choose_extend_duration": "⏱️ چند روز تمدید شود؟",
        "custom_days_prompt": "✍️ تعداد روز را وارد کنید (عدد):",
        "free_days_1": "۱ روز",
        "free_days_3": "۳ روز",
        "free_days_7": "۷ روز",
        "free_days_14": "۱۴ روز",
        "free_days_30": "۳۰ روز",
        "days_7": "۷ روز",
        "days_30": "۳۰ روز",
        "days_90": "۹۰ روز",
        "days_180": "۱۸۰ روز",
        "custom": "✍️ دلخواه",
        "access_granted_success": "✅ دسترسی رایگان اعطا شد",
        "access_extended_success": "✅ مدت دسترسی تمدید شد",
        "made_permanent_success": "✅ دسترسی دائمی شد",
        "user_notified": "🔔 به کاربر اطلاع‌رسانی شد",
        "invalid_days": "❌ عدد نامعتبر",
        "page_of": "صفحه {page} از {total}",
        "prev_page": "◀️ قبلی",
        "next_page": "بعدی ▶️",

        # ===== مدیریت تعرفه‌ها (قیمت‌گذاری) =====
        "manage_tariffs": "🏷️ تعرفه‌ها و قیمت‌گذاری",
        "tariffs_admin_title": "🏷️ *مدیریت تعرفه‌ها*\n\nروی هر پلن برای ویرایش بزنید:",
        "add_new_plan": "➕ افزودن پلن جدید",
        "edit_plan": "✏️ ویرایش پلن",
        "plan_name_prompt": "📝 نام پلن را وارد کنید:\nمثال: یک‌ماهه، سه‌ماهه، دائمی",
        "plan_days_prompt": "⏱️ مدت دسترسی به روز:\n• عدد وارد کنید (مثلاً 30)\n• یا `permanent` برای دائمی",
        "plan_price_prompt": "💰 قیمت را به **تومان** وارد کنید:\nمثال: 500000",
        "plan_created_success": "✅ پلن جدید ایجاد شد",
        "plan_updated_success": "✅ پلن بروزرسانی شد",
        "plan_deleted": "🗑️ پلن حذف شد",
        "set_price": "💰 تنظیم قیمت",
        "set_duration": "⏱️ تنظیم مدت",
        "toggle_plan": "🔄 فعال/غیرفعال",
        "delete_plan": "🗑️ حذف پلن",
        "broadcast_new_plan": "📣 اطلاع‌رسانی به همه کاربران",
        "broadcast_done": "📣 اطلاع‌رسانی انجام شد",
        "price_set_success": "✅ قیمت تنظیم شد",
        "duration_set_success": "✅ مدت تنظیم شد",
        "enter_price_new": "💰 قیمت جدید (تومان) را وارد کنید:",
        "enter_duration_new": "⏱️ مدت جدید به روز (یا permanent):",
        "confirm_delete_plan": "❓ مطمئنید پلن حذف شود؟",
        "yes_delete": "✅ بله حذف شود",
        "no_keep": "❌ انصراف",
        "plan_price_label": "💰 قیمت",
        "plan_duration_label": "⏱️ مدت",
        "plan_status_label": "📊 وضعیت",
        "default_trial_days": "⏱️ تست پیش‌فرض کاربران جدید",
        "trial_days_prompt": "⏱️ مدت تست رایگان پیش‌فرض (روز):\nعدد وارد کنید (0 برای غیرفعال)",
        "trial_days_success": "✅ مدت تست پیش‌فرض ذخیره شد",
        "users_count": "کاربران",
        "stats_line": "📊 آمار: {total} کاربر | {permanent} دائمی | {timed} محدود | {expired} منقضی",

        # ===== کدهای تخفیف =====
        "manage_discounts": "🎟️ کدهای تخفیف",
        "discounts_title": "🎟️ *مدیریت کدهای تخفیف*",
        "add_discount": "➕ کد تخفیف جدید",
        "disc_all": "📋 همه",
        "disc_active": "🟢 فعال",
        "disc_public": "🌍 عمومی",
        "disc_personal": "👤 شخصی",
        "disc_expired": "🔴 منقضی",
        "disc_exhausted": "⛔ تمام‌شده",
        "disc_back_to_tariffs": "🔙 بازگشت به تعرفه‌ها",
        "disc_toggle": "🔄 فعال/غیرفعال",
        "disc_edit": "✏️ ویرایش",
        "disc_usages": "📜 تاریخچه استفاده",
        "disc_stats": "📊 آمار",
        "disc_users": "👥 کاربران مجاز",
        "disc_plans": "📦 پلن‌های مشمول",
        "disc_notify": "📣 اطلاع‌رسانی",
        "disc_delete": "🗑️ حذف کد",
        "disc_percent": "٪ درصدی",
        "disc_fixed": "💰 مبلغی",
        "disc_scope_public": "🌍 عمومی (همه کاربران)",
        "disc_scope_personal": "👤 شخصی (کاربران خاص)",
        "disc_skip": "⏭️ رد شدن",
        "disc_unlimited": "♾️ نامحدود",
        "disc_confirm_create": "✅ ثبت نهایی",
        "disc_cancel": "❌ انصراف",
        "disc_autogen": "🎲 تولید خودکار کد",
        "disc_notify_users": "📣 ارسال به کاربران مجاز",
        "disc_broadcast": "📣 اطلاع‌رسانی به همه کاربران",
        "disc_pick_done": "✅ ثبت انتخاب",
        "disc_pick_search": "🔍 جستجو",
        "disc_pick_all": "🔙 کل لیست",
        "disc_pick_manual": "✍️ ورود دستی آیدی",
        "disc_pick_from_list": "📋 انتخاب از لیست",
        "disc_pick_empty": "❌ هنوز کاربری انتخاب نشده! روی نام کاربران بزنید.",
        "disc_pick_search_prompt": "🔍 نام کاربری یا بخشی از آیدی عددی را وارد کنید:",
        "disc_copy_code": "📋 کپی کد",
        "disc_code_detail": "🔍 جزئیات کد",
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

        # ===== Tariffs (all users) =====
        "tariffs": "🏷️ Tariffs",
        "tariffs_title": "🏷️ *Access Tariffs*\n\nSelect a plan:",
        "buy_this_plan": "💳 Buy this plan",

        # ===== Professional user management =====
        "users_list_title": "👥 *User Management*\n\nTap a user for details:",
        "user_detail_title": "👤 *User Profile*",
        "user_access_section": "═══ *Access Duration* ═══",
        "access_permanent": "♾️ Lifetime",
        "access_timed": "⏱️ Limited",
        "access_trial": "🎁 Free Trial",
        "access_expired": "🔴 Expired",
        "access_active": "🟢 Active",
        "access_until": "📅 Valid until",
        "access_remaining": "⏳ Remaining",
        "grant_free_access": "🎁 Grant free access",
        "extend_access": "⏱️ Extend access",
        "make_permanent": "♾️ Make permanent",
        "view_payments": "🧾 User payments",
        "view_user_logs": "📊 Recent activity",
        "choose_free_duration": "🎁 Choose free access duration:",
        "choose_extend_duration": "⏱️ Extend by how many days?",
        "custom_days_prompt": "✍️ Enter number of days:",
        "free_days_1": "1 day",
        "free_days_3": "3 days",
        "free_days_7": "7 days",
        "free_days_14": "14 days",
        "free_days_30": "30 days",
        "days_7": "7 days",
        "days_30": "30 days",
        "days_90": "90 days",
        "days_180": "180 days",
        "custom": "✍️ Custom",
        "access_granted_success": "✅ Free access granted",
        "access_extended_success": "✅ Access extended",
        "made_permanent_success": "✅ Access set to lifetime",
        "user_notified": "🔔 User notified",
        "invalid_days": "❌ Invalid number",
        "page_of": "Page {page} of {total}",
        "prev_page": "◀️ Prev",
        "next_page": "Next ▶️",

        # ===== Tariff management (pricing) =====
        "manage_tariffs": "🏷️ Tariffs & Pricing",
        "tariffs_admin_title": "🏷️ *Tariff Management*\n\nTap a plan to edit:",
        "add_new_plan": "➕ Add new plan",
        "edit_plan": "✏️ Edit plan",
        "plan_name_prompt": "📝 Enter plan name:\ne.g. Monthly, Quarterly, Lifetime",
        "plan_days_prompt": "⏱️ Access duration in days:\n• Enter a number (e.g. 30)\n• Or `permanent` for lifetime",
        "plan_price_prompt": "💰 Enter price in **TOMAN**:\ne.g. 500000",
        "plan_created_success": "✅ New plan created",
        "plan_updated_success": "✅ Plan updated",
        "plan_deleted": "🗑️ Plan deleted",
        "set_price": "💰 Set price",
        "set_duration": "⏱️ Set duration",
        "toggle_plan": "🔄 Enable/Disable",
        "delete_plan": "🗑️ Delete plan",
        "broadcast_new_plan": "📣 Notify all users",
        "broadcast_done": "📣 Notification sent",
        "price_set_success": "✅ Price set",
        "duration_set_success": "✅ Duration set",
        "enter_price_new": "💰 Enter new price (TOMAN):",
        "enter_duration_new": "⏱️ New duration in days (or permanent):",
        "confirm_delete_plan": "❓ Delete this plan?",
        "yes_delete": "✅ Yes, delete",
        "no_keep": "❌ Cancel",
        "plan_price_label": "💰 Price",
        "plan_duration_label": "⏱️ Duration",
        "plan_status_label": "📊 Status",
        "default_trial_days": "⏱️ Default trial for new users",
        "trial_days_prompt": "⏱️ Default free trial duration (days):\nEnter a number (0 to disable)",
        "trial_days_success": "✅ Default trial duration saved",
        "users_count": "users",
        "stats_line": "📊 Stats: {total} users | {permanent} lifetime | {timed} limited | {expired} expired",

        # ===== Discount coupons =====
        "manage_discounts": "🎟️ Discount Codes",
        "discounts_title": "🎟️ *Discount Code Management*",
        "add_discount": "➕ New discount code",
        "disc_all": "📋 All",
        "disc_active": "🟢 Active",
        "disc_public": "🌍 Public",
        "disc_personal": "👤 Personal",
        "disc_expired": "🔴 Expired",
        "disc_exhausted": "⛔ Exhausted",
        "disc_back_to_tariffs": "🔙 Back to tariffs",
        "disc_toggle": "🔄 Enable/Disable",
        "disc_edit": "✏️ Edit",
        "disc_usages": "📜 Usage history",
        "disc_stats": "📊 Stats",
        "disc_users": "👥 Allowed users",
        "disc_plans": "📦 Eligible plans",
        "disc_notify": "📣 Notify",
        "disc_delete": "🗑️ Delete code",
        "disc_percent": "٪ Percent",
        "disc_fixed": "💰 Fixed amount",
        "disc_scope_public": "🌍 Public (everyone)",
        "disc_scope_personal": "👤 Personal (specific users)",
        "disc_skip": "⏭️ Skip",
        "disc_unlimited": "♾️ Unlimited",
        "disc_confirm_create": "✅ Confirm & create",
        "disc_cancel": "❌ Cancel",
        "disc_autogen": "🎲 Auto-generate code",
        "disc_notify_users": "📣 Send to allowed users",
        "disc_broadcast": "📣 Notify all users",
        "disc_pick_done": "✅ Confirm selection",
        "disc_pick_search": "🔍 Search",
        "disc_pick_all": "🔙 Full list",
        "disc_pick_manual": "✍️ Manual ID entry",
        "disc_pick_from_list": "📋 Pick from list",
        "disc_pick_empty": "❌ No user selected yet! Tap user names.",
        "disc_pick_search_prompt": "🔍 Enter username or part of numeric ID:",
        "disc_copy_code": "📋 Copy code",
        "disc_code_detail": "🔍 Code details",
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
    """ارسال پیام - با retry مقاوم در برابر قطعی DNS/اینترنت"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = keyboard

    for attempt in range(3):
        try:
            resp = requests.post(f"{api}/sendMessage", json=data, timeout=15)
            if resp.status_code == 200:
                return True
            else:
                logger.error(f"❌ send_message HTTP {resp.status_code} attempt {attempt+1}: {resp.text[:200]}")
                if attempt < 2:
                    import time; time.sleep(1+attempt)
        except Exception as e:
            logger.error(f"❌ خطا در ارسال پیام (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                import time; time.sleep(2)
    return False


def edit_message(chat_id, message_id, text, keyboard=None):
    """ویرایش پیام - با retry"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if keyboard:
        data["reply_markup"] = keyboard

    for attempt in range(3):
        try:
            requests.post(f"{api}/editMessageText", json=data, timeout=15)
            return True
        except Exception as e:
            logger.error(f"❌ خطا در ویرایش پیام attempt {attempt+1}: {e}")
            if attempt < 2:
                import time; time.sleep(1)
    return False


def send_photo(chat_id, photo_id, caption=None, keyboard=None):
    """ارسال عکس - با retry"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    data = {"chat_id": chat_id, "photo": photo_id}
    if caption:
        data["caption"] = caption
    if keyboard:
        data["reply_markup"] = keyboard

    for attempt in range(3):
        try:
            requests.post(f"{api}/sendPhoto", json=data, timeout=20)
            return True
        except Exception as e:
            logger.error(f"❌ خطا در ارسال عکس attempt {attempt+1}: {e}")
            if attempt < 2:
                import time; time.sleep(1)
    return False


def send_video(chat_id, video_id, caption=None, keyboard=None):
    """ارسال ویدیو - با retry"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    data = {"chat_id": chat_id, "video": video_id}
    if caption:
        data["caption"] = caption
    if keyboard:
        data["reply_markup"] = keyboard

    for attempt in range(3):
        try:
            requests.post(f"{api}/sendVideo", json=data, timeout=20)
            return True
        except Exception as e:
            logger.error(f"❌ خطا در ارسال ویدیو attempt {attempt+1}: {e}")
            if attempt < 2:
                import time; time.sleep(1)
    return False


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
    """صفحه‌کلید منوی اصلی - دکمه‌های اصلی روی کیبورد (تحت کیبورد)"""
    keyboard_buttons = [
        [{"text": t(chat_id, "settings")}],
        [{"text": t(chat_id, "woocommerce_posts")}],
        [{"text": t(chat_id, "posting_management")}],
        [{"text": t(chat_id, "contents")}],
        [{"text": t(chat_id, "tariffs")}],
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
    """صفحه‌کلید منوی ادمین - دکمه‌های اصلی روی کیبورد (solid)"""
    is_super = auth_manager.is_super_admin(chat_id)

    # ردیف اول: دو دکمه اصلی کنار هم
    keyboard_buttons = [
        [
            {"text": t(chat_id, "manage_users")},
            {"text": t(chat_id, "manage_tariffs")},
        ],
        [{"text": t(chat_id, "view_access_requests")}],
    ]

    if is_super:
        keyboard_buttons.append([{"text": t(chat_id, "manage_admins")}])

    keyboard_buttons.extend([
        [
            {"text": t(chat_id, "activity_logs")},
            {"text": t(chat_id, "default_trial_days")},
        ],
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
    """نمایش منوی ادمین - پنل حرفه‌ای با آمار"""
    if not auth_manager.is_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    keyboard = create_admin_menu_keyboard(chat_id)

    lang = get_user_lang(chat_id)
    stats_line = ""
    try:
        stats = auth_manager.get_users_stats()
        stats_line = "\n" + t(chat_id, "stats_line").format(**stats)
    except Exception:
        pass

    if lang == "fa":
        msg = (
            "👮 *پنل مدیریت*\n"
            "━━━━━━━━━━━━━━━━\n"
            f"{stats_line}\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "یک گزینه را انتخاب کنید:\n\n"
            "👥 *مدیریت کاربران* — مشاهده پروفایل، هدیه و تمدید مدت دسترسی\n"
            "🏷️ *تعرفه‌ها* — تنظیم قیمت و مدت پلن‌ها + 🎟️ کدهای تخفیف\n"
            "📋 *درخواست‌ها* — بررسی درخواست‌های معلق\n"
            "⏱️ *تست پیش‌فرض* — مدت تست رایگان کاربران جدید"
        )
    else:
        msg = (
            "👮 *Admin Panel*\n"
            "━━━━━━━━━━━━━━━━\n"
            f"{stats_line}\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "Choose an option:"
        )

    send_message(chat_id, msg, keyboard)


USERS_PER_PAGE = 8


def _access_badge(user, lang="fa"):
    """نشان وضعیت دسترسی یک کاربر برای لیست"""
    atype = user.get('access_type') or 'permanent'
    until = user.get('access_until')
    if atype == 'permanent':
        return "♾️" if lang == "fa" else "♾️"
    if until:
        try:
            until_dt = datetime.strptime(until, '%Y-%m-%d %H:%M:%S')
            if datetime.now() > until_dt:
                return "🔴"
        except Exception:
            pass
    if atype == 'trial':
        return "🎁"
    return "🟢"


def handle_manage_users(chat_id, page=0, edit_id=None):
    """مدیریت کاربران - لیست صفحه‌بندی شده با دکمه‌های inline (شیشه‌ای)"""
    if not auth_manager.is_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    users = auth_manager.get_all_users()
    lang = get_user_lang(chat_id)

    if not users:
        msg = "👥 *کاربرانی وجود ندارد*" if lang == "fa" else "👥 *No users found*"
        send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))
        return

    total_pages = max(1, (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * USERS_PER_PAGE
    page_users = users[start:start + USERS_PER_PAGE]

    if lang == "fa":
        msg = t(chat_id, "users_list_title") + "\n"
        try:
            stats = auth_manager.get_users_stats()
            msg += "\n" + t(chat_id, "stats_line").format(**stats) + "\n"
        except Exception:
            pass
        msg += "\n"
    else:
        msg = t(chat_id, "users_list_title") + "\n\n"

    # دکمه‌های inline (شیشه‌ای) برای هر کاربر
    inline_rows = []
    for user in page_users:
        u_chat_id = user['chat_id']
        username = user['username'] or "Unknown"
        badge = _access_badge(user, lang)
        role_icon = "👨‍💼" if user['is_admin'] else "👤"
        label = f"{badge} {role_icon} {username} ({u_chat_id})"
        if len(label) > 60:
            label = label[:57] + "..."
        inline_rows.append([{"text": label, "callback_data": f"admin_user_{u_chat_id}"}])

    # صفحه‌بندی
    nav_row = []
    if page > 0:
        nav_row.append({"text": t(chat_id, "prev_page"), "callback_data": f"admin_users_page_{page - 1}"})
    nav_row.append({"text": t(chat_id, "page_of").format(page=page + 1, total=total_pages), "callback_data": "ignore"})
    if page < total_pages - 1:
        nav_row.append({"text": t(chat_id, "next_page"), "callback_data": f"admin_users_page_{page + 1}"})
    inline_rows.append(nav_row)

    # بازگشت inline به منوی ادمین
    inline_rows.append([{"text": t(chat_id, "back_to_admin_menu"), "callback_data": "admin_menu_back"}])

    keyboard = {"inline_keyboard": inline_rows}

    if edit_id:
        edit_message(chat_id, edit_id, msg, keyboard)
    else:
        send_message(chat_id, msg, keyboard)


def handle_user_detail(chat_id, target_chat_id, edit_id=None):
    """نمایش جزئیات یک کاربر - بخش‌های مختلف اطلاعات + مدت دسترسی"""
    if not auth_manager.is_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    lang = get_user_lang(chat_id)
    summary = auth_manager.get_access_summary(target_chat_id)
    info = summary['info'] if summary else auth_manager.get_user_info(target_chat_id)

    if not info:
        msg = t(chat_id, "user_not_found")
        if edit_id:
            edit_message(chat_id, edit_id, msg, {"inline_keyboard": [[{"text": t(chat_id, "back_to_admin_menu"), "callback_data": "admin_users_back"}]]})
        else:
            send_message(chat_id, msg, create_admin_menu_keyboard(chat_id))
        return

    username = info.get('username') or "Unknown"
    if info.get('is_admin'):
        role = "👨‍💼 ادمین" if lang == "fa" else "👨‍💼 Admin"
    else:
        role = "👤 کاربر عادی" if lang == "fa" else "👤 User"
    status = info.get('status', '?')

    if lang == "fa":
        msg = f"👤 *پروفایل کاربر*\n\n"
        msg += "═══ *اطلاعات پایه* ═══\n"
        msg += f"📛 نام: `{username}`\n"
        msg += f"🆔 آیدی: `{target_chat_id}`\n"
        msg += f"🔖 نقش: {role}\n"
        msg += f"📊 وضعیت: `{status}`\n"
        msg += f"📅 ثبت‌نام: {info.get('created_at', '-')}\n"
        if info.get('approved_at'):
            msg += f"✅ تایید: {info['approved_at']}\n"

        msg += "\n" + t(chat_id, "user_access_section") + "\n"
        if summary:
            # نمایش برچسب دسترسی
            atype = summary.get('access_type')
            if atype == 'permanent':
                badge = "♾️ *دائمی*"
            elif summary.get('expired'):
                badge = "🔴 *منقضی شده*"
            elif atype == 'trial':
                badge = "🎁 *تست رایگان*"
            else:
                badge = "🟢 *فعال (محدود)*"
            msg += f"نوع: {badge}\n"
            if summary.get('access_until'):
                msg += f"📅 معتبر تا: `{summary['access_until']}`\n"
            if summary.get('remaining_hours') is not None and not summary.get('expired'):
                hours = summary['remaining_hours']
                if hours >= 48:
                    msg += f"⏳ باقی‌مانده: {hours / 24:.1f} روز\n"
                else:
                    msg += f"⏳ باقی‌مانده: {hours:.1f} ساعت\n"
            elif summary.get('expired'):
                msg += "⚠️ دسترسی منقضی شده - کاربر نمی‌تواند از ربات استفاده کند\n"
        else:
            msg += "نامشخص\n"

        if info.get('access_note'):
            msg += f"📝 یادداشت: {info['access_note']}\n"
        if info.get('last_grant_at'):
            msg += f"🎁 آخرین هدیه: {info['last_grant_at']} ({info.get('last_grant_days', 0)} روز)\n"
    else:
        msg = f"👤 *User Profile*\n\n"
        msg += "═══ *Basic Info* ═══\n"
        msg += f"📛 Name: `{username}`\n"
        msg += f"🆔 ID: `{target_chat_id}`\n"
        msg += f"🔖 Role: {role}\n"
        msg += f"📊 Status: `{status}`\n"
        msg += f"📅 Joined: {info.get('created_at', '-')}\n"
        msg += "\n" + t(chat_id, "user_access_section") + "\n"
        if summary:
            atype = summary.get('access_type')
            if atype == 'permanent':
                badge = "♾️ *Lifetime*"
            elif summary.get('expired'):
                badge = "🔴 *Expired*"
            elif atype == 'trial':
                badge = "🎁 *Free trial*"
            else:
                badge = "🟢 *Active (limited)*"
            msg += f"Type: {badge}\n"
            if summary.get('access_until'):
                msg += f"📅 Valid until: `{summary['access_until']}`\n"
            if summary.get('remaining_hours') is not None and not summary.get('expired'):
                hours = summary['remaining_hours']
                if hours >= 48:
                    msg += f"⏳ Remaining: {hours / 24:.1f} days\n"
                else:
                    msg += f"⏳ Remaining: {hours:.1f} hours\n"
            elif summary.get('expired'):
                msg += "⚠️ Access expired\n"

    # دکمه‌های فرعی inline (شیشه‌ای)
    is_permanent = summary and summary.get('access_type') == 'permanent' and not summary.get('expired')
    action_rows = []

    # هدیه و تمدید برای همه کاربران (دائمی هم قابل تغییر است - با تایید)
    action_rows.append([
        {"text": t(chat_id, "grant_free_access"), "callback_data": f"admin_grant_{target_chat_id}"},
        {"text": t(chat_id, "extend_access"), "callback_data": f"admin_extend_{target_chat_id}"},
    ])
    if not is_permanent:
        action_rows.append([
            {"text": t(chat_id, "make_permanent"), "callback_data": f"admin_perm_{target_chat_id}"},
        ])
    else:
        # برای دائمی‌ها: دکمه تغییر صریح به مدت‌دار
        action_rows.append([
            {"text": "⏱️ تغییر به دسترسی مدت‌دار", "callback_data": f"admin_to_timed_{target_chat_id}"},
        ])

    action_rows.append([
        {"text": t(chat_id, "view_payments"), "callback_data": f"admin_payments_{target_chat_id}"},
        {"text": t(chat_id, "view_user_logs"), "callback_data": f"admin_ulogs_{target_chat_id}"},
    ])
    action_rows.append([
        {"text": t(chat_id, "back_to_admin_menu"), "callback_data": "admin_users_back"},
    ])

    keyboard = {"inline_keyboard": action_rows}

    if edit_id:
        edit_message(chat_id, edit_id, msg, keyboard)
    else:
        send_message(chat_id, msg, keyboard)


def handle_grant_free_menu(chat_id, target_chat_id, edit_id=None):
    """منوی انتخاب مدت دسترسی رایگان برای یک کاربر"""
    if not auth_manager.is_admin(chat_id):
        return
    lang = get_user_lang(chat_id)
    msg = t(chat_id, "choose_free_duration") + f"\n\n🆔 `{target_chat_id}`"
    options = [
        ("free_days_1", 1), ("free_days_3", 3), ("free_days_7", 7),
        ("free_days_14", 14), ("free_days_30", 30),
    ]
    inline_rows = []
    row = []
    for key, days in options:
        row.append({"text": t(chat_id, key), "callback_data": f"admin_grant_set_{target_chat_id}_{days}"})
        if len(row) == 3:
            inline_rows.append(row)
            row = []
    if row:
        inline_rows.append(row)
    inline_rows.append([
        {"text": t(chat_id, "custom"), "callback_data": f"admin_grant_custom_{target_chat_id}"}
    ])
    inline_rows.append([
        {"text": t(chat_id, "back_to_admin_menu"), "callback_data": f"admin_user_{target_chat_id}"}
    ])
    keyboard = {"inline_keyboard": inline_rows}
    if edit_id:
        edit_message(chat_id, edit_id, msg, keyboard)
    else:
        send_message(chat_id, msg, keyboard)


def handle_extend_menu(chat_id, target_chat_id, edit_id=None):
    """منوی انتخاب مدت تمدید"""
    if not auth_manager.is_admin(chat_id):
        return
    msg = t(chat_id, "choose_extend_duration") + f"\n\n🆔 `{target_chat_id}`"
    options = [("days_7", 7), ("days_30", 30), ("days_90", 90), ("days_180", 180)]
    inline_rows = []
    row = []
    for key, days in options:
        row.append({"text": t(chat_id, key), "callback_data": f"admin_extend_set_{target_chat_id}_{days}"})
        if len(row) == 2:
            inline_rows.append(row)
            row = []
    if row:
        inline_rows.append(row)
    inline_rows.append([
        {"text": t(chat_id, "custom"), "callback_data": f"admin_extend_custom_{target_chat_id}"}
    ])
    inline_rows.append([
        {"text": t(chat_id, "back_to_admin_menu"), "callback_data": f"admin_user_{target_chat_id}"}
    ])
    keyboard = {"inline_keyboard": inline_rows}
    if edit_id:
        edit_message(chat_id, edit_id, msg, keyboard)
    else:
        send_message(chat_id, msg, keyboard)


def _apply_access_change(admin_chat_id, target_chat_id, result, success_msg_key):
    """اعمال نتیجه تغییر دسترسی + اطلاع‌رسانی به کاربر"""
    lang = get_user_lang(admin_chat_id)
    if not result.get('success'):
        err = result.get('error', 'خطای نامشخص')
        send_message(admin_chat_id, f"❌ {err}", create_admin_menu_keyboard(admin_chat_id))
        return

    send_message(
        admin_chat_id,
        f"{t(admin_chat_id, success_msg_key)}\n🆔 `{target_chat_id}`\n{t(admin_chat_id, 'user_notified')}",
        {"inline_keyboard": [[{"text": t(admin_chat_id, "back_to_admin_menu"), "callback_data": f"admin_user_{target_chat_id}"}]]}
    )

    # 🔔 اطلاع‌رسانی به خود کاربر با دکمه تعرفه‌ها
    try:
        from auth_handlers import notify_access_changed
        notify_access_changed(
            target_chat_id,
            result.get('access_until'),
            result.get('access_type', 'timed'),
            config['messengers']['bale']['bot_token']
        )
    except Exception as e:
        logger.error(f"❌ خطا در اطلاع‌رسانی کاربر {target_chat_id}: {e}")


def handle_grant_free_set(admin_chat_id, target_chat_id, days):
    """اعطای دسترسی رایگان X روز"""
    # محافظ: کاربر دائمی نباید بدون تایید به محدود تبدیل شود
    summary = auth_manager.get_access_summary(target_chat_id)
    if summary and summary.get('access_type') == 'permanent' and not summary.get('expired'):
        send_message(
            admin_chat_id,
            "♾️ این کاربر دسترسی دائمی دارد!\nهدیه محدود، دسترسی دائمی او را تغییر می‌دهد.\n\nبرای تغییر، ابتدا از «تمدید مدت» استفاده نکنید — یا اگر می‌خواهید محدودش کنید، تایید کنید:",
            {"inline_keyboard": [[
                {"text": "✅ بله، محدود شود", "callback_data": f"admin_grant_force_{target_chat_id}_{days}"},
                {"text": t(admin_chat_id, "no_keep"), "callback_data": f"admin_user_{target_chat_id}"},
            ]]}
        )
        return
    result = auth_manager.grant_free_access(target_chat_id, days, admin_chat_id)
    _apply_access_change(admin_chat_id, target_chat_id, result, "access_granted_success")
    auth_manager.log_activity(admin_chat_id, "admin_grant", f"{days}d -> {target_chat_id}")


def handle_grant_force(admin_chat_id, target_chat_id, days):
    """اعطای محدود روی کاربر دائمی با تایید قبلی"""
    result = auth_manager.grant_free_access(target_chat_id, days, admin_chat_id, note=f"هدیه {days} روز (جایگزین دائمی)")
    _apply_access_change(admin_chat_id, target_chat_id, result, "access_granted_success")
    auth_manager.log_activity(admin_chat_id, "admin_grant_force", f"{days}d -> {target_chat_id}")


def handle_extend_set(admin_chat_id, target_chat_id, days):
    """تمدید مدت دسترسی X روز"""
    # محافظ: کاربر دائمی با تمدید، از دائمی به محدود تبدیل می‌شود - تایید بگیر
    summary = auth_manager.get_access_summary(target_chat_id)
    if summary and summary.get('access_type') == 'permanent' and not summary.get('expired'):
        send_message(
            admin_chat_id,
            "♾️ این کاربر دسترسی دائمی دارد!\n"
            f"تمدید {days} روز، دسترسی او را به «محدود تا {days} روز آینده» تغییر می‌دهد.\n\n"
            "آیا مطمئنید؟",
            {"inline_keyboard": [[
                {"text": f"✅ بله، {days} روز محدود شود", "callback_data": f"admin_extend_force_{target_chat_id}_{days}"},
                {"text": t(admin_chat_id, "no_keep"), "callback_data": f"admin_user_{target_chat_id}"},
            ]]}
        )
        return
    result = auth_manager.set_user_access(
        target_chat_id, 'timed',
        granted_by=admin_chat_id, grant_days=days,
        note=f"تمدید {days} روز توسط ادمین"
    )
    _apply_access_change(admin_chat_id, target_chat_id, result, "access_extended_success")
    auth_manager.log_activity(admin_chat_id, "admin_extend", f"{days}d -> {target_chat_id}")


def handle_extend_force(admin_chat_id, target_chat_id, days):
    """تبدیل دائمی به محدود با تمدید - با تایید قبلی"""
    result = auth_manager.set_user_access(
        target_chat_id, 'timed',
        granted_by=admin_chat_id, grant_days=days,
        note=f"تبدیل دائمی به {days} روز محدود (توسط ادمین)"
    )
    _apply_access_change(admin_chat_id, target_chat_id, result, "access_extended_success")
    auth_manager.log_activity(admin_chat_id, "admin_extend_force", f"{days}d -> {target_chat_id}")


def handle_to_timed_menu(admin_chat_id, target_chat_id, edit_id=None):
    """منوی تغییر صریح کاربر دائمی به مدت‌دار"""
    if not auth_manager.is_admin(admin_chat_id):
        return
    msg = (
        "⏱️ *تغییر به دسترسی مدت‌دار*\n\n"
        f"🆔 `{target_chat_id}`\n"
        "دسترسی دائمی این کاربر به مدت دلخواه محدود می‌شود.\n"
        "مدت را انتخاب کنید:"
    )
    options = [("days_7", 7), ("days_30", 30), ("days_90", 90), ("days_180", 180)]
    inline_rows = []
    row = []
    for key, days in options:
        row.append({"text": t(admin_chat_id, key), "callback_data": f"admin_extend_set_{target_chat_id}_{days}"})
        if len(row) == 2:
            inline_rows.append(row)
            row = []
    if row:
        inline_rows.append(row)
    inline_rows.append([
        {"text": t(admin_chat_id, "custom"), "callback_data": f"admin_extend_custom_{target_chat_id}"}
    ])
    inline_rows.append([
        {"text": t(admin_chat_id, "back_to_admin_menu"), "callback_data": f"admin_user_{target_chat_id}"}
    ])
    keyboard = {"inline_keyboard": inline_rows}
    if edit_id:
        edit_message(admin_chat_id, edit_id, msg, keyboard)
    else:
        send_message(admin_chat_id, msg, keyboard)


def handle_make_permanent(admin_chat_id, target_chat_id):
    """دائمی کردن دسترسی"""
    result = auth_manager.set_user_access(
        target_chat_id, 'permanent',
        granted_by=admin_chat_id,
        note="دائمی شده توسط ادمین"
    )
    _apply_access_change(admin_chat_id, target_chat_id, result, "made_permanent_success")
    auth_manager.log_activity(admin_chat_id, "admin_perm", f"-> {target_chat_id}")


def handle_user_payments(admin_chat_id, target_chat_id, edit_id=None):
    """نمایش پرداخت‌های کاربر"""
    payments = auth_manager.get_user_payments(target_chat_id)
    lang = get_user_lang(admin_chat_id)
    if not payments:
        msg = "🧾 پرداختی ثبت نشده" if lang == "fa" else "🧾 No payments"
    else:
        msg = f"🧾 *پرداخت‌های کاربر `{target_chat_id}`*\n\n" if lang == "fa" else f"🧾 *Payments for `{target_chat_id}`*\n\n"
        for p in payments[:15]:
            toman = (p['amount'] or 0) // 10
            status_icon = "✅" if p['status'] == 'completed' else "⏳" if p['status'] == 'pending' else "❌"
            msg += f"{status_icon} {toman:,} تومان | {p['status']}\n"
            if p.get('discount_code'):
                d_toman = (p.get('discount_amount') or 0) // 10
                o_toman = (p.get('original_amount') or p['amount'] or 0) // 10
                msg += f"   🎟️ {p['discount_code']} | تخفیف: {d_toman:,} (اصلی: {o_toman:,})\n"
            msg += f"   🆔 {p.get('payment_id') or '-'}\n"
            msg += f"   📅 {p.get('created_at') or '-'}\n\n"

    keyboard = {"inline_keyboard": [[
        {"text": t(admin_chat_id, "back_to_admin_menu"), "callback_data": f"admin_user_{target_chat_id}"}
    ]]}
    if edit_id:
        edit_message(admin_chat_id, edit_id, msg, keyboard)
    else:
        send_message(admin_chat_id, msg, keyboard)


def handle_user_logs(admin_chat_id, target_chat_id, edit_id=None):
    """نمایش فعالیت‌های اخیر کاربر"""
    logs = auth_manager.get_activity_log(chat_id=target_chat_id, limit=15)
    lang = get_user_lang(admin_chat_id)
    if not logs:
        msg = "📊 فعالیتی ثبت نشده" if lang == "fa" else "📊 No activity"
    else:
        msg = f"📊 *فعالیت‌های `{target_chat_id}`*\n\n" if lang == "fa" else f"📊 *Activity for `{target_chat_id}`*\n\n"
        for log in logs:
            msg += f"• {log['action']}"
            if log.get('details'):
                msg += f" | {log['details']}"
            msg += f"\n  ⏰ {log['timestamp']}\n"

    keyboard = {"inline_keyboard": [[
        {"text": t(admin_chat_id, "back_to_admin_menu"), "callback_data": f"admin_user_{target_chat_id}"}
    ]]}
    if edit_id:
        edit_message(admin_chat_id, edit_id, msg, keyboard)
    else:
        send_message(admin_chat_id, msg, keyboard)


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


# ========== مدیریت تعرفه‌ها (قیمت‌گذاری در ربات) ==========

def handle_manage_tariffs(chat_id, edit_id=None):
    """منوی مدیریت تعرفه‌ها - لیست پلن‌ها با دکمه‌های inline"""
    if not auth_manager.is_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return

    from auth_handlers import format_price_rial, format_duration_fa

    plans = auth_manager.get_plans(include_disabled=True)
    lang = get_user_lang(chat_id)

    if lang == "fa":
        msg = "🏷️ *مدیریت تعرفه‌ها*\n\nروی هر پلن برای ویرایش بزنید:\n"
    else:
        msg = "🏷️ *Tariff Management*\n\nTap a plan to edit:\n"

    if not plans:
        msg += "\n📭 پلنی وجود ندارد - پلن جدید بسازید."

    inline_rows = []
    for plan in plans:
        status = "✅" if plan['enabled'] else "⚪"
        dur = format_duration_fa(plan['duration_days'])
        price = format_price_rial(plan['price_rial'])
        label = f"{status} {plan['name']} | {dur} | {price}"
        if len(label) > 70:
            label = label[:67] + "..."
        inline_rows.append([{"text": label, "callback_data": f"admin_plan_{plan['id']}"}])

    inline_rows.append([{"text": t(chat_id, "add_new_plan"), "callback_data": "admin_plan_new"}])
    try:
        dover = auth_manager.get_discounts_overview()
        disc_label = f"{t(chat_id, 'manage_discounts')} ({dover['total']} کد)"
    except Exception:
        disc_label = t(chat_id, "manage_discounts")
    inline_rows.append([{"text": disc_label, "callback_data": "admin_disc_list"}])
    inline_rows.append([{"text": t(chat_id, "broadcast_new_plan"), "callback_data": "admin_broadcast_tariffs"}])
    inline_rows.append([{"text": t(chat_id, "back_to_admin_menu"), "callback_data": "admin_menu_back"}])

    keyboard = {"inline_keyboard": inline_rows}
    if edit_id:
        edit_message(chat_id, edit_id, msg, keyboard)
    else:
        send_message(chat_id, msg, keyboard)


def handle_plan_detail(chat_id, plan_id, edit_id=None):
    """نمایش جزئیات یک پلن + دکمه‌های ویرایش"""
    from auth_handlers import format_price_rial, format_duration_fa

    plan = auth_manager.get_plan(plan_id)
    if not plan:
        send_message(chat_id, t(chat_id, "user_not_found"), create_admin_menu_keyboard(chat_id))
        return

    lang = get_user_lang(chat_id)
    if lang == "fa":
        status = "✅ فعال" if plan['enabled'] else "⚪ غیرفعال"
        msg = (
            f"🏷️ *پلن: {plan['name']}*\n\n"
            f"💰 قیمت: {format_price_rial(plan['price_rial'])}\n"
            f"⏱️ مدت: {format_duration_fa(plan['duration_days'])}\n"
            f"📊 وضعیت: {status}\n"
            f"🆔 ID: `{plan['id']}`\n"
            f"📅 ایجاد: {plan.get('created_at') or '-'}\n\n"
            f"برای ویرایش یکی از دکمه‌ها را بزنید:"
        )
    else:
        status = "✅ Enabled" if plan['enabled'] else "⚪ Disabled"
        dur = "Lifetime" if plan['duration_days'] is None else f"{plan['duration_days']} days"
        toman = int(plan['price_rial']) // 10
        msg = (
            f"🏷️ *Plan: {plan['name']}*\n\n"
            f"💰 Price: {toman:,} TOMAN\n"
            f"⏱️ Duration: {dur}\n"
            f"📊 Status: {status}\n"
            f"🆔 ID: `{plan['id']}`\n\n"
            f"Choose an action:"
        )

    toggle_label = "⚪ غیرفعال کن" if plan['enabled'] else "✅ فعال کن" if lang == "fa" else "⚪ Disable" if plan['enabled'] else "✅ Enable"
    inline_rows = [
        [
            {"text": t(chat_id, "set_price"), "callback_data": f"admin_plan_price_{plan['id']}"},
            {"text": t(chat_id, "set_duration"), "callback_data": f"admin_plan_dur_{plan['id']}"},
        ],
        [
            {"text": toggle_label, "callback_data": f"admin_plan_toggle_{plan['id']}"},
            {"text": t(chat_id, "delete_plan"), "callback_data": f"admin_plan_del_{plan['id']}"},
        ],
        [
            {"text": t(chat_id, "broadcast_new_plan"), "callback_data": f"admin_plan_broadcast_{plan['id']}"},
        ],
        [
            {"text": t(chat_id, "back_to_admin_menu"), "callback_data": "admin_tariffs_back"},
        ],
    ]

    keyboard = {"inline_keyboard": inline_rows}
    if edit_id:
        edit_message(chat_id, edit_id, msg, keyboard)
    else:
        send_message(chat_id, msg, keyboard)


def handle_plan_create_start(chat_id):
    """شروع ویزارد ساخت پلن جدید"""
    if not auth_manager.is_admin(chat_id):
        return
    send_message(chat_id, t(chat_id, "plan_name_prompt"))
    set_state(chat_id, "awaiting_plan_name")


def handle_broadcast_tariffs(chat_id):
    """اطلاع‌رسانی تعرفه‌ها به همه کاربران"""
    if not auth_manager.is_admin(chat_id):
        return
    try:
        from auth_handlers import show_tariffs, get_active_plans
        bot_token = config['messengers']['bale']['bot_token']
        plans = get_active_plans()
        if not plans:
            send_message(chat_id, "📭 پلن فعالی وجود ندارد", create_admin_menu_keyboard(chat_id))
            return
        users = auth_manager.get_approved_users()
        sent = 0
        for user in users:
            uid = user['chat_id']
            if auth_manager.is_admin(uid):
                continue
            try:
                from auth_handlers import build_tariffs_text, build_tariffs_keyboard, send_message as auth_send
                msg = "🔔 *بروزرسانی تعرفه‌ها*\n\n" + build_tariffs_text("fa")
                kb = build_tariffs_keyboard("fa")
                if auth_send(uid, msg, kb, bot_token=bot_token):
                    sent += 1
            except Exception:
                pass
        send_message(chat_id, f"📣 اطلاع‌رسانی به {sent} کاربر ارسال شد", create_admin_menu_keyboard(chat_id))
        auth_manager.log_activity(chat_id, "broadcast_tariffs", f"sent={sent}")
    except Exception as e:
        logger.error(f"❌ خطا در اطلاع‌رسانی تعرفه‌ها: {e}")
        send_message(chat_id, f"❌ خطا: {e}", create_admin_menu_keyboard(chat_id))


def handle_default_trial_days_prompt(chat_id):
    """درخواست مدت تست پیش‌فرض"""
    if not auth_manager.is_admin(chat_id):
        return
    current = auth_manager.get_default_trial_days()
    lang = get_user_lang(chat_id)
    if lang == "fa":
        msg = f"⏱️ مدت تست رایگان پیش‌فرض فعلی: **{current} روز**\n\n" + t(chat_id, "trial_days_prompt")
    else:
        msg = f"⏱️ Current default trial: **{current} days**\n\n" + t(chat_id, "trial_days_prompt")
    send_message(chat_id, msg)
    set_state(chat_id, "awaiting_trial_days")


# ================================================================
# ========== مدیریت کدهای تخفیف (پنل ادمین) ==========
# ================================================================

DISCOUNTS_PER_PAGE = 6
DISC_FILTERS = ['all', 'active', 'public', 'personal', 'expired', 'exhausted']


def _disc_value_short(d):
    if d.get('discount_type') == 'percent':
        return f"٪{d.get('percent')}"
    return f"{int(d.get('amount_rial') or 0) // 10:,}ت"


def _disc_status_icon(status):
    return {'active': '🟢', 'inactive': '⚪', 'not_started': '⏳',
            'expired': '🔴', 'exhausted': '⛔'}.get(status, '•')


def _disc_scope_icon(d):
    return '👤' if d.get('scope') == 'personal' else '🌍'


def _disc_plan_names(plan_ids):
    if not plan_ids:
        return 'همه پلن‌ها'
    names = []
    for pid in plan_ids:
        try:
            p = auth_manager.get_plan(int(pid))
            names.append(p['name'] if p else f"#{pid} (حذف‌شده)")
        except Exception:
            names.append(f"#{pid}")
    return '، '.join(names)


def _disc_equivalents_text(disc_like):
    """پیش‌نمایش محاسبه خودکار معادل قیمت روی پلن‌های فعال"""
    try:
        plans = auth_manager.get_plans(include_disabled=False)
    except Exception:
        return ""
    if not plans:
        return ""
    lines = []
    for p in plans[:6]:
        price = int(p['price_rial'])
        disc, final = AuthManager.compute_discount_amount(disc_like, price)
        lines.append(f"• {p['name']}: {price // 10:,} ← 🎟️{disc // 10:,} ← 💳*{final // 10:,}*")
    more = f"\n… و {len(plans) - 6} پلن دیگر" if len(plans) > 6 else ""
    return "🧮 *معادل قیمت روی پلن‌ها:*\n" + "\n".join(lines) + more


def _disc_full_card(d, lang="fa"):
    """کارت کامل اطلاعات کد برای ادمین"""
    fa = (lang == "fa")
    if d['discount_type'] == 'percent':
        val_line = f"٪{d['percent']} درصدی"
        if d.get('max_discount_rial'):
            val_line += f"\n🎯 سقف تخفیف: {int(d['max_discount_rial']) // 10:,} تومان"
    else:
        val_line = f"{int(d['amount_rial'] or 0) // 10:,} تومان (مبلغی)"
    if d['scope'] == 'personal':
        scope_line = f"👤 شخصی ({len(d.get('allowed_users') or [])} کاربر مجاز)"
    else:
        scope_line = "🌍 عمومی (همه کاربران)"
    if d['total_limit'] is None:
        cap_line = f"♾️ نامحدود (استفاده‌شده: {d['used_count']})"
    else:
        cap_line = f"{d['used_count']} از {d['total_limit']} (باقی: {d.get('remaining', 0)})"
    first_line = "✅ بله" if d.get('first_purchase_only') else "❌ نه"
    min_line = f"{int(d['min_order_rial']) // 10:,} تومان" if d.get('min_order_rial') else "—"
    exp_line = d['expires_at'] if d.get('expires_at') else "♾️ نامحدود"
    start_line = d.get('starts_at') or "—"

    if fa:
        msg = (f"🎟️ *کد: `{d['code']}`*\n\n"
               f"{d.get('status_fa', '')} | {scope_line}\n")
        if d.get('title'):
            msg += f"📝 عنوان: {d['title']}\n"
        msg += (f"💸 تخفیف: {val_line}\n"
                f"🧾 کف خرید: {min_line}\n"
                f"📦 پلن‌ها: {_disc_plan_names(d.get('allowed_plans'))}\n"
                f"🔢 ظرفیت کل: {cap_line}\n"
                f"👤 سقف هر کاربر: {d.get('per_user_limit', 1)} بار\n"
                f"🛒 فقط خرید اول: {first_line}\n"
                f"▶️ شروع: {start_line}\n"
                f"⏰ انقضا: {exp_line}\n")
        if d.get('note'):
            msg += f"🗒️ یادداشت: {d['note']}\n"
        msg += f"\n🆔 ID: `{d['id']}` | 📅 ایجاد: {d.get('created_at') or '-'}"
        return msg
    return (f"🎟️ `{d['code']}`\n{d.get('status_fa', '')}\n"
            f"Type: {d['discount_type']} | Used: {d['used_count']}")


def _parse_chat_ids(text):
    """تجزیه آیدی‌های عددی جدا شده با کاما/فاصله/خط جدید + ارقام فارسی"""
    import re
    try:
        from auth_handlers import fa_to_en_digits as _fa
        s = _fa(text)
    except Exception:
        s = str(text or '')
    s = s.replace('،', ',').replace(';', ',')
    parts = re.split(r'[\s,]+', s)
    ids, bad = [], []
    for p in parts:
        p = (p or '').strip()
        if not p:
            continue
        try:
            v = int(p)
            if v <= 0:
                raise ValueError
            ids.append(v)
        except ValueError:
            bad.append(p)
    # حذف تکراری با حفظ ترتیب
    seen, uniq = set(), []
    for v in ids:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq, bad


def handle_discount_list(chat_id, page=0, dfilter='all', edit_id=None):
    """لیست کدهای تخفیف با فیلتر و صفحه‌بندی"""
    if not auth_manager.is_admin(chat_id):
        send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
        return
    if dfilter not in DISC_FILTERS:
        dfilter = 'all'
    lang = get_user_lang(chat_id)

    codes = auth_manager.list_discounts(status_filter=dfilter)
    try:
        over = auth_manager.get_discounts_overview()
    except Exception:
        over = None

    if lang == "fa":
        msg = t(chat_id, "discounts_title") + "\n"
        if over:
            msg += (f"\n📊 {over['total']} کد | 🟢{over['active_flag']} فعال | "
                    f"👤{over['personal']} شخصی | "
                    f"🎟️ {over['total_usages']} استفاده | "
                    f"💸 {over['total_discount_rial'] // 10:,} تومان تخفیف\n")
        msg += "\nروی هر کد برای جزئیات بزنید:\n"
    else:
        msg = t(chat_id, "discounts_title") + "\n\n"

    total_pages = max(1, (len(codes) + DISCOUNTS_PER_PAGE - 1) // DISCOUNTS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    page_codes = codes[page * DISCOUNTS_PER_PAGE:(page + 1) * DISCOUNTS_PER_PAGE]

    if not page_codes:
        msg += "\n📭 کدی در این دسته وجود ندارد."

    rows = []
    # ردیف‌های فیلتر
    rows.append([
        {"text": ("✅ " if dfilter == 'all' else "") + t(chat_id, "disc_all"),
         "callback_data": "admin_disc_filter_all"},
        {"text": ("✅ " if dfilter == 'active' else "") + t(chat_id, "disc_active"),
         "callback_data": "admin_disc_filter_active"},
    ])
    rows.append([
        {"text": ("✅ " if dfilter == 'public' else "") + t(chat_id, "disc_public"),
         "callback_data": "admin_disc_filter_public"},
        {"text": ("✅ " if dfilter == 'personal' else "") + t(chat_id, "disc_personal"),
         "callback_data": "admin_disc_filter_personal"},
    ])
    rows.append([
        {"text": ("✅ " if dfilter == 'expired' else "") + t(chat_id, "disc_expired"),
         "callback_data": "admin_disc_filter_expired"},
        {"text": ("✅ " if dfilter == 'exhausted' else "") + t(chat_id, "disc_exhausted"),
         "callback_data": "admin_disc_filter_exhausted"},
    ])
    for d in page_codes:
        if d['total_limit'] is None:
            use_s = f"{d['used_count']}/∞"
        else:
            use_s = f"{d['used_count']}/{d['total_limit']}"
        label = (f"{_disc_status_icon(d['status'])} {_disc_scope_icon(d)} "
                 f"{d['code']} | {_disc_value_short(d)} | {use_s}")
        if len(label) > 64:
            label = label[:61] + "..."
        rows.append([{"text": label, "callback_data": f"admin_disc_{d['id']}"}])

    # صفحه‌بندی
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": t(chat_id, "prev_page"),
                        "callback_data": f"admin_disc_page_{dfilter}_{page - 1}"})
        nav.append({"text": t(chat_id, "page_of").format(page=page + 1, total=total_pages),
                    "callback_data": "ignore"})
        if page < total_pages - 1:
            nav.append({"text": t(chat_id, "next_page"),
                        "callback_data": f"admin_disc_page_{dfilter}_{page + 1}"})
        rows.append(nav)

    rows.append([{"text": t(chat_id, "add_discount"), "callback_data": "admin_disc_new"}])
    rows.append([{"text": t(chat_id, "disc_back_to_tariffs"), "callback_data": "admin_tariffs_back"}])

    kb = {"inline_keyboard": rows}
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


def handle_discount_detail(chat_id, disc_id, edit_id=None):
    """جزئیات کامل یک کد + پیش‌نمایش معادل قیمت + اکشن‌ها"""
    if not auth_manager.is_admin(chat_id):
        return
    lang = get_user_lang(chat_id)
    d = auth_manager.get_discount(disc_id)
    if not d:
        send_message(chat_id, "❌ کد یافت نشد", create_admin_menu_keyboard(chat_id))
        return

    msg = _disc_full_card(d, lang)
    eq = _disc_equivalents_text(d)
    if eq:
        msg += "\n\n" + eq

    toggle_label = "⚪ غیرفعال کن" if d['is_active'] else "✅ فعال کن"
    if lang != "fa":
        toggle_label = "⚪ Disable" if d['is_active'] else "✅ Enable"
    n_users = len(d.get('allowed_users') or [])
    rows = [
        [
            {"text": f"{t(chat_id, 'disc_copy_code')}: {d['code']}",
             "copy_text": {"text": d['code']}},
        ],
        [
            {"text": toggle_label, "callback_data": f"admin_disc_toggle_{d['id']}"},
            {"text": t(chat_id, "disc_edit"), "callback_data": f"admin_disc_edit_{d['id']}"},
        ],
        [
            {"text": f"{t(chat_id, 'disc_users')} ({n_users})",
             "callback_data": f"admin_disc_users_{d['id']}"},
            {"text": t(chat_id, "disc_plans"), "callback_data": f"admin_disc_plans_{d['id']}"},
        ],
        [
            {"text": t(chat_id, "disc_usages"), "callback_data": f"admin_disc_usages_{d['id']}"},
            {"text": t(chat_id, "disc_stats"), "callback_data": f"admin_disc_stats_{d['id']}"},
        ],
        [
            {"text": t(chat_id, "disc_notify"), "callback_data": f"admin_disc_notify_{d['id']}"},
            {"text": t(chat_id, "disc_delete"), "callback_data": f"admin_disc_del_{d['id']}"},
        ],
        [
            {"text": "🎟️ لیست کدها", "callback_data": "admin_disc_back_list"},
            {"text": t(chat_id, "disc_back_to_tariffs"), "callback_data": "admin_tariffs_back"},
        ],
    ]
    kb = {"inline_keyboard": rows}
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


# ---------- ویزارد ساخت کد ----------

def handle_discount_create_start(chat_id):
    if not auth_manager.is_admin(chat_id):
        return
    lang = get_user_lang(chat_id)
    set_state(chat_id, "awaiting_disc_code", disc={})
    if lang == "fa":
        msg = ("🎟️ *ساخت کد تخفیف جدید — مرحله ۱ از ۱۰*\n\n"
               "🔑 *کد را وارد کنید:*\n"
               "• 3 تا 32 کاراکتر (حروف، عدد، - و _)\n"
               "• مثال: `SUMMER20` یا `VIP-50000`\n\n"
               "💡 یا دکمه تولید خودکار را بزنید:")
    else:
        msg = "🎟️ *New coupon — step 1/10*\n\n🔑 Enter the code (3-32 chars):"
    kb = {"inline_keyboard": [
        [{"text": t(chat_id, "disc_autogen"), "callback_data": "admin_disc_autogen"}],
        [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
    ]}
    send_message(chat_id, msg, kb)


def _disc_send_type_menu(chat_id, code):
    set_state(chat_id, "awaiting_disc_type", disc=get_state(chat_id)[1].get('disc', {}))
    lang = get_user_lang(chat_id)
    if lang == "fa":
        msg = (f"🎟️ کد: `{code}`\n\n"
               "💸 *مرحله ۲: نوع تخفیف؟*\n\n"
               "٪ *درصدی:* مثلاً ۲۰٪ از مبلغ هر پلن کم می‌شود\n"
               "💰 *مبلغی:* مبلغ ثابت تومان از قیمت کم می‌شود")
    else:
        msg = f"🎟️ `{code}`\n\n💸 Step 2: discount type?"
    kb = {"inline_keyboard": [
        [
            {"text": t(chat_id, "disc_percent"), "callback_data": "admin_disc_type_percent"},
            {"text": t(chat_id, "disc_fixed"), "callback_data": "admin_disc_type_fixed"},
        ],
        [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
    ]}
    send_message(chat_id, msg, kb)


def _disc_send_scope_menu(chat_id):
    st = get_state(chat_id)[1].get('disc', {})
    set_state(chat_id, "awaiting_disc_scope", disc=st)
    lang = get_user_lang(chat_id)
    if lang == "fa":
        msg = ("🌍👤 *مرحله ۵: دامنه کد؟*\n\n"
               "🌍 *عمومی:* همه کاربران می‌توانند استفاده کنند\n"
               "👤 *شخصی:* فقط کاربران خاصی که شما مشخص می‌کنید "
               "(بقیه خطای «این کد برای شما نیست» می‌گیرند)")
    else:
        msg = "🌍👤 Step 5: scope?"
    kb = {"inline_keyboard": [
        [{"text": t(chat_id, "disc_scope_public"), "callback_data": "admin_disc_scope_public"}],
        [{"text": t(chat_id, "disc_scope_personal"), "callback_data": "admin_disc_scope_personal"}],
        [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
    ]}
    send_message(chat_id, msg, kb)


def _disc_send_plans_menu(chat_id, edit_id=None, for_edit=False):
    """منوی چندانتخابی پلن‌ها (ویزارد یا ویرایش)"""
    lang = get_user_lang(chat_id)
    state_data = get_state(chat_id)[1]
    if for_edit:
        selected = [int(x) for x in state_data.get('selected', [])]
    else:
        selected = [int(x) for x in state_data.get('disc', {}).get('allowed_plan_ids', [])]
    plans = auth_manager.get_plans(include_disabled=True)
    prefix = "admin_disc_eplan_toggle_" if for_edit else "admin_disc_plan_toggle_"

    if lang == "fa":
        if for_edit:
            msg = "📦 *پلن‌های مشمول:*\n\nروی هر پلن بزنید تا انتخاب/حذف شود.\nاگر هیچ‌کدام انتخاب نشود = *همه پلن‌ها*"
        else:
            msg = ("📦 *مرحله ۶: پلن‌های مشمول؟*\n\n"
                   "روی هر پلن بزنید تا انتخاب/حذف شود.\n"
                   "اگر هیچ‌کدام انتخاب نشود = *همه پلن‌ها* ✅")
    else:
        msg = "📦 Select eligible plans (none = all):"

    rows = []
    for p in plans:
        mark = "✅" if p['id'] in selected else "⚪"
        en = "" if p['enabled'] else " (غیرفعال)"
        label = f"{mark} {p['name']}{en}"
        rows.append([{"text": label[:60], "callback_data": f"{prefix}{p['id']}"}])
    if for_edit:
        all_label = "🌍 همه پلن‌ها" if lang == "fa" else "🌍 All plans"
        done_label = "✅ ثبت" if lang == "fa" else "✅ Save"
        rows.append([
            {"text": all_label, "callback_data": "admin_disc_eplans_all"},
            {"text": done_label, "callback_data": "admin_disc_eplans_done"},
        ])
        if state_data.get('disc_id'):
            cancel_label = "❌ انصراف (بدون تغییر)" if lang == "fa" else "❌ Cancel"
            rows.append([{"text": cancel_label, "callback_data": "admin_disc_eplans_cancel"}])
    else:
        rows.append([
            {"text": "🌍 همه پلن‌ها", "callback_data": "admin_disc_plans_all"},
            {"text": "✅ ثبت و ادامه", "callback_data": "admin_disc_plans_done"},
        ])
        rows.append([{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}])
    kb = {"inline_keyboard": rows}
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


def _disc_send_confirm(chat_id):
    """پیش‌نمایش نهایی ویزارد + دکمه ثبت"""
    lang = get_user_lang(chat_id)
    st = get_state(chat_id)[1].get('disc', {})
    set_state(chat_id, "awaiting_disc_confirm", disc=st)

    disc_like = {
        'discount_type': st.get('discount_type'),
        'percent': st.get('percent'),
        'amount_rial': st.get('amount_rial', 0),
        'max_discount_rial': st.get('max_discount_rial'),
    }
    if st.get('discount_type') == 'percent':
        val = f"٪{st.get('percent')} درصدی"
        if st.get('max_discount_rial'):
            val += f" (سقف {st['max_discount_rial'] // 10:,} تومان)"
    else:
        val = f"{st.get('amount_rial', 0) // 10:,} تومان (مبلغی)"
    scope = "👤 شخصی" if st.get('scope') == 'personal' else "🌍 عمومی"
    users_s = ""
    if st.get('scope') == 'personal':
        users_s = f"\n👥 کاربران: {', '.join(str(x) for x in st.get('allowed_chat_ids', []))}"
    total = "♾️ نامحدود" if st.get('total_limit') is None else str(st['total_limit'])
    exp = st.get('expires_label') or (st.get('expires_at') or "♾️ نامحدود")
    first = "✅ بله" if st.get('first_purchase_only') else "❌ نه"
    min_s = f"{st['min_order_rial'] // 10:,} تومان" if st.get('min_order_rial') else "—"

    if lang == "fa":
        msg = ("🧾 *تأیید نهایی کد تخفیف*\n\n"
               f"🔑 کد: `{st.get('code')}`\n"
               f"💸 تخفیف: {val}\n"
               f"📡 دامنه: {scope}{users_s}\n"
               f"📦 پلن‌ها: {_disc_plan_names(st.get('allowed_plan_ids'))}\n"
               f"🔢 ظرفیت کل: {total}\n"
               f"👤 سقف هر کاربر: {st.get('per_user_limit', 1)} بار\n"
               f"⏰ انقضا: {exp}\n"
               f"🧾 کف خرید: {min_s}\n"
               f"🛒 فقط خرید اول: {first}\n")
        if st.get('title'):
            msg += f"📝 عنوان: {st['title']}\n"
        eq = _disc_equivalents_text(disc_like)
        if eq:
            msg += "\n" + eq
        msg += "\n\nثبت شود؟"
    else:
        msg = f"🧾 Confirm coupon `{st.get('code')}`?"
    kb = {"inline_keyboard": [
        [
            {"text": t(chat_id, "disc_confirm_create"), "callback_data": "admin_disc_confirm"},
            {"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"},
        ]
    ]}
    send_message(chat_id, msg, kb)


# ---------- پیکر انتخاب کاربر (دکمه شیشه‌ای چندانتخابی) ----------

USERPICK_PER_PAGE = 8
USERPICK_STATES = ("awaiting_disc_userpick", "awaiting_disc_euserpick", "awaiting_disc_uaddpick")


def _filter_pick_users(users, query):
    """فیلتر کاربران بر اساس نام کاربری/آیدی - خالص و قابل تست"""
    q = (query or "").strip().lower().lstrip("@")
    if not q:
        return list(users)
    try:
        from auth_handlers import fa_to_en_digits
        q = fa_to_en_digits(q)
    except Exception:
        pass
    out = []
    for u in users:
        uname = (u.get('username') or "").lower()
        cid = str(u.get('chat_id') or "")
        if q in uname or q in cid:
            out.append(u)
    return out


def _build_userpick_keyboard(chat_id, page_users, selected, page, total_pages, query):
    """ساخت کیبورد پیکر - خالص و قابل تست"""
    selected = set(int(x) for x in (selected or []))
    rows = []
    for u in page_users:
        uid = u['chat_id']
        mark = "✅" if uid in selected else "⚪"
        uname = u.get('username') or "—"
        role = "👨‍💼" if u.get('is_admin') else "👤"
        label = f"{mark} {role} {uname} ({uid})"
        if len(label) > 60:
            label = label[:57] + "..."
        rows.append([{"text": label, "callback_data": f"admin_disc_upick_{uid}"}])
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": t(chat_id, "prev_page"),
                        "callback_data": f"admin_disc_upage_{page - 1}"})
        nav.append({"text": t(chat_id, "page_of").format(page=page + 1, total=total_pages),
                    "callback_data": "ignore"})
        if page < total_pages - 1:
            nav.append({"text": t(chat_id, "next_page"),
                        "callback_data": f"admin_disc_upage_{page + 1}"})
        rows.append(nav)
    if query:
        q_short = query if len(query) <= 18 else query[:15] + "..."
        rows.append([{"text": f"{t(chat_id, 'disc_pick_all')} (🔍 {q_short})",
                      "callback_data": "admin_disc_uall"}])
    else:
        rows.append([{"text": t(chat_id, "disc_pick_search"),
                      "callback_data": "admin_disc_usearch"}])
    rows.append([
        {"text": f"{t(chat_id, 'disc_pick_done')} ({len(selected)})",
         "callback_data": "admin_disc_udone"},
    ])
    rows.append([
        {"text": t(chat_id, "disc_pick_manual"), "callback_data": "admin_disc_umanual"},
        {"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_ucancel"},
    ])
    return {"inline_keyboard": rows}


def _restore_pick_state(chat_id, search_state):
    """بازگردانی state پیکر از داخل state جستجو"""
    pick = search_state.get('pick_state', 'awaiting_disc_userpick')
    if pick not in USERPICK_STATES:
        pick = 'awaiting_disc_userpick'
    new = {'selected': search_state.get('selected', []),
           'page': search_state.get('page', 0),
           'query': search_state.get('query', '')}
    if 'disc' in search_state:
        new['disc'] = search_state['disc']
    if 'disc_id' in search_state:
        new['disc_id'] = search_state['disc_id']
    set_state(chat_id, pick, **new)
    return pick


def handle_userpick_menu(chat_id, edit_id=None):
    """رندر منوی انتخاب کاربر بر اساس state فعلی (هر ۳ حالت ویزارد/تبدیل/افزودن)"""
    if not auth_manager.is_admin(chat_id):
        return
    st_name, st = get_state(chat_id)
    if st_name not in USERPICK_STATES:
        return
    lang = get_user_lang(chat_id)
    selected = [int(x) for x in st.get('selected', [])]
    query = st.get('query', '') or ''

    users = auth_manager.get_all_users()
    if st_name == "awaiting_disc_uaddpick":
        # در حالت افزودن، اعضای فعلی را از لیست حذف کن (تکراری انتخاب نشود)
        try:
            current = set(auth_manager.get_discount_users(st.get('disc_id')))
            users = [u for u in users if u['chat_id'] not in current]
        except Exception:
            pass
    users = _filter_pick_users(users, query)

    total_pages = max(1, (len(users) + USERPICK_PER_PAGE - 1) // USERPICK_PER_PAGE)
    page = max(0, min(int(st.get('page', 0)), total_pages - 1))
    st['page'] = page
    page_users = users[page * USERPICK_PER_PAGE:(page + 1) * USERPICK_PER_PAGE]
    kb = _build_userpick_keyboard(chat_id, page_users, selected, page, total_pages, query)

    if lang == "fa":
        if st_name == "awaiting_disc_userpick":
            title = "👤 *کد شخصی — انتخاب کاربران مجاز:*\n\n"
        elif st_name == "awaiting_disc_euserpick":
            title = "👤 *تبدیل به شخصی — انتخاب کاربران مجاز:*\n\n"
        else:
            title = "➕ *افزودن کاربر مجاز:*\n\n"
        msg = title + "روی هر کاربر بزنید تا انتخاب/حذف شود (چندنفره).\n"
        msg += f"✅ انتخاب‌شده: *{len(selected)} نفر*\n"
        if query:
            msg += f"🔍 جستجو: `{query}` ({len(users)} نتیجه)\n"
        if not page_users:
            msg += "\n📭 کاربری در این صفحه نیست."
        msg += ("\n\n💡 کاربرانی که هنوز ربات را /start نکرده‌اند در لیست نیستند؛\n"
                "برای آن‌ها «✍️ ورود دستی آیدی» را بزنید.")
    else:
        msg = f"👥 *Select users* ({len(selected)} selected)\n\nTap to toggle."
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


MANUAL2PICK = {"awaiting_disc_users": "awaiting_disc_userpick",
                "awaiting_disc_eusers": "awaiting_disc_euserpick",
                "awaiting_disc_useradd": "awaiting_disc_uaddpick"}
PICK2MANUAL = {v: k for k, v in MANUAL2PICK.items()}


def handle_userpick_callback(chat_id, message_id, rest):
    """روت کال‌بک‌های پیکر انتخاب کاربر (تاگل، صفحه، جستجو، ورود دستی، تأیید، لغو)"""
    if not auth_manager.is_admin(chat_id):
        return
    st_name, st = get_state(chat_id)

    # --- بازگشت به لیست (از حالت دستی یا جستجو) ---
    if rest == "upickopen":
        if st_name == "awaiting_disc_usearch":
            _restore_pick_state(chat_id, st)
        elif st_name in MANUAL2PICK:
            new = {'selected': st.get('pick_selected', []),
                   'page': st.get('pick_page', 0),
                   'query': st.get('pick_query', '')}
            if 'disc' in st:
                new['disc'] = st['disc']
            if 'disc_id' in st:
                new['disc_id'] = st['disc_id']
            set_state(chat_id, MANUAL2PICK[st_name], **new)
        else:
            return
        handle_userpick_menu(chat_id, edit_id=message_id)
        return

    # --- لغو (حساس به زمینه) ---
    if rest == "ucancel":
        origin = st_name
        if st_name == "awaiting_disc_usearch":
            origin = st.get('pick_state', 'awaiting_disc_userpick')
        elif st_name in MANUAL2PICK:
            origin = MANUAL2PICK[st_name]
        did = st.get('disc_id')
        clear_state(chat_id)
        if origin == "awaiting_disc_euserpick" and did:
            handle_discount_detail(chat_id, did)
        elif origin == "awaiting_disc_uaddpick" and did:
            handle_discount_users(chat_id, did)
        else:
            handle_discount_list(chat_id)
        return

    # --- از اینجا فقط در یکی از ۳ state پیکر ---
    if st_name not in USERPICK_STATES:
        return
    selected = [int(x) for x in st.get('selected', [])]

    # --- تاگل انتخاب ---
    if rest.startswith("upick_"):
        try:
            uid = int(rest.replace("upick_", "", 1))
        except ValueError:
            return
        if uid in selected:
            selected.remove(uid)
        else:
            selected.append(uid)
        st['selected'] = selected
        set_state(chat_id, st_name, **st)
        handle_userpick_menu(chat_id, edit_id=message_id)
        return

    # --- صفحه‌بندی ---
    if rest.startswith("upage_"):
        try:
            st['page'] = max(0, int(rest.replace("upage_", "", 1)))
        except ValueError:
            return
        set_state(chat_id, st_name, **st)
        handle_userpick_menu(chat_id, edit_id=message_id)
        return

    # --- بازگشت به لیست کامل (حذف فیلتر جستجو) ---
    if rest == "uall":
        st['query'] = ''
        st['page'] = 0
        set_state(chat_id, st_name, **st)
        handle_userpick_menu(chat_id, edit_id=message_id)
        return

    # --- جستجو ---
    if rest == "usearch":
        new = {'pick_state': st_name, 'selected': selected,
               'page': st.get('page', 0), 'query': st.get('query', '')}
        if 'disc' in st:
            new['disc'] = st['disc']
        if 'disc_id' in st:
            new['disc_id'] = st['disc_id']
        set_state(chat_id, "awaiting_disc_usearch", **new)
        kb = {"inline_keyboard": [
            [{"text": t(chat_id, "disc_pick_from_list"),
              "callback_data": "admin_disc_upickopen"}],
            [{"text": t(chat_id, "disc_cancel"),
              "callback_data": "admin_disc_ucancel"}],
        ]}
        edit_message(chat_id, message_id, t(chat_id, "disc_pick_search_prompt"), kb)
        return

    # --- ورود دستی آیدی (برای کاربران ثبت‌نشده) ---
    if rest == "umanual":
        new = {'pick_selected': selected,
               'pick_page': st.get('page', 0),
               'pick_query': st.get('query', '')}
        if 'disc' in st:
            new['disc'] = st['disc']
        if 'disc_id' in st:
            new['disc_id'] = st['disc_id']
        set_state(chat_id, PICK2MANUAL[st_name], **new)
        if get_user_lang(chat_id) == "fa":
            prompt = ("✍️ *ورود دستی آیدی:*\n\n"
                      "آیدی عددی کاربران را با کاما یا خط جدید جدا کنید:\n"
                      "مثال: `123456789, 987654321`\n\n"
                      "💡 برای کاربرانی که هنوز /start نکرده‌اند هم می‌توانید "
                      "از قبل آیدی بدهید (وقتی عضو شوند کد کار می‌کند).")
        else:
            prompt = "✍️ Enter numeric chat IDs separated by comma:"
        kb = {"inline_keyboard": [
            [{"text": t(chat_id, "disc_pick_from_list"),
              "callback_data": "admin_disc_upickopen"}],
            [{"text": t(chat_id, "disc_cancel"),
              "callback_data": "admin_disc_ucancel"}],
        ]}
        edit_message(chat_id, message_id, prompt, kb)
        return

    # --- تأیید نهایی ---
    if rest == "udone":
        if not selected:
            send_message(chat_id, t(chat_id, "disc_pick_empty"))
            return
        if st_name == "awaiting_disc_userpick":
            disc = st.get('disc', {})
            disc['allowed_chat_ids'] = selected
            set_state(chat_id, "awaiting_disc_plans", disc=disc)
            edit_message(chat_id, message_id, f"✅ {len(selected)} کاربر انتخاب شد.")
            _disc_send_plans_menu(chat_id)
        elif st_name == "awaiting_disc_euserpick":
            did = st.get('disc_id')
            auth_manager.update_discount(did, scope='personal')
            res = auth_manager.add_discount_users(did, selected)
            clear_state(chat_id)
            if res.get('success'):
                auth_manager.log_activity(chat_id, "disc_users_add",
                                          f"{did} +{res.get('added', 0)}")
                send_message(chat_id,
                             f"✅ کد شخصی شد و {res.get('added', 0)} کاربر اضافه شد.")
            else:
                send_message(chat_id, f"❌ {res.get('error', 'خطا')}")
            handle_discount_detail(chat_id, did)
        else:  # awaiting_disc_uaddpick
            did = st.get('disc_id')
            res = auth_manager.add_discount_users(did, selected)
            clear_state(chat_id)
            if res.get('success'):
                auth_manager.log_activity(chat_id, "disc_users_add",
                                          f"{did} +{res.get('added', 0)}")
                send_message(chat_id, f"✅ {res.get('added', 0)} کاربر اضافه شد.")
            else:
                send_message(chat_id, f"❌ {res.get('error', 'خطا')}")
            handle_discount_users(chat_id, did)
        return


# ---------- اکشن‌های کد ----------

def handle_discount_toggle(chat_id, disc_id):
    if not auth_manager.is_admin(chat_id):
        return
    d = auth_manager.get_discount(disc_id)
    if not d:
        return
    auth_manager.set_discount_active(disc_id, not d['is_active'])
    auth_manager.log_activity(chat_id, "disc_toggle", f"{disc_id} -> {not d['is_active']}")
    handle_discount_detail(chat_id, disc_id)


def handle_discount_delete_ask(chat_id, disc_id, edit_id=None):
    if not auth_manager.is_admin(chat_id):
        return
    d = auth_manager.get_discount(disc_id)
    if not d:
        return
    lang = get_user_lang(chat_id)
    if lang == "fa":
        msg = (f"🗑️ حذف کد `{d['code']}`؟\n\n"
               f"⚠️ تاریخچه {d['used_count']} استفاده برای گزارش‌ها *حفظ* می‌شود، "
               f"اما کد دیگر قابل استفاده نخواهد بود.")
    else:
        msg = f"🗑️ Delete `{d['code']}`?"
    kb = {"inline_keyboard": [[
        {"text": t(chat_id, "yes_delete"), "callback_data": f"admin_disc_delconfirm_{disc_id}"},
        {"text": t(chat_id, "no_keep"), "callback_data": f"admin_disc_{disc_id}"},
    ]]}
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


def handle_discount_delete_confirm(chat_id, disc_id):
    if not auth_manager.is_admin(chat_id):
        return
    res = auth_manager.delete_discount(disc_id)
    if res.get('success'):
        auth_manager.log_activity(chat_id, "disc_delete", f"{res.get('code')}")
        send_message(chat_id,
                     f"🗑️ کد `{res.get('code')}` حذف شد.\n"
                     f"📜 تاریخچه {res.get('usages_kept', 0)} استفاده حفظ شد.")
    else:
        send_message(chat_id, f"❌ {res.get('error', 'خطا')}")
    handle_discount_list(chat_id)


def handle_discount_edit_menu(chat_id, disc_id, edit_id=None):
    if not auth_manager.is_admin(chat_id):
        return
    d = auth_manager.get_discount(disc_id)
    if not d:
        return
    lang = get_user_lang(chat_id)
    if d['discount_type'] == 'percent':
        val_btn = f"٪ ویرایش درصد (فعلی: ٪{d['percent']})"
    else:
        val_btn = f"💰 ویرایش مبلغ (فعلی: {int(d['amount_rial']) // 10:,}ت)"
    scope_btn = "🌍 عمومی کن" if d['scope'] == 'personal' else "👤 شخصی کن"
    first_btn = f"🛒 فقط-خرید-اول: {'✅' if d['first_purchase_only'] else '❌'}"
    rows = [
        [{"text": val_btn, "callback_data": f"admin_disc_efield_value_{disc_id}"}],
    ]
    if d['discount_type'] == 'percent':
        cap_s = f"{int(d['max_discount_rial']) // 10:,}ت" if d.get('max_discount_rial') else "—"
        rows.append([{"text": f"🎯 سقف تخفیف (فعلی: {cap_s})",
                      "callback_data": f"admin_disc_efield_cap_{disc_id}"}])
    min_s = f"{int(d['min_order_rial']) // 10:,}ت" if d.get('min_order_rial') else "—"
    tot_s = "∞" if d['total_limit'] is None else str(d['total_limit'])
    rows.append([{"text": f"🧾 کف خرید (فعلی: {min_s})",
                  "callback_data": f"admin_disc_efield_min_{disc_id}"}])
    rows.append([
        {"text": f"🔢 سقف کل (فعلی: {tot_s})",
         "callback_data": f"admin_disc_efield_total_{disc_id}"},
        {"text": f"👤 سقف هر کاربر ({d['per_user_limit']})",
         "callback_data": f"admin_disc_efield_peruser_{disc_id}"},
    ])
    rows.append([{"text": "⏰ ویرایش انقضا",
                  "callback_data": f"admin_disc_efield_expiry_{disc_id}"}])
    rows.append([{"text": "📝 ویرایش عنوان",
                  "callback_data": f"admin_disc_efield_title_{disc_id}"}])
    rows.append([
        {"text": scope_btn, "callback_data": f"admin_disc_escope_{disc_id}"},
        {"text": first_btn, "callback_data": f"admin_disc_efirst_{disc_id}"},
    ])
    rows.append([{"text": "🔙 بازگشت به جزئیات",
                  "callback_data": f"admin_disc_{disc_id}"}])
    msg = f"✏️ *ویرایش کد `{d['code']}`*\n\nکدام فیلد؟" if lang == "fa" else f"✏️ Edit `{d['code']}`"
    kb = {"inline_keyboard": rows}
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


def handle_discount_usages(chat_id, disc_id, edit_id=None):
    if not auth_manager.is_admin(chat_id):
        return
    d = auth_manager.get_discount(disc_id)
    if not d:
        return
    usages = auth_manager.get_discount_usages(disc_id, limit=15)
    lang = get_user_lang(chat_id)
    if lang == "fa":
        msg = f"📜 *تاریخچه استفاده `{d['code']}`* (مجموع: {d['used_count']})\n\n"
        if not usages:
            msg += "📭 هنوز استفاده‌ای ثبت نشده."
        for u in usages:
            who = f"@{u['username']}" if u.get('username') else str(u['chat_id'])
            msg += (f"• {who} (`{u['chat_id']}`)\n"
                    f"  📦 {u.get('plan_name') or '-'} | "
                    f"💰{u['original_rial'] // 10:,} ← 🎟️{u['discount_rial'] // 10:,} "
                    f"← 💳{u['final_rial'] // 10:,}\n"
                    f"  ⏰ {u['created_at']}\n")
    else:
        msg = f"📜 Usages of `{d['code']}`: {d['used_count']}"
    kb = {"inline_keyboard": [[
        {"text": "🔙 بازگشت به جزئیات", "callback_data": f"admin_disc_{disc_id}"}
    ]]}
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


def handle_discount_stats(chat_id, disc_id, edit_id=None):
    if not auth_manager.is_admin(chat_id):
        return
    s = auth_manager.get_discount_stats(disc_id)
    if not s:
        return
    d = s['discount']
    lang = get_user_lang(chat_id)
    if lang == "fa":
        msg = (f"📊 *آمار کد `{d['code']}`*\n\n"
               f"🔢 دفعات استفاده: {s['usages']}\n"
               f"👥 کاربران یکتا: {s['unique_users']}\n"
               f"💸 مجموع تخفیف اعطاشده: {s['total_discount_rial'] // 10:,} تومان\n"
               f"💰 مجموع دریافتی از این کد: {s['total_final_rial'] // 10:,} تومان\n")
        if d['total_limit'] is None:
            msg += f"♾️ ظرفیت: نامحدود\n"
        else:
            msg += f"📦 ظرفیت: {d['used_count']}/{d['total_limit']} (باقی: {d.get('remaining', 0)})\n"
        msg += f"⏰ آخرین استفاده: {s['last_used_at'] or '—'}\n"
    else:
        msg = f"📊 Stats `{d['code']}`: {s['usages']} uses"
    kb = {"inline_keyboard": [[
        {"text": "🔙 بازگشت به جزئیات", "callback_data": f"admin_disc_{disc_id}"}
    ]]}
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


def handle_discount_users(chat_id, disc_id, edit_id=None):
    if not auth_manager.is_admin(chat_id):
        return
    d = auth_manager.get_discount(disc_id)
    if not d:
        return
    lang = get_user_lang(chat_id)
    users = auth_manager.get_discount_users(disc_id)
    if lang == "fa":
        if d['scope'] == 'public':
            msg = (f"👥 کد `{d['code']}` *عمومی* است و همه کاربران مجازند.\n\n"
                   f"برای شخصی‌سازی از «✏️ ویرایش ← 👤 شخصی کن» استفاده کنید.")
        else:
            msg = f"👥 *کاربران مجاز `{d['code']}`* ({len(users)} نفر)\n\n"
            if not users:
                msg += "⚠️ هیچ کاربری ثبت نشده — این کد برای هیچ‌کس کار نمی‌کند!\n"
            msg += "برای حذف هر کاربر روی آن بزنید:"
    else:
        msg = f"👥 Allowed users: {len(users)}"

    rows = []
    for uid in users[:20]:
        try:
            info = auth_manager.get_user_info(uid)
            uname = (info or {}).get('username') or "—"
        except Exception:
            uname = "—"
        try:
            used = auth_manager.count_discount_user_uses(disc_id, uid)
        except Exception:
            used = 0
        label = f"❌ {uname} ({uid}) | {used}×"
        rows.append([{"text": label[:60],
                      "callback_data": f"admin_disc_userdel_{disc_id}_{uid}"}])
    if len(users) > 20:
        rows.append([{"text": f"… و {len(users) - 20} نفر دیگر", "callback_data": "ignore"}])
    if d['scope'] == 'personal':
        rows.append([{"text": "➕ افزودن کاربر", "callback_data": f"admin_disc_useradd_{disc_id}"}])
        rows.append([{"text": t(chat_id, "disc_notify_users"),
                      "callback_data": f"admin_disc_notify_{disc_id}"}])
    rows.append([{"text": "🔙 بازگشت به جزئیات", "callback_data": f"admin_disc_{disc_id}"}])
    kb = {"inline_keyboard": rows}
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


def handle_discount_notify_ask(chat_id, disc_id, edit_id=None):
    if not auth_manager.is_admin(chat_id):
        return
    d = auth_manager.get_discount(disc_id)
    if not d:
        return
    lang = get_user_lang(chat_id)
    if d['scope'] == 'personal':
        n = len(d.get('allowed_users') or [])
        msg = (f"📣 کد شخصی `{d['code']}` به {n} کاربر مجاز ارسال شود؟"
               if lang == "fa" else f"📣 Send `{d['code']}` to {n} users?")
    else:
        try:
            n_all = len([u for u in auth_manager.get_approved_users()
                         if not auth_manager.is_admin(u['chat_id'])])
        except Exception:
            n_all = "?"
        msg = (f"📣 کد عمومی `{d['code']}` به *همه کاربران* ({n_all} نفر) ارسال شود؟\n\n"
               f"⚠️ این پیام برای همه ارسال می‌شود."
               if lang == "fa" else f"📣 Broadcast `{d['code']}` to all?")
    kb = {"inline_keyboard": [[
        {"text": "✅ بله، ارسال شود", "callback_data": f"admin_disc_notifygo_{disc_id}"},
        {"text": t(chat_id, "no_keep"), "callback_data": f"admin_disc_{disc_id}"},
    ]]}
    if edit_id:
        edit_message(chat_id, edit_id, msg, kb)
    else:
        send_message(chat_id, msg, kb)


def handle_discount_notify_go(chat_id, disc_id):
    if not auth_manager.is_admin(chat_id):
        return
    d = auth_manager.get_discount(disc_id)
    if not d:
        return
    send_message(chat_id, "⏳ در حال ارسال اطلاع‌رسانی...")
    try:
        bot_token = config['messengers']['bale']['bot_token']
        if d['scope'] == 'personal':
            from auth_handlers import notify_personal_discount_bulk
            sent, failed = notify_personal_discount_bulk(disc_id, bot_token)
        else:
            from auth_handlers import broadcast_public_discount
            sent, failed = broadcast_public_discount(disc_id, bot_token)
        send_message(chat_id, f"📣 اطلاع‌رسانی انجام شد: ✅ {sent} موفق، ❌ {failed} ناموفق")
        auth_manager.log_activity(chat_id, "disc_notify", f"{d['code']} sent={sent} failed={failed}")
    except Exception as e:
        send_message(chat_id, f"❌ خطا در اطلاع‌رسانی: {e}")
    handle_discount_detail(chat_id, disc_id)


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


def clear_buy_code_state(chat_id):
    """پاک کردن state فقط اگر در حال ورود کد تخفیف باشد (بدون اثر روی stateهای دیگر)"""
    try:
        st = user_states.get(chat_id)
        if isinstance(st, dict) and st.get('state') == 'awaiting_buy_code':
            del user_states[chat_id]
    except Exception:
        pass


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
    # چک انقضای دسترسی (تست یا محدود) - اگر تمام شده، approved محسوب نمی‌شود
    if user_info and user_info.get('is_trial') and user_info.get('trial_expired'):
        user_is_approved = False
        logger.info(f"⏰ تست کاربر {chat_id} منقضی شده - نیاز به پرداخت")
    elif user_info and user_info.get('access_expired'):
        user_is_approved = False
        logger.info(f"⏰ دسترسی کاربر {chat_id} منقضی شده - نیاز به پرداخت")

    if not user_is_approved and not is_admin:
        if text == "/start":
            handle_unauthenticated_user(message, bot_token)

        # ✅ تعرفه‌ها - حتی برای کاربران منقضی هم در دسترس
        elif text == t(chat_id, "tariffs") or callback_data == "show_tariffs":
            clear_buy_code_state(chat_id)
            try:
                from auth_handlers import show_tariffs
                show_tariffs(chat_id, bot_token, lang=get_user_lang(chat_id))
            except Exception as e:
                logger.error(f"❌ خطا در نمایش تعرفه‌ها: {e}")

        # ✅ خرید پلن مشخص - برای کاربران منقضی (پیش‌فاکتور با امکان تخفیف)
        elif callback_data and callback_data.startswith("buy_plan_"):
            try:
                plan_id = int(callback_data.replace("buy_plan_", ""))
                clear_buy_code_state(chat_id)
                from auth_handlers import show_plan_purchase_options
                show_plan_purchase_options(chat_id, username, bot_token, plan_id,
                                           lang=get_user_lang(chat_id))
            except ValueError:
                pass

        # 🎟️ شروع ورود کد تخفیف برای پلن
        elif callback_data and callback_data.startswith("disc_enter_"):
            try:
                plan_id = int(callback_data.replace("disc_enter_", ""))
                set_state(chat_id, "awaiting_buy_code", plan_id=plan_id)
                kb = {"inline_keyboard": [[
                    {"text": "❌ انصراف", "callback_data": f"disc_remove_{plan_id}"}
                ]]}
                send_message(chat_id, "🎟️ *کد تخفیف را وارد کنید:*\n\n"
                                      "کد را دقیقاً همان‌طور که دریافت کرده‌اید بفرستید.",
                             kb)
            except ValueError:
                pass

        # 🎟️ انصراف/حذف کد - نمایش پیش‌فاکتور بدون تخفیف
        elif callback_data and callback_data.startswith("disc_remove_"):
            try:
                plan_id = int(callback_data.replace("disc_remove_", ""))
                clear_buy_code_state(chat_id)
                from auth_handlers import show_plan_purchase_options
                show_plan_purchase_options(chat_id, username, bot_token, plan_id,
                                           lang=get_user_lang(chat_id))
            except ValueError:
                pass

        # 💳 تایید و پرداخت (با/بدون تخفیف)
        elif callback_data and callback_data.startswith("buy_confirm_"):
            try:
                rest = callback_data.replace("buy_confirm_", "")
                if "_d" in rest:
                    plan_s, disc_s = rest.split("_d", 1)
                    plan_id, disc_id = int(plan_s), int(disc_s)
                else:
                    plan_id, disc_id = int(rest), None
                clear_buy_code_state(chat_id)
                from auth_handlers import handle_purchase_confirm
                handle_purchase_confirm(chat_id, username, bot_token,
                                        plan_id=plan_id, discount_id=disc_id)
            except ValueError:
                pass

        # 🎁 دریافت رایگان با تخفیف ۱۰۰٪
        elif callback_data and callback_data.startswith("buy_free_"):
            try:
                rest = callback_data.replace("buy_free_", "")
                plan_s, disc_s = rest.split("_d", 1)
                clear_buy_code_state(chat_id)
                from auth_handlers import redeem_free_with_discount
                redeem_free_with_discount(chat_id, username, bot_token,
                                          int(plan_s), int(disc_s),
                                          lang=get_user_lang(chat_id))
            except ValueError:
                pass

        # 🎟️ کدهای تخفیف شخصی من
        elif callback_data == "my_discounts":
            clear_buy_code_state(chat_id)
            try:
                from auth_handlers import show_my_discounts
                show_my_discounts(chat_id, bot_token, lang=get_user_lang(chat_id))
            except Exception as e:
                logger.error(f"❌ خطا در نمایش کدهای من: {e}")

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

        # 🎟️ ورود کد تخفیف هنگام خرید (کاربر منقضی/جدید)
        elif isinstance(user_states.get(chat_id), dict) and user_states.get(chat_id, {}).get('state') == 'awaiting_buy_code':
            if text:
                _st = user_states.get(chat_id, {})
                from auth_handlers import handle_discount_code_input
                ok = handle_discount_code_input(chat_id, username, text, bot_token,
                                                _st.get('plan_id'),
                                                lang=get_user_lang(chat_id))
                if ok:
                    clear_state(chat_id)

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

    # ========== خرید حتی برای کاربران تایید شده (تستی که می‌خواهد دائمی بخرد) =========
    if text in ["/buy", "💳 خرید دسترسی", "خرید", "buy"] or (callback_data == "auth_buy_access" and user_is_approved):
        from auth_handlers import _handle_buy_access
        _handle_buy_access(chat_id, username, bot_token, user_states)
        return
    if callback_data == "auth_confirm_purchase" and user_is_approved:
        from auth_handlers import handle_purchase_confirm
        handle_purchase_confirm(chat_id, username, bot_token)
        clear_state(chat_id)
        return
    if callback_data == "auth_back_to_menu" and user_is_approved:
        clear_state(chat_id)
        send_message(chat_id, t(chat_id, "main_menu"), create_main_keyboard(chat_id))
        return

    # ========== انتخاب زبان ==========
    if text == "/start":
        if str(chat_id) not in config.get("user_languages", {}):
            keyboard = create_language_keyboard()
            send_message(chat_id, LANGUAGES["en"]["welcome"], keyboard)
        else:
            # اگر کاربر تستی است، باقی مانده تست را نمایش بده + دکمه تعرفه‌ها
            trial_msg = ""
            extra_keyboard = None
            if user_info and user_info.get('is_trial') and not user_info.get('trial_expired'):
                remaining_h = user_info.get('trial_remaining_hours', 24)
                trial_end = user_info.get('trial_end', '')
                if get_user_lang(chat_id) == "fa":
                    trial_msg = f"\n\n🎁 *تست رایگان فعال:* {remaining_h:.1f} ساعت باقی مانده\n⏰ تا: {trial_end}\n💡 برای ادامه از بخش تعرفه‌ها اشتراک بخرید"
                    extra_keyboard = {
                        "inline_keyboard": [
                            [{"text": "🏷️ مشاهده تعرفه‌ها", "callback_data": "show_tariffs"}]
                        ]
                    }
                else:
                    trial_msg = f"\n\n🎁 Trial: {remaining_h:.1f}h left until {trial_end}"
            send_message(chat_id, t(chat_id, "main_menu") + trial_msg, create_main_keyboard(chat_id))
            if extra_keyboard:
                send_message(chat_id, "🏷️ برای مشاهده تعرفه‌ها و خرید اشتراک:", extra_keyboard)
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

    # ========== تعرفه‌ها - برای همه کاربران (دکمه اصلی روی کیبورد) ==========
    elif text == t(chat_id, "tariffs") or callback_data == "show_tariffs":
        clear_buy_code_state(chat_id)
        try:
            from auth_handlers import show_tariffs
            show_tariffs(chat_id, bot_token, lang=get_user_lang(chat_id))
        except Exception as e:
            logger.error(f"❌ خطا در نمایش تعرفه‌ها: {e}")
            send_message(chat_id, "❌ خطا در دریافت تعرفه‌ها", create_main_keyboard(chat_id))
        return

    # ========== خرید پلن مشخص (پیش‌فاکتور با امکان تخفیف) ==========
    elif callback_data and callback_data.startswith("buy_plan_"):
        try:
            plan_id = int(callback_data.replace("buy_plan_", ""))
            clear_buy_code_state(chat_id)
            from auth_handlers import show_plan_purchase_options
            show_plan_purchase_options(chat_id, username, bot_token, plan_id,
                                       lang=get_user_lang(chat_id))
        except ValueError:
            pass
        return

    # ========== کد تخفیف سمت کاربر ==========
    elif callback_data and callback_data.startswith("disc_enter_"):
        try:
            plan_id = int(callback_data.replace("disc_enter_", ""))
            set_state(chat_id, "awaiting_buy_code", plan_id=plan_id)
            kb = {"inline_keyboard": [[
                {"text": "❌ انصراف", "callback_data": f"disc_remove_{plan_id}"}
            ]]}
            send_message(chat_id, "🎟️ *کد تخفیف را وارد کنید:*\n\n"
                                  "کد را دقیقاً همان‌طور که دریافت کرده‌اید بفرستید.",
                         kb)
        except ValueError:
            pass
        return

    elif callback_data and callback_data.startswith("disc_remove_"):
        try:
            plan_id = int(callback_data.replace("disc_remove_", ""))
            clear_buy_code_state(chat_id)
            from auth_handlers import show_plan_purchase_options
            show_plan_purchase_options(chat_id, username, bot_token, plan_id,
                                       lang=get_user_lang(chat_id))
        except ValueError:
            pass
        return

    elif callback_data and callback_data.startswith("buy_confirm_"):
        try:
            rest = callback_data.replace("buy_confirm_", "")
            if "_d" in rest:
                plan_s, disc_s = rest.split("_d", 1)
                plan_id, disc_id = int(plan_s), int(disc_s)
            else:
                plan_id, disc_id = int(rest), None
            clear_buy_code_state(chat_id)
            from auth_handlers import handle_purchase_confirm
            handle_purchase_confirm(chat_id, username, bot_token,
                                    plan_id=plan_id, discount_id=disc_id)
        except ValueError:
            pass
        return

    elif callback_data and callback_data.startswith("buy_free_"):
        try:
            rest = callback_data.replace("buy_free_", "")
            plan_s, disc_s = rest.split("_d", 1)
            clear_buy_code_state(chat_id)
            from auth_handlers import redeem_free_with_discount
            redeem_free_with_discount(chat_id, username, bot_token,
                                      int(plan_s), int(disc_s),
                                      lang=get_user_lang(chat_id))
        except ValueError:
            pass
        return

    elif callback_data == "my_discounts":
        clear_buy_code_state(chat_id)
        try:
            from auth_handlers import show_my_discounts
            show_my_discounts(chat_id, bot_token, lang=get_user_lang(chat_id))
        except Exception as e:
            logger.error(f"❌ خطا در نمایش کدهای من: {e}")
        return

    # ========== مدیریت تعرفه‌ها (ادمین) ==========
    elif text == t(chat_id, "manage_tariffs"):
        handle_manage_tariffs(chat_id)
        return

    elif callback_data == "admin_tariffs_back":
        handle_manage_tariffs(chat_id, edit_id=message_id)
        return

    elif callback_data and callback_data.startswith("admin_plan_") and not callback_data.startswith("admin_plan_new"):
        if not auth_manager.is_admin(chat_id):
            send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
            return
        # admin_plan_{id} | admin_plan_price_{id} | admin_plan_dur_{id} | admin_plan_toggle_{id} | admin_plan_del_{id} | admin_plan_broadcast_{id}
        rest = callback_data.replace("admin_plan_", "")
        if rest.startswith("price_"):
            plan_id = int(rest.replace("price_", ""))
            set_state(chat_id, "awaiting_plan_price", plan_id=plan_id)
            send_message(chat_id, t(chat_id, "enter_price_new"))
        elif rest.startswith("dur_"):
            plan_id = int(rest.replace("dur_", ""))
            set_state(chat_id, "awaiting_plan_duration", plan_id=plan_id)
            send_message(chat_id, t(chat_id, "enter_duration_new"))
        elif rest.startswith("toggle_"):
            plan_id = int(rest.replace("toggle_", ""))
            plan = auth_manager.get_plan(plan_id)
            if plan:
                auth_manager.update_plan(plan_id, enabled=0 if plan['enabled'] else 1)
                handle_plan_detail(chat_id, plan_id, edit_id=message_id)
        elif rest.startswith("del_"):
            plan_id = int(rest.replace("del_", ""))
            keyboard = {"inline_keyboard": [
                [
                    {"text": t(chat_id, "yes_delete"), "callback_data": f"admin_plan_delconfirm_{plan_id}"},
                    {"text": t(chat_id, "no_keep"), "callback_data": f"admin_plan_{plan_id}"},
                ]
            ]}
            edit_message(chat_id, message_id, t(chat_id, "confirm_delete_plan"), keyboard)
        elif rest.startswith("delconfirm_"):
            plan_id = int(rest.replace("delconfirm_", ""))
            auth_manager.delete_plan(plan_id)
            handle_manage_tariffs(chat_id)
        elif rest.startswith("broadcast_"):
            plan_id = int(rest.replace("broadcast_", ""))
            plan = auth_manager.get_plan(plan_id)
            if plan:
                try:
                    from auth_handlers import broadcast_new_plan
                    bot_tk = config['messengers']['bale']['bot_token']
                    sent, failed = broadcast_new_plan(plan, bot_tk)
                    send_message(chat_id, f"{t(chat_id, 'broadcast_done')} ({sent} موفق، {failed} ناموفق)", create_admin_menu_keyboard(chat_id))
                except Exception as e:
                    send_message(chat_id, f"❌ {e}", create_admin_menu_keyboard(chat_id))
        else:
            plan_id = int(rest)
            handle_plan_detail(chat_id, plan_id, edit_id=message_id)
        return

    elif callback_data == "admin_plan_new":
        handle_plan_create_start(chat_id)
        return

    elif callback_data == "admin_broadcast_tariffs":
        handle_broadcast_tariffs(chat_id)
        return

    # ========== کدهای تخفیف (مدیریت ادمین) ==========
    elif callback_data and callback_data.startswith("admin_disc_"):
        if not auth_manager.is_admin(chat_id):
            send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
            return
        rest = callback_data.replace("admin_disc_", "", 1)

        # ---- پیکر انتخاب کاربر ----
        if (rest.startswith("upick_") or rest.startswith("upage_")
                or rest in ("udone", "usearch", "uall", "umanual",
                            "upickopen", "ucancel")):
            handle_userpick_callback(chat_id, message_id, rest)
            return

        # ---- لیست و فیلتر و صفحه‌بندی ----
        if rest == "list" or rest == "back_list":
            handle_discount_list(chat_id, edit_id=message_id)
        elif rest.startswith("filter_"):
            f = rest.replace("filter_", "", 1)
            handle_discount_list(chat_id, page=0, dfilter=f, edit_id=message_id)
        elif rest.startswith("page_"):
            parts = rest.replace("page_", "", 1).rsplit("_", 1)
            if len(parts) == 2:
                f, p_raw = parts
                try:
                    p = int(p_raw)
                except ValueError:
                    f, p = "all", 0
            else:
                f, p = "all", 0
            handle_discount_list(chat_id, page=p, dfilter=f, edit_id=message_id)

        # ---- شروع ساخت ----
        elif rest == "new":
            handle_discount_create_start(chat_id)
        elif rest == "cancel":
            clear_state(chat_id)
            handle_discount_list(chat_id)

        # ---- تولید خودکار کد (ویزارد) ----
        elif rest == "autogen":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_code":
                return
            code = auth_manager.generate_discount_code()
            disc = st_data.get('disc', {})
            disc['code'] = code
            set_state(chat_id, "awaiting_disc_type", disc=disc)
            _disc_send_type_menu(chat_id, code)

        # ---- نوع تخفیف ----
        elif rest in ("type_percent", "type_fixed"):
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_type":
                return
            disc = st_data.get('disc', {})
            disc['discount_type'] = 'percent' if rest == "type_percent" else 'fixed'
            set_state(chat_id, "awaiting_disc_value", disc=disc)
            if disc['discount_type'] == 'percent':
                send_message(chat_id,
                             "٪ *مرحله ۳: درصد تخفیف؟*\n\n"
                             "عدد بین 1 تا 100 وارد کنید:\nمثال: `20` یعنی ۲۰٪ تخفیف")
            else:
                send_message(chat_id,
                             "💰 *مرحله ۳: مبلغ تخفیف؟*\n\n"
                             "مبلغ را به *تومان* وارد کنید:\nمثال: `50000`")

        # ---- رد کردن سقف درصدی ----
        elif rest == "skip_maxcap":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_maxcap":
                return
            disc = st_data.get('disc', {})
            disc['max_discount_rial'] = None
            set_state(chat_id, "awaiting_disc_scope", disc=disc)
            _disc_send_scope_menu(chat_id)

        # ---- دامنه ----
        elif rest in ("scope_public", "scope_personal"):
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_scope":
                return
            disc = st_data.get('disc', {})
            if rest == "scope_public":
                disc['scope'] = 'public'
                disc['allowed_chat_ids'] = []
                set_state(chat_id, "awaiting_disc_plans", disc=disc)
                _disc_send_plans_menu(chat_id)
            else:
                disc['scope'] = 'personal'
                set_state(chat_id, "awaiting_disc_userpick", disc=disc,
                          selected=[], page=0, query='')
                handle_userpick_menu(chat_id)

        # ---- انتخاب پلن‌ها (ویزارد) ----
        elif rest.startswith("plan_toggle_"):
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_plans":
                return
            try:
                pid = int(rest.replace("plan_toggle_", ""))
            except ValueError:
                return
            disc = st_data.get('disc', {})
            sel = [int(x) for x in disc.get('allowed_plan_ids', [])]
            if pid in sel:
                sel.remove(pid)
            else:
                sel.append(pid)
            disc['allowed_plan_ids'] = sel
            set_state(chat_id, "awaiting_disc_plans", disc=disc)
            _disc_send_plans_menu(chat_id, edit_id=message_id)
        elif rest == "plans_all":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_plans":
                return
            disc = st_data.get('disc', {})
            disc['allowed_plan_ids'] = []
            set_state(chat_id, "awaiting_disc_plans", disc=disc)
            _disc_send_plans_menu(chat_id, edit_id=message_id)
        elif rest == "plans_done":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_plans":
                return
            disc = st_data.get('disc', {})
            set_state(chat_id, "awaiting_disc_total", disc=disc)
            kb = {"inline_keyboard": [
                [{"text": t(chat_id, "disc_unlimited"), "callback_data": "admin_disc_skip_total"}],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         "🔢 *مرحله ۷: سقف کل استفاده (ظرفیت کد)؟*\n\n"
                         "• عدد وارد کنید (مثلاً `100` یعنی فقط ۱۰۰ نفر اول)\n"
                         "• یا نامحدود را بزنید",
                         kb)

        # ---- رد کردن‌ها ----
        elif rest == "skip_total":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_total":
                return
            disc = st_data.get('disc', {})
            disc['total_limit'] = None
            set_state(chat_id, "awaiting_disc_peruser", disc=disc)
            kb = {"inline_keyboard": [
                [{"text": "⏭️ پیش‌فرض (۱ بار)", "callback_data": "admin_disc_skip_peruser"}],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         "👤 *مرحله ۸: سقف استفاده هر کاربر؟*\n\n"
                         "هر کاربر چند بار بتواند از این کد استفاده کند؟\n"
                         "مثال: `1` (پیشنهاد امنیتی: ۱ بار)",
                         kb)
        elif rest == "skip_peruser":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_peruser":
                return
            disc = st_data.get('disc', {})
            disc['per_user_limit'] = 1
            set_state(chat_id, "awaiting_disc_expiry", disc=disc)
            kb = {"inline_keyboard": [
                [
                    {"text": "۷ روز", "callback_data": "admin_disc_exp_7"},
                    {"text": "۳۰ روز", "callback_data": "admin_disc_exp_30"},
                ],
                [
                    {"text": "۹۰ روز", "callback_data": "admin_disc_exp_90"},
                    {"text": t(chat_id, "disc_unlimited"), "callback_data": "admin_disc_exp_0"},
                ],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         "⏰ *مرحله ۹: مدت اعتبار؟*\n\n"
                         "• عدد = روز از الان (مثلاً `30`)\n"
                         "• تاریخ شمسی (`1405/07/15`) یا میلادی (`2026-10-07`)\n"
                         "• یا نامحدود",
                         kb)
        elif rest == "skip_min":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_min":
                return
            disc = st_data.get('disc', {})
            disc['min_order_rial'] = None
            set_state(chat_id, "awaiting_disc_firstonly", disc=disc)
            kb = {"inline_keyboard": [
                [
                    {"text": "✅ بله، فقط خرید اول", "callback_data": "admin_disc_first_yes"},
                    {"text": "❌ نه، همه", "callback_data": "admin_disc_first_no"},
                ],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         "🛒 *فقط برای خرید اول؟*\n\n"
                         "اگر «بله»، کاربرانی که قبلاً خرید موفق داشته‌اند "
                         "نمی‌توانند از این کد استفاده کنند.",
                         kb)
        elif rest == "skip_title":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_title":
                return
            disc = st_data.get('disc', {})
            disc['title'] = ''
            set_state(chat_id, "awaiting_disc_confirm", disc=disc)
            _disc_send_confirm(chat_id)

        # ---- انقضای سریع ----
        elif rest.startswith("exp_"):
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_expiry":
                return
            try:
                days = int(rest.replace("exp_", ""))
            except ValueError:
                return
            from auth_handlers import parse_expiry_input
            parsed = parse_expiry_input("0" if days == 0 else str(days))
            if not parsed.get('success'):
                send_message(chat_id, f"❌ {parsed.get('error')}")
                return
            disc = st_data.get('disc', {})
            disc['expires_at'] = parsed.get('expires_at')
            disc['expires_label'] = parsed.get('label')
            set_state(chat_id, "awaiting_disc_min", disc=disc)
            kb = {"inline_keyboard": [
                [{"text": t(chat_id, "disc_skip"), "callback_data": "admin_disc_skip_min"}],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         f"⏰ اعتبار: {parsed.get('label')}\n\n"
                         "🧾 *کف مبلغ خرید (اختیاری):*\n\n"
                         "کد فقط برای پلن‌هایی که قیمتشان از این مبلغ بیشتر است کار کند؟\n"
                         "مبلغ به تومان (مثلاً `100000`) یا رد کنید.",
                         kb)

        # ---- فقط خرید اول ----
        elif rest in ("first_yes", "first_no"):
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_firstonly":
                return
            disc = st_data.get('disc', {})
            disc['first_purchase_only'] = (rest == "first_yes")
            set_state(chat_id, "awaiting_disc_title", disc=disc)
            kb = {"inline_keyboard": [
                [{"text": t(chat_id, "disc_skip"), "callback_data": "admin_disc_skip_title"}],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         "📝 *مرحله ۱۰: عنوان/توضیح (اختیاری):*\n\n"
                         "مثلاً: `جشنواره تابستان`",
                         kb)

        # ---- ثبت نهایی ----
        elif rest == "confirm":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_confirm":
                return
            disc = st_data.get('disc', {})
            res = auth_manager.create_discount(
                code=disc.get('code', ''),
                discount_type=disc.get('discount_type', 'percent'),
                percent=disc.get('percent'),
                amount_rial=disc.get('amount_rial', 0),
                title=disc.get('title', ''),
                max_discount_rial=disc.get('max_discount_rial'),
                min_order_rial=disc.get('min_order_rial'),
                scope=disc.get('scope', 'public'),
                allowed_chat_ids=disc.get('allowed_chat_ids', []),
                allowed_plan_ids=disc.get('allowed_plan_ids', []),
                first_purchase_only=disc.get('first_purchase_only', False),
                total_limit=disc.get('total_limit'),
                per_user_limit=disc.get('per_user_limit', 1),
                expires_at=disc.get('expires_at'),
                created_by=chat_id)
            clear_state(chat_id)
            if res.get('success'):
                auth_manager.log_activity(chat_id, "disc_create",
                                          f"{res.get('code')} id={res.get('discount_id')}")
                new_code = res.get('code')
                kb_ok = {"inline_keyboard": [[
                    {"text": f"{t(chat_id, 'disc_copy_code')}: {new_code}",
                     "copy_text": {"text": new_code}},
                ]]}
                send_message(chat_id, f"✅ کد تخفیف `{new_code}` با موفقیت ساخته شد!", kb_ok)
                new_id = res.get('discount_id')
                d = auth_manager.get_discount(new_id)
                if d and d['scope'] == 'personal':
                    kb = {"inline_keyboard": [[
                        {"text": t(chat_id, "disc_notify_users"),
                         "callback_data": f"admin_disc_notify_{new_id}"},
                        {"text": t(chat_id, "disc_code_detail"),
                         "callback_data": f"admin_disc_{new_id}"},
                    ]]}
                    send_message(chat_id,
                                 f"📣 کد شخصی است ({len(d.get('allowed_users') or [])} کاربر).\n"
                                 f"الان به کاربران مجاز اطلاع‌رسانی شود؟", kb)
                else:
                    handle_discount_detail(chat_id, new_id)
            else:
                send_message(chat_id, f"❌ ثبت نشد: {res.get('error', 'خطا')}",
                             create_admin_menu_keyboard(chat_id))

        # ---- فعال/غیرفعال ----
        elif rest.startswith("toggle_"):
            try:
                did = int(rest.replace("toggle_", ""))
            except ValueError:
                return
            handle_discount_toggle(chat_id, did)

        # ---- حذف ----
        elif rest.startswith("delconfirm_"):
            try:
                did = int(rest.replace("delconfirm_", ""))
            except ValueError:
                return
            handle_discount_delete_confirm(chat_id, did)
        elif rest.startswith("del_"):
            try:
                did = int(rest.replace("del_", ""))
            except ValueError:
                return
            handle_discount_delete_ask(chat_id, did, edit_id=message_id)

        # ---- ویرایش ----
        elif rest.startswith("efield_"):
            # admin_disc_efield_{field}_{id}
            try:
                _, field, did_s = rest.split("_", 2)
                did = int(did_s)
            except ValueError:
                return
            d = auth_manager.get_discount(did)
            if not d:
                return
            back_kb = {"inline_keyboard": [[
                {"text": "❌ انصراف", "callback_data": f"admin_disc_{did}"}]]}
            if field == "value":
                set_state(chat_id, "awaiting_disc_edit_value", disc_id=did)
                if d['discount_type'] == 'percent':
                    send_message(chat_id,
                                 f"٪ درصد جدید (فعلی: ٪{d['percent']})؟\nعدد 1 تا 100:",
                                 back_kb)
                else:
                    send_message(chat_id,
                                 f"💰 مبلغ جدید به تومان (فعلی: {int(d['amount_rial']) // 10:,})؟",
                                 back_kb)
            elif field == "cap":
                if d['discount_type'] != 'percent':
                    send_message(chat_id, "⚠️ سقف فقط برای کد درصدی معنا دارد.")
                    return
                set_state(chat_id, "awaiting_disc_edit_cap", disc_id=did)
                send_message(chat_id,
                             "🎯 سقف تخفیف جدید به تومان؟\n`0` یعنی حذف سقف.",
                             back_kb)
            elif field == "min":
                set_state(chat_id, "awaiting_disc_edit_min", disc_id=did)
                send_message(chat_id,
                             "🧾 کف مبلغ خرید جدید به تومان؟\n`0` یعنی حذف کف.",
                             back_kb)
            elif field == "total":
                set_state(chat_id, "awaiting_disc_edit_total", disc_id=did)
                send_message(chat_id,
                             "🔢 سقف کل جدید؟\nعدد یا `0` برای نامحدود.",
                             back_kb)
            elif field == "peruser":
                set_state(chat_id, "awaiting_disc_edit_peruser", disc_id=did)
                send_message(chat_id, "👤 سقف هر کاربر جدید؟ (عدد، حداقل 1)", back_kb)
            elif field == "expiry":
                set_state(chat_id, "awaiting_disc_edit_expiry", disc_id=did)
                kb2 = {"inline_keyboard": [
                    [{"text": "♾️ نامحدود", "callback_data": f"admin_disc_eexpinf_{did}"}],
                    [{"text": "❌ انصراف", "callback_data": f"admin_disc_{did}"}],
                ]}
                send_message(chat_id,
                             "⏰ انقضای جدید؟\n"
                             "• عدد = روز از الان • تاریخ شمسی/میلادی • نامحدود",
                             kb2)
            elif field == "title":
                set_state(chat_id, "awaiting_disc_edit_title", disc_id=did)
                send_message(chat_id,
                             "📝 عنوان جدید؟\n(`-` یعنی پاک کردن عنوان)",
                             back_kb)
        elif rest.startswith("eexpinf_"):
            try:
                did = int(rest.replace("eexpinf_", ""))
            except ValueError:
                return
            clear_state(chat_id)
            auth_manager.update_discount(did, expires_at=None)
            handle_discount_detail(chat_id, did)
        elif rest.startswith("escope_"):
            try:
                did = int(rest.replace("escope_", ""))
            except ValueError:
                return
            d = auth_manager.get_discount(did)
            if not d:
                return
            if d['scope'] == 'public':
                set_state(chat_id, "awaiting_disc_euserpick", disc_id=did,
                          selected=[], page=0, query='')
                handle_userpick_menu(chat_id)
            else:
                auth_manager.update_discount(did, scope='public')
                auth_manager.log_activity(chat_id, "disc_scope", f"{did} -> public")
                send_message(chat_id, "🌍 کد عمومی شد (لیست کاربران شخصی پاک شد).")
                handle_discount_detail(chat_id, did)
        elif rest.startswith("efirst_"):
            try:
                did = int(rest.replace("efirst_", ""))
            except ValueError:
                return
            d = auth_manager.get_discount(did)
            if d:
                auth_manager.update_discount(did,
                                             first_purchase_only=not d['first_purchase_only'])
                handle_discount_edit_menu(chat_id, did, edit_id=message_id)
        elif rest.startswith("edit_"):
            try:
                did = int(rest.replace("edit_", ""))
            except ValueError:
                return
            handle_discount_edit_menu(chat_id, did, edit_id=message_id)

        # ---- کاربران مجاز ----
        elif rest.startswith("userdel_"):
            try:
                _, did_s, uid_s = rest.split("_", 2)
                did, uid = int(did_s), int(uid_s)
            except ValueError:
                return
            auth_manager.remove_discount_user(did, uid)
            handle_discount_users(chat_id, did, edit_id=message_id)
        elif rest.startswith("useradd_"):
            try:
                did = int(rest.replace("useradd_", ""))
            except ValueError:
                return
            set_state(chat_id, "awaiting_disc_uaddpick", disc_id=did,
                          selected=[], page=0, query='')
            handle_userpick_menu(chat_id)
        elif rest.startswith("users_"):
            try:
                did = int(rest.replace("users_", ""))
            except ValueError:
                return
            handle_discount_users(chat_id, did, edit_id=message_id)

        # ---- پلن‌های مشمول (ویرایش) ----
        elif rest == "eplans_all":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_edit_plans":
                return
            st_data['selected'] = []
            set_state(chat_id, "awaiting_disc_edit_plans",
                      disc_id=st_data.get('disc_id'), selected=[])
            _disc_send_plans_menu(chat_id, edit_id=message_id, for_edit=True)
        elif rest == "eplans_done":
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_edit_plans":
                return
            did = st_data.get('disc_id')
            auth_manager.set_discount_plans(did, st_data.get('selected', []))
            clear_state(chat_id)
            send_message(chat_id, "✅ پلن‌های مشمول به‌روزرسانی شد.")
            handle_discount_detail(chat_id, did)
        elif rest == "eplans_cancel":
            st_name, st_data = get_state(chat_id)
            did = st_data.get('disc_id') if st_name == "awaiting_disc_edit_plans" else None
            clear_state(chat_id)
            if did:
                handle_discount_detail(chat_id, did, edit_id=message_id)
            else:
                handle_discount_list(chat_id, edit_id=message_id)
        elif rest.startswith("eplan_toggle_"):
            st_name, st_data = get_state(chat_id)
            if st_name != "awaiting_disc_edit_plans":
                return
            try:
                pid = int(rest.replace("eplan_toggle_", ""))
            except ValueError:
                return
            sel = [int(x) for x in st_data.get('selected', [])]
            if pid in sel:
                sel.remove(pid)
            else:
                sel.append(pid)
            set_state(chat_id, "awaiting_disc_edit_plans",
                      disc_id=st_data.get('disc_id'), selected=sel)
            _disc_send_plans_menu(chat_id, edit_id=message_id, for_edit=True)
        elif rest.startswith("plans_"):
            try:
                did = int(rest.replace("plans_", ""))
            except ValueError:
                return
            sel = auth_manager.get_discount_plans(did)
            set_state(chat_id, "awaiting_disc_edit_plans", disc_id=did, selected=sel)
            _disc_send_plans_menu(chat_id)

        # ---- گزارش‌ها ----
        elif rest.startswith("usages_"):
            try:
                did = int(rest.replace("usages_", ""))
            except ValueError:
                return
            handle_discount_usages(chat_id, did, edit_id=message_id)
        elif rest.startswith("stats_"):
            try:
                did = int(rest.replace("stats_", ""))
            except ValueError:
                return
            handle_discount_stats(chat_id, did, edit_id=message_id)

        # ---- اطلاع‌رسانی ----
        elif rest.startswith("notifygo_"):
            try:
                did = int(rest.replace("notifygo_", ""))
            except ValueError:
                return
            handle_discount_notify_go(chat_id, did)
        elif rest.startswith("notify_"):
            try:
                did = int(rest.replace("notify_", ""))
            except ValueError:
                return
            handle_discount_notify_ask(chat_id, did, edit_id=message_id)

        # ---- جزئیات کد ----
        elif rest.isdigit():
            handle_discount_detail(chat_id, int(rest), edit_id=message_id)
        return

    # ========== تست پیش‌فرض (ادمین) ==========
    elif text == t(chat_id, "default_trial_days"):
        handle_default_trial_days_prompt(chat_id)
        return

    # ========== لیست کاربران - صفحه‌بندی و جزئیات ==========
    elif callback_data and callback_data.startswith("admin_users_page_"):
        if not auth_manager.is_admin(chat_id):
            return
        page = int(callback_data.replace("admin_users_page_", ""))
        handle_manage_users(chat_id, page=page, edit_id=message_id)
        return

    elif callback_data == "admin_users_back":
        if not auth_manager.is_admin(chat_id):
            return
        handle_manage_users(chat_id, page=0, edit_id=message_id)
        return

    elif callback_data == "admin_menu_back":
        handle_admin_menu(chat_id, message_id)
        return

    elif callback_data and callback_data.startswith("admin_user_") and not callback_data.startswith("admin_users_"):
        if not auth_manager.is_admin(chat_id):
            send_message(chat_id, t(chat_id, "unauthorized_access"), create_main_keyboard(chat_id))
            return
        target_id = int(callback_data.replace("admin_user_", ""))
        handle_user_detail(chat_id, target_id, edit_id=message_id)
        return

    # ========== اعطای دسترسی رایگان ==========
    elif callback_data and callback_data.startswith("admin_grant_set_"):
        if not auth_manager.is_admin(chat_id):
            return
        parts = callback_data.replace("admin_grant_set_", "").split("_")
        target_id = int(parts[0])
        days = int(parts[1])
        handle_grant_free_set(chat_id, target_id, days)
        return

    elif callback_data and callback_data.startswith("admin_grant_custom_"):
        if not auth_manager.is_admin(chat_id):
            return
        target_id = int(callback_data.replace("admin_grant_custom_", ""))
        set_state(chat_id, "awaiting_custom_grant_days", target_id=target_id)
        send_message(chat_id, t(chat_id, "custom_days_prompt"))
        return

    elif callback_data and callback_data.startswith("admin_grant_force_"):
        if not auth_manager.is_admin(chat_id):
            return
        parts = callback_data.replace("admin_grant_force_", "").split("_")
        target_id = int(parts[0])
        days = int(parts[1])
        handle_grant_force(chat_id, target_id, days)
        return

    elif callback_data and callback_data.startswith("admin_grant_"):
        if not auth_manager.is_admin(chat_id):
            return
        target_id = int(callback_data.replace("admin_grant_", ""))
        handle_grant_free_menu(chat_id, target_id, edit_id=message_id)
        return

    # ========== تمدید مدت دسترسی ==========
    elif callback_data and callback_data.startswith("admin_extend_set_"):
        if not auth_manager.is_admin(chat_id):
            return
        parts = callback_data.replace("admin_extend_set_", "").split("_")
        target_id = int(parts[0])
        days = int(parts[1])
        handle_extend_set(chat_id, target_id, days)
        return

    elif callback_data and callback_data.startswith("admin_extend_force_"):
        if not auth_manager.is_admin(chat_id):
            return
        parts = callback_data.replace("admin_extend_force_", "").split("_")
        target_id = int(parts[0])
        days = int(parts[1])
        handle_extend_force(chat_id, target_id, days)
        return

    elif callback_data and callback_data.startswith("admin_extend_custom_"):
        if not auth_manager.is_admin(chat_id):
            return
        target_id = int(callback_data.replace("admin_extend_custom_", ""))
        set_state(chat_id, "awaiting_custom_extend_days", target_id=target_id)
        send_message(chat_id, t(chat_id, "custom_days_prompt"))
        return

    elif callback_data and callback_data.startswith("admin_to_timed_"):
        if not auth_manager.is_admin(chat_id):
            return
        target_id = int(callback_data.replace("admin_to_timed_", ""))
        handle_to_timed_menu(chat_id, target_id, edit_id=message_id)
        return

    elif callback_data and callback_data.startswith("admin_extend_"):
        if not auth_manager.is_admin(chat_id):
            return
        target_id = int(callback_data.replace("admin_extend_", ""))
        handle_extend_menu(chat_id, target_id, edit_id=message_id)
        return

    # ========== دائمی کردن ==========
    elif callback_data and callback_data.startswith("admin_perm_"):
        if not auth_manager.is_admin(chat_id):
            return
        target_id = int(callback_data.replace("admin_perm_", ""))
        handle_make_permanent(chat_id, target_id)
        return

    # ========== پرداخت‌ها و فعالیت کاربر ==========
    elif callback_data and callback_data.startswith("admin_payments_"):
        if not auth_manager.is_admin(chat_id):
            return
        target_id = int(callback_data.replace("admin_payments_", ""))
        handle_user_payments(chat_id, target_id, edit_id=message_id)
        return

    elif callback_data and callback_data.startswith("admin_ulogs_"):
        if not auth_manager.is_admin(chat_id):
            return
        target_id = int(callback_data.replace("admin_ulogs_", ""))
        handle_user_logs(chat_id, target_id, edit_id=message_id)
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
                    # گروهی پیدا نشد، ولی متصل است
                    err = chats_result.get("error", "")
                    msg = (
                        f"✅ *واتساپ متصل شد!* 🎉\n\n"
                        f"📱 شماره: {wa_cfg.get('chat_id','')}\n"
                        f"⚠️ گروهی پیدا نشد (یا هنوز در حال همگام‌سازی)\n"
                        f"خطا: {err}\n\n"
                        "💡 واتساپ بعد از اتصال 30-60 ثانیه طول می‌کشد تا گروه‌ها را لود کند.\n\n"
                        "🔄 30 ثانیه صبر کن و دوباره بزن:\n"
                        "📋 لیست گروه‌ها\n\n"
                        "✅ یا سریع دستی وارد کن - گروه هدف شما:\n"
                        "`120363312386194255@g.us`\n\n"
                        "این را کپی و ارسال کن تا به عنوان مقصد ذخیره شود،\n"
                        "یا شماره مقصد را وارد کن: 98912...\n"
                        "یا بنویس `ok` برای تایید شماره فعلی"
                        if lang == "fa"
                        else f"✅ WhatsApp connected! No groups found ({err}), wait 30s or send ID: 120363312386194255@g.us"
                    )
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "🔄 لیست گروه‌ها (30 ثانیه بعد)", "callback_data": "wa_list_groups"}],
                            [{"text": "✅ انتخاب گروه 120363...", "callback_data": "wa_select_dest_120363312386194255@g.us"}],
                            [{"text": "📱 وارد کردن دستی", "callback_data": "wa_select_personal"}]
                        ]
                    }
                    send_message(chat_id, msg, keyboard)
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
            result = messenger_whatsapp._send_via_neonize(dest_id, test_text, None, service_url, str(chat_id))
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

    elif callback_data == "wa_force_reset":
        lang = get_user_lang(chat_id)
        try:
            import messenger_whatsapp
            wa_cfg = user_config["messengers"].get("whatsapp", {})
            service_url = wa_cfg.get("service_url", "http://localhost:3001")
            phone_for_reset = wa_cfg.get("phone_number") or wa_cfg.get("own_phone") or ""
            send_message(chat_id, "🔥 در حال حذف کامل سشن خراب...")
            result = messenger_whatsapp.force_reset_session(chat_id, phone_for_reset, service_url)
            if result.get("qrImage"):
                import base64, tempfile, os
                b64 = result["qrImage"].split(",")[1] if "," in result["qrImage"] else result["qrImage"]
                qr_bytes = base64.b64decode(b64)
                bale_token = config["messengers"]["bale"]["bot_token"]
                api = f"https://tapi.bale.ai/bot{bale_token}"
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(qr_bytes)
                    tmp_path = tmp.name
                with open(tmp_path, "rb") as f:
                    files = {"photo": ("qr.png", f, "image/png")}
                    data = {"chat_id": chat_id, "caption": "🔥 QR جدید بعد از force reset"}
                    requests.post(f"{api}/sendPhoto", data=data, files=files, timeout=20)
                    os.unlink(tmp_path)
                if result.get("pairingCode"):
                    send_message(chat_id, f"{result.get('pairingCode')}\n\n👆 کپی")
            keyboard = {"inline_keyboard": [[{"text": "✅ بررسی اتصال", "callback_data": "check_whatsapp_status"}]]}
            send_message(chat_id, "✅ سشن حذف شد، QR جدید را اسکن کن", keyboard)
            set_state(chat_id, "waiting_whatsapp_qr_check", phone=phone_for_reset)
        except Exception as e:
            send_message(chat_id, f"❌ خطا: {e}")
        return

    elif callback_data == "wa_list_groups":
        lang = get_user_lang(chat_id)
        try:
            import messenger_whatsapp
            wa_cfg = user_config["messengers"].get("whatsapp", {})
            service_url = wa_cfg.get("service_url", "http://localhost:3001")
            
            sending_msg = "⏳ در حال دریافت لیست گروه‌ها... (ممکن است 15 ثانیه طول بکشد، واتساپ در حال همگام‌سازی)" if lang == "fa" else "⏳ Getting groups... (may take 15s)"
            send_message(chat_id, sending_msg)
            
            chats_result = messenger_whatsapp.get_chats_for_user(chat_id, service_url)
            
            if chats_result.get("ok") and chats_result.get("chats"):
                chats = chats_result["chats"]
                if len(chats) == 0:
                    # گروهی نیست ولی ok - واتساپ هنوز sync نکرده
                    msg = (
                        "⚠️ *هنوز گروهی پیدا نشد*\n\n"
                        "این طبیعی است - واتساپ بعد از اتصال 30-60 ثانیه طول می‌کشد تا گروه‌ها را همگام کند.\n\n"
                        "🔄 لطفاً 30 ثانیه صبر کنید و دوباره دکمه لیست گروه‌ها را بزنید.\n\n"
                        "💡 یا می‌توانید آیدی گروه را دستی وارد کنید:\n"
                        "`120363312386194255@g.us`\n\n"
                        "این آیدی گروه مورد نظر شماست - آن را کپی و ارسال کنید تا به عنوان مقصد ذخیره شود."
                        if lang == "fa"
                        else "No groups yet - WhatsApp syncing, wait 30s and try again, or send group ID manually: 120363312386194255@g.us"
                    )
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "🔄 تلاش مجدد - لیست گروه‌ها", "callback_data": "wa_list_groups"}],
                            [{"text": "📱 وارد کردن دستی آیدی گروه", "callback_data": "wa_select_personal"}]
                        ]
                    }
                    send_message(chat_id, msg, keyboard)
                    set_state(chat_id, "waiting_whatsapp_destination", chats=[])
                    return

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
                
                # اگر گروه 120363312386194255@g.us در لیست نیست، دستی اضافه کن
                target_group = "120363312386194255@g.us"
                if not any(c.get("id") == target_group for c in chats):
                    keyboard.append([{"text": f"👥 گروه هدف: {target_group[:20]}...", "callback_data": f"wa_select_dest_{target_group}"}])
                
                keyboard.append([{"text": "📱 شماره شخصی", "callback_data": "wa_select_personal"}])
                keyboard.append([{"text": t(chat_id, "back_to_settings"), "callback_data": "back_to_messengers_list"}])
                
                send_message(chat_id, "👇 انتخاب کنید:", {"inline_keyboard": keyboard})
                set_state(chat_id, "waiting_whatsapp_destination", chats=chats)
            else:
                error = chats_result.get("error", "Unknown")
                debug_info = chats_result.get("debug", {})
                msg = (
                    f"❌ خطا در دریافت گروه‌ها: {error}\n\n"
                    f"🔍 دیباگ: {debug_info}\n\n"
                    "💡 دلایل احتمالی:\n"
                    "1️⃣ واتساپ هنوز گروه‌ها را لود نکرده - 30 ثانیه صبر کن\n"
                    "2️⃣ گروهی نداری یا واتساپ بیزینس نیست\n"
                    "3️⃣ سشن قطع شده - دوباره QR بزن\n\n"
                    "✅ راه‌حل سریع:\n"
                    "آیدی گروهت رو دستی بفرست:\n"
                    "`120363312386194255@g.us`\n"
                    "یا بنویس `groups` دوباره"
                    if lang == "fa"
                    else f"❌ Error getting groups: {error} - send ID manually: 120363312386194255@g.us"
                )
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🔄 تلاش مجدد", "callback_data": "wa_list_groups"}],
                        [{"text": f"✅ انتخاب گروه هدف", "callback_data": f"wa_select_dest_120363312386194255@g.us"}]
                    ]
                }
                send_message(chat_id, msg, keyboard)
                set_state(chat_id, "waiting_whatsapp_destination", chats=[])
        except Exception as e:
            logger.error(f"❌ wa_list_groups error: {e}", exc_info=True)
            send_message(chat_id, f"❌ خطا: {e}\n\nدستی بفرست: 120363312386194255@g.us")
            set_state(chat_id, "waiting_whatsapp_destination", chats=[])
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

        # ===== ورود کد تخفیف هنگام خرید (کاربر تاییدشده) =====
        if current_state_name == "awaiting_buy_code":
            if text:
                from auth_handlers import handle_discount_code_input
                ok = handle_discount_code_input(chat_id, username, text, bot_token,
                                                current_state_data.get('plan_id'),
                                                lang=get_user_lang(chat_id))
                if ok:
                    clear_state(chat_id)
            return

        # ===== ویزارد کد تخفیف: ورود کد =====
        if current_state_name == "awaiting_disc_code":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            norm = AuthManager.normalize_discount_code(text or "")
            if not norm or not AuthManager.is_valid_discount_code_format(norm):
                send_message(chat_id, "❌ فرمت کد نامعتبر است.\n"
                                      "3 تا 32 کاراکتر (حروف، عدد، - و _) وارد کنید.")
                return
            if auth_manager.get_discount_by_code(norm, with_relations=False):
                send_message(chat_id, f"❌ این کد قبلاً ثبت شده: `{norm}`\nکد دیگری وارد کنید.")
                return
            disc = current_state_data.get('disc', {})
            disc['code'] = norm
            set_state(chat_id, "awaiting_disc_type", disc=disc)
            _disc_send_type_menu(chat_id, norm)
            return

        # ===== ویزارد کد تخفیف: مقدار (درصد/مبلغ) + محاسبه خودکار معادل =====
        elif current_state_name == "awaiting_disc_value":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            from auth_handlers import fa_to_en_digits
            disc = current_state_data.get('disc', {})
            raw = fa_to_en_digits(text)
            if disc.get('discount_type') == 'percent':
                try:
                    pct = int(raw)
                    if not 1 <= pct <= 100:
                        raise ValueError
                except ValueError:
                    send_message(chat_id, "❌ عدد نامعتبر! درصد بین 1 تا 100 وارد کنید.")
                    return
                disc['percent'] = pct
                disc['amount_rial'] = 0
                set_state(chat_id, "awaiting_disc_maxcap", disc=disc)
                eq = _disc_equivalents_text({
                    'discount_type': 'percent', 'percent': pct,
                    'amount_rial': 0, 'max_discount_rial': None})
                kb = {"inline_keyboard": [
                    [{"text": t(chat_id, "disc_skip"), "callback_data": "admin_disc_skip_maxcap"}],
                    [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
                ]}
                msg = f"✅ ثبت شد: ٪{pct}\n\n"
                if eq:
                    msg += eq + "\n\n"
                msg += ("🎯 *مرحله ۴: سقف تخفیف (اختیاری)؟*\n\n"
                        "حداکثر مبلغ تخفیف به تومان (مثلاً `200000`)؟\n"
                        "اگر سقفی نمی‌خواهید، رد کنید.")
                send_message(chat_id, msg, kb)
            else:
                try:
                    toman = int(raw)
                    if toman <= 0:
                        raise ValueError
                except ValueError:
                    send_message(chat_id, "❌ مبلغ نامعتبر! عدد بزرگ‌تر از صفر (تومان) وارد کنید.")
                    return
                disc['amount_rial'] = toman * 10
                disc['percent'] = None
                disc['max_discount_rial'] = None
                set_state(chat_id, "awaiting_disc_scope", disc=disc)
                eq = _disc_equivalents_text({
                    'discount_type': 'fixed', 'percent': None,
                    'amount_rial': toman * 10, 'max_discount_rial': None})
                if eq:
                    send_message(chat_id, f"✅ ثبت شد: {toman:,} تومان\n\n" + eq)
                _disc_send_scope_menu(chat_id)
            return

        # ===== ویزارد کد تخفیف: سقف درصدی =====
        elif current_state_name == "awaiting_disc_maxcap":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            from auth_handlers import fa_to_en_digits
            disc = current_state_data.get('disc', {})
            raw = fa_to_en_digits(text)
            if raw == "0":
                disc['max_discount_rial'] = None
            else:
                try:
                    toman = int(raw)
                    if toman <= 0:
                        raise ValueError
                    disc['max_discount_rial'] = toman * 10
                except ValueError:
                    send_message(chat_id, "❌ مبلغ نامعتبر! عدد (تومان) وارد کنید یا رد کنید.")
                    return
            set_state(chat_id, "awaiting_disc_scope", disc=disc)
            _disc_send_scope_menu(chat_id)
            return

        # ===== ویزارد کد تخفیف: کاربران شخصی =====
        # ===== پیکر کاربر: دریافت متن جستجو =====
        elif current_state_name == "awaiting_disc_usearch":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            current_state_data['query'] = (text or "").strip()
            current_state_data['page'] = 0
            _restore_pick_state(chat_id, current_state_data)
            handle_userpick_menu(chat_id)
            return

        elif current_state_name == "awaiting_disc_users":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            ids, bad = _parse_chat_ids(text)
            if bad:
                send_message(chat_id, f"❌ این‌ها آیدی معتبر نیستند: {', '.join(bad[:5])}\n"
                                      f"فقط عدد وارد کنید.")
                return
            if not ids:
                send_message(chat_id, "❌ حداقل یک آیدی معتبر وارد کنید.")
                return
            # هشدار برای آیدی‌های ثبت‌نشده (اما قبول می‌کنیم - وقتی عضو شوند کار می‌کند)
            unknown = []
            for uid in ids:
                try:
                    if not auth_manager.get_user_info(uid):
                        unknown.append(str(uid))
                except Exception:
                    pass
            disc = current_state_data.get('disc', {})
            disc['allowed_chat_ids'] = ids
            set_state(chat_id, "awaiting_disc_plans", disc=disc)
            if unknown:
                send_message(chat_id,
                             f"⚠️ این آیدی‌ها هنوز در ربات ثبت نشده‌اند (اشکالی ندارد، "
                             f"وقتی /start کنند کد برایشان کار می‌کند):\n`{', '.join(unknown[:10])}`")
            send_message(chat_id, f"✅ {len(ids)} کاربر ثبت شد.")
            _disc_send_plans_menu(chat_id)
            return

        # ===== ویزارد کد تخفیف: سقف کل =====
        elif current_state_name == "awaiting_disc_total":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            from auth_handlers import fa_to_en_digits
            raw = fa_to_en_digits(text).strip().lower()
            disc = current_state_data.get('disc', {})
            if raw in ("0", "نامحدود", "unlimited"):
                disc['total_limit'] = None
            else:
                try:
                    v = int(raw)
                    if v < 1:
                        raise ValueError
                    disc['total_limit'] = v
                except ValueError:
                    send_message(chat_id, "❌ عدد نامعتبر! عدد ≥ 1 یا نامحدود.")
                    return
            set_state(chat_id, "awaiting_disc_peruser", disc=disc)
            kb = {"inline_keyboard": [
                [{"text": "⏭️ پیش‌فرض (۱ بار)", "callback_data": "admin_disc_skip_peruser"}],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         "👤 *مرحله ۸: سقف استفاده هر کاربر؟*\n\n"
                         "هر کاربر چند بار بتواند از این کد استفاده کند؟\n"
                         "مثال: `1` (پیشنهاد امنیتی: ۱ بار)",
                         kb)
            return

        # ===== ویزارد کد تخفیف: سقف هر کاربر =====
        elif current_state_name == "awaiting_disc_peruser":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            from auth_handlers import fa_to_en_digits
            try:
                v = int(fa_to_en_digits(text))
                if v < 1 or v > 1000000:
                    raise ValueError
            except ValueError:
                send_message(chat_id, "❌ عدد نامعتبر! عدد ≥ 1 وارد کنید.")
                return
            disc = current_state_data.get('disc', {})
            disc['per_user_limit'] = v
            set_state(chat_id, "awaiting_disc_expiry", disc=disc)
            kb = {"inline_keyboard": [
                [
                    {"text": "۷ روز", "callback_data": "admin_disc_exp_7"},
                    {"text": "۳۰ روز", "callback_data": "admin_disc_exp_30"},
                ],
                [
                    {"text": "۹۰ روز", "callback_data": "admin_disc_exp_90"},
                    {"text": t(chat_id, "disc_unlimited"), "callback_data": "admin_disc_exp_0"},
                ],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         "⏰ *مرحله ۹: مدت اعتبار؟*\n\n"
                         "• عدد = روز از الان (مثلاً `30`)\n"
                         "• تاریخ شمسی (`1405/07/15`) یا میلادی (`2026-10-07`)\n"
                         "• یا نامحدود",
                         kb)
            return

        # ===== ویزارد کد تخفیف: انقضا =====
        elif current_state_name == "awaiting_disc_expiry":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            from auth_handlers import parse_expiry_input
            parsed = parse_expiry_input(text or "")
            if not parsed.get('success'):
                send_message(chat_id, f"❌ {parsed.get('error')}")
                return
            disc = current_state_data.get('disc', {})
            disc['expires_at'] = parsed.get('expires_at')
            disc['expires_label'] = parsed.get('label')
            set_state(chat_id, "awaiting_disc_min", disc=disc)
            kb = {"inline_keyboard": [
                [{"text": t(chat_id, "disc_skip"), "callback_data": "admin_disc_skip_min"}],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         f"⏰ اعتبار: {parsed.get('label')}\n\n"
                         "🧾 *کف مبلغ خرید (اختیاری):*\n\n"
                         "کد فقط برای پلن‌هایی که قیمتشان از این مبلغ بیشتر است کار کند؟\n"
                         "مبلغ به تومان (مثلاً `100000`) یا رد کنید.",
                         kb)
            return

        # ===== ویزارد کد تخفیف: کف خرید =====
        elif current_state_name == "awaiting_disc_min":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            from auth_handlers import fa_to_en_digits
            disc = current_state_data.get('disc', {})
            raw = fa_to_en_digits(text)
            if raw == "0":
                disc['min_order_rial'] = None
            else:
                try:
                    toman = int(raw)
                    if toman <= 0:
                        raise ValueError
                    disc['min_order_rial'] = toman * 10
                except ValueError:
                    send_message(chat_id, "❌ مبلغ نامعتبر! عدد (تومان) وارد کنید یا رد کنید.")
                    return
            set_state(chat_id, "awaiting_disc_firstonly", disc=disc)
            kb = {"inline_keyboard": [
                [
                    {"text": "✅ بله، فقط خرید اول", "callback_data": "admin_disc_first_yes"},
                    {"text": "❌ نه، همه", "callback_data": "admin_disc_first_no"},
                ],
                [{"text": t(chat_id, "disc_cancel"), "callback_data": "admin_disc_cancel"}],
            ]}
            send_message(chat_id,
                         "🛒 *فقط برای خرید اول؟*\n\n"
                         "اگر «بله»، کاربرانی که قبلاً خرید موفق داشته‌اند "
                         "نمی‌توانند از این کد استفاده کنند.",
                         kb)
            return

        # ===== ویزارد کد تخفیف: عنوان =====
        elif current_state_name == "awaiting_disc_title":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            disc = current_state_data.get('disc', {})
            disc['title'] = (text or "").strip()[:100]
            set_state(chat_id, "awaiting_disc_confirm", disc=disc)
            _disc_send_confirm(chat_id)
            return

        # ===== تایید نهایی: فقط دکمه =====
        elif current_state_name == "awaiting_disc_confirm":
            send_message(chat_id, "لطفاً از دکمه‌های «ثبت نهایی» یا «انصراف» استفاده کنید.")
            return

        # ===== ویرایش کد: مقدار =====
        elif current_state_name == "awaiting_disc_edit_value":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            from auth_handlers import fa_to_en_digits
            did = current_state_data.get('disc_id')
            d = auth_manager.get_discount(did)
            if not d:
                clear_state(chat_id)
                return
            try:
                v = int(fa_to_en_digits(text))
            except ValueError:
                send_message(chat_id, "❌ عدد نامعتبر!")
                return
            if d['discount_type'] == 'percent':
                if not 1 <= v <= 100:
                    send_message(chat_id, "❌ درصد باید بین 1 تا 100 باشد.")
                    return
                res = auth_manager.update_discount(did, percent=v)
            else:
                if v <= 0:
                    send_message(chat_id, "❌ مبلغ باید بزرگ‌تر از صفر باشد.")
                    return
                res = auth_manager.update_discount(did, amount_rial=v * 10)
            clear_state(chat_id)
            if res.get('success'):
                auth_manager.log_activity(chat_id, "disc_edit", f"{did} value->{v}")
                send_message(chat_id, "✅ مقدار تخفیف به‌روزرسانی شد.")
            else:
                send_message(chat_id, f"❌ {res.get('error', 'خطا')}")
            handle_discount_detail(chat_id, did)
            return

        # ===== ویرایش کد: سقف/کف/ظرفیت‌ها =====
        elif current_state_name in ("awaiting_disc_edit_cap", "awaiting_disc_edit_min",
                                    "awaiting_disc_edit_total", "awaiting_disc_edit_peruser"):
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            from auth_handlers import fa_to_en_digits
            did = current_state_data.get('disc_id')
            field_map = {"awaiting_disc_edit_cap": "max_discount_rial",
                         "awaiting_disc_edit_min": "min_order_rial",
                         "awaiting_disc_edit_total": "total_limit",
                         "awaiting_disc_edit_peruser": "per_user_limit"}
            field = field_map[current_state_name]
            raw = fa_to_en_digits(text).strip().lower()
            if raw in ("0", "نامحدود", "unlimited", "-") and field != "per_user_limit":
                new_val = None
            else:
                try:
                    new_val = int(raw)
                    if field == "per_user_limit":
                        if new_val < 1:
                            raise ValueError
                    elif new_val <= 0:
                        raise ValueError
                except ValueError:
                    send_message(chat_id, "❌ عدد نامعتبر!")
                    return
                if field in ("max_discount_rial", "min_order_rial"):
                    new_val = new_val * 10  # تومان → ریال
            res = auth_manager.update_discount(did, **{field: new_val})
            clear_state(chat_id)
            if res.get('success'):
                auth_manager.log_activity(chat_id, "disc_edit", f"{did} {field}->{new_val}")
                send_message(chat_id, "✅ به‌روزرسانی شد.")
            else:
                send_message(chat_id, f"❌ {res.get('error', 'خطا')}")
            handle_discount_detail(chat_id, did)
            return

        # ===== ویرایش کد: انقضا =====
        elif current_state_name == "awaiting_disc_edit_expiry":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            from auth_handlers import parse_expiry_input
            did = current_state_data.get('disc_id')
            parsed = parse_expiry_input(text or "")
            if not parsed.get('success'):
                send_message(chat_id, f"❌ {parsed.get('error')}")
                return
            res = auth_manager.update_discount(did, expires_at=parsed.get('expires_at'))
            clear_state(chat_id)
            if res.get('success'):
                send_message(chat_id, f"✅ انقضا تنظیم شد: {parsed.get('label')}")
            else:
                send_message(chat_id, f"❌ {res.get('error', 'خطا')}")
            handle_discount_detail(chat_id, did)
            return

        # ===== ویرایش کد: عنوان =====
        elif current_state_name == "awaiting_disc_edit_title":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            did = current_state_data.get('disc_id')
            title = (text or "").strip()[:100]
            if title == "-":
                title = ""
            res = auth_manager.update_discount(did, title=title)
            clear_state(chat_id)
            if res.get('success'):
                send_message(chat_id, "✅ عنوان به‌روزرسانی شد.")
            else:
                send_message(chat_id, f"❌ {res.get('error', 'خطا')}")
            handle_discount_detail(chat_id, did)
            return

        # ===== افزودن کاربر مجاز =====
        elif current_state_name in ("awaiting_disc_useradd", "awaiting_disc_eusers"):
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            did = current_state_data.get('disc_id')
            ids, bad = _parse_chat_ids(text)
            if bad:
                send_message(chat_id, f"❌ این‌ها معتبر نیستند: {', '.join(bad[:5])}")
                return
            if not ids:
                send_message(chat_id, "❌ حداقل یک آیدی معتبر وارد کنید.")
                return
            if current_state_name == "awaiting_disc_eusers":
                # تبدیل به شخصی + افزودن کاربران
                auth_manager.update_discount(did, scope='personal')
            res = auth_manager.add_discount_users(did, ids)
            clear_state(chat_id)
            if res.get('success'):
                auth_manager.log_activity(chat_id, "disc_users_add",
                                          f"{did} +{res.get('added', 0)}")
                send_message(chat_id, f"✅ {res.get('added', 0)} کاربر اضافه شد.")
            else:
                send_message(chat_id, f"❌ {res.get('error', 'خطا')}")
            if current_state_name == "awaiting_disc_eusers":
                handle_discount_detail(chat_id, did)
            else:
                handle_discount_users(chat_id, did)
            return

        # ===== ویزارد ساخت پلن جدید: نام =====
        if current_state_name == "awaiting_plan_name":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            plan_name = (text or "").strip()
            if not plan_name:
                send_message(chat_id, t(chat_id, "invalid_days"))
                return
            user_states[chat_id] = {"state": "awaiting_plan_days", "plan_name": plan_name}
            send_message(chat_id, t(chat_id, "plan_days_prompt"))
            return

        # ===== ویزارد ساخت پلن: مدت =====
        elif current_state_name == "awaiting_plan_days":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            raw = (text or "").strip().lower()
            duration_days = None
            if raw in ("permanent", "دائمی", "0", "inf", "lifetime"):
                duration_days = None
            else:
                try:
                    duration_days = int(raw)
                    if duration_days <= 0:
                        raise ValueError
                except ValueError:
                    send_message(chat_id, t(chat_id, "invalid_days"))
                    return
            saved_plan_name = current_state_data.get("plan_name", "")
            user_states[chat_id] = {
                "state": "awaiting_plan_price",
                "plan_name": saved_plan_name,
                "plan_days": duration_days,
            }
            send_message(chat_id, t(chat_id, "plan_price_prompt"))
            return

        # ===== ویزارد ساخت پلن: قیمت (ایجاد نهایی) =====
        elif current_state_name == "awaiting_plan_price" and "plan_name" in current_state_data:
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            raw = (text or "").strip().replace(",", "").replace("،", "")
            try:
                price_toman = int(raw)
                if price_toman <= 0:
                    raise ValueError
            except ValueError:
                send_message(chat_id, t(chat_id, "invalid_days"))
                return
            plan_name = current_state_data.get("plan_name")
            duration_days = current_state_data.get("plan_days")
            price_rial = price_toman * 10
            result = auth_manager.create_plan(plan_name, duration_days, price_rial)
            clear_state(chat_id)
            if result.get("success"):
                try:
                    from auth_handlers import broadcast_new_plan
                    plan = auth_manager.get_plan(result["plan_id"])
                    bot_tk = config['messengers']['bale']['bot_token']
                    sent, failed = broadcast_new_plan(plan, bot_tk)
                    send_message(
                        chat_id,
                        f"{t(chat_id, 'plan_created_success')} ✅\n📣 اطلاع‌رسانی به {sent} کاربر ارسال شد",
                        {"inline_keyboard": [[{"text": t(chat_id, "back_to_admin_menu"), "callback_data": "admin_tariffs_back"}]]}
                    )
                except Exception as be:
                    logger.error(f"❌ broadcast error: {be}")
                    send_message(
                        chat_id,
                        t(chat_id, "plan_created_success"),
                        {"inline_keyboard": [[{"text": t(chat_id, "back_to_admin_menu"), "callback_data": "admin_tariffs_back"}]]}
                    )
            else:
                send_message(chat_id, f"❌ {result.get('error', 'خطا')}", create_admin_menu_keyboard(chat_id))
            return

        # ===== ویرایش قیمت پلن موجود =====
        elif current_state_name == "awaiting_plan_price" and "plan_id" in current_state_data:
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            raw = (text or "").strip().replace(",", "").replace("،", "")
            try:
                price_toman = int(raw)
                if price_toman <= 0:
                    raise ValueError
            except ValueError:
                send_message(chat_id, t(chat_id, "invalid_days"))
                return
            plan_id = current_state_data.get("plan_id")
            result = auth_manager.update_plan(plan_id, price_rial=price_toman * 10)
            clear_state(chat_id)
            if result.get("success"):
                try:
                    from auth_handlers import broadcast_new_plan
                    plan = auth_manager.get_plan(plan_id)
                    bot_tk = config['messengers']['bale']['bot_token']
                    sent, failed = broadcast_new_plan(plan, bot_tk)
                    send_message(chat_id, f"{t(chat_id, 'price_set_success')}\n📣 اطلاع‌رسانی به {sent} کاربر ارسال شد")
                except Exception:
                    send_message(chat_id, t(chat_id, "price_set_success"))
                handle_plan_detail(chat_id, plan_id)
            else:
                send_message(chat_id, f"❌ {result.get('error', 'خطا')}")
            return

        # ===== ویرایش مدت پلن موجود =====
        elif current_state_name == "awaiting_plan_duration":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            raw = (text or "").strip().lower()
            duration_days = None
            if raw in ("permanent", "دائمی", "0", "inf", "lifetime"):
                duration_days = None
            else:
                try:
                    duration_days = int(raw)
                    if duration_days <= 0:
                        raise ValueError
                except ValueError:
                    send_message(chat_id, t(chat_id, "invalid_days"))
                    return
            plan_id = current_state_data.get("plan_id")
            result = auth_manager.update_plan(plan_id, duration_days=duration_days)
            clear_state(chat_id)
            if result.get("success"):
                send_message(chat_id, t(chat_id, "duration_set_success"))
                handle_plan_detail(chat_id, plan_id)
            else:
                send_message(chat_id, f"❌ {result.get('error', 'خطا')}")
            return

        # ===== روزهای دلخواه - هدیه رایگان =====
        elif current_state_name == "awaiting_custom_grant_days":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            try:
                days = int((text or "").strip())
                if days <= 0 or days > 3650:
                    raise ValueError
            except ValueError:
                send_message(chat_id, t(chat_id, "invalid_days"))
                return
            target_id = current_state_data.get("target_id")
            clear_state(chat_id)
            handle_grant_free_set(chat_id, target_id, days)
            return

        # ===== روزهای دلخواه - تمدید =====
        elif current_state_name == "awaiting_custom_extend_days":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            try:
                days = int((text or "").strip())
                if days <= 0 or days > 3650:
                    raise ValueError
            except ValueError:
                send_message(chat_id, t(chat_id, "invalid_days"))
                return
            target_id = current_state_data.get("target_id")
            clear_state(chat_id)
            handle_extend_set(chat_id, target_id, days)
            return

        # ===== مدت تست پیش‌فرض =====
        elif current_state_name == "awaiting_trial_days":
            if not auth_manager.is_admin(chat_id):
                clear_state(chat_id)
                return
            try:
                days = int((text or "").strip())
                if days < 0 or days > 365:
                    raise ValueError
            except ValueError:
                send_message(chat_id, t(chat_id, "invalid_days"))
                return
            auth_manager.set_default_trial_days(days)
            clear_state(chat_id)
            send_message(chat_id, f"{t(chat_id, 'trial_days_success')}: {days} روز", create_admin_menu_keyboard(chat_id))
            auth_manager.log_activity(chat_id, "trial_days_change", f"{days}d")
            return

        # ===== اضافه کردن ادمین جدید =====
        elif current_state_name == "awaiting_new_admin_id":
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

        # ===== پیکربندی WhatsApp - نسخه نهایی FIXED v2 - force reset + No sessions =====
        elif current_state_name == "waiting_whatsapp_chat":
            # دستورات خاص اول
            wa_input_raw = text.strip()
            lang = get_user_lang(chat_id)

            # ✅ FIX: دستورات force reset برای حل "قبلا سشن هست" و "No sessions"
            if wa_input_raw.lower() in ["reset", "force", "force reset", "newqr force", "ریست", "حذف سشن", "force qr", "new qr force", "پاک کردن سشن"]:
                try:
                    import messenger_whatsapp
                    wa_cfg = user_config["messengers"].get("whatsapp", {})
                    service_url = wa_cfg.get("service_url", "http://localhost:3001")
                    phone_for_reset = wa_cfg.get("phone_number") or wa_cfg.get("own_phone") or wa_cfg.get("chat_id") or ""
                    send_message(chat_id, f"🔥 در حال حذف کامل سشن خراب {chat_id} و ساخت QR جدید..." if lang == "fa" else f"🔥 Force deleting corrupted session {chat_id}...")
                    # force reset
                    result = messenger_whatsapp.force_reset_session(chat_id, phone_for_reset, service_url)
                    if result.get("ok") or result.get("hasQR") or result.get("qrImage"):
                        # QR جدید بفرست
                        if result.get("qrImage"):
                            import base64, tempfile, os
                            b64 = result["qrImage"].split(",")[1] if "," in result["qrImage"] else result["qrImage"]
                            qr_bytes = base64.b64decode(b64)
                            bale_token = config["messengers"]["bale"]["bot_token"]
                            api = f"https://tapi.bale.ai/bot{bale_token}"
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                                tmp.write(qr_bytes)
                                tmp_path = tmp.name
                            with open(tmp_path, "rb") as f:
                                files = {"photo": ("qr.png", f, "image/png")}
                                pc = result.get("pairingCode","")
                                caption = f"🔥 QR جدید بعد از حذف سشن خراب - کد {pc}" if pc else "🔥 QR جدید بعد از حذف سشن خراب"
                                data = {"chat_id": chat_id, "caption": caption}
                                requests.post(f"{api}/sendPhoto", data=data, files=files, timeout=20)
                                os.unlink(tmp_path)
                            if result.get("pairingCode"):
                                pc = result.get("pairingCode")
                                send_message(chat_id, f"{pc}\n\n👆 کپی کن - QR جدید")
                                send_message(chat_id, f"{pc.replace('-','')}\n\n👆 بدون خط تیره")
                        else:
                            # درخواست QR جدید با force
                            qr2 = messenger_whatsapp.get_qr_for_user(chat_id, phone_for_reset, service_url, force=True)
                            if qr2.get("qrImage"):
                                import base64, tempfile, os
                                b64 = qr2["qrImage"].split(",")[1] if "," in qr2["qrImage"] else qr2["qrImage"]
                                qr_bytes = base64.b64decode(b64)
                                bale_token = config["messengers"]["bale"]["bot_token"]
                                api = f"https://tapi.bale.ai/bot{bale_token}"
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                                    tmp.write(qr_bytes)
                                    tmp_path = tmp.name
                                with open(tmp_path, "rb") as f:
                                    files = {"photo": ("qr.png", f, "image/png")}
                                    data = {"chat_id": chat_id, "caption": "🔥 QR جدید (force) - اسکن کن"}
                                    requests.post(f"{api}/sendPhoto", data=data, files=files, timeout=20)
                                    os.unlink(tmp_path)
                                if qr2.get("pairingCode"):
                                    send_message(chat_id, f"{qr2.get('pairingCode')}\n\n👆 کپی")
                        keyboard = {"inline_keyboard": [[{"text": "✅ بررسی اتصال", "callback_data": "check_whatsapp_status"}]]}
                        send_message(chat_id, "✅ سشن خراب حذف شد! QR جدید بالا را اسکن کن و بعد بررسی بزن" if lang == "fa" else "Corrupted session deleted, new QR above", keyboard)
                        set_state(chat_id, "waiting_whatsapp_qr_check", phone=phone_for_reset, own_phone=phone_for_reset, last_qr=result.get("qr",""))
                    else:
                        send_message(chat_id, f"❌ حذف سشن ناموفق: {result}\nسعی کن دوباره یا شماره خودت را بفرست: 989..." if lang == "fa" else f"Failed: {result}")
                except Exception as e:
                    logger.error(f"Force reset error: {e}", exc_info=True)
                    send_message(chat_id, f"❌ خطا در force reset: {e}\nدستی: curl -X DELETE http://localhost:3001/session?userId={chat_id}&force=true")
                return
            
            if wa_input_raw.lower() in ["groups", "گروه", "گروه‌ها", "لیست", "list", "group"]:
                try:
                    import messenger_whatsapp
                    wa_cfg = user_config["messengers"].get("whatsapp", {})
                    service_url = wa_cfg.get("service_url", "http://localhost:3001")
                    status = messenger_whatsapp.check_connection_status(chat_id, service_url)
                    if not status.get("connected"):
                        send_message(chat_id, "❌ واتساپ متصل نیست، اول شماره خودت رو بفرست تا وصل بشی" if lang == "fa" else "❌ Not connected")
                        return
                    send_message(chat_id, "⏳ در حال دریافت لیست گروه‌ها... ممکن است 30 ثانیه طول بکشد (واتساپ در حال همگام‌سازی)")
                    chats_result = messenger_whatsapp.get_chats_for_user(chat_id, service_url)
                    if chats_result.get("ok") and chats_result.get("chats") is not None:
                        chats = chats_result["chats"]
                        if len(chats) == 0:
                            debug = chats_result.get("debug", {})
                            msg = (
                                f"⚠️ *هنوز گروهی پیدا نشد*\n"
                                f"دیباگ: {debug}\n\n"
                                "واتساپ بعد از اتصال 60 ثانیه طول می‌کشد تا گروه‌ها sync کند.\n"
                                "🔄 30 ثانیه صبر کن و دوباره بنویس `groups`\n\n"
                                "✅ یا دستی گروه هدف را انتخاب کن:\n"
                                "`120363312386194255@g.us`"
                            )
                            keyboard = {
                                "inline_keyboard": [
                                    [{"text": "🔄 تلاش مجدد - لیست گروه‌ها", "callback_data": "wa_list_groups"}],
                                    [{"text": "✅ انتخاب گروه 120363312386194255", "callback_data": "wa_select_dest_120363312386194255@g.us"}],
                                    [{"text": "📋 لیست گروه‌ها", "callback_data": "wa_list_groups"}]
                                ]
                            }
                            send_message(chat_id, msg, keyboard)
                            set_state(chat_id, "waiting_whatsapp_destination", chats=[])
                            return
                        keyboard = []
                        for chat in chats[:15]:
                            name = chat.get("name", "Unknown")[:30]
                            chat_id_val = chat.get("id", "")
                            participants = chat.get("participants", 0)
                            btn_text = f"👥 {name} ({participants})" if participants else f"👥 {name}"
                            keyboard.append([{"text": btn_text, "callback_data": f"wa_select_dest_{chat_id_val}"}])
                        # اگر گروه هدف نیست، اضافه کن
                        target_group = "120363312386194255@g.us"
                        if not any(c.get("id") == target_group for c in chats):
                            keyboard.append([{"text": f"👥 گروه هدف 120363...", "callback_data": f"wa_select_dest_{target_group}"}])
                        keyboard.append([{"text": "📱 شماره شخصی", "callback_data": "wa_select_personal"}])
                        send_message(chat_id, f"📋 {len(chats)} گروه پیدا شد، انتخاب کنید:", {"inline_keyboard": keyboard})
                        set_state(chat_id, "waiting_whatsapp_destination", chats=chats)
                    else:
                        err = chats_result.get('error','')
                        debug = chats_result.get('debug','')
                        raw = chats_result.get('raw','')
                        send_message(chat_id, f"❌ خطا: {err}\nدیباگ: {debug}\n{raw}\n\nدستی بفرست: 120363312386194255@g.us")
                        set_state(chat_id, "waiting_whatsapp_destination", chats=[])
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    send_message(chat_id, f"❌ خطا: {e}\nدستی بفرست: 120363312386194255@g.us")
                    set_state(chat_id, "waiting_whatsapp_destination", chats=[])
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
            # ===== اگر کاربر مستقیم آیدی گروه فرستاد، به عنوان مقصد ذخیره کن (حتی اگر در حالت شماره خودت باشد) =====
            raw_for_group = wa_input_raw.strip()
            if "@g.us" in raw_for_group or raw_for_group.startswith("120363") or (raw_for_group.replace("@g.us","").replace("@s.whatsapp.net","").isdigit() and len(raw_for_group.replace("@g.us","").replace("@s.whatsapp.net","")) > 15):
                normalized_group = raw_for_group.replace(" ", "").replace("+", "").strip()
                if "@g.us" not in normalized_group and "@s.whatsapp.net" not in normalized_group:
                    if normalized_group.isdigit() and (normalized_group.startswith("120363") or len(normalized_group) > 15):
                        normalized_group = f"{normalized_group}@g.us"
                user_config["messengers"]["whatsapp"]["chat_id"] = normalized_group
                user_config["messengers"]["whatsapp"]["destination_selected"] = True
                if user_config["messengers"]["whatsapp"].get("phone_number"):
                    user_config["messengers"]["whatsapp"]["connected"] = True
                save_user_config(chat_id, user_config)
                success_msg = (
                    f"✅ *گروه به عنوان مقصد ذخیره شد!* 🎉\n\n"
                    f"📱 مقصد: {normalized_group}\n"
                    f"🔗 وضعیت: متصل + مقصد ✅\n\n"
                    "⏳ در حال ارسال پیام تست..."
                    if lang == "fa"
                    else f"✅ Group saved as destination: {normalized_group}"
                )
                send_message(chat_id, success_msg)
                try:
                    import messenger_whatsapp
                    wa_cfg = user_config["messengers"].get("whatsapp", {})
                    service_url = wa_cfg.get("service_url", "http://localhost:3001")
                    test_text = "✅ ربات متصل شد! اوکی وصله 🎉\n\nاین گروه به عنوان مقصد انتخاب شد"
                    result = messenger_whatsapp._send_via_neonize(normalized_group, test_text, None, service_url, str(chat_id))
                    if result:
                        send_message(chat_id, "✅ پیام تست ارسال شد! اوکی وصله 🎉" if lang == "fa" else "✅ Test sent!", create_messengers_keyboard(chat_id, user_config))
                    else:
                        send_message(chat_id, "⚠️ تنظیمات ذخیره شد ولی پیام تست ارسال نشد - ممکن است واتساپ هنوز sync نشده یا گروه وجود ندارد" if lang == "fa" else "⚠️ Saved but test failed", create_messengers_keyboard(chat_id, user_config))
                except Exception as e:
                    send_message(chat_id, "⚠️ ذخیره شد" if lang == "fa" else "Saved", create_messengers_keyboard(chat_id, user_config))
                clear_state(chat_id)
                return

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
            user_config["messengers"]["whatsapp"]["provider"] = "neonize"
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
            
            # نرمال‌سازی ورودی - حفظ آیدی گروه @g.us
            normalized = dest_input.replace(" ", "").replace("+", "").strip()
            # اگر آیدی گروه کامل است، دست نزن
            if "@g.us" in normalized or "@s.whatsapp.net" in normalized:
                pass  # همان بماند
            elif normalized.startswith("120363") or (normalized.isdigit() and len(normalized) > 15):
                # گروه واتساپ - @g.us اضافه کن اگر نیست
                if "@g.us" not in normalized:
                    normalized = f"{normalized}@g.us"
            else:
                # شماره شخصی
                if normalized.startswith("0"):
                    normalized = "98" + normalized[1:]
                if normalized.isdigit() and len(normalized) == 10 and normalized.startswith("9"):
                    normalized = "98" + normalized
            
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
                result = messenger_whatsapp._send_via_neonize(normalized, test_text, None, service_url, str(chat_id))
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
    """دریافت update‌های جدید - با retry مقاوم"""
    global config
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset

    for attempt in range(3):
        try:
            response = requests.get(f"{api}/getUpdates", params=params, timeout=35)
            return response.json()
        except Exception as e:
            if attempt == 0:
                logger.warning(f"⚠️ getUpdates failed attempt {attempt+1}: {e} - retrying...")
            if attempt < 2:
                import time; time.sleep(2)
            else:
                logger.error(f"❌ getUpdates failed after 3 attempts: {e} - likely DNS/internet issue")
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
