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
PAYMENT_AMOUNT = 20000000  # مبلغ به ریال
PAYMENT_CURRENCY = "IRR"


def get_wallet_token():
    """دریافت توکن کیف‌پول از config"""
    config = load_config()
    return config.get("wallet_token", "")


# ========== صفحه‌کلیدهای احراز هویت ==========

def create_auth_keyboard_fa():
    """صفحه‌کلید انتخاب روش ورود (فارسی) - با دکمه خرید"""
    return {
        "inline_keyboard": [
            [
                {"text": "🔐 ورود با توکن", "callback_data": "auth_with_token"}
            ],
            [
                {"text": "📝 درخواست دسترسی", "callback_data": "auth_request_access"}
            ],
            [
                {"text": "💳 خرید دسترسی", "callback_data": "auth_buy_access"}
            ]
        ]
    }


def create_auth_keyboard_en():
    """صفحه‌کلید انتخاب روش ورود (انگلیسی) - با دکمه خرید"""
    return {
        "inline_keyboard": [
            [
                {"text": "🔐 Login with Token", "callback_data": "auth_with_token"}
            ],
            [
                {"text": "📝 Request Access", "callback_data": "auth_request_access"}
            ],
            [
                {"text": "💳 Buy Access", "callback_data": "auth_buy_access"}
            ]
        ]
    }


# ========== ارسال پیام ==========

def send_message(chat_id, text, keyboard=None, bot_token=None):
    """ارسال پیام به کاربر"""
    if not bot_token:
        config = load_config()
        bot_token = config['messengers']['bale']['bot_token']

    api = f"https://tapi.bale.ai/bot{bot_token}"
    data = {"chat_id": chat_id, "text": text}

    if keyboard:
        data["reply_markup"] = keyboard

    try:
        response = requests.post(f"{api}/sendMessage", json=data, timeout=10)
        if response.status_code == 200:
            logger.debug(f"✅ پیام برای {chat_id} ارسال شد")
        else:
            logger.error(f"❌ خطا در ارسال پیام: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ خطا در ارسال پیام: {e}")


def send_invoice_to_user(chat_id, bot_token):
    """
    ارسال درخواست پرداخت (invoice) به کاربر

    Args:
        chat_id: شناسه چت کاربر
        bot_token: توکن ربات

    Returns:
        bool: موفقیت ارسال
    """
    wallet_token = get_wallet_token()

    if not wallet_token:
        logger.error("❌ wallet_token در config.json تنظیم نشده!")
        send_message(
            chat_id,
            "❌ سیستم پرداخت در حال حاضر در دسترس نیست. لطفاً با پشتیبانی تماس بگیرید.",
            bot_token=bot_token
        )
        return False

    api = f"https://tapi.bale.ai/bot{bot_token}"

    import time
    payload = f"purchase_{chat_id}_{int(time.time())}"

    data = {
        "chat_id": chat_id,
        "title": "خرید دسترسی به ربات",
        "description": (
            "با خرید این اشتراک، به تمام امکانات ربات دسترسی خواهید داشت.\n"
            "پس از پرداخت، یک توکن اختصاصی برای شما صادر می‌شود."
        ),
        "payload": payload,
        "provider_token": wallet_token,
        "prices": [
            {
                "label": "دسترسی به ربات",
                "amount": PAYMENT_AMOUNT
            }
        ]
    }

    try:
        response = requests.post(f"{api}/sendInvoice", json=data, timeout=15)
        result = response.json()

        if result.get("ok"):
            logger.info(f"✅ فاکتور پرداخت برای {chat_id} ارسال شد")
            return True
        else:
            error_desc = result.get('description', 'خطای نامشخص')
            logger.error(f"❌ خطا در ارسال فاکتور: {error_desc}")
            send_message(
                chat_id,
                f"❌ خطا در ایجاد درخواست پرداخت: {error_desc}",
                bot_token=bot_token
            )
            return False

    except Exception as e:
        logger.error(f"❌ Exception در send_invoice: {e}")
        send_message(
            chat_id,
            "❌ خطا در اتصال به سرویس پرداخت. لطفاً دوباره تلاش کنید.",
            bot_token=bot_token
        )
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
    رسیدگی به کاربر غیرمجاز

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
                f"می‌توانید از طریق خرید دسترسی، اشتراک تهیه کنید:"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "💳 خرید دسترسی", "callback_data": "auth_buy_access"}]
                ]
            }
            send_message(chat_id, msg, keyboard, bot_token=bot_token)
            return False

    # کاربر جدید
    msg = (
        f"👋 خوش‌آمدید {username}!\n\n"
        f"🔐 برای استفاده از ربات، لطفاً یکی از روش‌های زیر را انتخاب کنید:"
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

    # ===== خرید دسترسی =====
    elif callback_data == "auth_buy_access":
        _handle_buy_access(chat_id, username, bot_token, user_states)

    else:
        logger.warning(f"⚠️ callback ناشناخته: {callback_data}")


def _handle_buy_access(chat_id, username, bot_token, user_states):
    """
    مدیریت فرایند خرید دسترسی

    1. توضیح محصول به کاربر
    2. ارسال فاکتور پرداخت
    """
    logger.info(f"💳 شروع فرایند خرید برای {chat_id}")

    # بررسی: آیا قبلاً توکن خرید دارد؟
    existing_token = auth_manager.get_purchase_token_by_chat_id(chat_id)
    if existing_token:
        msg = (
            "✅ *شما قبلاً اشتراک خریداری کرده‌اید!*\n\n"
            f"🔑 توکن شما:\n`{existing_token['token']}`\n\n"
            "این توکن دائمی است و همیشه می‌توانید از آن استفاده کنید.\n"
            "برای ورود، از گزینه «ورود با توکن» استفاده کنید."
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔐 ورود با توکن", "callback_data": "auth_with_token"}]
            ]
        }
        send_message(chat_id, msg, keyboard, bot_token=bot_token)
        return

    # توضیح محصول
    amount_toman = PAYMENT_AMOUNT // 10
    msg = (
        f"💳 *خرید دسترسی به ربات*\n\n"
        f"💰 مبلغ: {amount_toman:,} تومان\n\n"
        f"✅ پس از پرداخت:\n"
        f"  • یک توکن اختصاصی برای شما صادر می‌شود\n"
        f"  • توکن دائمی است و بدون انقضا\n"
        f"  • هر زمان می‌توانید با این توکن وارد شوید\n\n"
        f"🔒 پرداخت از طریق کیف‌پول بیل انجام می‌شود."
    )

    keyboard = {
        "inline_keyboard": [
            [{"text": "💳 پرداخت و دریافت توکن", "callback_data": "auth_confirm_purchase"}],
            [{"text": "🔙 بازگشت", "callback_data": "auth_back_to_menu"}]
        ]
    }
    send_message(chat_id, msg, keyboard, bot_token=bot_token)

    user_states[chat_id] = {
        'state': 'awaiting_purchase_confirm',
        'username': username
    }


