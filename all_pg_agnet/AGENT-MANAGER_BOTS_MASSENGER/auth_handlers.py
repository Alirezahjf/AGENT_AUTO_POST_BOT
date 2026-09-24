# auth_handlers.py
import requests
from logger import logger
from auth_manager import AuthManager
from config import load_config, save_config
from pathlib import Path
import json

auth_manager = AuthManager()

# ========== تنظیمات پرداخت ==========
# توکن کیف‌پول بیل - از config.json خوانده می‌شود
PAYMENT_AMOUNT = 200000000  # مبلغ پیش‌فرض به ریال (fallback اگر پلنی تنظیم نشده)
PAYMENT_CURRENCY = "IRR"


def get_wallet_token():
    """دریافت توکن کیف‌پول از config"""
    config = load_config()
    return config.get("wallet_token", "")


def get_default_trial_days():
    """مدت تست رایگان پیش‌فرض - توسط ادمین قابل تنظیم"""
    try:
        return max(0, int(load_config().get("default_trial_days", 1)))
    except Exception:
        return 1


def get_active_plans():
    """دریافت پلن‌های فعال خرید (تعرفه‌ها)"""
    try:
        return auth_manager.get_plans(include_disabled=False)
    except Exception as e:
        logger.error(f"❌ خطا در دریافت پلن‌ها: {e}")
        return []


def format_price_rial(price_rial):
    """فرمت قیمت: ریال → تومان"""
    try:
        toman = int(price_rial) // 10
        return f"{toman:,} تومان"
    except Exception:
        return str(price_rial)


def format_duration_fa(duration_days):
    """فرمت مدت به فارسی"""
    if duration_days is None:
        return "♾️ دائمی"
    days = int(duration_days)
    if days == 1:
        return "۱ روزه"
    if days == 30:
        return "۱ ماهه"
    if days == 90:
        return "۳ ماهه"
    if days == 180:
        return "۶ ماهه"
    if days == 365:
        return "۱ ساله"
    return f"{days} روزه"


def build_tariffs_text(lang="fa"):
    """متن لیست تعرفه‌ها"""
    plans = get_active_plans()
    if lang == "fa":
        if not plans:
            return "🏷️ *تعرفه‌ها*\n\nهنوز پلنی تنظیم نشده است.\nلطفاً با پشتیبانی تماس بگیرید."
        msg = "🏷️ *تعرفه‌های دسترسی*\n\n"
        msg += "یکی از پلن‌های زیر را انتخاب کنید:\n\n"
        for i, plan in enumerate(plans, 1):
            dur = format_duration_fa(plan['duration_days'])
            price = format_price_rial(plan['price_rial'])
            msg += f"{i}️⃣ *{plan['name']}* — {dur}\n"
            msg += f"    💰 {price}\n\n"
        msg += "💡 هر پلن بر اساس مدت دسترسی قیمت متفاوتی دارد."
    else:
        if not plans:
            return "🏷️ *Tariffs*\n\nNo plans configured yet.\nPlease contact support."
        msg = "🏷️ *Access Tariffs*\n\nSelect a plan:\n\n"
        for i, plan in enumerate(plans, 1):
            dur = plan['duration_days']
            dur_s = "Lifetime" if dur is None else f"{dur} days"
            toman = int(plan['price_rial']) // 10
            msg += f"{i}️⃣ *{plan['name']}* — {dur_s}\n"
            msg += f"    💰 {toman:,} TOMAN\n\n"
        msg += "💡 Each plan is priced by its access duration."
    return msg


def build_tariffs_keyboard(lang="fa"):
    """صفحه‌کلید لیست تعرفه‌ها با دکمه خرید هر پلن"""
    plans = get_active_plans()
    rows = []
    for plan in plans:
        dur = format_duration_fa(plan['duration_days']) if lang == "fa" else (
            "Lifetime" if plan['duration_days'] is None else f"{plan['duration_days']}d"
        )
        price = format_price_rial(plan['price_rial']) if lang == "fa" else (
            f"{int(plan['price_rial']) // 10:,} T"
        )
        rows.append([{
            "text": f"💳 {plan['name']} | {dur} | {price}",
            "callback_data": f"buy_plan_{plan['id']}"
        }])
    return {"inline_keyboard": rows}


# ========== صفحه‌کلیدهای احراز هویت ==========

def create_auth_keyboard_fa():
    """صفحه‌کلید انتخاب روش ورود (فارسی) - با دکمه تعرفه‌ها"""
    return {
        "inline_keyboard": [
            [
                {"text": "🔐 ورود با توکن", "callback_data": "auth_with_token"}
            ],
            [
                {"text": "📝 درخواست دسترسی", "callback_data": "auth_request_access"}
            ],
            [
                {"text": "🏷️ تعرفه‌ها و خرید", "callback_data": "show_tariffs"}
            ]
        ]
    }


def create_auth_keyboard_en():
    """صفحه‌کلید انتخاب روش ورود (انگلیسی) - با دکمه تعرفه‌ها"""
    return {
        "inline_keyboard": [
            [
                {"text": "🔐 Login with Token", "callback_data": "auth_with_token"}
            ],
            [
                {"text": "📝 Request Access", "callback_data": "auth_request_access"}
            ],
            [
                {"text": "🏷️ Tariffs & Buy", "callback_data": "show_tariffs"}
            ]
        ]
    }


