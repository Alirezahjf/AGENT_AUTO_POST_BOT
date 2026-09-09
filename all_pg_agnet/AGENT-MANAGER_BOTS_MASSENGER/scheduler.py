# scheduler.py
import time
import threading
import requests
import re
from datetime import datetime
import pytz

TEHRAN_TZ = pytz.timezone("Asia/Tehran")

def tehran_now():
    """زمان فعلی به وقت تهران"""
    return datetime.now(TEHRAN_TZ)

def tehran_today():
    """تاریخ امروز به وقت تهران"""
    return tehran_now().date()
from logger import logger
from config import (
    load_config, load_json, save_json,
    PRODUCTS_FILE, NEW_PRODUCTS_FILE, SENT_PRODUCTS_FILE,
    get_user_db, load_user_config
)
import messenger_bale
import messenger_rubika
import messenger_eitaa


# ========== ثبت زمان‌های اجرا شده برای جلوگیری از ارسال مضاعف ==========
_executed_posts = set()
_executed_lock = threading.Lock()

# ========== ثبت WooCommerce jobs اجرا شده ==========
_executed_wc_jobs = set()
_executed_wc_lock = threading.Lock()


# ========== اطلاع‌رسانی ==========

def notify_auto_post_success(chat_id, product, platforms_sent, is_new):
    """اطلاع‌رسانی ادمین/کاربر درباره ارسال موفق خودکار از WooCommerce"""
    config = load_config()

    message = "✅ *پست WooCommerce منتشر شد!*\n\n"
    message += f"🆔 شناسه محصول: #{product['id']}\n"
    message += f"📦 محصول: {product.get('name', 'N/A')[:50]}\n"
    message += f"🆕 وضعیت: {'محصول جدید' if is_new else 'محصول موجود'}\n"
    message += f"📅 زمان انتشار: {tehran_now().strftime('%Y-%m-%d %H:%M')}\n\n"

    desc = product.get('short_description', '')
    if desc:
        desc_clean = re.sub('<[^<]+?>', '', desc)
        preview = desc_clean[:100] + "..." if len(desc_clean) > 100 else desc_clean
        message += f"📝 توضیحات:\n{preview}\n\n"

    message += "📱 *منتشر شده در:*\n"
    platform_emojis = {
        "bale": "🔵 Bale",
        "rubika": "🟢 Rubika",
        "eitaa": "🟡 Eitaa"
    }
    for platform in platforms_sent:
        message += f"  {platform_emojis.get(platform, platform)}\n"

    message += f"\n🎉 تعداد پلتفرم‌ها: {len(platforms_sent)}"

    if product.get('permalink'):
        message += f"\n\n🔗 مشاهده محصول: {product['permalink']}"

    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"

    try:
        if product.get('images') and len(product['images']) > 0:
            image_url = product['images'][0].get('src')
            if image_url:
                data = {
                    "chat_id": chat_id,
                    "photo": image_url,
                    "caption": message
                }
                resp = requests.post(f"{api}/sendPhoto", json=data, timeout=10)
                if resp.status_code == 200 and resp.json().get("ok"):
                    return

        data = {"chat_id": chat_id, "text": message}
        requests.post(f"{api}/sendMessage", json=data, timeout=10)

    except Exception as e:
        logger.error(f"❌ Failed to send WooCommerce notification: {e}")