def handle_purchase_confirm(chat_id, username, bot_token):
    """ارسال فاکتور پرداخت پس از تایید کاربر"""
    logger.info(f"💳 ارسال فاکتور برای {chat_id}")

    preparing_msg = "⏳ در حال آماده‌سازی درخواست پرداخت..."
    send_message(chat_id, preparing_msg, bot_token=bot_token)

    success = send_invoice_to_user(chat_id, bot_token)

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

    logger.info(
        f"💳 پرداخت موفق از {chat_id}: "
        f"amount={amount}, payment_id={payment_id}"
    )

    try:
        # 1. ثبت پرداخت در دیتابیس
        auth_manager.complete_payment(chat_id, payment_id, amount, currency)

        # 2. ایجاد توکن خرید دائمی
        purchase_token = auth_manager.create_purchase_token(
            chat_id=chat_id,
            username=username,
            payment_id=payment_id,
            amount=amount,
            currency=currency
        )

        # 3. تایید کاربر در سیستم
        auth_manager.approve_user_by_purchase(chat_id, username)

        # 4. ثبت فعالیت
        auth_manager.log_activity(
            chat_id,
            'purchase',
            f'پرداخت موفق: {amount} {currency}, payment_id={payment_id}'
        )

        # 5. ارسال توکن به کاربر
        amount_toman = amount // 10
        msg = (
            f"🎉 *پرداخت با موفقیت انجام شد!*\n\n"
            f"💰 مبلغ پرداختی: {amount_toman:,} تومان\n"
            f"🆔 شناسه پرداخت: `{payment_id}`\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔑 *توکن اختصاصی شما:*\n\n"
            f"`{purchase_token}`\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⚠️ *نکات مهم:*\n"
            f"  • این توکن را در جای امنی ذخیره کنید\n"
            f"  • توکن دائمی است و بدون انقضا\n"
            f"  • هر زمان که ربات از شما توکن خواست، این توکن را وارد کنید\n"
            f"  • این توکن را به کسی ندهید\n\n"
            f"برای ورود به ربات، از گزینه «ورود با توکن» استفاده کنید یا همین الان /start رو بزنید."
        )

        keyboard = {
            "inline_keyboard": [
                [{"text": "🔐 ورود به ربات", "callback_data": "auth_with_token"}]
            ]
        }
        send_message(chat_id, msg, keyboard, bot_token=bot_token)

        logger.info(f"✅ توکن خرید برای {chat_id} ارسال شد")

        # 6. اطلاع‌رسانی به ادمین
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