# ========== ارسال پیام ==========

def send_message(chat_id, text, keyboard=None, bot_token=None):
    """ارسال پیام به کاربر - با retry مقاوم در برابر قطعی DNS/اینترنت"""
    if not bot_token:
        config = load_config()
        bot_token = config['messengers']['bale']['bot_token']

    api = f"https://tapi.bale.ai/bot{bot_token}"
    data = {"chat_id": chat_id, "text": text}

    if keyboard:
        data["reply_markup"] = keyboard

    # Retry 3 بار برای مقاومت در برابر قطعی موقت DNS/اینترنت
    for attempt in range(3):
        try:
            response = requests.post(f"{api}/sendMessage", json=data, timeout=15)
            if response.status_code == 200:
                logger.debug(f"✅ پیام برای {chat_id} ارسال شد (attempt {attempt+1})")
                return True
            else:
                logger.error(f"❌ خطا در ارسال پیام: {response.status_code} - {response.text[:200]} (attempt {attempt+1})")
                if attempt < 2:
                    import time; time.sleep(1 + attempt)
        except Exception as e:
            logger.error(f"❌ خطا در ارسال پیام (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                import time; time.sleep(2)
            else:
                logger.error(f"❌ ارسال پیام برای {chat_id} پس از 3 تلاش ناموفق ماند - احتمال قطعی اینترنت/DNS سرور")
    return False


def send_invoice_to_user(chat_id, bot_token, plan=None):
    """
    ارسال درخواست پرداخت (invoice) بر اساس پلن انتخاب شده
    اگر plan داده نشود، اولین پلن فعال یا مبلغ پیش‌فرض استفاده می‌شود
    """
    wallet_token = get_wallet_token()

    # انتخاب پلن
    if plan is None:
        plans = get_active_plans()
        plan = plans[0] if plans else None

    if plan:
        price_rial = int(plan['price_rial'])
        plan_name = plan['name']
        dur_days = plan['duration_days']
        plan_id = plan['id']
        dur_fa = format_duration_fa(dur_days)
    else:
        price_rial = PAYMENT_AMOUNT
        plan_name = "دسترسی دائمی"
        plan_id = 0
        dur_days = None
        dur_fa = "دائمی"

    if not wallet_token:
        logger.error("❌ wallet_token در config.json تنظیم نشده! پرداخت ممکن نیست")
        msg = (
            "❌ *سیستم پرداخت خودکار تنظیم نشده*\n\n"
            "💡 ادمین باید `wallet_token` را در `config.json` تنظیم کند.\n\n"
            "🔧 راه‌حل موقت:\n"
            "• با پشتیبانی تماس بگیرید\n"
            "• یا از ادمین بخواهید دستی شما را تایید کند\n"
            "• یا اگر تست رایگان دارید، فعلاً از ربات استفاده کنید\n\n"
            "📞 برای پرداخت دستی به ادمین پیام دهید."
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "📝 درخواست دسترسی به ادمین", "callback_data": "auth_request_access"}],
                [{"text": "🔙 بازگشت", "callback_data": "auth_back_to_menu"}]
            ]
        }
        send_message(chat_id, msg, keyboard, bot_token=bot_token)
        return False

    api = f"https://tapi.bale.ai/bot{bot_token}"

    import time
    payload = f"purchase_{chat_id}_{plan_id}_{int(time.time())}"

    price_toman = price_rial // 10
    desc_duration = "دسترسی دائمی و بدون محدودیت" if dur_days is None else f"دسترسی به مدت {dur_fa}"
    data = {
        "chat_id": chat_id,
        "title": f"خرید {plan_name} - {price_toman:,} تومان",
        "description": (
            f"📦 پلن: {plan_name} ({dur_fa})\n"
            f"✅ {desc_duration}\n"
            f"💰 قیمت: {price_toman:,} تومان\n\n"
            "پس از پرداخت، دسترسی شما فعال می‌شود."
        ),
        "payload": payload,
        "provider_token": wallet_token,
        "prices": [
            {
                "label": f"{plan_name} - {dur_fa}",
                "amount": price_rial
            }
        ]
    }

    for attempt in range(3):
        try:
            response = requests.post(f"{api}/sendInvoice", json=data, timeout=20)
            result = response.json()

            if result.get("ok"):
                logger.info(f"✅ فاکتور پرداخت پلن {plan_id} برای {chat_id} ارسال شد (attempt {attempt+1})")
                return True
            else:
                error_desc = result.get('description', 'خطای نامشخص')
                logger.error(f"❌ خطا در ارسال فاکتور (attempt {attempt+1}): {error_desc} - full={result}")
                if "PAYMENT_PROVIDER_INVALID" in error_desc or "provider" in error_desc.lower():
                    send_message(
                        chat_id,
                        f"❌ توکن کیف پول نامعتبر است!\n\nادمین باید wallet_token را چک کند.\nخطا: {error_desc}\n\nلطفاً با ادمین تماس بگیرید.",
                        bot_token=bot_token
                    )
                    return False
                if attempt < 2:
                    time.sleep(2)
                else:
                    send_message(
                        chat_id,
                        f"❌ خطا در ایجاد درخواست پرداخت: {error_desc}\n\nلطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
                        bot_token=bot_token
                    )
                    return False

        except Exception as e:
            logger.error(f"❌ Exception در send_invoice attempt {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(2)
            else:
                send_message(
                    chat_id,
                    "❌ خطا در اتصال به سرویس پرداخت (احتمال قطعی اینترنت سرور).\nلطفاً 1 دقیقه بعد دوباره روی پرداخت بزنید.",
                    bot_token=bot_token
                )
                return False
    return False


def answer_pre_checkout_query(pre_checkout_query_id, bot_token,
                               ok=True, error_message=None):
    """پاسخ به درخواست تایید پیش از پرداخت"""
    api = f"https://tapi.bale.ai/bot{bot_token}"
    data = {
        "pre_checkout_query_id": pre_checkout_query_id,
        "ok": ok
    }
    if not ok and error_message:
        data["error_message"] = error_message

    try:
        response = requests.post(
            f"{api}/answerPreCheckoutQuery", json=data, timeout=10
        )
        result = response.json()
        if result.get("ok"):
            logger.info(f"✅ PreCheckoutQuery {pre_checkout_query_id} پاسخ داده شد")
        else:
            logger.error(f"❌ خطا در answerPreCheckoutQuery: {result}")
    except Exception as e:
        logger.error(f"❌ Exception در answer_pre_checkout_query: {e}")


# ========== صفحه استقبال ==========

def handle_unauthenticated_user(message, bot_token):
    """
    رسیدگی به کاربر غیرمجاز - با تست 1 روزه رایگان برای کاربران جدید
    Returns:
        bool: True اگر مجاز باشد
    """
    chat_id = message["chat"]["id"]
    username = message.get("from", {}).get("username", "unknown")

    logger.info(f"👤 کاربر غیرمجاز: {chat_id} ({username})")

    if auth_manager.is_admin(chat_id):
        logger.info(f"✅ {chat_id} ادمین است")
        return True

    user_info = auth_manager.get_user_info(chat_id)

    if user_info:
        if user_info['status'] == 'approved':
            # چک انقضای دسترسی (تست یا محدود)
            access_expired = (
                (user_info.get('is_trial') and user_info.get('trial_expired'))
                or user_info.get('access_expired')
            )
            if access_expired:
                trial_days = get_default_trial_days()
                msg = (
                    f"⏰ *مدت دسترسی شما به پایان رسید!*\n\n"
                    f"👋 {username} عزیز، اعتبار رایگان شما تمام شده است.\n\n"
                    f"💳 برای ادامه استفاده، یکی از پلن‌های زیر را انتخاب کنید:"
                )
                keyboard = build_tariffs_keyboard("fa")
                keyboard["inline_keyboard"].append(
                    [{"text": "📝 درخواست دسترسی به ادمین", "callback_data": "auth_request_access"}]
                )
                send_message(chat_id, msg, keyboard, bot_token=bot_token)
                return False
            # اگر تست فعال است، باقی مانده را نمایش بده در لاگ
            if user_info.get('is_trial'):
                remaining = user_info.get('trial_remaining_hours', 0)
                logger.info(f"⏳ کاربر تستی {chat_id} - {remaining:.1f} ساعت باقی مانده")
            return True

        elif user_info['status'] == 'pending':
            msg = (
                f"👋 سلام {username}!\n\n"
                f"⏳ درخواست دسترسی شما در حال بررسی است.\n"
                f"لطفاً منتظر تایید ادمین باشید."
            )
            send_message(chat_id, msg, bot_token=bot_token)
            return False

        elif user_info['status'] == 'rejected':
            msg = (
                f"❌ متأسفانه درخواست دسترسی شما رد شد.\n\n"
                f"می‌توانید از طریق خرید اشتراک، دسترسی تهیه کنید:"
            )
            keyboard = build_tariffs_keyboard("fa")
            send_message(chat_id, msg, keyboard, bot_token=bot_token)
            return False

    # کاربر جدید - خودکار تست رایگان بده (مدت از config خوانده می‌شود)
    trial_days = get_default_trial_days()
    logger.info(f"🆕 کاربر جدید {chat_id} - ثبت با تست {trial_days} روزه رایگان")
    result = auth_manager.register_user(chat_id, username)
    if result.get('success') and result.get('is_trial'):
        trial_end = result.get('trial_end', '')
        got_days = result.get('trial_days', trial_days)
        msg = (
            f"🎉 *خوش‌آمدید {username}!* \n\n"
            f"🎁 *هدیه ویژه: {got_days} روز تست رایگان!* 🎁\n\n"
            f"✅ دسترسی شما به مدت {got_days} روز فعال شد\n"
            f"⏰ تا: {trial_end}\n\n"
            f"🚀 می‌توانید همین الان از ربات استفاده کنید:\n"
            f"• اتصال پیام‌رسان‌ها\n"
            f"• تنظیم ووکامرس\n"
            f"• ارسال پست خودکار\n\n"
            f"💡 پس از پایان تست، از بخش تعرفه‌ها اشتراک بخرید:\n\n"
            f"برای شروع /start را بزنید"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 شروع استفاده", "callback_data": "main_menu"}],
                [{"text": "🏷️ مشاهده تعرفه‌ها", "callback_data": "show_tariffs"}],
                [{"text": "📝 درخواست دسترسی به ادمین", "callback_data": "auth_request_access"}]
            ]
        }
        send_message(chat_id, msg, keyboard, bot_token=bot_token)
        return True
    else:
        # کاربر جدید بدون تست (مثلاً تست غیرفعال) - مستقیم تعرفه‌ها
        msg = (
            f"👋 خوش‌آمدید {username}!\n\n"
            f"🔐 برای استفاده از ربات، یکی از روش‌های زیر را انتخاب کنید:"
        )
        keyboard = create_auth_keyboard_fa()
        send_message(chat_id, msg, keyboard, bot_token=bot_token)
        return False