def notify_post_success(notify_chat_id, post_tuple, platforms_sent, is_owner=True):
    """
    اطلاع‌رسانی درباره ارسال موفق پست دستی

    Args:
        notify_chat_id: شناسه چت گیرنده
        post_tuple: اطلاعات پست
        platforms_sent: لیست پلتفرم‌های ارسال شده
        is_owner: آیا گیرنده صاحب پست است؟
    """
    config = load_config()
    api = f"https://tapi.bale.ai/bot{config['messengers']['bale']['bot_token']}"

    try:
        post_id = post_tuple[0]
        media_type = post_tuple[2] if len(post_tuple) > 2 else "unknown"
        caption = post_tuple[3] if len(post_tuple) > 3 else ""
        scheduled_date = post_tuple[5] if len(post_tuple) > 5 else ""
        scheduled_time = post_tuple[6] if len(post_tuple) > 6 else ""
        owner_chat_id = post_tuple[7] if len(post_tuple) > 7 else None

        platform_emojis = {
            "bale": "🔵 Bale",
            "rubika": "🟢 Rubika",
            "eitaa": "🟡 Eitaa"
        }

        if is_owner:
            message = "✅ *پست شما با موفقیت ارسال شد!*\n\n"
            message += f"🆔 شناسه پست: #{post_id}\n"
            message += f"📋 نوع: {'📸 عکس' if media_type == 'photo' else '🎥 ویدیو'}\n"
            message += f"📅 زمان‌بندی: {scheduled_date} ساعت {scheduled_time}\n"
            message += f"⏰ ارسال شده در: {tehran_now().strftime('%Y-%m-%d %H:%M')}\n\n"

            if caption:
                preview = caption[:100] + "..." if len(caption) > 100 else caption
                message += f"📝 پیش‌نمایش کپشن:\n{preview}\n\n"

            message += "📱 *ارسال شده به:*\n"
            for platform in platforms_sent:
                message += f"  {platform_emojis.get(platform, platform)}\n"

            message += f"\n🎉 تعداد پلتفرم‌ها: {len(platforms_sent)}"

        else:
            message = "📢 *گزارش ارسال پست زمان‌بندی شده*\n\n"
            message += f"👤 کاربر: `{owner_chat_id}`\n"
            message += f"🆔 شناسه پست: #{post_id}\n"
            message += f"📋 نوع: {'📸 Photo' if media_type == 'photo' else '🎥 Video'}\n"
            message += f"📅 Scheduled: {scheduled_date} at {scheduled_time}\n"
            message += f"⏰ Posted at: {tehran_now().strftime('%Y-%m-%d %H:%M')}\n\n"

            if caption:
                preview = caption[:100] + "..." if len(caption) > 100 else caption
                message += f"📝 Caption:\n{preview}\n\n"

            message += "📱 *Published on:*\n"
            for platform in platforms_sent:
                message += f"  {platform_emojis.get(platform, platform)}\n"

            message += f"\n🎉 Total platforms: {len(platforms_sent)}"

        data = {"chat_id": notify_chat_id, "text": message}
        requests.post(f"{api}/sendMessage", json=data, timeout=10)
        logger.info(
            f"✅ Notification sent to {'owner' if is_owner else 'admin'} "
            f"({notify_chat_id}) for post #{post_id}"
        )

    except Exception as e:
        logger.error(f"❌ Failed to send post success notification: {e}")


# ========== توابع WooCommerce ==========