# ========== مدیریت Callback های احراز هویت ==========

def handle_auth_callback(callback_data, message, bot_token, user_states):
    """
    مدیریت callback‌های احراز هویت

    callback_data های پشتیبانی شده:
    - auth_with_token
    - auth_request_access
    - auth_buy_access      ← جدید
    - auth_request_reason  ← جدید (پس از انتخاب درخواست دسترسی)
    """
    chat_id = message["chat"]["id"]
    username = message.get("from", {}).get("username", "unknown")

    logger.info(f"🔑 callback احراز: {callback_data} از {chat_id}")

    if auth_manager.is_admin(chat_id):
        logger.info(f"✅ {chat_id} ادمین است - نیاز به احراز ندارد")
        return

    # ===== ورود با توکن =====
    if callback_data == "auth_with_token":
        msg = (
            "🔐 *ورود با توکن*\n\n"
            "لطفاً توکن خود را وارد کنید:\n\n"
            "💡 توکن شما از دو منبع ممکن است:\n"
            "  • توکن ارسال شده توسط ادمین\n"
            "  • توکن دریافتی پس از خرید اشتراک"
        )
        send_message(chat_id, msg, bot_token=bot_token)
        user_states[chat_id] = {'state': 'awaiting_token', 'step': 'token_entry'}
        logger.info(f"🔑 در انتظار توکن برای {chat_id}")

    # ===== درخواست دسترسی =====
    elif callback_data == "auth_request_access":
        if auth_manager.is_admin(chat_id):
            send_message(
                chat_id,
                "👮 شما از قبل ادمین هستید!",
                bot_token=bot_token
            )
            return

        # درخواست نوشتن دلیل
        msg = (
            "📝 *درخواست دسترسی*\n\n"
            "لطفاً دلیل درخواست دسترسی خود را بنویسید:\n\n"
            "💡 مثال: 'پرداخت انجام دادم اما توکن دریافت نکردم' یا "
            "'می‌خواهم از امکانات ربات استفاده کنم'"
        )
        send_message(chat_id, msg, bot_token=bot_token)
        user_states[chat_id] = {
            'state': 'awaiting_access_reason',
            'username': username
        }
        logger.info(f"📝 در انتظار دلیل درخواست از {chat_id}")

    # ===== خرید دسترسی (نمایش تعرفه‌ها) =====
    elif callback_data == "auth_buy_access":
        _handle_buy_access(chat_id, username, bot_token, user_states)

    # ===== نمایش تعرفه‌ها =====
    elif callback_data == "show_tariffs":
        show_tariffs(chat_id, bot_token)

    # ===== خرید یک پلن مشخص =====
    elif callback_data.startswith("buy_plan_"):
        try:
            plan_id = int(callback_data.replace("buy_plan_", ""))
            handle_purchase_confirm(chat_id, username, bot_token, plan_id=plan_id)
        except ValueError:
            show_tariffs(chat_id, bot_token)

    else:
        logger.warning(f"⚠️ callback ناشناخته: {callback_data}")


def show_tariffs(chat_id, bot_token, lang="fa"):
    """نمایش لیست تعرفه‌ها با دکمه خرید هر پلن"""
    msg = build_tariffs_text(lang)
    keyboard = build_tariffs_keyboard(lang)
    if lang == "fa":
        keyboard["inline_keyboard"].append(
            [{"text": "🔙 بازگشت", "callback_data": "auth_back_to_menu"}]
        )
    send_message(chat_id, msg, keyboard, bot_token=bot_token)


def notify_access_changed(user_chat_id, new_until, access_type, bot_token, changed_by_admin=True):
    """
    ارسال پییم به کاربر وقتی مدت دسترسی‌اش تغییر کرد
    با دکمه تعرفه‌ها برای مشاهده لیست و خرید
    """
    if access_type == 'permanent':
        access_line = "♾️ نوع دسترسی: **دائمی**"
    elif access_type == 'trial':
        access_line = f"🎁 نوع دسترسی: **تست رایگان**\n⏳ تا: {new_until}"
    elif new_until:
        access_line = f"⏱️ نوع دسترسی: **مدت‌دار**\n⏳ تا: {new_until}"
    else:
        access_line = "⏳ مدت دسترسی شما بروزرسانی شد"

    msg = (
        "🔔 *تغییر در مدت دسترسی*\n\n"
        f"{access_line}\n\n"
        "ℹ️ مدت دسترسی شما توسط مدیریت تغییر کرد.\n"
        "برای مشاهده تعرفه‌ها و خرید اشتراک:"
    )
    keyboard = {
        "inline_keyboard": [
            [{"text": "🏷️ تعرفه‌ها", "callback_data": "show_tariffs"}],
            [{"text": "🏠 منوی اصلی", "callback_data": "main_menu"}]
        ]
    }
    send_message(user_chat_id, msg, keyboard, bot_token=bot_token)