def get_user_products_file(user_chat_id):
    """مسیر فایل محصولات اختصاصی کاربر"""
    from pathlib import Path
    user_dir = Path('users') / str(user_chat_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return str(user_dir / 'known_products.json')


def get_user_new_products_file(user_chat_id):
    """مسیر فایل محصولات جدید اختصاصی کاربر"""
    from pathlib import Path
    user_dir = Path('users') / str(user_chat_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return str(user_dir / 'new_products.json')


def get_user_sent_products_file(user_chat_id):
    """مسیر فایل محصولات ارسال شده اختصاصی کاربر"""
    from pathlib import Path
    user_dir = Path('users') / str(user_chat_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return str(user_dir / 'sent_products.json')


def get_todays_new_products(user_chat_id=None):
    """
    محصولات جدید امروز
    اگر user_chat_id داده شود از فایل اختصاصی کاربر می‌خواند
    """
    today = tehran_today().strftime("%Y-%m-%d")

    if user_chat_id:
        new_products_file = get_user_new_products_file(user_chat_id)
        products_file = get_user_products_file(user_chat_id)
    else:
        new_products_file = NEW_PRODUCTS_FILE
        products_file = PRODUCTS_FILE

    log = load_json(new_products_file, {})

    if today not in log:
        return []

    new_ids = log[today]
    all_products = load_json(products_file, [])

    return [p for p in all_products if p["id"] in new_ids]


def get_unsent_product(user_chat_id=None):
    """
    یک محصول ارسال نشده
    اگر user_chat_id داده شود از فایل اختصاصی کاربر می‌خواند
    """
    if user_chat_id:
        sent_file = get_user_sent_products_file(user_chat_id)
        products_file = get_user_products_file(user_chat_id)
    else:
        sent_file = SENT_PRODUCTS_FILE
        products_file = PRODUCTS_FILE

    sent = load_json(sent_file, [])
    products = load_json(products_file, [])

    for product in products:
        if product["id"] not in sent:
            return product

    if products:
        return products[0]

    return None


def post_to_all_messengers(product, config, is_new=False):
    """ارسال محصول WooCommerce به همه پیام‌رسان‌های پیکربندی شده"""
    platforms_sent = []

    if config["messengers"]["bale"].get("bot_token"):
        try:
            if messenger_bale.send_product(product, config, is_new):
                platforms_sent.append("bale")
        except Exception as e:
            logger.error(f"❌ Bale WooCommerce send error: {e}")
        time.sleep(2)

    if config["messengers"]["rubika"].get("bot_token"):
        try:
            if messenger_rubika.send_product(product, config, is_new):
                platforms_sent.append("rubika")
        except Exception as e:
            logger.error(f"❌ Rubika WooCommerce send error: {e}")
        time.sleep(2)

    if config["messengers"]["eitaa"].get("bot_token"):
        try:
            if messenger_eitaa.send_product(product, config, is_new):
                platforms_sent.append("eitaa")
        except Exception as e:
            logger.error(f"❌ Eitaa WooCommerce send error: {e}")
        time.sleep(2)

    return platforms_sent


def daily_job(user_config, user_chat_id=None):
    """
    وظیفه روزانه WooCommerce - ارسال محصولات

    ✅ اصلاح شده:
    - اگر فایل‌های اختصاصی کاربر خالی باشند، از فایل سراسری sync می‌کند
    - از ارسال مضاعف جلوگیری می‌کند
    """
    logger.info(f"🚀 Starting WooCommerce daily job for user={user_chat_id}...")

    global_config = load_config()
    posted = 0

    # تعیین فایل‌های ذخیره‌سازی
    if user_chat_id:
        sent_file = get_user_sent_products_file(user_chat_id)
        products_file = get_user_products_file(user_chat_id)
        new_products_file = get_user_new_products_file(user_chat_id)
    else:
        sent_file = SENT_PRODUCTS_FILE
        products_file = PRODUCTS_FILE
        new_products_file = NEW_PRODUCTS_FILE

    # ✅ sync فایل محصولات از سراسری اگر اختصاصی خالی است
    if user_chat_id:
        user_products = load_json(products_file, [])
        if not user_products:
            global_products = load_json(PRODUCTS_FILE, [])
            if global_products:
                save_json(products_file, global_products)
                logger.info(
                    f"✅ Synced {len(global_products)} products "
                    f"from global to user={user_chat_id}"
                )

        # ✅ sync فایل sent از سراسری اگر اختصاصی خالی است
        user_sent = load_json(sent_file, [])
        if not user_sent:
            global_sent = load_json(SENT_PRODUCTS_FILE, [])
            if global_sent:
                save_json(sent_file, global_sent)
                logger.info(
                    f"✅ Synced sent_products from global to user={user_chat_id}"
                )

    sent = load_json(sent_file, [])

    # ارسال محصول جدید
    new_products = get_todays_new_products(user_chat_id)
    if new_products:
        logger.info(f"📦 Found {len(new_products)} new product(s) for user={user_chat_id}")
        platforms_sent = post_to_all_messengers(new_products[0], user_config, is_new=True)
        if platforms_sent:
            sent.append(new_products[0]["id"])
            posted += 1

            notify_target = user_chat_id or global_config.get("admin_chat_id")
            if notify_target:
                notify_auto_post_success(
                    notify_target, new_products[0], platforms_sent, is_new=True
                )

            admin_chat_id = global_config.get("admin_chat_id")
            if (admin_chat_id and user_chat_id
                    and int(admin_chat_id) != int(user_chat_id)):
                notify_auto_post_success(
                    admin_chat_id, new_products[0], platforms_sent, is_new=True
                )

    # ارسال محصول موجود
    existing = get_unsent_product(user_chat_id)
    if existing:
        logger.info(f"📦 Sending existing product #{existing['id']} for user={user_chat_id}")
        platforms_sent = post_to_all_messengers(existing, user_config, is_new=False)
        if platforms_sent:
            sent.append(existing["id"])
            posted += 1

            notify_target = user_chat_id or global_config.get("admin_chat_id")
            if notify_target:
                notify_auto_post_success(
                    notify_target, existing, platforms_sent, is_new=False
                )

            admin_chat_id = global_config.get("admin_chat_id")
            if (admin_chat_id and user_chat_id
                    and int(admin_chat_id) != int(user_chat_id)):
                notify_auto_post_success(
                    admin_chat_id, existing, platforms_sent, is_new=False
                )
    else:
        logger.warning(f"⚠️ No unsent products found for user={user_chat_id}")

    save_json(sent_file, sent)
    logger.info(
        f"✅ WooCommerce job finished for user={user_chat_id}. "
        f"Posted {posted} product(s)."
    )

# ========== دانلود فایل از بیل ==========

def download_bale_file(file_id, bot_token):
    """دانلود فایل از بیل با file_id"""
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


# ========== بررسی WooCommerce برای یک کاربر ==========

def check_woocommerce_for_user(user_chat_id, user_config, now):
    """بررسی زمان‌بندی WooCommerce برای یک کاربر خاص"""
    global _executed_wc_jobs

    try:
        wc_cfg = user_config.get("woocommerce", {})
        if not wc_cfg.get("url") or not wc_cfg.get("consumer_key"):
            return

        auto_post = user_config.get("auto_post", {})
        if not auto_post.get("enabled"):
            return

        has_messenger = (
            user_config["messengers"]["bale"].get("bot_token")
            or user_config["messengers"]["rubika"].get("bot_token")
            or user_config["messengers"]["eitaa"].get("bot_token")
        )
        if not has_messenger:
            logger.warning(
                f"⚠️ No messenger configured for user={user_chat_id} WC auto-post"
            )
            return

        current_day = now.strftime("%A").lower()
        current_time = now.strftime("%H:%M")

        schedule = auto_post.get("schedule", {}).get(current_day, {})

        if not schedule.get("enabled"):
            return

        times_list = schedule.get("times", [])
        if current_time not in times_list:
            return

        wc_key = (user_chat_id, now.strftime("%Y-%m-%d"), current_time, "woocommerce")

        with _executed_wc_lock:
            if wc_key in _executed_wc_jobs:
                return
            _executed_wc_jobs.add(wc_key)

        logger.info(
            f"⏰ WooCommerce auto-post triggered for user={user_chat_id} "
            f"at {current_time} on {current_day}"
        )

        # ✅ sync محصولات قبل از daily_job
        _sync_user_products(user_chat_id)

        daily_job(user_config, user_chat_id)

    except Exception as e:
        logger.error(
            f"❌ check_woocommerce_for_user error (user={user_chat_id}): {e}",
            exc_info=True
        )


def _sync_user_products(user_chat_id):
    """
    همگام‌سازی فایل‌های محصولات کاربر با فایل‌های سراسری
    این تابع اطمینان می‌دهد که کاربر به محصولات دسترسی دارد
    """
    try:
        products_file = get_user_products_file(user_chat_id)
        user_products = load_json(products_file, [])

        if not user_products:
            global_products = load_json(PRODUCTS_FILE, [])
            if global_products:
                save_json(products_file, global_products)
                logger.info(
                    f"✅ Synced {len(global_products)} products "
                    f"to user={user_chat_id}"
                )
            else:
                logger.warning(
                    f"⚠️ No global products to sync for user={user_chat_id}. "
                    f"WooCommerce may need to be fetched first."
                )

        # sync new_products هم اگر خالی است
        new_file = get_user_new_products_file(user_chat_id)
        user_new = load_json(new_file, {})
        if not user_new:
            global_new = load_json(NEW_PRODUCTS_FILE, {})
            if global_new:
                save_json(new_file, global_new)

    except Exception as e:
        logger.error(f"❌ _sync_user_products error (user={user_chat_id}): {e}")

# ========== ارسال پست‌های زمان‌بندی شده ==========

def post_scheduled_posts_for_user(user_chat_id, global_config):
    """
    بررسی و ارسال پست‌های دستی زمان‌بندی شده برای یک کاربر خاص
    """
    global _executed_posts

    try:
        user_db = get_user_db(user_chat_id)
        user_config = load_user_config(user_chat_id)

        now = tehran_now()
        current_date = tehran_today().strftime("%Y-%m-%d")

        posts = user_db.get_scheduled_posts()

        if not posts:
            return

        for post in posts:
            if len(post) >= 9:
                (post_id, media_path, media_type, caption,
                 hashtags, scheduled_date, scheduled_time,
                 post_type, messengers) = post[:9]
            elif len(post) == 8:
                (post_id, media_path, media_type, caption,
                 hashtags, scheduled_date, scheduled_time,
                 post_type) = post[:8]
                messengers = 'all'
            else:
                logger.warning(
                    f"⚠️ Post #{post[0] if post else '?'} "
                    f"unexpected format, skipping."
                )
                continue

            execution_key = (post_id, scheduled_date, scheduled_time, user_chat_id)

            with _executed_lock:
                if execution_key in _executed_posts:
                    continue

            if scheduled_date != current_date:
                continue

            try:
                sched_dt_naive = datetime.strptime(
                    f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M"
                )
                sched_dt = TEHRAN_TZ.localize(sched_dt_naive)
                diff_seconds = (now - sched_dt).total_seconds()

                if not (0 <= diff_seconds <= 120):
                    continue

            except ValueError as ve:
                logger.error(f"❌ Invalid datetime for post #{post_id}: {ve}")
                continue

            logger.info(
                f"📤 Time to post! User={user_chat_id}, "
                f"Post=#{post_id}, "
                f"Scheduled={scheduled_date} {scheduled_time}, "
                f"Messengers={messengers}"
            )

            with _executed_lock:
                _executed_posts.add(execution_key)

            selected_messengers = _resolve_messengers(messengers, user_config)

            if not selected_messengers:
                logger.warning(
                    f"⚠️ No messengers configured for post #{post_id}, skipping."
                )
                user_db.mark_post_as_failed(post_id)
                continue

            media_content = None
            needs_download = (
                media_path
                and not media_path.startswith(("http://", "https://", "/"))
                and (
                    len(selected_messengers) > 1
                    or (
                        len(selected_messengers) == 1
                        and "bale" not in selected_messengers
                    )
                )
            )

            if needs_download:
                bot_token = global_config["messengers"]["bale"]["bot_token"]
                media_content = download_bale_file(media_path, bot_token)

                if not media_content:
                    logger.error(
                        f"❌ Failed to download media for post #{post_id}."
                    )
                    user_db.mark_post_as_failed(post_id)
                    with _executed_lock:
                        _executed_posts.discard(execution_key)
                    continue

            platforms_sent = _send_to_platforms(
                post_id=post_id,
                media_path=media_path,
                media_type=media_type,
                caption=caption or "",
                media_content=media_content,
                selected_messengers=selected_messengers,
                user_config=user_config,
                global_config=global_config
            )

            if platforms_sent:
                user_db.mark_post_as_posted(post_id)

                post_tuple = (
                    post_id,
                    media_path,
                    media_type,
                    caption,
                    hashtags,
                    scheduled_date,
                    scheduled_time,
                    user_chat_id
                )

                # نوتیف به کاربر
                notify_post_success(
                    notify_chat_id=user_chat_id,
                    post_tuple=post_tuple,
                    platforms_sent=platforms_sent,
                    is_owner=True
                )

                # نوتیف به ادمین (فقط اگر کاربر ≠ ادمین)
                admin_chat_id = global_config.get("admin_chat_id")
                if admin_chat_id and int(admin_chat_id) != int(user_chat_id):
                    notify_post_success(
                        notify_chat_id=admin_chat_id,
                        post_tuple=post_tuple,
                        platforms_sent=platforms_sent,
                        is_owner=False
                    )

                logger.info(
                    f"✅ Post #{post_id} published to "
                    f"{len(platforms_sent)} platform(s): "
                    f"{', '.join(platforms_sent)}"
                )

            else:
                logger.error(f"❌ Post #{post_id} failed on all platforms.")
                user_db.mark_post_as_failed(post_id)
                with _executed_lock:
                    _executed_posts.discard(execution_key)

    except Exception as e:
        logger.error(
            f"❌ Error in post_scheduled_posts_for_user "
            f"(user={user_chat_id}): {e}",
            exc_info=True
        )


def _resolve_messengers(messengers_str, user_config):
    """تبدیل رشته messengers به لیست پیام‌رسان‌های فعال"""
    configured = []

    bale_ok = (
        user_config["messengers"]["bale"].get("bot_token")
        and user_config["messengers"]["bale"].get("channel_id")
    )
    rubika_ok = (
        user_config["messengers"]["rubika"].get("bot_token")
        and user_config["messengers"]["rubika"].get("chat_id")
    )
    eitaa_ok = (
        user_config["messengers"]["eitaa"].get("bot_token")
        and user_config["messengers"]["eitaa"].get("chat_id")
    )

    if bale_ok:
        configured.append("bale")
    if rubika_ok:
        configured.append("rubika")
    if eitaa_ok:
        configured.append("eitaa")

    if not messengers_str or messengers_str.strip().lower() == 'all':
        return configured

    requested = [m.strip().lower() for m in messengers_str.split(',') if m.strip()]
    return [m for m in requested if m in configured]


def _send_to_platforms(
    post_id, media_path, media_type, caption,
    media_content, selected_messengers,
    user_config, global_config
):
    """ارسال پست به پلتفرم‌های انتخابی"""
    platforms_sent = []
    base_caption = caption or ""

    # ===== 1. Bale =====
    if "bale" in selected_messengers:
        try:
            bale_cfg = user_config["messengers"]["bale"]
            bot_token = (
                bale_cfg.get("bot_token")
                or global_config["messengers"]["bale"]["bot_token"]
            )
            channel_id = bale_cfg.get("channel_id")

            if bot_token and channel_id:
                api = f"https://tapi.bale.ai/bot{bot_token}"
                bale_caption = base_caption
                clean_channel = channel_id.replace('@', '')
                bale_caption += f"\n\n━━━━━━━━━━━━━━━━\n🔹 Bale: @{clean_channel}"

                if media_type == "photo":
                    data = {
                        "chat_id": channel_id,
                        "photo": media_path,
                        "caption": bale_caption
                    }
                    response = requests.post(
                        f"{api}/sendPhoto", json=data, timeout=30
                    )
                elif media_type == "video":
                    data = {
                        "chat_id": channel_id,
                        "video": media_path,
                        "caption": bale_caption
                    }
                    response = requests.post(
                        f"{api}/sendVideo", json=data, timeout=30
                    )
                else:
                    response = None

                if response and response.status_code == 200:
                    resp_json = response.json()
                    if resp_json.get("ok"):
                        platforms_sent.append("bale")
                        logger.info(f"✅ Bale: Post #{post_id} sent.")
                    else:
                        logger.error(
                            f"❌ Bale API error for post #{post_id}: "
                            f"{resp_json.get('description', 'unknown')}"
                        )
                else:
                    logger.error(
                        f"❌ Bale HTTP error for post #{post_id}: "
                        f"{response.status_code if response else 'No response'}"
                    )
            else:
                logger.warning(f"⚠️ Bale not fully configured for post #{post_id}")

        except Exception as e:
            logger.error(f"❌ Bale exception for post #{post_id}: {e}")

        time.sleep(1)

    # ===== 2. Rubika =====
    if "rubika" in selected_messengers:
        try:
            rubika_cfg = user_config["messengers"]["rubika"]

            if rubika_cfg.get("bot_token") and rubika_cfg.get("chat_id"):
                rubika_caption = base_caption
                clean_chat = rubika_cfg["chat_id"].replace('@', '')
                rubika_caption += f"\n\n━━━━━━━━━━━━━━━━\n🔹 Rubika: @{clean_chat}"

                content_to_send = media_content
                if not content_to_send and media_path:
                    bot_token = global_config["messengers"]["bale"]["bot_token"]
                    content_to_send = download_bale_file(media_path, bot_token)

                if content_to_send:
                    if messenger_rubika.send_manual_post(
                        rubika_caption, content_to_send, media_type, user_config
                    ):
                        platforms_sent.append("rubika")
                        logger.info(f"✅ Rubika: Post #{post_id} sent.")
                    else:
                        logger.error(
                            f"❌ Rubika: send_manual_post returned False for #{post_id}"
                        )
                else:
                    logger.error(f"❌ Rubika: No media content for post #{post_id}")
            else:
                logger.warning(f"⚠️ Rubika not fully configured for post #{post_id}")

        except Exception as e:
            logger.error(f"❌ Rubika exception for post #{post_id}: {e}")

        time.sleep(1)

    # ===== 3. Eitaa =====
    if "eitaa" in selected_messengers:
        try:
            eitaa_cfg = user_config["messengers"]["eitaa"]

            if eitaa_cfg.get("bot_token") and eitaa_cfg.get("chat_id"):
                eitaa_caption = base_caption
                clean_chat = eitaa_cfg["chat_id"].replace('@', '')
                eitaa_caption += f"\n\n━━━━━━━━━━━━━━━━\n🔹 Eitaa: @{clean_chat}"

                content_to_send = media_content
                if not content_to_send and media_path:
                    bot_token = global_config["messengers"]["bale"]["bot_token"]
                    content_to_send = download_bale_file(media_path, bot_token)

                if content_to_send:
                    if messenger_eitaa.send_manual_post(
                        eitaa_caption, content_to_send, media_type, user_config
                    ):
                        platforms_sent.append("eitaa")
                        logger.info(f"✅ Eitaa: Post #{post_id} sent.")
                    else:
                        logger.error(
                            f"❌ Eitaa: send_manual_post returned False for #{post_id}"
                        )
                else:
                    logger.error(f"❌ Eitaa: No media content for post #{post_id}")
            else:
                logger.warning(f"⚠️ Eitaa not fully configured for post #{post_id}")

        except Exception as e:
            logger.error(f"❌ Eitaa exception for post #{post_id}: {e}")

        time.sleep(1)

    return platforms_sent


# ========== بررسی زمان‌بندی کلی ==========

def check_schedule(global_config):
    """
    بررسی زمان‌بندی برای همه کاربران:
    1. پست خودکار WooCommerce (از user_config هر کاربر)
    2. پست‌های دستی زمان‌بندی شده
    """
    from auth_manager import AuthManager

    now = tehran_now()

    try:
        auth_manager = AuthManager()
        approved_users = auth_manager.get_approved_users()

        for user in approved_users:
            user_chat_id = user['chat_id']

            try:
                # بارگذاری user_config اختصاصی
                user_config = load_user_config(user_chat_id)

                # ===== 1. بررسی WooCommerce auto-post =====
                check_woocommerce_for_user(user_chat_id, user_config, now)

                # ===== 2. بررسی پست‌های دستی =====
                post_scheduled_posts_for_user(user_chat_id, global_config)

            except Exception as e:
                logger.error(
                    f"❌ Error processing user {user_chat_id}: {e}",
                    exc_info=True
                )

    except Exception as e:
        logger.error(f"❌ Error getting approved users: {e}")

    # ===== 3. پاکسازی حافظه =====
    _cleanup_executed_posts()
    _cleanup_executed_wc_jobs()


def _cleanup_executed_posts():
    """پاکسازی کلیدهای قدیمی پست‌های دستی"""
    global _executed_posts

    try:
        today = tehran_today().strftime("%Y-%m-%d")

        with _executed_lock:
            old_keys = {
                key for key in _executed_posts
                if len(key) >= 2 and key[1] < today
            }
            _executed_posts -= old_keys

            if old_keys:
                logger.debug(f"🧹 Cleaned {len(old_keys)} old post execution records.")

    except Exception as e:
        logger.error(f"❌ cleanup_executed_posts error: {e}")


def _cleanup_executed_wc_jobs():
    """پاکسازی کلیدهای قدیمی WooCommerce jobs"""
    global _executed_wc_jobs

    try:
        today = tehran_today().strftime("%Y-%m-%d")

        with _executed_wc_lock:
            old_keys = {
                key for key in _executed_wc_jobs
                if len(key) >= 2 and key[1] < today
            }
            _executed_wc_jobs -= old_keys

            if old_keys:
                logger.debug(f"🧹 Cleaned {len(old_keys)} old WC job records.")

    except Exception as e:
        logger.error(f"❌ cleanup_executed_wc_jobs error: {e}")


# ========== راه‌اندازی Scheduler ==========

def start_scheduler(global_config):
    """راه‌اندازی scheduler در background thread - هر 30 ثانیه"""
    def run_scheduler():
        logger.info("⏰ Scheduler thread started.")
        time.sleep(5)

        while True:
            try:
                fresh_config = load_config()
                check_schedule(fresh_config)
            except Exception as e:
                logger.error(f"❌ Scheduler main loop error: {e}", exc_info=True)

            time.sleep(30)

    thread = threading.Thread(
        target=run_scheduler,
        daemon=True,
        name="SchedulerThread"
    )
    thread.start()
    logger.info("⏰ Scheduler started successfully (checks every 30s).")
    return thread