def notify_new_plan_available(user_chat_id, plan, bot_token, lang="fa"):
    """ارسال پیام به کاربر وقتی روش خرید جدیدی اضافه شد"""
    if lang == "fa":
        dur = format_duration_fa(plan['duration_days'])
        price = format_price_rial(plan['price_rial'])
        msg = (
            "🆕 *روش خرید جدید اضافه شد!*\n\n"
            f"📦 پلن: **{plan['name']}**\n"
            f"⏱️ مدت: {dur}\n"
            f"💰 قیمت: {price}\n\n"
            "برای مشاهده کامل تعرفه‌ها و خرید:"
        )
        kb_text = "🏷️ مشاهده تعرفه‌ها"
    else:
        dur = "Lifetime" if plan['duration_days'] is None else f"{plan['duration_days']} days"
        toman = int(plan['price_rial']) // 10
        msg = (
            "🆕 *New purchase plan available!*\n\n"
            f"📦 Plan: **{plan['name']}**\n"
            f"⏱️ Duration: {dur}\n"
            f"💰 Price: {toman:,} TOMAN\n\n"
            "View all tariffs and buy:"
        )
        kb_text = "🏷️ View Tariffs"

    keyboard = {
        "inline_keyboard": [
            [{"text": kb_text, "callback_data": "show_tariffs"}],
            [{"text": "🏠 Main Menu" if lang != "fa" else "🏠 منوی اصلی", "callback_data": "main_menu"}]
        ]
    }
    send_message(user_chat_id, msg, keyboard, bot_token=bot_token)


def broadcast_new_plan(plan, bot_token, lang="fa"):
    """اطلاع‌رسانی گروهی پلن جدید به همه کاربران تایید شده"""
    try:
        users = auth_manager.get_approved_users()
        sent = 0
        failed = 0
        for user in users:
            uid = user['chat_id']
            if auth_manager.is_admin(uid):
                continue
            try:
                user_lang = "fa"  # پیش‌فرض فارسی؛ می‌توان از config خواند
                if notify_new_plan_available(uid, plan, bot_token, lang=user_lang):
                    sent += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        logger.info(f"📢 اطلاع‌رسانی پلن '{plan['name']}' به {sent} کاربر ارسال شد ({failed} ناموفق)")
        return sent, failed
    except Exception as e:
        logger.error(f"❌ خطا در اطلاع‌رسانی گروهی: {e}")
        return 0, 0


def _handle_buy_access(chat_id, username, bot_token, user_states):
    """
    مدیریت فرایند خرید - نمایش لیست تعرفه‌ها (پلن‌های متعدد)
    کاربر یکی را انتخاب می‌کند و فاکتور همان پلن ارسال می‌شود
    """
    logger.info(f"💳 شروع فرایند خرید برای {chat_id}")

    plans = get_active_plans()
    if not plans:
        msg = (
            "🏷️ *تعرفه‌ها*\n\n"
            "هنوز پلن خریدی تنظیم نشده است.\n"
            "لطفاً با پشتیبانی تماس بگیرید."
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "📝 درخواست دسترسی به ادمین", "callback_data": "auth_request_access"}],
                [{"text": "🔙 بازگشت", "callback_data": "auth_back_to_menu"}]
            ]
        }
        send_message(chat_id, msg, keyboard, bot_token=bot_token)
        return

    msg = build_tariffs_text("fa") + "\n\n🔒 پرداخت از طریق کیف‌پول بیل انجام می‌شود."
    keyboard = build_tariffs_keyboard("fa")
    keyboard["inline_keyboard"].append(
        [{"text": "🔙 بازگشت", "callback_data": "auth_back_to_menu"}]
    )
    send_message(chat_id, msg, keyboard, bot_token=bot_token)

    user_states[chat_id] = {
        'state': 'choosing_plan',
        'username': username
    }


def handle_purchase_confirm(chat_id, username, bot_token, plan_id=None):
    """ارسال فاکتور پرداخت پس از انتخاب پلن"""
    logger.info(f"💳 ارسال فاکتور برای {chat_id} (plan={plan_id})")

    plan = None
    if plan_id is not None:
        plan = auth_manager.get_plan(plan_id)
        if plan and not plan.get('enabled'):
            send_message(
                chat_id,
                "❌ این پلن در حال حاضر غیرفعال است.\nلطفاً پلن دیگری را انتخاب کنید.",
                build_tariffs_keyboard("fa"),
                bot_token=bot_token
            )
            return

    preparing_msg = "⏳ در حال آماده‌سازی درخواست پرداخت..."
    send_message(chat_id, preparing_msg, bot_token=bot_token)

    success = send_invoice_to_user(chat_id, bot_token, plan=plan)

    if not success:
        logger.error(f"❌ ارسال فاکتور برای {chat_id} ناموفق بود")


def handle_successful_payment(chat_id, username, payment_info, bot_token):
    """
    ✅ پردازش پرداخت موفق

    1. ثبت پرداخت در دیتابیس
    2. ایجاد توکن خرید دائمی
    3. تایید کاربر در سیستم
    4. ارسال توکن به کاربر
    5. اطلاع‌رسانی به ادمین

    Args:
        chat_id: شناسه چت کاربر
        username: نام کاربری
        payment_info: اطلاعات پرداخت از بیل
        bot_token: توکن ربات
    """
    payment_id = payment_info.get('telegram_payment_charge_id', '')
    amount = payment_info.get('total_amount', 0)
    currency = payment_info.get('currency', 'IRR')
    payload = payment_info.get('invoice_payload', '') or payment_info.get('payload', '')

    # استخراج plan_id از payload: purchase_{chat_id}_{plan_id}_{ts}
    plan_id = None
    try:
        parts = str(payload).split('_')
        if len(parts) >= 4 and parts[0] == 'purchase':
            plan_id = int(parts[2])
    except Exception:
        plan_id = None

    plan = auth_manager.get_plan(plan_id) if plan_id else None

    logger.info(
        f"💳 پرداخت موفق از {chat_id}: "
        f"amount={amount}, payment_id={payment_id}, plan={plan_id}"
    )

    try:
        # 1. ثبت پرداخت در دیتابیس
        auth_manager.complete_payment(chat_id, payment_id, amount, currency)

        # 2. ایجاد توکن خرید (برای ورود با توکن - حفظ سازگاری با قبل)
        purchase_token = auth_manager.create_purchase_token(
            chat_id=chat_id,
            username=username,
            payment_id=payment_id,
            amount=amount,
            currency=currency
        )

        # 3. تایید کاربر در سیستم
        auth_manager.approve_user_by_purchase(chat_id, username)

        # 4. ✅ اعمال مدت دسترسی بر اساس پلن خریداری شده
        # اگر پلنی مشخص نشد (پرداخت قدیمی/نامشخص) → دائمی (رفتار قبلی سیستم)
        if plan is None:
            plan = {'name': 'دسترسی دائمی', 'duration_days': None}

        if plan['duration_days'] is None:
            # پلن دائمی
            access_result = auth_manager.set_user_access(
                chat_id, 'permanent',
                granted_by=None,
                note=f"خرید پلن {plan['name']} (پرداخت {payment_id})"
            )
        else:
            # پلن مدت‌دار - از انتهای اعتبار فعلی ادامه پیدا می‌کند
            access_result = auth_manager.set_user_access(
                chat_id, 'timed',
                granted_by=None,
                grant_days=plan['duration_days'],
                note=f"خرید پلن {plan['name']} ({plan['duration_days']} روز) - پرداخت {payment_id}"
            )

        # 5. ثبت فعالیت
        auth_manager.log_activity(
            chat_id,
            'purchase',
            f'پرداخت موفق: {amount} {currency}, payment_id={payment_id}, plan={plan_id}'
        )

        # 6. ارسال پیکربندی نهایی به کاربر
        amount_toman = amount // 10
        access_line = ""
        if access_result and access_result.get('success'):
            if access_result.get('access_type') == 'permanent':
                access_line = "♾️ دسترسی: **دائمی**\n"
            elif access_result.get('access_until'):
                access_line = f"⏳ دسترسی تا: **{access_result['access_until']}**\n"

        plan_name = plan['name'] if plan else "دسترسی"
        msg = (
            f"🎉 *پرداخت با موفقیت انجام شد!*\n\n"
            f"📦 پلن: {plan_name}\n"
            f"💰 مبلغ پرداختی: {amount_toman:,} تومان\n"
            f"🆔 شناسه پرداخت: `{payment_id}`\n"
            f"{access_line}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔑 *توکن اختصاصی شما:*\n\n"
            f"`{purchase_token}`\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⚠️ *نکات مهم:*\n"
            f"  • این توکن را در جای امنی ذخیره کنید\n"
            f"  • هر زمان که ربات از شما توکن خواست، این توکن را وارد کنید\n"
            f"  • این توکن را به کسی ندهید\n\n"
            f"برای ورود به ربات، از گزینه «ورود با توکن» استفاده کنید یا همین الان /start رو بزنید."
        )

        keyboard = {
            "inline_keyboard": [
                [{"text": "🔐 ورود به ربات", "callback_data": "auth_with_token"}],
                [{"text": "🏷️ مشاهده تعرفه‌ها", "callback_data": "show_tariffs"}]
            ]
        }
        send_message(chat_id, msg, keyboard, bot_token=bot_token)

        logger.info(f"✅ دسترسی خریداری شده برای {chat_id} اعمال شد (plan={plan_id})")

        # 7. اطلاع‌رسانی به ادمین
        _notify_admin_purchase(chat_id, username, amount, currency,
                                payment_id, purchase_token, bot_token)

    except Exception as e:
        logger.error(f"❌ خطا در پردازش پرداخت موفق: {e}", exc_info=True)
        error_msg = (
            "❌ خطایی در پردازش پرداخت رخ داد.\n"
            "لطفاً با پشتیبانی تماس بگیرید و شناسه پرداخت را ارسال کنید:\n"
            f"`{payment_id}`"
        )
        send_message(chat_id, error_msg, bot_token=bot_token)


def handle_pre_checkout(pre_checkout_query_id, chat_id, bot_token):
    """
    مدیریت PreCheckoutQuery - تایید یا رد پرداخت قبل از نهایی شدن

    Args:
        pre_checkout_query_id: شناسه درخواست
        chat_id: شناسه چت کاربر
        bot_token: توکن ربات
    """
    logger.info(f"🔍 PreCheckoutQuery از {chat_id}: {pre_checkout_query_id}")

    # همیشه تایید کن (می‌توان اینجا اعتبارسنجی اضافه کرد)
    answer_pre_checkout_query(pre_checkout_query_id, bot_token, ok=True)
    logger.info(f"✅ PreCheckoutQuery {pre_checkout_query_id} تایید شد")


# ========== مدیریت ورودی دلیل درخواست ==========

def handle_access_reason_input(chat_id, username, reason, bot_token):
    """
    پردازش دلیل درخواست دسترسی که کاربر نوشته

    Args:
        chat_id: شناسه چت
        username: نام کاربری
        reason: دلیل نوشته شده
        bot_token: توکن ربات

    Returns:
        bool: موفقیت
    """
    result = auth_manager.submit_access_request(chat_id, username, reason)

    if result['success']:
        msg = (
            "✅ *درخواست دسترسی ارسال شد*\n\n"
            "درخواست شما برای بررسی ادمین ارسال شد.\n"
            "پس از تایید، یک توکن ویژه برای شما ارسال خواهد شد.\n\n"
            "💡 اگر نیاز فوری دارید، می‌توانید از طریق خرید اشتراک دسترسی فوری داشته باشید:"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "💳 خرید دسترسی فوری", "callback_data": "auth_buy_access"}]
            ]
        }
        send_message(chat_id, msg, keyboard, bot_token=bot_token)
        _notify_admin_new_request(chat_id, username, reason, bot_token)
        logger.info(f"✅ درخواست دسترسی با دلیل برای {chat_id} ارسال شد")
        return True
    else:
        error_msg = f"❌ خطا: {result.get('error', 'خطای نامشخص')}"
        send_message(chat_id, error_msg, bot_token=bot_token)
        logger.error(f"❌ خطا در ارسال درخواست: {result.get('error')}")
        return False


# ========== مدیریت ورود توکن ==========

def handle_token_input(chat_id, token_input, bot_token):
    """
    مدیریت ورود توکن - بررسی سه نوع توکن:
    1. توکن ادمین-تایید (در جدول users)
    2. توکن موقت (در جدول temp_tokens)
    3. توکن خرید دائمی (در جدول purchase_tokens) ← جدید

    Returns:
        bool: موفقیت احراز
    """
    logger.info(f"🔐 بررسی توکن برای {chat_id}")

    if auth_manager.is_admin(chat_id):
        logger.info(f"✅ {chat_id} ادمین است")
        return True

    token_input = token_input.strip() if token_input else ""

    if not token_input:
        send_message(
            chat_id,
            "❌ توکن نمی‌تواند خالی باشد. لطفاً توکن خود را وارد کنید.",
            bot_token=bot_token
        )
        return False

    # ===== 1. بررسی توکن خرید دائمی =====
    # ✅ chat_id پاس میدیم تا مالکیت چک بشه
    purchase_info = auth_manager.verify_purchase_token(token_input, chat_id=chat_id)
    if purchase_info:
        # ✅ توکن فقط برای صاحب اصلی‌اش معتبره
        owner_chat_id = purchase_info['chat_id']
        
        # ✅ double-check مالکیت
        if owner_chat_id != chat_id:
            msg = (
                "❌ *توکن نامعتبر*\n\n"
                "این توکن متعلق به شما نیست.\n"
                "هر کاربر فقط می‌تواند از توکن خود استفاده کند."
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "💳 خرید دسترسی", "callback_data": "auth_buy_access"}],
                    [{"text": "📝 درخواست دسترسی", "callback_data": "auth_request_access"}]
                ]
            }
            send_message(chat_id, msg, keyboard, bot_token=bot_token)
            logger.warning(
                f"⚠️ {chat_id} تلاش کرد با توکن {owner_chat_id} وارد شود - رد شد"
            )
            return False

        username = purchase_info.get('username', 'unknown')

        # تایید کاربر در سیستم
        auth_manager.approve_user_by_purchase(chat_id, username)

        # ثبت فعالیت
        auth_manager.log_activity(
            chat_id, 'login',
            f'ورود با توکن خرید (purchase_id={purchase_info["token_id"]})'
        )

        msg = (
            "✅ *ورود موفق!*\n\n"
            "توکن خرید شما تأیید شد.\n"
            "دسترسی شما فعال است.\n\n"
            f"📅 تاریخ خرید: {purchase_info['created_at']}\n"
            "🎉 خوش‌آمدید!"
        )
        send_message(chat_id, msg, bot_token=bot_token)
        logger.info(f"✅ {chat_id} با توکن خرید دائمی وارد شد")
        return True

    # ===== 2. بررسی توکن موقت =====
    temp_result = auth_manager.verify_temp_token(token_input)
    if temp_result:
        token_chat_id, token_type = temp_result
        if token_chat_id == chat_id:
            auth_manager.log_activity(chat_id, 'login', 'ورود با توکن موقت')
            msg = (
                "✅ *احراز هویت موفق*\n\n"
                "توکن موقت شما تأیید شد.\n"
                "🎉 خوش‌آمدید!"
            )
            send_message(chat_id, msg, bot_token=bot_token)
            logger.info(f"✅ {chat_id} با توکن موقت وارد شد")
            return True

    # ===== 3. بررسی توکن ادمین-تایید =====
    if auth_manager.verify_token(chat_id, token_input):
        auth_manager.log_activity(chat_id, 'login', 'ورود با توکن ادمین-تایید')
        msg = (
            "✅ *احراز هویت موفق*\n\n"
            "توکن شما تأیید شد.\n"
            "🎉 خوش‌آمدید!"
        )
        send_message(chat_id, msg, bot_token=bot_token)
        logger.info(f"✅ {chat_id} با توکن ادمین-تایید وارد شد")
        return True

    # ===== توکن نامعتبر =====
    msg = (
        "❌ *توکن نامعتبر*\n\n"
        "توکن وارد شده معتبر نیست.\n\n"
        "لطفاً یکی از موارد زیر را بررسی کنید:\n"
        "  • توکن را بدون فاصله وارد کنید\n"
        "  • از صحت توکن اطمینان حاصل کنید\n"
        "  • در صورت نیاز، توکن جدید خریداری کنید"
    )

    keyboard = {
        "inline_keyboard": [
            [{"text": "💳 خرید دسترسی", "callback_data": "auth_buy_access"}],
            [{"text": "📝 درخواست دسترسی", "callback_data": "auth_request_access"}]
        ]
    }
    send_message(chat_id, msg, keyboard, bot_token=bot_token)
    logger.warning(f"⚠️ توکن نامعتبر برای {chat_id}")
    return False


# ========== اطلاع‌رسانی ادمین ==========

def _notify_admin_new_request(chat_id, username, reason, bot_token):
    """اطلاع‌رسانی به ادمین درباره درخواست جدید (با دلیل)"""
    config = load_config()
    admin_chat_id = config.get('admin_chat_id')

    if not admin_chat_id:
        logger.warning("⚠️ admin_chat_id تنظیم نشده")
        return

    pending = auth_manager.get_pending_requests()
    request = next((r for r in pending if r['chat_id'] == chat_id), None)

    if not request:
        logger.warning(f"⚠️ درخواست {chat_id} یافت نشد")
        return

    msg = (
        f"🔔 *درخواست دسترسی جدید*\n\n"
        f"👤 کاربر: {username}\n"
        f"🆔 Chat ID: `{chat_id}`\n"
        f"🕐 زمان: {request['requested_at']}\n\n"
        f"📝 *دلیل درخواست:*\n{reason or 'ذکر نشده'}\n\n"
        f"برای تصمیم‌گیری از دکمه‌های زیر استفاده کنید:"
    )

    keyboard = {
        "inline_keyboard": [
            [{"text": "🔍 مشاهده درخواست‌ها", "callback_data": "admin_view_requests"}],
            [{"text": "🔙 منوی ادمین", "callback_data": "admin_menu"}]
        ]
    }

    send_message(admin_chat_id, msg, keyboard, bot_token=bot_token)
    logger.info(f"📢 ادمین درباره درخواست {chat_id} اطلاع‌رسانی شد")


def _notify_admin_purchase(chat_id, username, amount, currency,
                            payment_id, token, bot_token):
    """اطلاع‌رسانی به ادمین درباره خرید موفق"""
    config = load_config()
    admin_chat_id = config.get('admin_chat_id')

    if not admin_chat_id:
        return

    amount_toman = amount // 10

    msg = (
        f"💳 *خرید موفق جدید!*\n\n"
        f"👤 کاربر: {username}\n"
        f"🆔 Chat ID: `{chat_id}`\n"
        f"💰 مبلغ: {amount_toman:,} تومان\n"
        f"🏦 واحد: {currency}\n"
        f"🆔 Payment ID: `{payment_id}`\n"
        f"⏰ زمان: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"✅ دسترسی کاربر فعال شد و توکن ارسال گردید."
    )

    send_message(admin_chat_id, msg, bot_token=bot_token)
    logger.info(f"📢 ادمین درباره خرید {chat_id} اطلاع‌رسانی شد")